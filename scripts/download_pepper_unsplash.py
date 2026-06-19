"""Download pepper images from Unsplash Source API."""
import requests, time
from pathlib import Path

DEST    = Path(__file__).parent.parent / "frontend" / "public" / "crops"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SEARCHES = [
    "red+pepper+vegetable",
    "green+chili+pepper+farm",
    "bell+pepper+harvest",
    "capsicum+pepper+market",
    "pepper+crop+agriculture",
]

for i, term in enumerate(SEARCHES, 1):
    dest = DEST / f"pepper_{i}.jpg"
    if dest.exists():
        print(f"pepper_{i}.jpg already exists")
        continue
    url = f"https://source.unsplash.com/800x600/?{term}"
    print(f"[{i}] {term}... ", end="", flush=True)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and "image" in ct:
            with open(dest, "wb") as f:
                f.write(r.content)
            print(f"OK ({dest.stat().st_size // 1024} KB)")
        else:
            print(f"HTTP {r.status_code} ct={ct[:40]}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(3)

have = [i for i in range(1, 6) if (DEST / f"pepper_{i}.jpg").exists()]
print(f"\nDone: {len(have)}/5 pepper images: {have}")
