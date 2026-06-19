"""
Alert engine for AgriMatch (M17).

Generates and sends SMS alerts to farmers via Africa's Talking.
Supports dry_run=True for safe testing without real SMS delivery.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from config.settings import AT_API_KEY, AT_SENDER_ID, AT_USERNAME
from db.connection import get_session

logger = logging.getLogger(__name__)


class AlertEngine:

    def __init__(self, dry_run: bool = False):
        self.dry_run  = dry_run
        self._at_sms  = None   # lazy-init Africa's Talking SMS service
        self._sg      = None   # lazy-init StrategyGenerator
        self._ensure_table()

    # ── Table bootstrap ──────────────────────────────────────────────────────

    def _ensure_table(self) -> None:
        """Create alerts_log if it does not already exist."""
        from db.connection import get_engine
        from db.models import AlertLog, Base
        Base.metadata.create_all(
            get_engine(), tables=[AlertLog.__table__], checkfirst=True
        )

    # ── Lazy initializers ────────────────────────────────────────────────────

    def _get_at_sms(self):
        if self._at_sms is None:
            if not AT_API_KEY:
                logger.warning("AT_API_KEY not set -- SMS delivery disabled")
                return None
            try:
                import africastalking
                africastalking.initialize(AT_USERNAME, AT_API_KEY)
                self._at_sms = africastalking.SMS
            except ImportError:
                logger.error("africastalking SDK not installed")
        return self._at_sms

    def _get_strategy(self):
        if self._sg is None:
            from models.lstm_predictor import LSTMPredictor
            from models.strategy_generator import StrategyGenerator
            from models.xgboost_predictor import XGBoostPredictor
            xgb = XGBoostPredictor()
            xgb.load_models()
            lstm = LSTMPredictor()
            lstm.load_models()
            sg = StrategyGenerator()
            sg.xgb_predictor  = xgb
            sg.lstm_predictor = lstm
            self._sg = sg
        return self._sg

    # ── Dedup helpers ────────────────────────────────────────────────────────

    def _already_alerted(
        self, declaration_id: int, alert_type: str, within_hours: int = 168
    ) -> bool:
        """True if a 'sent' alert of this type exists for this declaration within the window."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        with get_session() as db:
            row = db.execute(
                text("""
                    SELECT id FROM alerts_log
                    WHERE declaration_id = :did
                      AND alert_type     = :atype
                      AND status         = 'sent'
                      AND sent_at        >= :cutoff
                    LIMIT 1
                """),
                {"did": declaration_id, "atype": alert_type, "cutoff": cutoff},
            ).fetchone()
        return row is not None

    def _already_alerted_today(self, declaration_id: int, alert_type: str) -> bool:
        """True if a 'sent' alert of this type exists for this declaration today."""
        today = date.today()
        with get_session() as db:
            row = db.execute(
                text("""
                    SELECT id FROM alerts_log
                    WHERE declaration_id = :did
                      AND alert_type     = :atype
                      AND status         = 'sent'
                      AND sent_at::date  = :today
                    LIMIT 1
                """),
                {"did": declaration_id, "atype": alert_type, "today": today},
            ).fetchone()
        return row is not None

    # ── Logging helper ───────────────────────────────────────────────────────

    def _log_alert(
        self,
        phone_number: str,
        message: str,
        alert_type: str,
        status: str,
        farmer_id: Optional[int] = None,
        declaration_id: Optional[int] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        with get_session() as db:
            db.execute(
                text("""
                    INSERT INTO alerts_log
                        (farmer_id, declaration_id, phone_number,
                         alert_type, message, status, error_detail)
                    VALUES
                        (:fid, :did, :phone, :atype, :msg, :status, :err)
                """),
                {
                    "fid":    farmer_id,
                    "did":    declaration_id,
                    "phone":  phone_number,
                    "atype":  alert_type,
                    "msg":    message,
                    "status": status,
                    "err":    error_detail,
                },
            )

    # ── Method 1: send_sms ───────────────────────────────────────────────────

    def send_sms(
        self,
        phone_number: str,
        message: str,
        alert_type: str,
        farmer_id: Optional[int] = None,
        declaration_id: Optional[int] = None,
    ) -> bool:
        """Send an SMS and log the result. Returns True on success (or dry_run)."""
        message = message[:160]

        if self.dry_run:
            print(
                f"[DRY RUN] To: {phone_number}  Type: {alert_type}\n"
                f"          Msg: {message}",
                flush=True,
            )
            self._log_alert(phone_number, message, alert_type, "skipped",
                            farmer_id, declaration_id)
            return True

        at_sms = self._get_at_sms()
        if at_sms is None:
            self._log_alert(phone_number, message, alert_type, "failed",
                            farmer_id, declaration_id, "AT SDK unavailable")
            return False

        try:
            phone = phone_number if phone_number.startswith("+") else f"+{phone_number}"
            response  = at_sms.send(message, [phone], sender_id=AT_SENDER_ID)
            recipient = (
                response.get("SMSMessageData", {})
                        .get("Recipients", [{}])[0]
            )
            at_status = recipient.get("status", "Unknown")
            if at_status == "Success":
                self._log_alert(phone_number, message, alert_type, "sent",
                                farmer_id, declaration_id)
                logger.info("SMS sent to %s [%s]", phone_number, alert_type)
                return True
            else:
                err = f"AT status: {at_status}"
                self._log_alert(phone_number, message, alert_type, "failed",
                                farmer_id, declaration_id, err)
                logger.warning("SMS failed for %s: %s", phone_number, err)
                return False
        except Exception as exc:
            logger.exception("SMS exception for %s", phone_number)
            self._log_alert(phone_number, message, alert_type, "failed",
                            farmer_id, declaration_id, str(exc))
            return False

    # ── Method 2: check_price_alerts ─────────────────────────────────────────

    def _get_delay_days(self, declaration_id: int) -> int:
        """Harvest delay days from the most recent climate indicator for the declaration's district."""
        with get_session() as db:
            row = db.execute(
                text("""
                    SELECT ci.harvest_delay_days
                    FROM climate_indicators ci
                    JOIN farmer_declarations fd ON fd.district_id = ci.district_id
                    WHERE fd.id = :did
                    ORDER BY ci.indicator_date DESC
                    LIMIT 1
                """),
                {"did": declaration_id},
            ).fetchone()
        return int(row.harvest_delay_days) if (row and row.harvest_delay_days) else 0

    def check_price_alerts(self) -> int:
        """Send sell-timing alerts using M13 sell strategy urgency."""
        sg = self._get_strategy()

        with get_session() as db:
            decls = db.execute(
                text("""
                    SELECT fd.id, fd.farmer_id, fd.crop,
                           fd.harvest_date, fd.adjusted_harvest_date,
                           fd.csi_flag,
                           f.phone_number
                    FROM farmer_declarations fd
                    JOIN farmers f ON f.id = fd.farmer_id
                    WHERE fd.status = 'active'
                    ORDER BY fd.id
                """)
            ).fetchall()

        sent = 0
        for decl in decls:
            if self._already_alerted(int(decl.id), "price", within_hours=168):
                continue

            strategy = sg.farmer_sell_strategy(int(decl.id))
            if strategy is None:
                continue

            urgency = strategy.get("urgency")
            csi     = strategy.get("csi_flag", "normal")
            nums    = strategy.get("numbers", {})

            target_date = decl.adjusted_harvest_date or decl.harvest_date
            price       = nums.get("current_price_ghs", 0.0)
            pct         = abs(nums.get("price_change_pct", 0.0))

            if urgency == "sell_now":
                msg = (
                    f"AgriMatch: Your {decl.crop} price drops {pct:.1f}%"
                    f" in 7 days. Sell by {target_date}"
                    f" for GHS {price:.2f}/kg. Dial *384# for details."
                )[:160]
            elif urgency == "sell_soon" and csi in ("warning", "critical"):
                delay = self._get_delay_days(int(decl.id))
                msg = (
                    f"AgriMatch: Climate warning in your district."
                    f" Harvest delay of {delay} days expected for your"
                    f" {decl.crop}. Sell before {target_date}."
                )[:160]
            else:
                continue

            ok = self.send_sms(
                str(decl.phone_number), msg, "price",
                farmer_id=int(decl.farmer_id), declaration_id=int(decl.id),
            )
            if ok:
                sent += 1

        return sent

    # ── Method 3: check_csi_alerts ───────────────────────────────────────────

    def check_csi_alerts(self) -> int:
        """Send climate-flag alerts for declarations with warning or critical CSI."""
        with get_session() as db:
            decls = db.execute(
                text("""
                    SELECT fd.id, fd.farmer_id, fd.crop, fd.csi_flag,
                           fd.adjusted_harvest_date, fd.harvest_date,
                           gd.district_name,
                           f.phone_number
                    FROM farmer_declarations fd
                    JOIN farmers f          ON f.id  = fd.farmer_id
                    JOIN ghana_districts gd ON gd.id = fd.district_id
                    WHERE fd.status   = 'active'
                      AND fd.csi_flag IN ('warning', 'critical')
                    ORDER BY fd.id
                """)
            ).fetchall()

        sent = 0
        for decl in decls:
            if self._already_alerted(int(decl.id), "csi", within_hours=24):
                continue

            delay    = self._get_delay_days(int(decl.id))
            new_date = decl.adjusted_harvest_date or decl.harvest_date

            msg = (
                f"AgriMatch: {decl.csi_flag} weather alert for"
                f" {decl.district_name}. Your {decl.crop} harvest"
                f" may delay {delay} days to {new_date}."
                f" Dial *384# for options."
            )[:160]

            ok = self.send_sms(
                str(decl.phone_number), msg, "csi",
                farmer_id=int(decl.farmer_id), declaration_id=int(decl.id),
            )
            if ok:
                sent += 1

        return sent

    # ── Method 4: check_logistics_alerts ─────────────────────────────────────

    def check_logistics_alerts(self) -> int:
        """Send truck-sharing alerts for each new cooperative group.

        group["farmers"] is a list of dicts from find_groups(), each with
        declaration_id, farmer_name, saving_ghs, shared_cost_ghs, etc.
        """
        from models.cooperative_logistics import CooperativeLogistics
        groups = CooperativeLogistics().find_groups()

        sent = 0
        for group in groups:
            dec_ids      = group.get("declarations", [])
            farmers_data = group.get("farmers", [])
            if not dec_ids or not farmers_data:
                continue

            # Skip if any declaration in the group was already notified in last 24h
            if any(
                self._already_alerted(did, "logistics", within_hours=24)
                for did in dec_ids
            ):
                continue

            # Look up phone numbers for all declarations in the group at once
            with get_session() as db:
                phone_rows = db.execute(
                    text("""
                        SELECT fd.id AS declaration_id,
                               f.id AS farmer_id,
                               f.phone_number
                        FROM farmer_declarations fd
                        JOIN farmers f ON f.id = fd.farmer_id
                        WHERE fd.id = ANY(:dids)
                    """),
                    {"dids": dec_ids},
                ).fetchall()
            phone_map = {
                int(r.declaration_id): (int(r.farmer_id), str(r.phone_number))
                for r in phone_rows
            }

            n      = len(farmers_data)
            market = group.get("destination_market", "market")
            depart = str(group.get("proposed_departure_date", ""))[:10]

            try:
                from datetime import datetime as _dt
                date_str = _dt.strptime(depart, "%Y-%m-%d").strftime("%b %d")
            except Exception:
                date_str = depart

            for fdata in farmers_data:
                fdec_id = fdata.get("declaration_id")
                if fdec_id is None:
                    continue
                farmer_info = phone_map.get(int(fdec_id))
                if not farmer_info:
                    continue
                farmer_id, phone = farmer_info
                saving = round(fdata.get("saving_ghs", 0.0))

                msg = (
                    f"AgriMatch: Save GHS {saving} on transport!"
                    f" {n} farms near you going to {market}"
                    f" around {date_str}. Dial *384# to confirm."
                )[:160]

                ok = self.send_sms(
                    phone, msg, "logistics",
                    farmer_id=farmer_id,
                    declaration_id=int(fdec_id),
                )
                if ok:
                    sent += 1

        return sent

    # ── Method 5: check_byproduct_alerts ─────────────────────────────────────

    def check_byproduct_alerts(self) -> int:
        """Send urgency alerts for farmers with perishable byproducts due in <= 3 days."""
        today  = date.today()
        window = today + timedelta(days=3)

        with get_session() as db:
            rows = db.execute(
                text("""
                    SELECT bd.id            AS bp_id,
                           bd.declaration_id,
                           bd.byproduct_type,
                           bd.available_date,
                           fd.farmer_id,
                           fd.crop,
                           f.phone_number
                    FROM byproduct_declarations bd
                    JOIN farmer_declarations fd ON fd.id = bd.declaration_id
                    JOIN farmers f             ON f.id  = fd.farmer_id
                    WHERE bd.is_perishable = true
                      AND bd.status        = 'active'
                      AND fd.status        = 'active'
                      AND bd.available_date BETWEEN :today AND :window
                    ORDER BY bd.available_date ASC
                """),
                {"today": today, "window": window},
            ).fetchall()

        sent = 0
        for row in rows:
            if self._already_alerted_today(int(row.declaration_id), "byproduct"):
                continue

            msg = (
                f"AgriMatch: Your {row.byproduct_type} from {row.crop}"
                f" available {row.available_date} - perishable."
                f" Buyers nearby. Dial *384# to check."
            )[:160]

            ok = self.send_sms(
                str(row.phone_number), msg, "byproduct",
                farmer_id=int(row.farmer_id),
                declaration_id=int(row.declaration_id),
            )
            if ok:
                sent += 1

        return sent

    # ── Method 6: run_all_checks ─────────────────────────────────────────────

    def run_all_checks(self) -> dict:
        """Run all four alert checks and return a summary."""
        price_sent = self.check_price_alerts()
        csi_sent   = self.check_csi_alerts()
        logi_sent  = self.check_logistics_alerts()
        bp_sent    = self.check_byproduct_alerts()

        # Count failures logged in the last 10 minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        with get_session() as db:
            fail_row = db.execute(
                text("""
                    SELECT COUNT(*) AS cnt FROM alerts_log
                    WHERE status = 'failed' AND sent_at >= :cutoff
                """),
                {"cutoff": cutoff},
            ).fetchone()
        total_failed = int(fail_row.cnt) if fail_row else 0

        total_sent = price_sent + csi_sent + logi_sent + bp_sent

        summary = {
            "price_alerts_sent":     price_sent,
            "csi_alerts_sent":       csi_sent,
            "logistics_alerts_sent": logi_sent,
            "byproduct_alerts_sent": bp_sent,
            "total_sent":            total_sent,
            "total_failed":          total_failed,
        }
        logger.info("Alert run complete: %s", summary)
        return summary
