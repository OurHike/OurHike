"""Connecting only to an address `urlguard.py` already approved.

`test_sitefetch.py`'s peer check proves what a connection reached AFTER the
socket opened and the GET was already sent - so a name that rebinds between
`inspect()`'s check and the connect still received a blind request before
anybody noticed (#1641 finding 5). `PinnedBackend` in `app/core/sitefetch.py`
closes the window instead of reporting on it: the connection is dialled to
one of the addresses already validated, never re-resolved from the hostname.

This file is split from `test_sitefetch.py` because it is testing a
different layer. That file never reaches the network - `httpx.MockTransport`
replaces the whole connection - so it cannot see `PinnedBackend` at all,
which sits one level below, inside the real `httpx.HTTPTransport`'s
`httpcore.ConnectionPool`. What is under test here is that substitution:
that `connect_tcp` is handed the pinned address rather than the hostname,
that an unpinned host is refused rather than silently resolved, and that
`reader()`/`read_page` populate the pin table before the socket opens - not
whether a whole page can be read, which the other file already covers.

The one real socket in this file is a loopback TCP listener this test
starts itself, proving `PinnedBackend.connect_tcp` actually dials the
address it was given - the strongest evidence short of a live DNS-rebinding
attack, which nothing running in a sandbox with no outbound network access
beyond a proxy could stage. TLS/SNI behaviour is not exercised here: that
is `httpcore`'s own `start_tls`, reached from `origin.host` further up the
stack rather than from anything this class touches, so it is reasoned
rather than measured - see `PinnedBackend`'s own docstring.
"""

from __future__ import annotations

import socket
import threading

import httpcore
import httpx
import pytest

from app.core.sitefetch import PIN_ATTRIBUTE, PinnedBackend, PinnedHTTPTransport, reader
from app.core.urlguard import inspect


class _RecordingBackend(httpcore.NetworkBackend):
    """A stand-in inner backend: records what it was asked to dial and never
    touches a real socket, so `PinnedBackend`'s own routing can be tested
    without the flakiness or slowness of a real connection attempt."""

    def __init__(self, *, fail_for: set[str] = frozenset()) -> None:
        self.calls: list[str] = []
        self._fail_for = fail_for

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.calls.append(host)
        if host in self._fail_for:
            raise httpcore.ConnectError(f"refused to connect to {host}")
        return object()  # A real NetworkStream would go here; nothing reads it in these tests.


class TestPinnedBackendRouting:
    def test_connects_to_the_pinned_address_rather_than_the_hostname(self):
        inner = _RecordingBackend()
        backend = PinnedBackend({"cmc.org": ("203.0.113.7",)}, backend=inner)

        backend.connect_tcp("cmc.org", 443)

        assert inner.calls == ["203.0.113.7"]

    def test_an_unpinned_host_is_refused_rather_than_resolved(self):
        inner = _RecordingBackend()
        backend = PinnedBackend({}, backend=inner)

        with pytest.raises(httpcore.ConnectError, match="No approved address is pinned"):
            backend.connect_tcp("cmc.org", 443)

        assert inner.calls == [], "an unpinned host must never reach the real network backend"

    def test_a_host_pinned_to_nothing_is_also_refused(self):
        inner = _RecordingBackend()
        backend = PinnedBackend({"cmc.org": ()}, backend=inner)

        with pytest.raises(httpcore.ConnectError, match="No approved address is pinned"):
            backend.connect_tcp("cmc.org", 443)

    def test_a_failing_first_address_falls_through_to_the_next(self):
        """`urlguard.py`'s guarantee is that every resolved address is safe,
        not that every one is reachable - a host with two public addresses
        where one refuses connections should still succeed on the other."""
        inner = _RecordingBackend(fail_for={"203.0.113.7"})
        backend = PinnedBackend({"cmc.org": ("203.0.113.7", "203.0.113.8")}, backend=inner)

        backend.connect_tcp("cmc.org", 443)

        assert inner.calls == ["203.0.113.7", "203.0.113.8"]

    def test_every_pinned_address_failing_raises_the_last_error(self):
        inner = _RecordingBackend(fail_for={"203.0.113.7", "203.0.113.8"})
        backend = PinnedBackend({"cmc.org": ("203.0.113.7", "203.0.113.8")}, backend=inner)

        with pytest.raises(httpcore.ConnectError, match="203.0.113.8"):
            backend.connect_tcp("cmc.org", 443)

        assert inner.calls == ["203.0.113.7", "203.0.113.8"]


