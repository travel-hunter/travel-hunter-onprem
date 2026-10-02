"""로그인 화면 사진 받기(시안 v54) - 지역 8곳 풍경, 위키미디어 공용의 CC0 · 퍼블릭 도메인만.
출처 표시 의무가 없는 사진이라 로그인 화면에는 적지 않고 앱 안 '사진 출처' 창에만 모은다(frontend/src/components/heroPhotos.ts).

    python login_photos.py --out-dir ../../../frontend/src/assets/login   # 1280px WebP 파일 + 작가 · 라이선스 줄 출력
"""
import argparse
import io
import time
from pathlib import Path

from PIL import Image

from hero_photos import fetch

# (지역, 공용 파일 이름, 화면에 적을 사진 이름, 앱 파일 이름)
PICKS = [
    ("서울", "File:Bukchon Hanok Village 03.jpg", "북촌 한옥마을", "bukchon-hanok"),
    ("경기", "File:Hwaseong Fortress 01.jpg", "수원 화성", "hwaseong-fortress"),
    ("강원", "File:Seoraksan Cable Car 04.jpg", "설악산 케이블카", "seoraksan-cable-car"),
    ("전북", "File:Jeonju Hanok Maeul 02.jpg", "전주 한옥마을", "jeonju-hanok-maeul"),
    ("전남", "File:Panorama of Reed fields in Suncheon bay.jpg", "순천만 갈대밭", "suncheon-bay-reeds"),   # 파노라마 - 가운데 3:2
    ("경북", "File:Hahoe Folk Village 02.jpg", "안동 하회마을", "hahoe-village"),
    ("부산", "File:Gwangan Bridge and Gwangalli Beach - Gwangalli2721.jpg", "광안대교와 광안리", "gwangan-bridge"),
    ("제주", "File:Seongsan, Jeju Island.jpg", "성산일출봉 일대", "seongsan-jeju"),
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    out = Path(ap.parse_args().out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for region, title, subject, name in PICKS:
        data, artist, lic, page, size = fetch(title, 1280, 64)
        if size[0] / size[1] > 2:   # 파노라마는 1280 폭이면 높이가 200 남짓 - 크게 받아 가운데 3:2 를 잘라 쓴다
            data, artist, lic, page, size = fetch(title, 3840, 64)
            img = Image.open(io.BytesIO(data))
            w, h = img.size
            cut = round(h * 3 / 2)
            img = img.crop(((w - cut) // 2, 0, (w - cut) // 2 + cut, h))
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=64, method=6)
            data, size = buf.getvalue(), img.size
        (out / f"{name}.webp").write_bytes(data)
        print(f"{region} | {subject} | {artist} | {lic} | {name}.webp {size} {len(data) // 1024}KB | {page}")
        time.sleep(1.5)
