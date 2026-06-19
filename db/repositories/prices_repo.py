from sqlalchemy import text
from sqlalchemy.orm import Session

# mkt_clause is one of two hardcoded strings — not user-interpolated, injection-safe
_MKT_CLAUSE     = "AND market = :market"
_MKT_CLAUSE_ALL = ""


class PricesRepo:

    @staticmethod
    def get_price_history(db: Session, crop: str, start_date: str, market: str = "") -> list:
        params: dict = {"crop": crop, "start_date": start_date}
        mkt_clause = _MKT_CLAUSE if market else _MKT_CLAUSE_ALL
        if market:
            params["market"] = market

        rows = db.execute(text(f"""
            SELECT
                DATE_TRUNC('month', price_date)::date AS month,
                market,
                ROUND(AVG(price_ghs)::numeric, 2)    AS avg_price,
                ROUND(MIN(price_ghs)::numeric, 2)    AS min_price,
                ROUND(MAX(price_ghs)::numeric, 2)    AS max_price,
                COUNT(*)                              AS data_points
            FROM clean_prices
            WHERE crop       = :crop
              AND price_date >= :start_date
              {mkt_clause}
            GROUP BY month, market
            ORDER BY month ASC, market
        """), params).fetchall()

        return [
            {
                "month":       str(r.month),
                "market":      r.market,
                "avg_price":   float(r.avg_price  or 0),
                "min_price":   float(r.min_price  or 0),
                "max_price":   float(r.max_price  or 0),
                "data_points": int(r.data_points  or 0),
            }
            for r in rows
        ]

    @staticmethod
    def get_markets_for_crop(db: Session, crop: str) -> list:
        rows = db.execute(text("""
            SELECT DISTINCT market FROM clean_prices
            WHERE crop = :crop ORDER BY market
        """), {"crop": crop}).fetchall()
        return [r.market for r in rows]

    @staticmethod
    def get_bulletin(db: Session) -> list:
        rows = db.execute(text("""
            WITH latest AS (
                SELECT DISTINCT ON (crop, market)
                    crop, market, region, price_ghs, price_date
                FROM clean_prices
                ORDER BY crop, market, price_date DESC
            ),
            prev AS (
                SELECT DISTINCT ON (crop, market)
                    crop, market, price_ghs AS price_30d
                FROM clean_prices
                WHERE price_date <= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY crop, market, price_date DESC
            )
            SELECT l.crop, l.market, l.region,
                   l.price_ghs  AS latest_price,
                   l.price_date AS latest_date,
                   p.price_30d
            FROM latest l
            LEFT JOIN prev p ON p.crop = l.crop AND p.market = l.market
            ORDER BY l.crop, l.market
        """)).fetchall()

        return [
            {
                "crop":          r.crop,
                "market":        r.market,
                "region":        r.region,
                "latest_price":  float(r.latest_price or 0),
                "latest_date":   str(r.latest_date),
                "price_30d_ago": float(r.price_30d) if r.price_30d else None,
                "change_pct":    round(
                    ((float(r.latest_price) - float(r.price_30d)) / float(r.price_30d)) * 100, 1
                ) if r.price_30d and float(r.price_30d) > 0 else None,
            }
            for r in rows
        ]