class TestPinnedBackendRealSocket:
    def test_it_actually_dials_the_pinned_address(self):
        """The one test in this file with a real socket: a loopback listener
        this test owns, reached only if `connect_tcp` dialled the address in
        `pins` rather than trying (and, in this sandbox, failing or hanging)
        to resolve a hostname that names nothing real."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        accepted: list[socket.socket] = []

        def accept_once() -> None:
            conn, _ = listener.accept()
            accepted.append(conn)

        thread = threading.Thread(target=accept_once, daemon=True)
        thread.start()

        backend = PinnedBackend({"not-a-real-host.invalid": ("127.0.0.1",)})
        try:
            stream = backend.connect_tcp("not-a-real-host.invalid", port, timeout=5.0)
            thread.join(timeout=5.0)
            assert accepted, "the pinned address was never actually dialled"
            stream.close()
        finally:
            listener.close()
            if accepted:
                accepted[0].close()


class TestReaderWiring:
    def test_reader_hangs_a_pin_table_off_the_client(self):
        client = reader()
        try:
            pins = getattr(client, PIN_ATTRIBUTE, None)
            assert isinstance(pins, dict)
            assert pins == {}
        finally:
            client.close()

    def test_reader_uses_the_pinned_transport(self):
        client = reader()
        try:
            assert isinstance(client._transport, PinnedHTTPTransport)
            assert isinstance(client._transport._pool._network_backend, PinnedBackend)
        finally:
            client.close()

    def test_a_plain_client_with_no_pin_table_is_untouched(self):
        """`read_page` reads `PIN_ATTRIBUTE` with `getattr(..., None)` rather
        than assuming it exists, so every test in test_sitefetch.py - which
        builds `httpx.Client(transport=MockTransport(...))` directly - keeps
        working exactly as it did before this class existed."""
        client = httpx.Client()
        try:
            assert getattr(client, PIN_ATTRIBUTE, None) is None
        finally:
            client.close()


class TestReadPagePinsBeforeSending:
    def test_the_targets_addresses_are_pinned_before_the_socket_opens(self):
        """`read_page` cannot be driven all the way to a real connection here
        without a real reachable address - see the module docstring - so
        this proves the ordering the fix depends on instead: by the time
        `client.send` is reached, `PIN_ATTRIBUTE`'s dict already carries the
        exact addresses `inspect()` approved for this host, which is what
        `PinnedBackend.connect_tcp` reads at connect time."""
        from app.core.sitefetch import read_page

        client = reader()
        seen_pins: list[dict] = []

        def fail_after_recording_the_pin(request, **kwargs):
            seen_pins.append(dict(getattr(client, PIN_ATTRIBUTE)))
            raise httpx.ConnectError("not actually sent - this test never touches the network")

        client.send = fail_after_recording_the_pin  # type: ignore[method-assign]

        # Real, publicly-routed addresses (Cloudflare's and Google's public
        # resolvers) so `inspect()`'s own public-address check passes - this
        # test never dials either one, it only needs `inspect()` to approve
        # them. TEST-NET ranges (203.0.113.0/24, used above) are deliberately
        # blocked by urlguard.py and would raise `UrlRefused` here instead.
        resolve = lambda host: ["1.1.1.1", "8.8.8.8"]  # noqa: E731
        target = inspect("https://cmc.org/", resolve=resolve)

        with pytest.raises(Exception):
            read_page(target, client=client, resolve=resolve)

        assert seen_pins == [{"cmc.org": ("1.1.1.1", "8.8.8.8")}]
