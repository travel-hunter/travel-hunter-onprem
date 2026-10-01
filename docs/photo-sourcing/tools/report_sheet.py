"""사진 수집 dry-run 보고서(--report JSON)를 사람이 보는 한 장 그림으로 모은다(로컬, Pillow 필요).

    python report_sheet.py region-report.json region-sheet.jpg [--max-rows 40]

줄마다: 대상(시도·시군 또는 정책 제목) | 고른 사진(초록 테두리) | 뺀 사진 몇 장(붉은 테두리 + 이유).
보기 좋고 나쁨(염전·공사 현장 등)은 규칙이 못 가른다 - 이 그림을 보고 사람이 판단한다(2단계 검토 대기의 연습).
"""

from __future__ import annotations

import argparse
import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

UA = {"User-Agent": "travel-hunter-photo-review/0.1"}
THUMB = (200, 133)
LABEL_W = 220
REJECTED_PER_ROW = 4
ROW_H = THUMB[1] + 34


def font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "AppleSDGothicNeo.ttc", "NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def thumb(url: str | None) -> Image.Image:
    tile = Image.new("RGB", THUMB, (230, 230, 230))
    if not url:
        return tile
    try:
        img = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())).convert("RGB")
        img.thumbnail(THUMB)
        tile.paste(img, ((THUMB[0] - img.width) // 2, (THUMB[1] - img.height) // 2))
        time.sleep(0.2)
    except Exception:
        pass
    return tile


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("out")
    ap.add_argument("--max-rows", type=int, default=40)
    args = ap.parse_args()
    rows = json.loads(Path(args.report).read_text(encoding="utf-8"))[: args.max_rows]
    width = LABEL_W + (THUMB[0] + 10) * (1 + REJECTED_PER_ROW) + 10
    sheet = Image.new("RGB", (width, ROW_H * len(rows) + 10), "white")
    draw = ImageDraw.Draw(sheet)
    small, label = font(12), font(15)
    for i, row in enumerate(rows):
        y = 5 + i * ROW_H
        name = row.get("title") or f"{row.get('sido')} {row.get('city') or '(도 대표)'}"
        draw.text((8, y + 6), str(name)[:16], fill="black", font=label)
        chosen = row.get("chosen")
        x = LABEL_W
        if chosen:
            sheet.paste(thumb(chosen.get("imageUrl")), (x, y))
            draw.rectangle([x - 2, y - 2, x + THUMB[0] + 1, y + THUMB[1] + 1], outline=(16, 150, 72), width=3)
            size = chosen.get("size")
            caption = f"{chosen.get('title', '')[:12]} · {chosen.get('copyright')}" + (f" · {size[0]}x{size[1]}" if size else "")
            draw.text((x, y + THUMB[1] + 4), caption, fill=(16, 110, 60), font=small)
        else:
            draw.text((x + 8, y + 50), "고른 사진 없음 → 비움", fill=(180, 30, 30), font=label)
        for j, rejected in enumerate(row.get("rejected", [])[:REJECTED_PER_ROW]):
            rx = LABEL_W + (THUMB[0] + 10) * (j + 1)
            sheet.paste(thumb(rejected.get("imageUrl")), (rx, y))
            draw.rectangle([rx - 1, y - 1, rx + THUMB[0], y + THUMB[1]], outline=(200, 60, 60), width=2)
            caption = f"{rejected.get('title', '')[:8]} · {','.join(rejected.get('reasons', []))[:22]}"
            draw.text((rx, y + THUMB[1] + 4), caption, fill=(160, 40, 40), font=small)
    sheet.save(args.out, quality=82)
    print("saved", args.out, len(rows), "rows")


if __name__ == "__main__":
    main()
