from __future__ import annotations

from dataclasses import dataclass


SOURCE_CATEGORY = "digital_tourism_resident_card"
SOURCE_NAME = "디지털관광주민증"
SOURCE_URL = "https://korean.visitkorea.or.kr/dgtourcard/"
TITLE_SUFFIX = "디지털관광주민증 혜택"
OFFICIAL_PARTICIPATING_REGIONS_SOURCE_URL = SOURCE_URL
OFFICIAL_PARTICIPATING_REGIONS_VERIFIED_ON = "2026-07-25"
VISITKOREA_DGTOURCARD_HOST = "korean.visitkorea.or.kr"
VISITKOREA_DGTOURCARD_PATH_PREFIX = "/dgtourcard/"


def regional_url(mtpc_do_cd: str, signgu_cd: str) -> str:
    return f"{SOURCE_URL}biz/regn/regnMain.do?mtpcDoCd={mtpc_do_cd}&signguCd={signgu_cd}"


REGIONAL_URL_CODE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("철원", "강원", "51", "51780"),
    ("양양", "강원", "51", "51830"),
    ("정선", "강원", "51", "51770"),
    ("삼척", "강원", "51", "51230"),
    ("태백", "강원", "51", "51190"),
    ("홍천", "강원", "51", "51720"),
    ("평창", "강원", "51", "51760"),
    ("영월", "강원", "51", "51750"),
    ("연천", "경기", "41", "41800"),
    ("가평", "경기", "41", "41820"),
    ("강화", "인천", "28", "28710"),
    ("태안", "충남", "44", "44825"),
    ("제천", "충북", "43", "43150"),
    ("단양", "충북", "43", "43800"),
    ("괴산", "충북", "43", "43760"),
    ("예산", "충남", "44", "44810"),
    ("옥천", "충북", "43", "43730"),
    ("영동", "충북", "43", "43740"),
    ("보령", "충남", "44", "44180"),
    ("보은", "충북", "43", "43720"),
    ("김제", "전북", "52", "52210"),
    ("무주", "전북", "52", "52730"),
    ("고창", "전북", "52", "52790"),
    ("임실", "전북", "52", "52750"),
    ("영광", "전남", "12", "12830"),
    ("남원", "전북", "52", "52190"),
    ("함평", "전남", "12", "12820"),
    ("곡성", "전남", "12", "12720"),
    ("신안", "전남", "12", "12870"),
    ("해남", "전남", "12", "12790"),
    ("장흥", "전남", "12", "12770"),
    ("구례", "전남", "12", "12730"),
    ("담양", "전남", "12", "12710"),
    ("순창", "전북", "52", "52770"),
    ("고흥", "전남", "12", "12740"),
    ("완도", "전남", "12", "12850"),
    ("영주", "경북", "47", "47210"),
    ("안동", "경북", "47", "47170"),
    ("영덕", "경북", "47", "47770"),
    ("청도", "경북", "47", "47820"),
    ("부산동구", "부산", "26", "26170"),
    ("부산영도", "부산", "26", "26200"),
    ("부산서구", "부산", "26", "26140"),
    ("밀양", "경남", "48", "48270"),
    ("하동", "경남", "48", "48850"),
    ("합천", "경남", "48", "48890"),
    ("거창", "경남", "48", "48880"),
    ("고령", "경북", "47", "47830"),
    ("의성", "경북", "47", "47730"),
    ("울진", "경북", "47", "47930"),
    ("함양", "경남", "48", "48870"),
    ("산청", "경남", "48", "48860"),
)

REGIONAL_URLS: dict[str, str] = {
    city: regional_url(mtpc_do_cd, signgu_cd)
    for city, _region, mtpc_do_cd, signgu_cd in REGIONAL_URL_CODE_ROWS
}

