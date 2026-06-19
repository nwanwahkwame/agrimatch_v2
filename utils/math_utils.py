def safe_float(v) -> float:
    """Convert v to float, returning 0.0 on any error or NaN."""
    try:
        val = float(v)
        return 0.0 if (val != val) else val
    except (TypeError, ValueError):
        return 0.0
