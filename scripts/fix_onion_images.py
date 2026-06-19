"""Replace onion images using Wikimedia Commons API."""
import requests, time
from pathlib import Path

DEST    = Path(__file__).parent.parent / "frontend" / "public" / "crops"
HEADERS = {"User-Agent": "AgriMatch/1.0 (agrimatch.gh; IT@okbfoundation.org)"}

QUERIES = [
    "onion crop harvest",
    "onion field farm",
    "Allium cepa harvest",
    "onion bulb agriculture",
    "onion farming Africa",
]


def search_wikimedia(query, limit=20):
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action":       "query",
                "generator":    "search",
                "gsrnamespace": "6",
                "gsrsearch":    query,
                "gsrlimit":     limit,
                "prop":         "imageinfo",
                "iiprop":       "url|size|mime",
                "format":       "json",
            },
            headers=HEADERS, timeout=20,
        )
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {}).values()
            results = []
            for page in pages:
                ii = page.get("imageinfo", [])
                if not ii:
                    continue
                info = ii[0]
                if info.get("mime", "") != "image/jpeg":
                    continue
                w = info.get("width", 0)
                h = info.get("height", 0)
                if w < 400 or h < 300:
                    continue
                results.append((info["url"], page.get("title", "")))
            return results
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


def main():
    print("[ONION] Replacing with Wikimedia Commons images\n")

    # Remove existing
    for i in range(1, 6):
        p = DEST / f"onion_{i}.jpg"
        if p.exists():
            p.unlink()
            print(f"  Removed old onion_{i}.jpg")

    idx = 1
    for query in QUERIES:
        if idx > 5:
            break
        print(f"\nSearching: {query}")
        results = search_wikimedia(query)
        for url, title in results:
            if idx > 5:
                break
            dest = DEST / f"onion_{idx}.jpg"
            short = title[:60].encode("ascii", "replace").decode()
            print(f"  [{idx}] {short}... ", end="", flush=True)
            if download(url, dest):
                print(f"OK ({dest.stat().st_size // 1024} KB)")
                idx += 1
            else:
                print("FAIL")
            time.sleep(0.5)

    have = [i for i in range(1, 6) if (DEST / f"onion_{i}.jpg").exists()]
    print(f"\nDone: {len(have)}/5 onion images")


if __name__ == "__main__":
    main()
