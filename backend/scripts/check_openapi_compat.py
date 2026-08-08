"""Fail when this build's API breaks the last release's clients (#374, surface 2).

RELEASING.md §8c: "Old clients stay in the field; a PWA can be served from
cache and an app-store build cannot be forced forward. Diff the OpenAPI
document against the previous release's attached copy - removals and
narrowings fail."

`openapi_baseline.json` is that attached copy. It is regenerated when a
release is cut (`python scripts/check_openapi_compat.py --write`), NOT when
the API changes - the whole point is that it lags HEAD by one release, so an
ordinary additive change passes without anybody touching it.

WHY REQUEST AND RESPONSE ARE OPPOSITE

The instinct is one rule - "nothing may be removed" - and it is wrong in both
directions, because an old client is a WRITER of requests and a READER of
responses.

*Responses.* The old client reads fields. Removing one it reads breaks it;
so does demoting one from required to optional, which is the same removal
spread over time. Adding a field is harmless - it ignores what it does not
know. A new enum member is a judgment call and is allowed here: every enum
this API returns is rendered through a client-side lookup with a fallback
(`reportStatus.ts`, `closureBanner.ts`), so an unknown member degrades to a
neutral label rather than throwing.

*Requests.* The old client writes fields. A newly REQUIRED property breaks
it, because it will never send one. Removing an accepted enum member breaks
it, because it may still send that value. Removing an optional property is
not a break by itself - the server ignoring something is survivable - but
`extra="forbid"` schemas turn it into a 422, so removals are reported for
request schemas too rather than assumed benign.

WHAT IS DELIBERATELY NOT CHECKED

Type narrowing beyond required/optional and enum membership - `string` to a
pattern-constrained `string`, a widened numeric bound. Detecting those well
means implementing JSON Schema subtyping, and detecting them badly means a
check people learn to override. The four rules below are the ones that are
unambiguous.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

BASELINE_PATH = pathlib.Path(__file__).resolve().parent.parent / "openapi_baseline.json"

# A schema reachable from a requestBody is written by the client; one
# reachable from a response is read by it. A schema reachable from both gets
# both rule sets, which is stricter than either and is the safe way round.
REQUEST = "request"
RESPONSE = "response"


class Break:
    """One incompatibility, in the terms a reader needs to act on it."""

    def __init__(self, rule: str, where: str, detail: str) -> None:
        self.rule = rule
        self.where = where
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.rule}: {self.where} - {self.detail}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Break({self.rule!r}, {self.where!r}, {self.detail!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Break):
            return NotImplemented
        return (self.rule, self.where, self.detail) == (other.rule, other.where, other.detail)


def _schema_name(ref: str) -> str | None:
    prefix = "#/components/schemas/"
    return ref[len(prefix) :] if ref.startswith(prefix) else None


def _referenced_names(node: Any) -> set[str]:
    """Every component schema named anywhere under `node`, at any depth."""
    found: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            name = _schema_name(ref)
            if name is not None:
                found.add(name)
        for value in node.values():
            found |= _referenced_names(value)
    elif isinstance(node, list):
        for value in node:
            found |= _referenced_names(value)
    return found


def _roles(document: dict[str, Any]) -> dict[str, set[str]]:
    """Which schemas the client writes, and which it reads.

    Resolved transitively: a schema nested inside a request body is written
    just as much as the top-level one, and stopping at the first level would
    exempt exactly the nested shapes most likely to change.
    """
    schemas = document.get("components", {}).get("schemas", {})
    direct: dict[str, set[str]] = {}

    for path_item in document.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for name in _referenced_names(operation.get("requestBody", {})):
                direct.setdefault(name, set()).add(REQUEST)
            for name in _referenced_names(operation.get("responses", {})):
                direct.setdefault(name, set()).add(RESPONSE)
            # A query/path parameter is written by the client too.
            for name in _referenced_names(operation.get("parameters", [])):
                direct.setdefault(name, set()).add(REQUEST)

    # Push roles down through nested references until nothing moves.
    roles = {name: set(values) for name, values in direct.items()}
    changed = True
    while changed:
        changed = False
        for name in list(roles):
            for nested in _referenced_names(schemas.get(name, {})):
                inherited = roles.get(nested, set())
                if not roles[name] <= inherited:
                    roles[nested] = inherited | roles[name]
                    changed = True
    return roles


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def _required(schema: dict[str, Any]) -> set[str]:
    required = schema.get("required")
    return set(required) if isinstance(required, list) else set()


def _enum_values(schema: dict[str, Any]) -> set[Any] | None:
    values = schema.get("enum")
    if isinstance(values, list):
        return {value for value in values if isinstance(value, (str, int, float, bool))}
    return None


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> list[Break]:
    """Every way `current` breaks a client written against `baseline`."""
    breaks: list[Break] = []

    old_paths = baseline.get("paths", {})
    new_paths = current.get("paths", {})

    for path, old_item in old_paths.items():
        new_item = new_paths.get(path)
        if new_item is None:
            breaks.append(Break("path removed", path, "clients calling it get a 404"))
            continue
        for method, old_operation in old_item.items():
            if not isinstance(old_operation, dict):
                continue
            if method not in new_item:
                breaks.append(Break("operation removed", f"{method.upper()} {path}", "clients calling it get a 405"))

    old_schemas = baseline.get("components", {}).get("schemas", {})
    new_schemas = current.get("components", {}).get("schemas", {})
    old_roles = _roles(baseline)

    for name, old_schema in old_schemas.items():
        roles = old_roles.get(name, {REQUEST, RESPONSE})
        new_schema = new_schemas.get(name)
        if new_schema is None:
            # Only a break if something still points at it; an orphaned
            # component that no operation referenced is not part of the wire
            # contract at all.
            if name in old_roles:
                breaks.append(Break("schema removed", name, "was referenced by an operation"))
            continue

        old_props = _properties(old_schema)
        new_props = _properties(new_schema)
        old_required = _required(old_schema)
        new_required = _required(new_schema)

        for prop in old_props:
            if prop in new_props:
                continue
            if RESPONSE in roles:
                breaks.append(Break("response field removed", f"{name}.{prop}", "an old client reads this field"))
            else:
                breaks.append(
                    Break(
                        "request field removed",
                        f"{name}.{prop}",
                        "an old client may still send it, and a forbid-extra schema 422s",
                    )
                )

        if RESPONSE in roles:
            for prop in old_required & set(new_props.keys()):
                if prop not in new_required:
                    breaks.append(
                        Break(
                            "response field no longer guaranteed",
                            f"{name}.{prop}",
                            "was always present, now optional - the same removal spread over time",
                        )
                    )

        if REQUEST in roles:
            for prop in new_required - old_required:
                breaks.append(
                    Break(
                        "request field newly required",
                        f"{name}.{prop}",
                        "an old client will never send it",
                    )
                )

        # Enum membership, per property and on the schema itself.
        for prop, old_prop in old_props.items():
            new_prop = new_props.get(prop)
            if not isinstance(old_prop, dict) or not isinstance(new_prop, dict):
                continue
            breaks.extend(_enum_breaks(f"{name}.{prop}", old_prop, new_prop, roles))
        breaks.extend(_enum_breaks(name, old_schema, new_schema, roles))

    return breaks


def _enum_breaks(where: str, old: dict[str, Any], new: dict[str, Any], roles: set[str]) -> list[Break]:
    """A request enum may not lose members; a response enum may gain them.

    Only meaningful for request schemas - see the module docstring on why a
    new response member is allowed and a lost request member is not.
    """
    if REQUEST not in roles:
        return []
    old_values = _enum_values(old)
    new_values = _enum_values(new)
    if old_values is None or new_values is None:
        return []
    lost = old_values - new_values
    return [
        Break("request enum member removed", where, f"an old client may still send {value!r}") for value in sorted(lost, key=repr)
    ]


def load_baseline(path: pathlib.Path = BASELINE_PATH) -> dict[str, Any]:
    """The last release's document.

    Raises rather than returning `{}` when the file is missing. An empty
    baseline compares clean against anything, so a silent fallback would turn
    this whole check into a green light - the failure
    tests/test_preferences_contract.py names: passing because it failed to
    find the file.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. It is the last release's OpenAPI document and the "
            "check is meaningless without it; regenerate with --write only when cutting a release."
        )
    return json.loads(path.read_text())


def current_document() -> dict[str, Any]:
    # `backend/` on the path, so this runs as a script from anywhere as well
    # as under pytest, whose pyproject sets `pythonpath = ["."]`.
    backend_root = str(BASELINE_PATH.parent)
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    from app.main import app

    return app.openapi()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Overwrite the baseline with this build's document. Only when cutting a release.",
    )
    args = parser.parse_args(argv)

    document = current_document()

    if args.write:
        BASELINE_PATH.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        print(f"wrote {BASELINE_PATH}")
        return 0

    breaks = compare(load_baseline(), document)
    if not breaks:
        print("OpenAPI is backwards compatible with the baseline.")
        return 0

    print(f"{len(breaks)} backwards-incompatible change(s) against openapi_baseline.json:\n")
    for item in breaks:
        print(f"  {item}")
    print(
        "\nIf this is a deliberate break, the release it lands in is a major one and the "
        "baseline moves with it - see RELEASING.md §8c and §11b."
    )
    return 1


if __name__ == "__main__":  # pragma: no cover - entry point
    sys.exit(main())
