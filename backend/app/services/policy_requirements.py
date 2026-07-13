from __future__ import annotations

import re

DEFAULT_REQUIREMENT = "공식 혜택 안내에서 조건을 확인하세요."
PHONE_ONLY_REQUIREMENT_PATTERN = re.compile(
    r"^\s*(?:문의전화|문의|전화|tel|contact|고객센터|운영사무국)?\s*[:：-]?\s*"
    r"(?:\+?\d[\d\s().-]{5,}\d)\s*$",
    re.IGNORECASE,
)
PHONE_IN_REQUIREMENT_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{5,}\d)")
CONTACT_ONLY_REQUIREMENT_PATTERN = re.compile(
    r"^\s*(?:문의전화|문의|전화|tel|contact|고객센터|운영사무국)\s*[:：-]?\s*$",
    re.IGNORECASE,
)


def split_requirement_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def is_public_requirement(value: str) -> bool:
    text = " ".join(str(value or "").split())
    if not text:
        return False
    if PHONE_ONLY_REQUIREMENT_PATTERN.match(text):
        return False
    if PHONE_IN_REQUIREMENT_PATTERN.search(text):
        return False
    return not CONTACT_ONLY_REQUIREMENT_PATTERN.match(text)


def sanitize_requirement_items(values: list[str] | None) -> list[str]:
    return [text for value in values or [] if is_public_requirement(text := str(value or "").strip())]


def sanitize_target_condition(value: str | None) -> str:
    items = sanitize_requirement_items(split_requirement_lines(value))
    if items:
        return "\n".join(items)
    return DEFAULT_REQUIREMENT
