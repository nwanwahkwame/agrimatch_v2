"""Download 5 pepper images from Wikimedia Commons."""
import sys, os, time, requests
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEST    = Path(__file__).parent.parent / "frontend" / "public" / "crops"
HEADERS = {"User-Agent": "AgriMatchBot/1.0 (agrimatch.gh)"}

QUERIES = [
    "pepper vegetable harvest",
    "Capsicum pepper fruit red green",
    "chili pepper plant field Africa",
    "bell pepper capsicum annuum",
    "hot pepper market Ghana",
]


def search(query, limit=30):
    try:
        time.sleep(1.2)
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": query, "srnamespace": "6",
                "srlimit": limit, "format": "json",
            },
            headers=HEADERS, timeout=25,
        )
        return [
            x["title"] for x in r.json().get("query", {}).get("search", [])
            if x["title"].lower().endswith((".jpg", ".jpeg"))
            and "capsicum" not in x["title"].lower()   # avoid very scientific files
        ]
    except Exception:
        return []


def get_url(title):
    try:
        time.sleep(0.8)
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "titles": title,
                "prop": "imageinfo", "iiprop": "url|mime|size",
                "format": "json",
            },
            headers=HEADERS, timeout=25,
        )
        for page in r.json().get("query", {}).get("pages", {}).values():
            for info in page.get("imageinfo", []):
                mime = info.get("mime", "")
                url  = info.get("url", "")
                size = info.get("size", 0)
                if "jpeg" in mime and size > 50_000:
                    return url
    except Exception:
        pass
    return None


def dl(url, dest):
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and ("image" in ct or "jpeg" in ct or "octet" in ct):
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            sz = dest.stat().st_size
            if sz > 20_000:
                return True
            dest.unlink()
    except Exception:
        pass
    return False




def main():
    idx = 1
    for query in QUERIES:
        if idx > 5:
            break
        print(f"Searching: {query}")
        files = search(query)
        for title in files:
            if idx > 5:
                break
            dest = DEST / f"pepper_{idx}.jpg"
            if dest.exists():
                idx += 1
                continue
            url = get_url(title)
            if not url:
                continue
            short = title[:50].encode("ascii", "replace").decode()
            print(f"  [{idx}] {short}... ", end="", flush=True)
            if dl(url, dest):
                print(f"OK ({dest.stat().st_size // 1024} KB)")
                idx += 1
            else:
                print("FAIL")
            time.sleep(1)

    have = [i for i in range(1, 6) if (DEST / f"pepper_{i}.jpg").exists()]
    print(f"\nDone: {len(have)}/5 pepper images -> {have}")


if __name__ == "__main__":
    main()
