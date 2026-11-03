"""lib/strict_json.py - JSON read the way a phone reads it.

The stdlib is the thing under test as much as the module: `json.dumps`
writes a non-finite float as a bare token and `json.loads` reads it back,
and both facts are asserted here so that a future Python that changes either
turns up as a red test rather than as a gate that silently stopped mattering.
"""

from __future__ import annotations

import json
import math

import pytest

from lib import strict_json


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_the_stdlib_writes_a_non_finite_float_as_a_bare_token(value):
    """The premise. Python 3.13's json module: allow_nan=True by default."""
    token = json.dumps(value)
    assert token in strict_json.TOKENS
    assert json.loads(token) != json.loads(token) or math.isinf(json.loads(token))


@pytest.mark.parametrize("text", ["[NaN]", "[Infinity]", "[-Infinity]", '{"mile": NaN}'])
def test_loads_refuses_each_token_a_phone_rejects(text):
    with pytest.raises(strict_json.NonFiniteNumber) as refused:
        strict_json.loads(text)
    assert "JSON.parse" in str(refused.value)


def test_loads_is_otherwise_the_stdlib():
    assert strict_json.loads('{"a": [1, 2.5, "NaN", null]}') == {"a": [1, 2.5, "NaN", None]}


def test_load_reads_bytes_from_a_path(tmp_path):
    path = tmp_path / "doc.json"
    path.write_bytes(b'{"elevation_ft": 1234.5}')
    assert strict_json.load(path) == {"elevation_ft": 1234.5}

    path.write_bytes(b'{"elevation_ft": NaN}')
    with pytest.raises(strict_json.NonFiniteNumber):
        strict_json.load(path)


def test_dumps_refuses_a_non_finite_float_instead_of_writing_the_token():
    with pytest.raises(ValueError):
        strict_json.dumps({"climb": float("nan")})


def test_dumps_passes_every_other_keyword_through():
    assert strict_json.dumps({"b": 1, "a": 2}, sort_keys=True, separators=(",", ":")) == '{"a":2,"b":1}'
