from __future__ import annotations

from functools import lru_cache


_FROZEN_LEGACY_DGTOUR_SLUGS = frozenset({
    "dgtour-하동-3",
    "dgtour-밀양-1",
    "dgtour-평창-2",
    "dgtour-거창-4",
    "dgtour-영월-5",
    "dgtour-제천-6",
    "dgtour-강진-7",
    "dgtour-영광-8",
    "dgtour-합천-9",
    "dgtour-해남-10",
    "dgtour-남해-11",
    "dgtour-영암-12",
    "dgtour-고흥-13",
    "dgtour-횡성-14",
    "dgtour-완도-15",
    "dgtour-고창-16",
})


@lru_cache(maxsize=1)
def frozen_legacy_dgtour_slugs() -> frozenset[str]:
    return _FROZEN_LEGACY_DGTOUR_SLUGS
