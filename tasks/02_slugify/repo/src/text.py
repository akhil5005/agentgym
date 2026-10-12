"""Helpers for turning human text into machine-friendly text."""

import re


def slugify(text):
    """Turn a title into a URL slug."""
    lowered = text.lower().strip()
    return re.sub(r"[^\w]", "-", lowered, flags=re.UNICODE)
