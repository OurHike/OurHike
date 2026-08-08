"""fly.toml and fly.ua.toml still describe the same service.

UA exists to be production with the release candidate on it. Every way the two
differ that nobody chose is a way UA verifies something other than what ships -
and the failure is silent in the direction that matters, because UA works fine
while being the wrong thing to have tested.

There are exactly three intended differences, all of them one decision: UA
scales to zero between testers and production keeps a machine warm. Everything
else - the port, the region, the machine size, the memory - has to track
fly.toml, and a second file is the standard way for that to quietly stop being
true (CONTRIBUTING.md's one-home rule is about exactly this).

`.github/workflows/deploy-backend.yml` is what reads these two files, one per
leg. Nothing else in the suite looks at them, so without this they are checked
by the first real deploy.
"""

from __future__ import annotations

from pathlib import Path

import tomllib

BACKEND = Path(__file__).resolve().parents[1]
PRODUCTION_CONFIG = BACKEND / "fly.toml"
UA_CONFIG = BACKEND / "fly.ua.toml"

# Dotted paths, so a nested table reads the way it does in the file.
INTENDED_DIFFERENCES = {
    "app",
    "http_service.auto_stop_machines",
    "http_service.min_machines_running",
}


def _flatten(table, prefix=""):
    """Every leaf in a parsed toml, keyed by its dotted path.

    Comparing whole tables would report one difference for `[http_service]` and
    leave somebody to find which key inside it moved. `[[vm]]` is a list of
    tables, so its entries are indexed - `vm.0.memory` - which is what makes a
    second machine definition appearing in one file and not the other show up
    as the difference it is rather than as a changed value.
    """
    flat = {}
    for key, value in table.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{path}."))
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value) and value:
            for index, item in enumerate(value):
                flat.update(_flatten(item, f"{path}.{index}."))
        else:
            flat[path] = value
    return flat


def _config(path):
    return _flatten(tomllib.loads(path.read_text(encoding="utf-8")))


PRODUCTION = _config(PRODUCTION_CONFIG)
UA = _config(UA_CONFIG)


def test_the_two_configs_differ_only_where_they_are_meant_to():
    unexpected = []
    for path in sorted(set(PRODUCTION) | set(UA)):
        if path in INTENDED_DIFFERENCES:
            continue
        if PRODUCTION.get(path) != UA.get(path):
            unexpected.append(f"{path}: fly.toml has {PRODUCTION.get(path)!r}, fly.ua.toml has {UA.get(path)!r}")
    assert not unexpected, (
        "fly.toml and fly.ua.toml have drifted apart on settings neither is supposed to own. UA is meant to be "
        "production with the candidate on it, so a difference here means UA verifies something else - which it does "
        "without ever looking broken. Change both, or add the key to INTENDED_DIFFERENCES with a reason in "
        "fly.ua.toml's header:\n  " + "\n  ".join(unexpected)
    )


def test_every_intended_difference_is_really_a_difference():
    """The other half, and the one that rots. An exemption outlives the reason
    for it: somebody aligns the two files, the entry above stays, and from then
    on it hides a real difference in a key nobody is watching any more."""
    identical = sorted(path for path in INTENDED_DIFFERENCES if PRODUCTION.get(path) == UA.get(path))
    assert not identical, (
        "INTENDED_DIFFERENCES names settings the two configs now agree on, so those entries are exempting nothing and "
        "would hide the next real difference. Delete them:\n  " + "\n  ".join(identical)
    )


def test_production_keeps_a_machine_warm_and_ua_does_not():
    """The three exemptions above say these settings may differ. This says what
    they must be, because "differs from UA" is satisfied just as well by a
    production app that also scales to zero - which is the exact behaviour
    fly.toml was written to avoid (its own comment: the Render free-tier cold
    start is why Fly was picked at all, and scaling to zero here would undo
    that choice)."""
    assert PRODUCTION["http_service.min_machines_running"] == 1, (
        "Production is meant to keep one machine running - a cold start on the first request after quiet is the "
        "behaviour Fly was chosen over Render to avoid. See the comment in fly.toml and RELEASING.md §3."
    )
    assert PRODUCTION["http_service.auto_stop_machines"] == "off", (
        "min_machines_running = 1 does not keep a machine up on its own if Fly is also allowed to stop it. Both "
        "settings are the one decision."
    )
    assert UA["http_service.min_machines_running"] == 0, (
        "UA is meant to cost nothing while nobody is testing - a cold start is fine for a tester and is exactly what "
        "production declines to accept (RELEASING.md §3d)."
    )


def test_both_apps_are_named_and_named_differently():
    """A deploy reads `app` out of whichever config it was pointed at. Two
    configs naming one app is a UA deploy that lands on production, which is
    the single worst thing either of these files can be made to do."""
    assert PRODUCTION["app"] and UA["app"], "Both configs need an `app` - `fly deploy` has nothing to target without one."
    assert PRODUCTION["app"] != UA["app"], (
        f"Both configs name {PRODUCTION['app']!r}, so deploying UA would deploy over production. `fly apps create` "
        f"needs two distinct, globally-unique names - see LAUNCH_CHECKLIST.md 6."
    )


def test_the_port_fly_routes_to_is_the_one_the_container_listens_on():
    """Three places have to agree and none of them checks the others: Fly sends
    traffic to `internal_port`, the container listens on `$PORT`, and the image
    defaults `PORT` to 8000 (Dockerfile). A mismatch deploys cleanly, passes
    every test here, and answers nothing - the machine is up and Fly is knocking
    on a port with no listener."""
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV PORT=8000" in dockerfile, (
        "The Dockerfile no longer defaults PORT to 8000, so the [env] PORT and internal_port in both Fly configs are "
        "now asserting against a number this test cannot see. Update all three together."
    )
    for name, config in (("fly.toml", PRODUCTION), ("fly.ua.toml", UA)):
        assert config["http_service.internal_port"] == 8000, f"{name} routes to a port the container does not listen on."
        assert config["env.PORT"] == "8000", f"{name} tells the container to listen on a port Fly does not route to."
