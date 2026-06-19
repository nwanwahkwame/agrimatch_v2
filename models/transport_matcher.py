"""
Transport provider matching for AgriMatch.

Runs after cooperative_logistics groups declarations into transport_jobs.
Each pending job (currently held by the system-platform placeholder) is
matched to the best available real provider using four sub-scores:

  distance   40%  road km from provider's base district to pickup district
  capacity   30%  how well truck size fits the cargo (penalises over/under)
  rating     20%  provider star rating (0-5)
  cost       10%  lower base_rate_per_km is better

A job is skipped if no eligible provider exists; it stays 'pending' and
will be retried on the next nightly run.
"""

import logging
from typing import Optional

from sqlalchemy import text

from db.connection import get_session

logger = logging.getLogger(__name__)

_VEHICLE_CAPACITY_KG = {
    "pickup":       1_500.0,
    "mini_van":     2_000.0,
    "medium_truck": 8_000.0,
    "large_truck":  30_000.0,
}


def _f(v) -> float:
    try:
        val = float(v)
        return 0.0 if (val != val) else val
    except (TypeError, ValueError):
        return 0.0


def _road_km(from_did: int, to_did: int) -> float:
    if from_did == to_did:
        return 0.0
    with get_session() as db:
        row = db.execute(text("""
            SELECT road_distance_km FROM district_distances
            WHERE from_district_id = :f AND to_district_id = :t LIMIT 1
        """), {"f": from_did, "t": to_did}).fetchone()
    return _f(row.road_distance_km) if row else 500.0


def _score_provider(
    provider,
    cargo_kg: float,
    pickup_district_id: int,
    dist_km_cache: dict,
) -> float:
    """Return a composite match score in [0, 1]."""
    prov_did = int(provider.district_id) if provider.district_id else 0
    cache_key = (prov_did, pickup_district_id)
    if cache_key not in dist_km_cache:
        dist_km_cache[cache_key] = _road_km(prov_did, pickup_district_id)
    km = dist_km_cache[cache_key]

    # 1. Distance score — closer is better, 0 km = 1.0, 500+ km = 0.0
    distance_score = max(0.0, 1.0 - km / 500.0)

    # 2. Capacity fit — want total fleet capacity >= cargo, but not 3x over
    fleet_kg = _f(provider.truck_capacity_kg) * max(1, int(provider.truck_count or 1))
    if fleet_kg == 0 or fleet_kg < cargo_kg:
        return 0.0   # cannot carry the load — disqualified
    over_ratio = fleet_kg / cargo_kg   # 1.0 = perfect fit, 3.0 = triple capacity
    capacity_score = max(0.0, 1.0 - (over_ratio - 1.0) / 4.0)

    # 3. Rating score (0-5 scale -> 0-1)
    rating_score = min(1.0, _f(provider.rating) / 5.0)

    # 4. Cost score — lower rate is better; cap at 10 GHS/km
    rate = _f(provider.base_rate_per_km) if provider.base_rate_per_km else 3.0
    cost_score = max(0.0, 1.0 - rate / 10.0)

    return round(
        0.40 * distance_score
        + 0.30 * capacity_score
        + 0.20 * rating_score
        + 0.10 * cost_score,
        4,
    )


def match_pending_jobs() -> dict:
    """
    Match each pending transport job to the best available real provider.

    Returns a summary dict with keys:
      jobs_examined, jobs_matched, jobs_unmatched, assignments
    """
    # 1. Get the system placeholder provider id
    with get_session() as db:
        sys_row = db.execute(text("""
            SELECT id FROM transport_providers
            WHERE phone_number = 'system-platform' LIMIT 1
        """)).fetchone()
    platform_id = int(sys_row.id) if sys_row else None

    # 2. Load all pending jobs (assigned to system placeholder or no provider)
    with get_session() as db:
        job_rows = db.execute(text("""
            SELECT tj.id, tj.pickup_district_id, tj.delivery_district_id,
                   tj.total_cargo_kg, tj.scheduled_date, tj.estimated_distance_km,
                   tj.estimated_cost_ghs,
                   gd.region_name AS pickup_region
            FROM transport_jobs tj
            LEFT JOIN ghana_districts gd ON gd.id = tj.pickup_district_id
            WHERE tj.status = 'pending'
              AND (
                  tj.provider_id IS NULL
                  OR tj.provider_id = :platform_id
              )
            ORDER BY tj.scheduled_date ASC
        """), {"platform_id": platform_id}).fetchall()

    if not job_rows:
        logger.info("Transport matching: no pending jobs found")
        return {
            "jobs_examined": 0,
            "jobs_matched": 0,
            "jobs_unmatched": 0,
            "assignments": [],
        }

    # 3. Load all eligible real providers
    with get_session() as db:
        provider_rows = db.execute(text("""
            SELECT id, full_name, phone_number, district_id,
                   truck_capacity_kg, truck_count, vehicle_type,
                   base_rate_per_km, rating, service_regions
            FROM transport_providers
            WHERE is_available = true
              AND is_active    = true
              AND phone_number != 'system-platform'
        """)).fetchall()

    if not provider_rows:
        logger.info("Transport matching: no real providers available")
        return {
            "jobs_examined": len(job_rows),
            "jobs_matched": 0,
            "jobs_unmatched": len(job_rows),
            "assignments": [],
        }

    dist_km_cache: dict = {}
    matched = 0
    unmatched = 0
    assignments = []

    for job in job_rows:
        cargo_kg      = _f(job.total_cargo_kg)
        pickup_did    = int(job.pickup_district_id) if job.pickup_district_id else 0
        pickup_region = str(job.pickup_region or "")

        # Filter providers that cover this region (empty service_regions = covers all)
        eligible = []
        for p in provider_rows:
            regions = p.service_regions
            if regions:
                # service_regions stored as jsonb list of strings
                if isinstance(regions, str):
                    import json
                    regions = json.loads(regions)
                if regions and pickup_region and pickup_region not in regions:
                    continue
            eligible.append(p)

        if not eligible:
            logger.info("Job %d: no providers cover region '%s'", job.id, pickup_region)
            unmatched += 1
            continue

        # Score all eligible providers
        scored = []
        for p in eligible:
            s = _score_provider(p, cargo_kg, pickup_did, dist_km_cache)
            if s > 0:
                scored.append((s, p))

        if not scored:
            logger.info("Job %d: all providers disqualified (capacity/distance)", job.id)
            unmatched += 1
            continue

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_provider = scored[0]

        # 4. Assign provider and update job status
        try:
            with get_session() as db:
                db.execute(text("""
                    UPDATE transport_jobs
                    SET provider_id = :pid,
                        status      = 'assigned'
                    WHERE id = :jid
                """), {"pid": int(best_provider.id), "jid": int(job.id)})
            matched += 1
            assignments.append({
                "job_id":           int(job.id),
                "provider_id":      int(best_provider.id),
                "provider_name":    str(best_provider.full_name),
                "provider_phone":   str(best_provider.phone_number),
                "match_score":      best_score,
                "pickup_region":    pickup_region,
                "cargo_kg":         cargo_kg,
                "scheduled_date":   str(job.scheduled_date) if job.scheduled_date else None,
            })
            logger.info(
                "Job %d assigned to provider %d (%s) — score %.3f",
                job.id, best_provider.id, best_provider.full_name, best_score,
            )
        except Exception as exc:
            logger.error("Failed to assign job %d: %s", job.id, exc)
            unmatched += 1

    return {
        "jobs_examined": len(job_rows),
        "jobs_matched":  matched,
        "jobs_unmatched": unmatched,
        "assignments":   assignments,
    }
