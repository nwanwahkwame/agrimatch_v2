# AgriMatch -- Ghana Agricultural Price Pipeline (M1)

## What this project does

AgriMatch ingests historical and live agricultural market price data for Ghana from two
sources: HDX (WFP Humanitarian Data Exchange, fetched via API) and MoFA SRID (Ghana
Ministry of Food and Agriculture Excel reports dropped into an inbox folder). Raw rows
are validated, normalised to a standard set of crops and units, and loaded into a Neon
PostgreSQL database. Rows that cannot be mapped are held in a quarantine table for
review. The pipeline can be triggered manually or run on a schedule (daily for HDX,
weekly for MoFA). As of M1 completion the database holds 37,933 clean price records
across 44 markets, 16 crops, and 13 regions, spanning 2006-2023.

---

## Collaborators

1. Ena Ayimey [GitHub](https://github.com/Ena753 "Ena's repo")
2. Kwame Boadi Nwanwah [GitHub](https://github.com/nwanwahkwame "Kwame's repo")
3. Olivia Matey [GitHub](https://github.com/mateyolivia-maker "Livy's repo")
4. Robert Ewonam Agbo [GitHub](https://github.com/Ing-RAKE "Ing_Rake's repo")
5. Rebecca Eshun [GitHub](https://github.com/Eshun-Rebecca "Becks' repo")
6. Bright Adu-Boahen [GitHub](https://github.com/NehlTech/agrimatch "Bright's repo")

---

## Setup

### 1. Prerequisites

- Python 3.11
- A Neon PostgreSQL database (free tier is sufficient for M1)

### 2. Clone and create virtual environment

```
git clone <repo-url>
cd agrimatch
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Create the .env file

Copy the template below into a file named `.env` in the project root:

```
# Required
DATABASE_URL=postgresql+psycopg2://user:password@host/dbname?sslmode=require&channel_binding=require

# Optional -- defaults shown
HDX_DATASET_ID=wfp-food-prices-for-ghana
MOFA_INBOX_PATH=data/mofa_inbox
LOG_LEVEL=INFO
ALERT_EMAIL=
```

Replace the `DATABASE_URL` value with your Neon connection string. The other variables
can be left at their defaults for a standard setup.

### 5. Create the database tables

```
python -c "from db.models import Base; from db.connection import get_engine; Base.metadata.create_all(get_engine())"
```

---

## Running the pipeline manually

```
# HDX only (recommended first run)
python run_pipeline.py --source hdx

# MoFA only (requires .xlsx files in data/mofa_inbox)
python run_pipeline.py --source mofa

# Both sources in sequence
python run_pipeline.py --source all
```

The pipeline prints a summary table showing rows fetched, rows loaded to clean_prices,
rows quarantined, and overall status. Exit code is 0 on success, 1 if any source fails.

---

## Adding a new crop mapping

When a new raw name variant appears in quarantine (e.g., `unmapped_crop: Maize (dry)`),
add it to `config/crop_map.py`:

```python
# Find the relevant crop block and add the new variant:
"maize (dry)": "maize",
```

The key must be the raw name lowercased exactly as it appears in the rejection_reason.
After saving, add the new reason string to the `RESCUABLE_REASONS` set at the top of
`rescue_quarantine.py`, then run it to re-process matching quarantine rows:

```
python rescue_quarantine.py
```

### Adding a new unit mapping

Unit variants go in `config/unit_map.py` in the `UNIT_MAP` dict (value is the kg
conversion factor). For units that cannot be converted to kg (e.g., eggs per tray),
add an entry to `_CROP_UNIT_FACTORS` in `ingestion/transformers.py`:

```python
("eggs", "30 pcs"): (1.0, "tray"),
```

---

## Adding a new MoFA file

1. Drop the `.xlsx` file into `data/mofa_inbox/`.
2. Run the pipeline: `python run_pipeline.py --source mofa`

The pipeline detects new files automatically by comparing filenames against the
`ingestion_log` table. Already-processed files are skipped. The file must follow
the standard SRID format with a header row containing columns for market, commodity,
price, and date (the pipeline searches rows 1-10 for the header automatically).

---

## Checking if the pipeline ran successfully

Query the `ingestion_log` table:

```python
from db.connection import get_session
from sqlalchemy import text

with get_session() as s:
    rows = s.execute(text("""
        SELECT source, file_ref, rows_fetched, rows_clean, rows_quarantined,
               status, error, created_at
        FROM ingestion_log
        ORDER BY created_at DESC
        LIMIT 10
    """)).all()
    for r in rows:
        print(r)
```

A successful run shows `status = 'success'`. A failed run shows `status = 'failed'`
with a message in the `error` column.

---

## Investigating quarantined rows

```python
from db.connection import get_session
from sqlalchemy import text

with get_session() as s:
    rows = s.execute(text("""
        SELECT rejection_reason, COUNT(*) AS cnt
        FROM price_quarantine
        GROUP BY rejection_reason
        ORDER BY cnt DESC
        LIMIT 20
    """)).all()
    for r in rows:
        print(r.cnt, r.rejection_reason)
```

Common reasons and fixes:

| Reason prefix | Fix |
|---------------|-----|
| `unmapped_crop: X` | Add `"x": "canonical_name"` to `config/crop_map.py` |
| `unmapped_unit: X` | Add to `UNIT_MAP` in `config/unit_map.py` or `_CROP_UNIT_FACTORS` in `ingestion/transformers.py` |
| `missing_field: X` | The source data is missing a required column -- check the raw file |
| `invalid_price` | Price value is zero, negative, or non-numeric in the source |

After adding mappings, run `python rescue_quarantine.py` to re-process matching rows.

---

## Running the test suite

Tests use an in-memory SQLite database and do not touch the real PostgreSQL instance.

```
pytest tests/ -v
```

Expected output: `8 passed`. No `.env` file or database connection is required.

---

## Running the data quality report

```
python -m reports.data_quality
```

This prints a report to the terminal and saves a plain-text copy to
`reports/latest_quality_report.txt`. The report covers:

- Row counts by source, crop, and market
- Quarantine summary and top rejection reasons
- Data gaps greater than 3 consecutive months
- The last 10 ingestion log entries

---

## Project structure

| Path | Purpose |
|------|---------|
| `ingestion/` | HDX and MoFA clients, validators, transformers, scheduler |
| `db/` | SQLAlchemy connection factory and ORM models |
| `config/` | Environment settings, crop map, unit map |
| `reports/` | Data quality report generator |
| `tests/` | Pytest unit tests (SQLite, no real DB required) |
| `data/mofa_inbox/` | Drop zone for MoFA SRID Excel files |
| `data/M1_HANDOVER_NOTES.md` | M1 data quality findings and modelling notes |
| `run_pipeline.py` | Manual pipeline trigger (CLI) |
| `rescue_quarantine.py` | Re-process quarantine after mapping fixes |
