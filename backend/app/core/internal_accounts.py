from __future__ import annotations

import re


_INTERNAL_ADMIN_IDENTIFIER = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.invalid$",
    re.IGNORECASE,
)


def is_internal_admin_identifier(value: str) -> bool:
    return bool(_INTERNAL_ADMIN_IDENTIFIER.fullmatch(value.strip()))
