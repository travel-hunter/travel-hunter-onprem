"""위키미디어 공용 후보를 작게 받아 한 장(contact sheet)에 모아 눈으로 비교한다.

    python commons_preview.py out.jpg "File:A.jpg" "File:B.jpg" ...

칸마다 번호와 파일 이름, 라이선스를 적는다. 판단은 ../2026-10-01-home-banner-photos.md 의 비교 표에 남긴다.
공용은 요청이 잦으면 429 로 막는다 - 정보 조회는 한 번에 묶고, 사진 받기 사이에 쉬고, 429 면 기다렸다 다시 한다.
"""
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

UA = {"User-Agent": "travel-hunter-photo-sourcing/0.1 (internal review)"}


def get(url, tries=5):
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * (attempt + 1))
    raise RuntimeError("unreachable")


def thumbs(titles, width=480):
    q = {"action": "query", "format": "json", "titles": "|".join(titles), "prop": "imageinfo",
         "iiprop": "url|extmetadata", "iiurlwidth": str(width)}
    pages = json.loads(get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q)))["query"]["pages"]
    found = {p["title"]: p["imageinfo"][0] for p in pages.values() if "imageinfo" in p}
    norm = {t.replace("_", " "): t for t in found}
    return [(t, found.get(norm.get(t.replace("_", " "), t))) for t in titles]


if __name__ == "__main__":
    out, titles = sys.argv[1], sys.argv[2:]
    tiles = []
    for i, (title, info) in enumerate(thumbs(titles)):
        tile = Image.new("RGB", (480, 300), "white")
        lic = ""
        if info:
            lic = info["extmetadata"].get("LicenseShortName", {}).get("value", "")
            img = Image.open(io.BytesIO(get(info["thumburl"]))).convert("RGB")
            img.thumbnail((480, 270))
            tile.paste(img, (0, 0))
            time.sleep(1.5)
        ImageDraw.Draw(tile).text((6, 278), f"{i + 1}. {title[5:55]} | {lic or 'not found'}", fill="black")
        tiles.append(tile)
    sheet = Image.new("RGB", (960, 300 * ((len(tiles) + 1) // 2)), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 2) * 480, (i // 2) * 300))
    sheet.save(out, quality=80)
    print("saved", out, len(tiles))
