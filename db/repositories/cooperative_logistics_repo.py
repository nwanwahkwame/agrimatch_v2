import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CooperativeLogisticsRepo:

    @staticmethod
    def get_markets_with_coords(db: Session):
        return db.execute(text("""
            SELECT gm.canonical_name, gm.district_id,
                   gd.centroid_lat, gd.centroid_lon
            FROM ghana_markets gm
            JOIN ghana_districts gd ON gd.id = gm.district_id
            WHERE gm.district_id IS NOT NULL
              AND gd.centroid_lat IS NOT NULL
        """)).fetchall()

    @staticmethod
    def get_or_create_platform_provider(db: Session) -> Optional[int]:
        try:
            result = db.execute(text("""
                INSERT INTO transport_providers
                    (full_name, phone_number, truck_capacity_kg,
                     vehicle_type, is_available, is_active)
                VALUES
                    ('Platform Coordinator', 'system-platform', 20000,
                     'large_truck', true, true)
                ON CONFLICT (phone_number) DO UPDATE
                    SET full_name = EXCLUDED.full_name
                RETURNING id
            """))
            row = result.fetchone()
            return int(row.id) if row else None
        except Exception as exc:
            logger.error("Could not create platform provider: %s", exc)
            return None

    @staticmethod
    def get_road_km(db: Session, from_district: int, to_district: int):
        return db.execute(text("""
            SELECT road_distance_km FROM district_distances
            WHERE from_district_id = :f AND to_district_id = :t LIMIT 1
        """), {"f": from_district, "t": to_district}).fetchone()

    @staticmethod
    def get_active_declarations_in_window(db: Session, today: date, window_to: date):
        return db.execute(text("""
            SELECT fd.id, fd.farmer_id, fd.crop, fd.quantity_kg, fd.district_id,
                   fd.harvest_date, fd.adjusted_harvest_date,
                   f.full_name AS farmer_name,
                   gd.district_name, gd.centroid_lat, gd.centroid_lon
            FROM farmer_declarations fd
            JOIN farmers f ON f.id = fd.farmer_id
            JOIN ghana_districts gd ON gd.id = fd.district_id
            WHERE fd.status = 'active'
              AND fd.harvest_date BETWEEN :hfrom AND :hto
            ORDER BY fd.harvest_date ASC
        """), {"hfrom": today, "hto": window_to}).fetchall()

    @staticmethod
    def get_distances_for_districts(db: Session, district_ids: list):
        return db.execute(text("""
            SELECT from_district_id, to_district_id, road_distance_km
            FROM district_distances
            WHERE from_district_id = ANY(:ids)
              AND to_district_id   = ANY(:ids)
        """), {"ids": district_ids}).fetchall()

    @staticmethod
    def get_farmer_active_declaration_ids(db: Session, farmer_id: int):
        return db.execute(text("""
            SELECT id FROM farmer_declarations
            WHERE farmer_id = :fid AND status = 'active'
        """), {"fid": farmer_id}).fetchall()

    @staticmethod
    def get_transport_jobs_for_declarations(db: Session, dec_ids: list):
        return db.execute(text("""
            SELECT DISTINCT tj.id, tj.pickup_district_id, tj.delivery_district_id,
                   tj.scheduled_date, tj.total_cargo_kg,
                   tj.declaration_ids, tj.estimated_cost_ghs
            FROM transport_jobs tj,
                 jsonb_array_elements(tj.declaration_ids) elem
            WHERE (elem #>> '{}')::bigint = ANY(:ids)
            ORDER BY tj.id DESC
        """), {"ids": dec_ids}).fetchall()

    @staticmethod
    def get_job_summary(db: Session, job_id: int, dest_district_id: Optional[int]):
        """Return market name, status, and non-platform provider in one query."""
        return db.execute(text("""
            SELECT
                tj.status,
                m.canonical_name          AS market_name,
                tp.full_name              AS provider_name,
                tp.phone_number           AS provider_phone
            FROM transport_jobs tj
            LEFT JOIN ghana_markets m
                   ON m.district_id = :dest_did
            LEFT JOIN transport_providers tp
                   ON tp.id = tj.provider_id
                  AND tp.phone_number != 'system-platform'
            WHERE tj.id = :jid
            LIMIT 1
        """), {"jid": job_id, "dest_did": dest_district_id}).fetchone()

    @staticmethod
    def get_declarations_details(db: Session, dec_ids: list):
        """Batch fetch district_id and quantity_kg for individual cost calculation."""
        return db.execute(text("""
            SELECT id, district_id, quantity_kg
            FROM farmer_declarations
            WHERE id = ANY(:ids)
        """), {"ids": dec_ids}).fetchall()

    @staticmethod
    def get_co_farmers(db: Session, dec_ids: list):
        return db.execute(text("""
            SELECT f.full_name, gd.district_name
            FROM farmer_declarations fd
            JOIN farmers f ON f.id = fd.farmer_id
            JOIN ghana_districts gd ON gd.id = fd.district_id
            WHERE fd.id = ANY(:ids)
        """), {"ids": dec_ids}).fetchall()

    @staticmethod
    def get_farmer_ids_for_declarations(db: Session, dec_ids: list):
        return db.execute(text("""
            SELECT DISTINCT farmer_id FROM farmer_declarations
            WHERE id = ANY(:ids)
        """), {"ids": dec_ids}).fetchall()

    @staticmethod
    def insert_transport_job(
        db: Session,
        provider_id: int,
        group: dict,
        dec_ids: list,
        farmer_ids: list,
    ) -> None:
        db.execute(text("""
            INSERT INTO transport_jobs (
                provider_id, status,
                pickup_district_id, delivery_district_id,
                scheduled_date, total_cargo_kg,
                declaration_ids, farmer_ids,
                estimated_distance_km, estimated_cost_ghs
            ) VALUES (
                :provider_id, 'pending',
                :pickup_did, :dest_did,
                :sched_date, :cargo_kg,
                CAST(:dec_ids AS jsonb), CAST(:far_ids AS jsonb),
                :dist_km, :cost_ghs
            )
        """), {
            "provider_id": provider_id,
            "pickup_did":  group["pickup_district_id"],
            "dest_did":    group["destination_district_id"],
            "sched_date":  group["proposed_departure_date"],
            "cargo_kg":    group["total_cargo_kg"],
            "dec_ids":     json.dumps(dec_ids),
            "far_ids":     json.dumps(farmer_ids),
            "dist_km":     group["estimated_distance_km"],
            "cost_ghs":    group["total_cost_ghs"],
        })
