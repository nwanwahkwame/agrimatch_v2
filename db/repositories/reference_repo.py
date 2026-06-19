from sqlalchemy import text
from sqlalchemy.orm import Session


class ReferenceRepo:

    @staticmethod
    def get_crops(db: Session):
        return db.execute(text("""
            SELECT id, internal_name, is_byproduct_source
            FROM crop_reference
            ORDER BY internal_name
        """)).fetchall()

    @staticmethod
    def get_regions(db: Session):
        return db.execute(text("""
            SELECT
                m.region,
                COUNT(DISTINCT m.id)  AS market_count,
                COUNT(DISTINCT d.id)  AS district_count
            FROM ghana_markets    m
            LEFT JOIN ghana_districts d ON d.region_name = m.region
            GROUP BY m.region
            ORDER BY market_count DESC
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
    def get_model_accuracy(db: Session):
        return db.execute(text("""
            SELECT
                market,
                model_type,
                ROUND(CAST((1 - COALESCE(mape_30d, 0.05)) * 100 AS numeric), 1) AS accuracy_pct,
                ROUND(CAST(mae_30d AS numeric), 4) AS mae,
                training_rows
            FROM model_baselines
            WHERE mape_30d IS NOT NULL
              AND market IS NOT NULL
            ORDER BY market, model_type
        """)).fetchall()
