"""Shared field validators for AgriMatch API schemas."""

import re

_GHANA_PHONE = re.compile(r'^(\+233|0)[0-9]{9}$')


def validate_ghana_phone(v: str) -> str:
    """Normalise and validate a Ghana mobile number.

    Accepts formats: 0244123456, +233244123456, or with spaces/dashes.
    Raises ValueError with a user-friendly message on invalid input.
    """
    cleaned = re.sub(r"[\s\-()+]", "", v).lstrip()
    normalised = cleaned if cleaned.startswith(("+", "0")) else "0" + cleaned
    if not _GHANA_PHONE.match(normalised):
        raise ValueError(
            "Must be a valid Ghana phone number (e.g. 0244123456 or +233244123456)"
        )
    return v
