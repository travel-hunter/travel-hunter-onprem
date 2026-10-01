"""홈 배너 사진 받기 - 위키미디어 공용에서 이용 조건이 분명한 사진만(CC0 · CC BY · CC BY-SA).
장의 성격에 맞춰 고른다: 지역 장 = region:<도>, 마감 장 = theme:<refund|stay|partner|move>, 전국 장 = theme:move.
고른 이유·후보는 ../2026-10-01-home-banner-photos.md.

    python hero_photos.py                                   # 시안용: hero_photos.json(data URI) + hero_credits.md
    python hero_photos.py --out-dir ../../../frontend/src/assets/hero   # 앱용: 1280px WebP 파일 + 출처 줄 출력
"""
import argparse
import base64
import io
import json
import re
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
}


def info(title, width):
    q = {"action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": str(width)}
    data = json.load(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q), headers=UA), timeout=30))
    return next(iter(data["query"]["pages"].values()))["imageinfo"][0]


def fetch(title, width, quality):
    i = info(title, width)
    meta = i["extmetadata"]
    artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
    lic = meta.get("LicenseShortName", {}).get("value", "")
    img = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(i["thumburl"], headers=UA), timeout=60).read())).convert("RGB")
    w, h = img.size
    if w > width:
        img = img.resize((width, round(h * width / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue(), artist, lic, i["descriptionurl"], img.size


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", help="앱 자산 폴더 - 주면 1280px WebP 파일로 쓴다")
    args = ap.parse_args()
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
