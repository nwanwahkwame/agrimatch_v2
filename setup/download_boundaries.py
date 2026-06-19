"""
Download Ghana GADM 4.1 level-2 district boundaries (GeoPackage).

Usage:
    python setup/download_boundaries.py
"""

from pathlib import Path

import requests

URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_GHA.gpkg"
DEST = Path("data/gadm41_GHA.gpkg")
CHUNK = 65536  # 64 KB per read


def download() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)

    if DEST.exists():
        print("Boundaries file already exists:", DEST)
        return

    print("Downloading", URL)
    resp = requests.get(URL, stream=True, timeout=(10, 300))
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    last_reported_mb = -1

    with DEST.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=CHUNK):
            if not chunk:
                continue
            fh.write(chunk)
            downloaded += len(chunk)
            mb_done = downloaded / 1_048_576
            # Print one line per whole MB
            if int(mb_done) > last_reported_mb:
                last_reported_mb = int(mb_done)
                if total:
                    pct = downloaded / total * 100
                    mb_total = total / 1_048_576
                    print(f"  {mb_done:5.1f} / {mb_total:.1f} MB  ({pct:.0f}%)", flush=True)
                else:
                    print(f"  {mb_done:.1f} MB downloaded", flush=True)

    print(f"Done. Saved to {DEST} ({downloaded / 1_048_576:.2f} MB)")


def inspect() -> None:
    import geopandas as gpd
    from pyogrio import list_layers, read_dataframe

    raw = list_layers(str(DEST))          # returns array of [name, geometry_type]
    layers = [row[0] for row in raw]
    print()
    print(f"Layers in file: {len(layers)}")
    for name in layers:
        gdf = read_dataframe(str(DEST), layer=name, columns=[])  # geometry only, fast
        print(f"  {name}: {len(gdf)} rows")

    target = layers[2] if len(layers) > 2 else layers[-1]
    print()
    print(f"Column names in layer '{target}':")
    gdf = gpd.read_file(str(DEST), layer=target, engine="pyogrio")
    for col in gdf.columns:
        print(f"  {col}")


if __name__ == "__main__":
    download()
    inspect()
