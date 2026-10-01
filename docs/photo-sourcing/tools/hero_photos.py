"""홈 배너 사진 받기 - 위키미디어 공용에서 이용 조건이 분명한 사진만(CC0 · CC BY · CC BY-SA).
장의 성격에 맞춰 고른다: 지역 장 = region:<도>, 마감 장 = theme:<refund|stay|partner|move>, 전국 장 = theme:move.
고른 이유·후보는 ../2026-10-01-home-banner-photos.md.

    python hero_photos.py                                   # 시안용: hero_photos.json(data URI) + hero_credits.md
    python hero_photos.py --out-dir ../../../frontend/src/assets/hero   # 앱용: 1280px WebP 파일 + 출처 줄 출력
    python hero_photos.py --out-dir ../../../frontend/src/assets/hero --only theme:stay,theme:partner   # 새 열쇠만

공용은 요청이 잦으면 429 로 막는다 - 받기 사이에 쉬고, 429 면 기다렸다 다시 한다.
"""
import argparse
import base64
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

UA = {"User-Agent": "travel-hunter-photo-sourcing/0.1 (internal review)"}
here = Path(__file__).parent
# 열쇠: (공용 파일 이름, 화면에 적을 사진 이름, 앱 파일 이름)
PICKS = {
    "region:전남": ("File:Boseong Green Tea Field South Korea Travel Photography (253061695).jpeg", "보성 녹차밭", "boseong-green-tea"),
    "theme:refund": ("File:Jeonju- Part II - Jeonju3094.jpg", "전주 한옥마을", "jeonju-hanok"),
    "theme:move": ("File:KTX-Sancheon.jpg", "KTX-산천", "ktx-sancheon"),
    "theme:stay": ("File:Hwangnamguan Hotel at night.jpg", "경주 황남관 한옥 숙소", "hwangnamguan-hanok-stay"),
    "theme:partner": ("File:Korean pancakes and pan-fried foods at Gwangjang Market.jpg", "광장시장 전", "gwangjang-market-jeon"),
}


def get(url, tries=5):
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * (attempt + 1))
    raise RuntimeError("unreachable")


def info(title, width):
    q = {"action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": str(width)}
    data = json.loads(get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q)))
    return next(iter(data["query"]["pages"].values()))["imageinfo"][0]


def fetch(title, width, quality):
    i = info(title, width)
    meta = i["extmetadata"]
    artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
    lic = meta.get("LicenseShortName", {}).get("value", "")
    time.sleep(1.5)
    img = Image.open(io.BytesIO(get(i["thumburl"]))).convert("RGB")
    w, h = img.size
    if w > width:
        img = img.resize((width, round(h * width / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue(), artist, lic, i["descriptionurl"], img.size


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", help="앱 자산 폴더 - 주면 1280px WebP 파일로 쓴다")
    ap.add_argument("--only", help="이 열쇠만(쉼표로 구분)")
    args = ap.parse_args()
    if args.only:
        PICKS = {k: v for k, v in PICKS.items() if k in args.only.split(",")}
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for key, (title, subject, name) in PICKS.items():
            data, artist, lic, page, size = fetch(title, 1280, 64)
            (out / f"{name}.webp").write_bytes(data)
            print(f'  "{key}": {{ file: "{name}.webp", credit: "{subject} · {artist} · {lic}" }},  // {size} {len(data) // 1024}KB {page}')
    else:
        result, credits = {}, []
        for key, (title, subject, _) in PICKS.items():
            data, artist, lic, page, size = fetch(title, 1600, 68)
            result[key] = {"src": "data:image/webp;base64," + base64.b64encode(data).decode(), "subject": subject,
                           "credit": f"{subject} · {artist} · {lic}", "page": page}
            credits.append(f"- {key}: {subject} - {artist}, {lic}, {page}")
            print(key, size, len(data) // 1024, "KB |", result[key]["credit"])
        (here / "hero_photos.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8", newline="\n")
        (here / "hero_credits.md").write_text("# 홈 배너 사진 출처(위키미디어 공용)\n\n" + "\n".join(credits) + "\n", encoding="utf-8", newline="\n")
