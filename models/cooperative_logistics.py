"""
Cooperative logistics engine for AgriMatch (M15).

Groups nearby active farmer declarations into shared truck runs
and computes per-farmer savings vs individual transport.
"""

import json
import logging
import uuid
from collections import Counter
from datetime import date, timedelta

from db.connection import get_session
from db.repositories.cooperative_logistics_repo import CooperativeLogisticsRepo
from utils.geo import haversine as _hav
from utils.math_utils import safe_float as _f

logger = logging.getLogger(__name__)

# ── Group-finding parameters ──────────────────────────────────────────────────
_MAX_DISTANCE_KM       = 50.0   # farmers further apart than this are not grouped
_HARVEST_WINDOW_DAYS   = 3      # max days between harvest dates within a group
_MIN_GROUP_SIZE        = 2      # minimum declarations to form a group
_DECLARATIONS_HORIZON  = 90     # days ahead to look for active declarations

# ── Vehicle selection thresholds ──────────────────────────────────────────────
# (max_kg_inclusive, vehicle_type) — ordered from smallest to largest
_VEHICLE_THRESHOLDS: list[tuple[float, str]] = [
    (1500.0, "pickup"),
    (8000.0, "medium_truck"),
]
_VEHICLE_LARGE = "large_truck"


def _vehicle_for(kg: float) -> str:
    for max_kg, vtype in _VEHICLE_THRESHOLDS:
        if kg <= max_kg:
            return vtype
    return _VEHICLE_LARGE


def _harvest_window_label(earliest: date, latest: date) -> str:
    if earliest == latest:
        return earliest.strftime("%B %d")
    if earliest.month == latest.month:
        return f"{earliest.strftime('%B %d')}-{latest.day}"
    return f"{earliest.strftime('%B %d')} - {latest.strftime('%B %d')}"


