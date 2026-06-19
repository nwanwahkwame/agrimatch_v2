from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminRepo:

    @staticmethod
    def list_farmers(db: Session):
        return db.execute(text("""
            SELECT
                f.id, f.full_name, f.phone_number, f.is_active, f.created_at,
                d.district_name, d.region_name,
                COUNT(fd.id) AS declaration_count
            FROM farmers f
            LEFT JOIN ghana_districts d ON d.id = f.district_id
            LEFT JOIN farmer_declarations fd
                   ON fd.farmer_id = f.id AND fd.status = 'active'
            GROUP BY
                f.id, f.full_name, f.phone_number,
                f.is_active, f.created_at,
                d.district_name, d.region_name
            ORDER BY f.created_at DESC
        """)).fetchall()

    @staticmethod
    def update_farmer_status(db: Session, farmer_id: int, is_active: bool) -> int:
        result = db.execute(
            text("UPDATE farmers SET is_active = :v WHERE id = :id"),
            {"v": is_active, "id": farmer_id},
        )
        return result.rowcount

    @staticmethod
    def list_markets(db: Session):
        return db.execute(text("""
            SELECT
                m.id, m.market_name, m.canonical_name, m.region, m.is_major_hub,
                d.district_name,
                MAX(cp.price_date)      AS last_price_date,
                COUNT(DISTINCT cp.crop) AS crop_count
            FROM ghana_markets m
            LEFT JOIN ghana_districts d ON d.id = m.district_id
            LEFT JOIN clean_prices    cp ON cp.market = m.canonical_name
            GROUP BY
                m.id, m.market_name, m.canonical_name,
                m.region, m.is_major_hub, d.district_name
            ORDER BY m.is_major_hub DESC NULLS LAST, m.market_name
        """)).fetchall()

    @staticmethod
    def list_districts(db: Session):
        return db.execute(text("""
            SELECT id, district_name, region_name, centroid_lat, centroid_lon
            FROM ghana_districts
            ORDER BY region_name, district_name
        """)).fetchall()

    @staticmethod
    def list_crops(db: Session):
        return db.execute(text("""
            SELECT id, internal_name, default_unit, is_byproduct_source, byproduct_types
            FROM crop_reference
            ORDER BY internal_name
        """)).fetchall()

    @staticmethod
    def get_stats(db: Session):
        return db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM farmers WHERE is_active = true)            AS active_farmers,
                (SELECT COUNT(*) FROM ghana_markets)                             AS total_markets,
                (SELECT COUNT(*) FROM farmer_declarations WHERE status='active') AS active_declarations,
                COALESCE((
                    SELECT SUM(quantity_kg * price_forecast_ghs)
                    FROM   farmer_declarations
                    WHERE  status = 'active' AND price_forecast_ghs IS NOT NULL
                ), 0) AS total_value_ghs
        """)).fetchone()

    @staticmethod
    def list_regions(db: Session):
        return db.execute(text("""
            SELECT
                m.region,
                COUNT(DISTINCT m.id) AS market_count,
                COUNT(DISTINCT d.id) AS district_count
            FROM ghana_markets    m
            LEFT JOIN ghana_districts d ON d.region_name = m.region
            GROUP BY m.region
            ORDER BY market_count DESC
        """)).fetchall()

    @staticmethod
    def get_model_accuracy(db: Session):
        return db.execute(text("""
            SELECT
                market, model_type,
                ROUND(CAST((1 - COALESCE(mape_30d, 0.05)) * 100 AS numeric), 1) AS accuracy_pct,
                ROUND(CAST(mae_30d AS numeric), 4) AS mae,
                training_rows, trained_at
            FROM model_baselines
            WHERE mape_30d IS NOT NULL
            ORDER BY market, model_type
        """)).fetchall()

    @staticmethod
    def get_pipeline_stats(db: Session) -> tuple:
        # Discover which tables actually exist before querying them
        existing = {
            r[0] for r in db.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )).fetchall()
        }

        _TABLES = {
            'clean_prices':       'clean_prices',
            'raw_prices':         'raw_prices',
            'quarantine':         'price_quarantine',
            'chirps':             'chirps_daily',
            'nasa_power':         'nasa_power_daily',
            'climate_indicators': 'climate_indicators',
            'logistics_costs':    'logistics_costs',
            'feature_store':      'feature_store',
            'price_forecasts':    'price_forecasts',
            'farmers':            'farmers',
            'declarations':       'farmer_declarations',
            'markets':            'ghana_markets',
            'districts':          'ghana_districts',
        }

        counts: dict = {alias: 0 for alias in _TABLES}
        parts = [
            f"(SELECT COUNT(*) FROM {tbl}) AS {alias}"
            for alias, tbl in _TABLES.items()
            if tbl in existing
        ]
        if parts:
            row = db.execute(text(f"SELECT {', '.join(parts)}")).fetchone()
            if row:
                for k, v in row._mapping.items():
                    counts[k] = int(v or 0)

        last_run = []
        if 'ingestion_log' in existing:
            last_run = db.execute(text("""
                SELECT source, run_at, rows_clean, rows_quarantined, status
                FROM ingestion_log
                ORDER BY run_at DESC
                LIMIT 10
            """)).fetchall()

        return counts, last_run
