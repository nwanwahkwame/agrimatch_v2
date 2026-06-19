"""
Download 5 real crop images per crop from Wikimedia Commons.
Images are saved as {crop}_{1-5}.jpg in frontend/public/crops/

Run from project root:  python scripts/download_crop_images.py
"""
import requests
import time
import sys
from pathlib import Path

DEST = Path(__file__).parent.parent / "frontend" / "public" / "crops"
DEST.mkdir(exist_ok=True)

# Wikimedia Commons search queries for each crop
# Multiple queries per crop increases the chance of finding 5 good photos
CROP_QUERIES = {
    "maize":     ["Zea mays field harvest", "maize farm Africa", "corn crop field"],
    "tomato":    ["tomato harvest farm", "Lycopersicon tomato", "tomato field Africa"],
    "onion":     ["onion harvest field", "Allium cepa bulb", "onion farm"],
    "cassava":   ["cassava harvest Africa", "Manihot esculenta", "cassava root tuber"],
    "rice":      ["rice paddy harvest", "Oryza sativa field", "rice farm West Africa"],
    "plantain":  ["plantain bunch harvest", "Musa paradisiaca Ghana", "plantain farm Africa"],
    "cowpea":    ["cowpea Vigna unguiculata", "black-eyed pea harvest", "cowpea field Africa"],
    "groundnut": ["groundnut Arachis hypogaea", "peanut harvest Africa", "groundnut farm Ghana"],
    "sorghum":   ["sorghum Sorghum bicolor field", "sorghum harvest Africa", "guinea corn"],
    "yam":       ["yam Dioscorea harvest", "yam tuber Africa", "yam farm Ghana"],
}

HEADERS = {"User-Agent": "AgriMatchBot/1.0 (agricultural platform; contact@agrimatch.gh)"}


def search_commons(query: str, limit: int = 20) -> list[str]:
    """Search Wikimedia Commons for image filenames matching query."""
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srnamespace": "6",
                "srlimit": limit,
                "format": "json",
            },
            headers=HEADERS,
            timeout=20,
        )
        results = r.json().get("query", {}).get("search", [])
        return [
            x["title"] for x in results
            if x["title"].lower().endswith((".jpg", ".jpeg"))
        ]
    except Exception as e:
        print(f"    search error: {e}")
        return []


def get_thumb_url(file_title: str, width: int = 1200) -> str | None:
    """Get a thumbnail URL for a Wikimedia Commons file."""
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "titles": file_title,
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": width,
                "format": "json",
            },
            headers=HEADERS,
            timeout=20,
        )
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("imageinfo", [])
            if info and "image/jpeg" in info[0].get("mime", ""):
                return info[0].get("thumburl") or info[0].get("url")
    except Exception as e:
        print(f"    url error: {e}")
    return None


def download(url: str, dest: Path) -> bool:
    """Download a URL to a file. Returns True on success."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=40, stream=True)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            size_kb = dest.stat().st_size // 1024
            # Reject tiny files (likely error pages)
            if size_kb < 20:
                dest.unlink()
                return False
            return True
    except Exception as e:
        print(f"    download error: {e}")
    return False


def images_needed(crop: str) -> list[int]:
    """Return list of indices (1-5) that still need downloading."""
    return [i for i in range(1, 6) if not (DEST / f"{crop}_{i}.jpg").exists()]


def copy_original_as_first(crop: str) -> bool:
    """If {crop}.jpg exists and {crop}_1.jpg does not, copy it."""
    src = DEST / f"{crop}.jpg"
    dst = DEST / f"{crop}_1.jpg"
    if src.exists() and not dst.exists():
        import shutil
        shutil.copy2(src, dst)
        print(f"  copied {crop}.jpg -> {crop}_1.jpg")
        return True
    return False


def main():
    print("=== AgriMatch Crop Image Downloader ===\n")

    for crop, queries in CROP_QUERIES.items():
        # Use existing single image as variant 1 if available
        copy_original_as_first(crop)

        needed = images_needed(crop)
        if not needed:
            print(f"[{crop}] already have all 5 images — skipping")
            continue

        print(f"[{crop}] need indices {needed}")
        idx_iter = iter(needed)
        current_idx = next(idx_iter, None)

        for query in queries:
            if current_idx is None:
                break
            print(f"  searching: {query}")
            files = search_commons(query, limit=25)

            for file_title in files:
                if current_idx is None:
                    break
                dest = DEST / f"{crop}_{current_idx}.jpg"
                if dest.exists():
                    current_idx = next(idx_iter, None)
                    continue

                img_url = get_thumb_url(file_title)
                if not img_url:
                    time.sleep(0.3)
                    continue

                sys.stdout.write(f"  [{current_idx}] {file_title[:55]}... ")
                sys.stdout.flush()

                if download(img_url, dest):
                    size_kb = dest.stat().st_size // 1024
                    print(f"OK ({size_kb} KB)")
                    current_idx = next(idx_iter, None)
                else:
                    print("FAIL")

                time.sleep(0.6)  # be respectful to Wikimedia API

        # Report final state
        have = [i for i in range(1, 6) if (DEST / f"{crop}_{i}.jpg").exists()]
        print(f"  -> have {len(have)}/5: {have}\n")

    print("=== Done ===")
    print(f"Images saved to: {DEST}")


if __name__ == "__main__":
    main()
