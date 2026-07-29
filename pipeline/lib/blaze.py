"""Normalize raw trail-line blaze-color values into one `blaze_color`
attribute, per features/TRAIL_BLAZE_COLORS.md.

Pure - no I/O, no logging. Deciding what "decoded" means is this module's
job; deciding whether to warn about a failed decode is the caller's (during
export, where the raw feature/source context is available to put in the
message).
"""

NEUTRAL_FALLBACK = "Unknown"


def normalize_blaze_color(raw_value, coded_domain: dict[int, str] | None, source_default: str | None = None) -> tuple[str, bool]:
    """Resolve one feature's raw blaze value to (blaze_color, decoded).

    - `raw_value` missing (None): a source with a flat per-source default
      (e.g. centerline, uniformly white with no per-feature field - see
      `blaze_default` in sources.json) resolves to that default, decoded=True.
      Without a default, this is a true non-decode: (Unknown, False).
    - `raw_value` is a real key in `coded_domain`: decode it. This includes
      code 0 -> "None" and code 9 -> "Other" (side_trails' real domain) -
      both are successful decodes, not fallbacks.
    - Anything else (an unmapped literal like "Unknown"/"Gold", an
      out-of-range code, or no domain and no default to fall back on): the
      neutral (Unknown, False) fallback.
    """
    if raw_value is None:
        if source_default is not None:
            return source_default, True
        return NEUTRAL_FALLBACK, False
    if coded_domain is not None and raw_value in coded_domain:
        return coded_domain[raw_value], True
    return NEUTRAL_FALLBACK, False
