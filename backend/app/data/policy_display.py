"""Display-only policy metadata.

This keeps demo/presentation labels out of service logic. Operational policy
facts still come from the database.
"""

DISPLAY_OVERRIDES = {}

SUPPORTED_CATEGORIES = {"교통", "숙박", "여행상품", "지역할인", "이벤트", "기타"}
