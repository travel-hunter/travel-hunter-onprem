"""위키미디어 공용(Commons)에서 홈 배너 사진 후보를 찾는다 - 라이선스·작가·크기를 같이 받는다(키 필요 없음).

    python commons_search.py "Boseong green tea field" "KTX-Sancheon"          # 쓸 만한 것만 화면에
    python commons_search.py --json candidates.json "Boseong green tea field"  # 전부(거른 이유 포함) JSON 으로

쓸 만한 것 = 라이선스가 CC0 · 퍼블릭 도메인 · CC BY · CC BY-SA · 공공누리 1유형이고, 가로 사진(가로 ≥ 세로 × 1.2)이며
가로 1200px 이상. 그 밖(CC BY-NC 등 상업 이용 불가, 세로, 작은 사진)은 JSON 에 reject 사유와 함께 남는다.
"""
import argparse
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "travel-hunter-photo-sourcing/0.1 (internal review)"}
ALLOWED = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)? [0-9.]+|KOGL Type 1)", re.I)


def search(query: str, limit: int = 12) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": "6",
        "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": "1280",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
    rows = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        w, h = info.get("width", 0), info.get("height", 0)
        reject = []
        if not ALLOWED.match(lic):
            reject.append(f"license:{lic or 'unknown'}")
        if not w > h * 1.2:
            reject.append("not-landscape")
        if w < 1200:
            reject.append("too-small")
        rows.append({
            "query": query, "title": page["title"], "license": lic, "artist": artist[:80],
            "width": w, "height": h, "page": info.get("descriptionurl", ""), "thumb1280": info.get("thumburl", ""),
            "usable": not reject, "reject": reject,
        })
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", nargs="+")
    ap.add_argument("--json", help="모든 후보를 이 파일에 JSON 으로 쓴다")
    args = ap.parse_args()
    found = [row for q in args.queries for row in search(q)]
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(found, fh, ensure_ascii=False, indent=1)
    for row in found:
        if row["usable"]:
            print(f"- [{row['query']}] {row['title'][5:80]} | {row['license']} | {row['artist']} | {row['width']}x{row['height']}")
            print(f"  {row['page']}")
    print(f"{sum(r['usable'] for r in found)} usable / {len(found)} found")
