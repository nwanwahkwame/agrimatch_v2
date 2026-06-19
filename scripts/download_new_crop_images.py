"""Download 5 images each for soybean, millet, garden_egg via Openverse."""
import requests, time
from pathlib import Path

DEST    = Path(__file__).parent.parent / "frontend" / "public" / "crops"
HEADERS = {"User-Agent": "AgriMatch/1.0 (agrimatch.gh; opensource agricultural platform)"}

CROP_QUERIES = {
    "soybean":    ["soybean plant harvest", "soya beans pods farm", "soybean field crop"],
    "millet":     ["millet grain harvest Africa", "pearl millet crop field", "millet sorghum Ghana"],
    "garden_egg": ["eggplant aubergine harvest", "garden egg brinjal Africa", "aubergine purple vegetable farm"],
}


def search_openverse(query, limit=10):
    try:
        r = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "license_type": "commercial", "page_size": limit, "extension": "jpg"},
            headers=HEADERS, timeout=20,
        )
        if r.status_code == 200:
            return [(item["url"], item.get("title", "")) for item in r.json().get("results", [])]
    except Exception as e:
        print(f"  search error: {e}")
    return []


def download(url, dest):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            if dest.stat().st_size > 20_000:
                return True
            dest.unlink()
    except Exception as e:
        print(f"  download error: {e}")
    return False


for crop, queries in CROP_QUERIES.items():
    print(f"\n[{crop.upper()}]")
    idx = 1
    for query in queries:
        if idx > 5:
            break
        print(f"  Searching: {query}")
        results = search_openverse(query)
        for url, title in results:
            if idx > 5:
                break
            dest = DEST / f"{crop}_{idx}.jpg"
            if dest.exists():
                idx += 1
                continue
            short = title[:50].encode("ascii", "replace").decode()
            print(f"    [{idx}] {short}... ", end="", flush=True)
            if download(url, dest):
                print(f"OK ({dest.stat().st_size // 1024} KB)")
                idx += 1
            else:
                print("FAIL")
            time.sleep(1)
    have = [i for i in range(1, 6) if (DEST / f"{crop}_{i}.jpg").exists()]
    print(f"  -> {len(have)}/5 images")
