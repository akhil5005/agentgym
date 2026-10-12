"""Helpers for turning human text into machine-friendly text."""

import re
import unicodedata


def slugify(text):
    """Turn a title into a URL slug."""
    # NFKD splits an accented letter into the plain letter plus a combining
    # accent, so dropping the non-ASCII bytes leaves the plain letter behind.
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")

    collapsed = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower())
    return collapsed.strip("-")