class CooperativeLogistics:

    def __init__(self):
        self._logistics   = None   # injected at startup via app.state
        self.xgb_predictor = None  # injected at startup (optional)

    # ── Market helpers ───────────────────────────────────────────────────────

    def _load_markets(self) -> list:
        with get_session() as db:
            return CooperativeLogisticsRepo.get_markets_with_coords(db)

    def _nearest_market(self, lat: float, lon: float, markets: list):
        """Return (canonical_name, district_id) of market nearest to (lat, lon)."""
        if not markets:
            return None, None
        nearest = min(
            markets,
            key=lambda m: _hav(lat, lon, _f(m.centroid_lat), _f(m.centroid_lon)),
        )
        return str(nearest.canonical_name), int(nearest.district_id)

    # ── Platform provider ────────────────────────────────────────────────────

    def _get_or_create_platform_provider(self) -> int | None:
        """Return provider_id for the system coordinator via atomic upsert."""
        with get_session() as db:
            return CooperativeLogisticsRepo.get_or_create_platform_provider(db)

    # ── Road distance (single pair, used for group→market leg) ───────────────

    def _road_km(self, d1: int, d2: int) -> float:
        if d1 == d2:
            return 0.0
        with get_session() as db:
            row = CooperativeLogisticsRepo.get_road_km(db, d1, d2)
        return _f(row.road_distance_km) if row else float("inf")

    # ── find_groups helpers ──────────────────────────────────────────────────

    def _load_declarations_in_window(self, today: date, window_to: date) -> list:
        with get_session() as db:
            return CooperativeLogisticsRepo.get_active_declarations_in_window(
                db, today, window_to
            )

    def _build_distance_map(self, district_ids: list) -> dict:
        """Fetch all pairwise road distances for the given district set."""
        if len(district_ids) <= 1:
            return {}
        with get_session() as db:
            dist_rows = CooperativeLogisticsRepo.get_distances_for_districts(
                db, district_ids
            )
        return {
            (int(d.from_district_id), int(d.to_district_id)): _f(d.road_distance_km)
            for d in dist_rows
        }

    def _cluster_declarations(
        self,
        rows: list,
        dist_map: dict,
        max_distance_km: float,
        harvest_window_days: int,
        min_group_size: int,
    ) -> list[list]:
        """Greedy clustering: group declarations that are close in space and time."""
        def road_km_fast(d1: int, d2: int) -> float:
            if d1 == d2:
                return 0.0
            return dist_map.get((d1, d2), dist_map.get((d2, d1), float("inf")))

        grouped: set = set()
        raw_groups: list = []

        for i, anchor in enumerate(rows):
            if int(anchor.id) in grouped:
                continue
            anchor_date = anchor.adjusted_harvest_date or anchor.harvest_date
            anchor_did  = int(anchor.district_id)

            companions = [
                other for j, other in enumerate(rows)
                if j != i
                and int(other.id) not in grouped
                and abs(((other.adjusted_harvest_date or other.harvest_date) - anchor_date).days) <= harvest_window_days
                and road_km_fast(anchor_did, int(other.district_id)) <= max_distance_km
            ]

            if len(companions) + 1 < min_group_size:
                continue

            members = [anchor] + companions
            grouped.update(int(r.id) for r in members)
            raw_groups.append(members)

        return raw_groups

    def _safe_delivery_cost(self, from_did: int, to_did: int, cargo_kg: float) -> float:
        """Return total delivery cost in GHS, or 0.0 if logistics engine unavailable."""
        if not self._logistics:
            return 0.0
        logi = self._logistics.get_delivery_cost(from_did, to_did, cargo_kg)
        return _f(logi["total_cost_ghs"]) if logi else 0.0

    def _build_farmer_entry(self, row, market_did: int, shared_cost: float) -> dict:
        ind_cost = self._safe_delivery_cost(
            int(row.district_id), market_did, float(row.quantity_kg)
        )
        return {
            "declaration_id":      int(row.id),
            "farmer_name":         str(row.farmer_name),
            "district":            str(row.district_name),
            "quantity_kg":         float(row.quantity_kg),
            "harvest_date":        str(row.adjusted_harvest_date or row.harvest_date),
            "individual_cost_ghs": round(ind_cost, 2),
            "shared_cost_ghs":     round(shared_cost, 2),
            "saving_ghs":          round(max(0.0, ind_cost - shared_cost), 2),
        }

    def _build_group_dict(self, members: list, markets: list) -> dict | None:
        """Assemble the full group representation from a cluster of declarations."""
        primary_crop = Counter(r.crop for r in members).most_common(1)[0][0]
        total_kg     = sum(float(r.quantity_kg) for r in members)
        vehicle_type = _vehicle_for(total_kg)

        lats = [_f(r.centroid_lat) for r in members if r.centroid_lat]
        lons = [_f(r.centroid_lon) for r in members if r.centroid_lon]
        if not lats:
            return None
        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)

        market_name, market_did = self._nearest_market(centroid_lat, centroid_lon, markets)
        if market_did is None:
            logger.warning("No linked market found for group centroid; skipping group")
            return None

        pickup_did = int(min(
            members,
            key=lambda r: (
                _hav(centroid_lat, centroid_lon, _f(r.centroid_lat), _f(r.centroid_lon))
                if r.centroid_lat else float("inf")
            ),
        ).district_id)

        est_km     = self._road_km(pickup_did, market_did)
        est_km     = 0.0 if est_km == float("inf") else est_km
        total_cost = self._safe_delivery_cost(pickup_did, market_did, total_kg)
        shared_cost = total_cost / len(members) if members else 0.0

        harvest_dates = [r.adjusted_harvest_date or r.harvest_date for r in members]
        earliest = min(harvest_dates)
        latest   = max(harvest_dates)

        return {
            "group_id":                str(uuid.uuid4()),
            "declarations":            [int(r.id) for r in members],
            "farmers":                 [self._build_farmer_entry(r, market_did, shared_cost) for r in members],
            "primary_crop":            primary_crop,
            "destination_market":      market_name,
            "destination_district_id": market_did,
            "pickup_district_id":      pickup_did,
            "total_cargo_kg":          round(total_kg, 1),
            "vehicle_type":            vehicle_type,
            "total_cost_ghs":          round(total_cost, 2),
            "estimated_distance_km":   round(est_km, 1),
            "proposed_departure_date": str(earliest - timedelta(days=1)),
            "group_harvest_window":    _harvest_window_label(earliest, latest),
        }

    # ── Method 1: find_groups ────────────────────────────────────────────────

    def find_groups(
        self,
        max_distance_km: float = _MAX_DISTANCE_KM,
        harvest_window_days: int = _HARVEST_WINDOW_DAYS,
        min_group_size: int = _MIN_GROUP_SIZE,
    ) -> list:
        """Group active declarations into shared truck runs."""
        today     = date.today()
        window_to = today + timedelta(days=_DECLARATIONS_HORIZON)

        rows = self._load_declarations_in_window(today, window_to)
        if not rows:
            return []

        district_ids = list({int(r.district_id) for r in rows})
        dist_map     = self._build_distance_map(district_ids)
        markets      = self._load_markets()
        raw_groups   = self._cluster_declarations(
            rows, dist_map, max_distance_km, harvest_window_days, min_group_size
        )

        result = []
        for members in raw_groups:
            group = self._build_group_dict(members, markets)
            if group:
                result.append(group)
        return result

    # ── Method 2: save_groups ────────────────────────────────────────────────

    def save_groups(self, groups: list) -> int:
        if not groups:
            return 0

        provider_id = self._get_or_create_platform_provider()
        if provider_id is None:
            logger.warning("No transport provider available - skipping save_groups")
            return 0

        count = 0
        for group in groups:
            dec_ids = group["declarations"]
            try:
                with get_session() as db:
                    farmer_rows = CooperativeLogisticsRepo.get_farmer_ids_for_declarations(
                        db, dec_ids
                    )
                    farmer_ids = [int(r.farmer_id) for r in farmer_rows]
                    CooperativeLogisticsRepo.insert_transport_job(
                        db, provider_id, group, dec_ids, farmer_ids
                    )
                count += 1
                logger.info(
                    "Saved transport_job for group %s (%d declarations)",
                    group["group_id"], len(dec_ids),
                )
            except Exception as exc:
                logger.error("Failed to save group %s: %s", group["group_id"], exc)

        return count

    # ── Method 3: run ────────────────────────────────────────────────────────

    def run(self) -> dict:
        """Find groups, save transport jobs, return summary."""
        groups = self.find_groups()
        if not groups:
            return {
                "groups_found":                  0,
                "jobs_created":                  0,
                "total_farmers_in_groups":        0,
                "total_cargo_kg":                0.0,
                "total_estimated_savings_ghs":   0.0,
                "average_saving_per_farmer_ghs": 0.0,
                "groups":                        [],
            }

        jobs_created    = self.save_groups(groups)
        total_farmers   = sum(len(g["farmers"]) for g in groups)
        total_cargo     = sum(g["total_cargo_kg"] for g in groups)
        total_savings   = sum(f["saving_ghs"] for g in groups for f in g["farmers"])
        avg_saving      = total_savings / total_farmers if total_farmers > 0 else 0.0

        return {
            "groups_found":                  len(groups),
            "jobs_created":                  jobs_created,
            "total_farmers_in_groups":        total_farmers,
            "total_cargo_kg":                round(total_cargo, 1),
            "total_estimated_savings_ghs":   round(total_savings, 2),
            "average_saving_per_farmer_ghs": round(avg_saving, 2),
            "groups": [
                {
                    "group_id":                g["group_id"],
                    "destination_market":      g["destination_market"],
                    "total_cargo_kg":          g["total_cargo_kg"],
                    "vehicle_type":            g["vehicle_type"],
                    "total_cost_ghs":          g["total_cost_ghs"],
                    "proposed_departure_date": g["proposed_departure_date"],
                    "group_harvest_window":    g["group_harvest_window"],
                    "farmer_count":            len(g["farmers"]),
                }
                for g in groups
            ],
        }

    # ── Method 4: get_farmer_logistics_options ───────────────────────────────

    def get_farmer_logistics_options(self, farmer_id: int) -> dict:
        """Return transport jobs containing any of this farmer's active declarations."""
        with get_session() as db:
            dec_rows = CooperativeLogisticsRepo.get_farmer_active_declaration_ids(db, farmer_id)

        dec_ids = [int(r.id) for r in dec_rows]
        if not dec_ids:
            return {"in_group": False, "transport_jobs": []}

        with get_session() as db:
            job_rows = CooperativeLogisticsRepo.get_transport_jobs_for_declarations(db, dec_ids)

        if not job_rows:
            return {"in_group": False, "transport_jobs": []}

        all_dec_ids_per_job: list[list[int]] = []
        for job in job_rows:
            raw_dec = job.declaration_ids
            if isinstance(raw_dec, str):
                parsed = json.loads(raw_dec)
            else:
                parsed = list(raw_dec) if raw_dec else []
            all_dec_ids_per_job.append([int(d) for d in parsed])

        job_results = []
        for job, all_dec_ids in zip(job_rows, all_dec_ids_per_job):
            dest_did    = int(job.delivery_district_id) if job.delivery_district_id else None
            group_size  = len(all_dec_ids) or 1
            total_cost  = _f(job.estimated_cost_ghs)
            shared_cost = round(total_cost / group_size, 2)

            my_dec_in_job = [d for d in dec_ids if d in all_dec_ids]
            other_dec_ids = [d for d in all_dec_ids if d not in my_dec_in_job]

            with get_session() as db:
                summary = CooperativeLogisticsRepo.get_job_summary(db, int(job.id), dest_did)

            market_name    = str(summary.market_name)  if summary and summary.market_name  else (f"District {dest_did}" if dest_did else None)
            job_status     = str(summary.status)        if summary                          else "pending"
            provider_name  = str(summary.provider_name) if summary and summary.provider_name else None
            provider_phone = str(summary.provider_phone) if summary and summary.provider_phone else None

            ind_cost = 0.0
            if my_dec_in_job and dest_did and self._logistics:
                with get_session() as db:
                    decl_rows = CooperativeLogisticsRepo.get_declarations_details(
                        db, my_dec_in_job
                    )
                for decl in decl_rows:
                    ind_cost += self._safe_delivery_cost(
                        int(decl.district_id), dest_did, float(decl.quantity_kg)
                    )

            saving = round(max(0.0, ind_cost - shared_cost), 2)

            co_farmers = []
            if other_dec_ids:
                with get_session() as db:
                    co_rows = CooperativeLogisticsRepo.get_co_farmers(db, other_dec_ids)
                co_farmers = [
                    {"name": str(r.full_name), "district": str(r.district_name)}
                    for r in co_rows
                ]

            job_results.append({
                "job_id":              int(job.id),
                "group_size":          group_size,
                "destination_market":  market_name,
                "departure_date":      str(job.scheduled_date) if job.scheduled_date else None,
                "individual_cost_ghs": round(ind_cost, 2),
                "shared_cost_ghs":     shared_cost,
                "saving_ghs":          saving,
                "co_farmers":          co_farmers,
                "status":              job_status,
                "provider_name":       provider_name,
                "provider_phone":      provider_phone,
            })

        return {
            "farmer_id":      farmer_id,
            "in_group":       True,
            "transport_jobs": job_results,
        }
