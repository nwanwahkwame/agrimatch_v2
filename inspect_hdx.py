import sys
import requests
import pandas as pd
from pathlib import Path

HDX_API = "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-ghana"


def main():
    print("Fetching package metadata from HDX...")
    resp = requests.get(HDX_API, timeout=30)
    resp.raise_for_status()
    package = resp.json()

    if not package.get("success"):
        print("HDX API returned success=false:", package.get("error"))
        sys.exit(1)

    # Find the first CSV resource
    resources = package["result"]["resources"]
    csv_resource = next(
        (r for r in resources if r.get("format", "").upper() == "CSV"),
        None,
    )
    if csv_resource is None:
        print("No CSV resource found. Available formats:")
        for r in resources:
            print(" ", r.get("format"), "—", r.get("url"))
        sys.exit(1)

    csv_url = csv_resource["url"]
    print(f"Found CSV resource: {csv_resource['name']}")
    print(f"URL: {csv_url}\n")

    out_path = Path("data/hdx_sample.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        print(f"Using cached CSV at {out_path} (delete it to force re-download)\n")
    else:
        print("Downloading CSV (streaming)...")
        with requests.get(csv_url, timeout=(10, 300), stream=True) as csv_resp:
            csv_resp.raise_for_status()
            total = int(csv_resp.headers.get("content-length", 0))
            downloaded = 0
            with open(out_path, "wb") as f:
                for chunk in csv_resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"  {downloaded/1024:.0f} KB / {total/1024:.0f} KB", end="\r")
        print(f"\nRaw CSV saved to {out_path}\n")

    df = pd.read_csv(out_path)
    print(f"Total rows: {len(df):,}")
    print(f"Columns:    {list(df.columns)}\n")

    for col in ("commodity", "unit", "market"):
        if col not in df.columns:
            print(f"[!] Column '{col}' not found in dataset — skipping.")
            continue
        vals = sorted(df[col].dropna().unique().tolist())
        print(f"-- {col} ({len(vals)} unique) ----------------------")
        for v in vals:
            print(f"  {v}")
        print()


if __name__ == "__main__":
    main()
