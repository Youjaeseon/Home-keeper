"""One-time fetch of real 용인시 repair businesses from the Kakao Local keyword search API.

Usage (from hk-integration/):
    apps/api/.venv/bin/python apps/api/scripts/fetch_yongin_vendors.py [output.json]

- Reads KAKAO_REST_API_KEY from apps/api/.env (never printed).
- Keeps only places whose address is in 경기 용인시 and that list a business phone.
- Maps each place to the app's work types for the "추천" tag.
- Writes JSON for review; the app copies the confirmed entries into src/data/yongin-vendors.ts.
The app itself never calls Kakao at runtime.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

API = "https://dapi.kakao.com/v2/local/search/keyword.json"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Search keyword -> app work types (data/options + backend work_types names)
QUERIES: dict[str, list[str]] = {
    "용인 곰팡이 제거": ["곰팡이 제거"],
    "용인 결로 곰팡이": ["곰팡이 제거", "원인 점검"],
    "용인 누수탐지": ["원인 점검"],
    "용인 방수공사": ["균열 보수", "원인 점검"],
    "용인 균열 보수": ["균열 보수"],
    "용인 크랙 보수": ["균열 보수"],
    "용인 도배": ["벽지·도장 보수"],
    "용인 페인트 도장": ["벽지·도장 보수"],
}
MAX_PAGES = 3  # 15 results per page


def load_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("KAKAO_REST_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit("KAKAO_REST_API_KEY is not set in apps/api/.env")


def search(key: str, query: str, page: int) -> dict:
    url = f"{API}?{urllib.parse.urlencode({'query': query, 'page': page, 'size': 15})}"
    request = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {key}"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def main() -> None:
    key = load_key()
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("yongin_vendors_kakao.json")
    places: dict[str, dict] = {}
    for query, work_types in QUERIES.items():
        for page in range(1, MAX_PAGES + 1):
            data = search(key, query, page)
            for doc in data.get("documents", []):
                address = doc.get("road_address_name") or doc.get("address_name") or ""
                phone = (doc.get("phone") or "").strip()
                if "용인시" not in address or not phone:
                    continue
                entry = places.setdefault(
                    doc["id"],
                    {
                        "id": f"kakao-{doc['id']}",
                        "name": doc["place_name"],
                        "phone": phone,
                        "address": address,
                        "category": doc.get("category_name", ""),
                        "specialties": [],
                        "sourceUrl": doc.get("place_url", ""),
                        "checkedAt": date.today().isoformat(),
                        "queries": [],
                    },
                )
                entry["queries"].append(query)
                for work_type in work_types:
                    if work_type not in entry["specialties"]:
                        entry["specialties"].append(work_type)
            if data.get("meta", {}).get("is_end", True):
                break
            time.sleep(0.2)
    result = sorted(places.values(), key=lambda p: (-len(p["queries"]), p["name"]))
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(result)} places to {out_path}")


if __name__ == "__main__":
    main()
