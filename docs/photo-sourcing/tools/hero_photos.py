"""시안 v48: 홈 배너 사진 - 위키미디어 공용에서 이용 조건이 분명한 사진만(CC0 · CC BY · CC BY-SA).
장의 성격에 맞춰 고른다: 지역 장 = 그 도를 대표하는 여행 사진, 마감 장 = 혜택 종류(여행비 환급 = 여행지 풍경),
전국 장 = 교통. 결과: hero_photos.json {key: {src(data URI), subject, credit, page}} + hero_credits.md(출처 목록)."""
import base64
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

UA = {"User-Agent": "travel-hunter-mockup/0.1 (photo review)"}
here = Path(__file__).parent
PICKS = {
    "region:전남": ("File:Boseong Green Tea Field South Korea Travel Photography (253061695).jpeg", "보성 녹차밭"),
    "theme:refund": ("File:Jeonju- Part II - Jeonju3094.jpg", "전주 한옥마을"),
    "theme:move": ("File:KTX-Sancheon.jpg", "KTX-산천"),
}


def info(title):
    q = {"action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1600"}
    data = json.load(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q), headers=UA), timeout=30))
    return next(iter(data["query"]["pages"].values()))["imageinfo"][0]


out, credits = {}, []
for key, (title, subject) in PICKS.items():
    i = info(title)
    meta = i["extmetadata"]
    artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
    lic = meta.get("LicenseShortName", {}).get("value", "")
    img = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(i["thumburl"], headers=UA), timeout=60).read())).convert("RGB")
    w, h = img.size
    if w > 1600:
        img = img.resize((1600, round(h * 1600 / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=68, method=6)
    out[key] = {
        "src": "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode(),
        "subject": subject,
        "credit": f"{subject} · {artist} · {lic}",
        "page": i["descriptionurl"],
    }
    credits.append(f"- {key}: {subject} - {artist}, {lic}, {i['descriptionurl']}")
    print(key, img.size, len(buf.getvalue()) // 1024, "KB |", out[key]["credit"])

(here / "hero_photos.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")
(here / "hero_credits.md").write_text("# 홈 배너 사진 출처(위키미디어 공용)\n\n" + "\n".join(credits) + "\n", encoding="utf-8", newline="\n")