CHEORWON_REGIONAL_URL = REGIONAL_URLS["철원"]
YANGYANG_REGIONAL_URL = REGIONAL_URLS["양양"]
JEONGSEON_REGIONAL_URL = REGIONAL_URLS["정선"]
SAMCHEOK_REGIONAL_URL = REGIONAL_URLS["삼척"]
TAEBAEK_REGIONAL_URL = REGIONAL_URLS["태백"]
HONGCHEON_REGIONAL_URL = REGIONAL_URLS["홍천"]
PYEONGCHANG_REGIONAL_URL = REGIONAL_URLS["평창"]
YEONGWOL_REGIONAL_URL = REGIONAL_URLS["영월"]
YEONCHEON_REGIONAL_URL = REGIONAL_URLS["연천"]
GAPYEONG_REGIONAL_URL = REGIONAL_URLS["가평"]
GANGHWA_REGIONAL_URL = REGIONAL_URLS["강화"]
TAEAN_REGIONAL_URL = REGIONAL_URLS["태안"]
JECHEON_REGIONAL_URL = REGIONAL_URLS["제천"]
DANYANG_REGIONAL_URL = REGIONAL_URLS["단양"]
GOESAN_REGIONAL_URL = REGIONAL_URLS["괴산"]
YESAN_REGIONAL_URL = REGIONAL_URLS["예산"]
OKCHEON_REGIONAL_URL = REGIONAL_URLS["옥천"]
YEONGDONG_REGIONAL_URL = REGIONAL_URLS["영동"]
BORYEONG_REGIONAL_URL = REGIONAL_URLS["보령"]
BOEUN_REGIONAL_URL = REGIONAL_URLS["보은"]
GIMJE_REGIONAL_URL = REGIONAL_URLS["김제"]
MUJU_REGIONAL_URL = REGIONAL_URLS["무주"]
GOCHANG_REGIONAL_URL = REGIONAL_URLS["고창"]
IMSIL_REGIONAL_URL = REGIONAL_URLS["임실"]
YEONGGWANG_REGIONAL_URL = REGIONAL_URLS["영광"]
NAMWON_REGIONAL_URL = REGIONAL_URLS["남원"]
HAMPYEONG_REGIONAL_URL = REGIONAL_URLS["함평"]
GOKSEONG_REGIONAL_URL = REGIONAL_URLS["곡성"]
SINAN_REGIONAL_URL = REGIONAL_URLS["신안"]
HAENAM_REGIONAL_URL = REGIONAL_URLS["해남"]
JANGHEUNG_REGIONAL_URL = REGIONAL_URLS["장흥"]
GURYE_REGIONAL_URL = REGIONAL_URLS["구례"]
DAMYANG_REGIONAL_URL = REGIONAL_URLS["담양"]
SUNCHANG_REGIONAL_URL = REGIONAL_URLS["순창"]
GOHEUNG_REGIONAL_URL = REGIONAL_URLS["고흥"]
WANDO_REGIONAL_URL = REGIONAL_URLS["완도"]
YEONGJU_REGIONAL_URL = REGIONAL_URLS["영주"]
ANDONG_REGIONAL_URL = REGIONAL_URLS["안동"]
YEONGDEOK_REGIONAL_URL = REGIONAL_URLS["영덕"]
CHEONGDO_REGIONAL_URL = REGIONAL_URLS["청도"]
BUSAN_DONG_REGIONAL_URL = REGIONAL_URLS["부산동구"]
BUSAN_YEONGDO_REGIONAL_URL = REGIONAL_URLS["부산영도"]
BUSAN_SEO_REGIONAL_URL = REGIONAL_URLS["부산서구"]
MIRYANG_REGIONAL_URL = REGIONAL_URLS["밀양"]
HADONG_REGIONAL_URL = REGIONAL_URLS["하동"]
HAPCHEON_REGIONAL_URL = REGIONAL_URLS["합천"]
GEOCHANG_REGIONAL_URL = REGIONAL_URLS["거창"]
GORYEONG_REGIONAL_URL = REGIONAL_URLS["고령"]
UISEONG_REGIONAL_URL = REGIONAL_URLS["의성"]
ULJIN_REGIONAL_URL = REGIONAL_URLS["울진"]
HAMYANG_REGIONAL_URL = REGIONAL_URLS["함양"]
SANCHEONG_REGIONAL_URL = REGIONAL_URLS["산청"]


@dataclass(frozen=True)
class ParticipatingRegion:
    city: str
    region: str
    official_url: str = SOURCE_URL


PARTICIPATING_REGIONS: tuple[ParticipatingRegion, ...] = tuple(
    ParticipatingRegion(city, region, REGIONAL_URLS[city])
    for city, region, _mtpc_do_cd, _signgu_cd in REGIONAL_URL_CODE_ROWS
)

PARTICIPATING_CITY_REGIONS: dict[str, str] = {
    item.city: item.region for item in PARTICIPATING_REGIONS
}
PARTICIPATING_CITIES = frozenset(PARTICIPATING_CITY_REGIONS)

CITY_ALIASES: dict[str, str] = {
    "부산동": "부산동구",
    "부산동구": "부산동구",
    "부산 동구": "부산동구",
    "부산광역시동구": "부산동구",
    "부산영도": "부산영도",
    "부산영도구": "부산영도",
    "부산 영도": "부산영도",
    "부산광역시영도구": "부산영도",
    "부산서": "부산서구",
    "부산서구": "부산서구",
    "부산 서구": "부산서구",
    "부산광역시서구": "부산서구",
}
