from sqlalchemy import text
from sqlalchemy.orm import Session


class UssdRepo:

    @staticmethod
    def get_stats(db: Session, today_start, week_start, active_cutoff) -> dict:
        total_today = db.execute(
            text("SELECT COUNT(*) FROM ussd_sessions WHERE created_at >= :ts"),
            {"ts": today_start},
        ).scalar() or 0

        total_week = db.execute(
            text("SELECT COUNT(*) FROM ussd_sessions WHERE created_at >= :ts"),
            {"ts": week_start},
        ).scalar() or 0

        completed_via_ussd = db.execute(
            text("SELECT COUNT(*) FROM farmer_declarations WHERE source = 'ussd'"),
        ).scalar() or 0

        avg_secs_raw = db.execute(text("""
            SELECT AVG(EXTRACT(EPOCH FROM (last_activity - created_at)))
            FROM ussd_sessions
            WHERE last_activity > created_at
        """)).scalar()
        avg_secs = round(float(avg_secs_raw), 1) if avg_secs_raw else 0.0

        drop_row = db.execute(text("""
            SELECT menu_state, COUNT(*) AS cnt
            FROM ussd_sessions
            WHERE menu_state NOT IN ('main_menu', 'done', 'welcome')
            GROUP BY menu_state
            ORDER BY cnt DESC
            LIMIT 1
        """)).fetchone()
        most_common_drop_off = drop_row[0] if drop_row else "none"

        active_now = db.execute(
            text("SELECT COUNT(*) FROM ussd_sessions WHERE last_activity >= :ts"),
            {"ts": active_cutoff},
        ).scalar() or 0

        return {
            "total_sessions_today":            int(total_today),
            "total_sessions_week":             int(total_week),
            "completed_declarations_via_ussd": int(completed_via_ussd),
            "avg_session_duration_seconds":    avg_secs,
            "most_common_drop_off_state":      most_common_drop_off,
            "active_sessions_now":             int(active_now),
        }
