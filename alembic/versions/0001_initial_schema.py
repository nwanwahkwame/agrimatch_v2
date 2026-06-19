"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-17

NOTE: This migration captures the schema that already exists in production.
For an existing deployment run:
    alembic stamp head
to mark it as applied without re-running DDL.
For a fresh deployment run:
    alembic upgrade head
to create all tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ghana_districts",
        sa.Column("id",            sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("district_code", sa.Text()),
        sa.Column("district_name", sa.Text()),
        sa.Column("region_name",   sa.Text()),
        sa.Column("variant_names", sa.Text()),
        sa.Column("district_type", sa.Text()),
        sa.Column("hasc_code",     sa.Text()),
        sa.Column("centroid_lat",  sa.Numeric(10, 6)),
        sa.Column("centroid_lon",  sa.Numeric(10, 6)),
    )

    op.create_table(
        "crop_reference",
        sa.Column("id",                  sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("internal_name",       sa.Text()),
        sa.Column("hdx_names",           ARRAY(sa.Text())),
        sa.Column("mofa_names",          ARRAY(sa.Text())),
        sa.Column("default_unit",        sa.Text()),
        sa.Column("unit_conversions",    JSONB()),
        sa.Column("is_byproduct_source", sa.Boolean(), server_default="false"),
        sa.Column("byproduct_types",     JSONB(), server_default="'[]'"),
    )

    op.create_table(
        "ghana_markets",
        sa.Column("id",             sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("market_name",    sa.Text()),
        sa.Column("canonical_name", sa.Text()),
        sa.Column("district_id",    sa.BigInteger()),
        sa.Column("region",         sa.Text()),
        sa.Column("is_major_hub",   sa.Boolean()),
        sa.Column("hdx_names",      ARRAY(sa.Text())),
        sa.Column("mofa_names",     ARRAY(sa.Text())),
    )

    op.create_table(
        "raw_prices",
        sa.Column("id",          sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source",      sa.Text()),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("raw_payload", JSONB()),
        sa.Column("file_ref",    sa.Text()),
    )

    op.create_table(
        "clean_prices",
        sa.Column("id",         sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("raw_id",     sa.BigInteger(), sa.ForeignKey("raw_prices.id"), nullable=False),
        sa.Column("market",     sa.Text()),
        sa.Column("region",     sa.Text()),
        sa.Column("district_id",sa.BigInteger()),
        sa.Column("crop",       sa.Text()),
        sa.Column("unit",       sa.Text()),
        sa.Column("price_ghs",  sa.Numeric(10, 2)),
        sa.Column("price_date", sa.Date()),
        sa.Column("source",     sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_clean_prices_price_date",  "clean_prices", ["price_date"])
    op.create_index("ix_clean_prices_crop_market", "clean_prices", ["crop", "market"])

    op.create_table(
        "price_quarantine",
        sa.Column("id",               sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("raw_id",           sa.BigInteger(), sa.ForeignKey("raw_prices.id"), nullable=False),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("raw_payload",      JSONB()),
        sa.Column("quarantined_at",   sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "ingestion_log",
        sa.Column("id",               sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source",           sa.Text()),
        sa.Column("run_at",           sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("rows_fetched",     sa.Integer()),
        sa.Column("rows_clean",       sa.Integer()),
        sa.Column("rows_quarantined", sa.Integer()),
        sa.Column("status",           sa.Text()),
        sa.Column("error_detail",     sa.Text()),
        sa.Column("file_ref",         sa.Text()),
    )

    op.create_table(
        "chirps_daily",
        sa.Column("id",                sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("obs_date",          sa.Date(), nullable=False),
        sa.Column("district_id",       sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.Column("mean_rainfall_mm",  sa.Numeric(8, 3)),
        sa.Column("cell_count",        sa.Integer()),
        sa.Column("ingested_at",       sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("obs_date", "district_id", name="uq_chirps_obs_date_district"),
    )
    op.create_index("ix_chirps_daily_obs_date", "chirps_daily", ["obs_date"])

    op.create_table(
        "nasa_power_daily",
        sa.Column("id",          sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("obs_date",    sa.Date(), nullable=False),
        sa.Column("district_id", sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.Column("temp_mean",   sa.Numeric(6, 2)),
        sa.Column("temp_max",    sa.Numeric(6, 2)),
        sa.Column("temp_min",    sa.Numeric(6, 2)),
        sa.Column("solar_mj",    sa.Numeric(8, 3)),
        sa.Column("humidity_pct",sa.Numeric(5, 2)),
        sa.Column("wind_ms",     sa.Numeric(6, 3)),
        sa.Column("et0_mm",      sa.Numeric(8, 3)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("obs_date", "district_id", name="uq_nasa_obs_date_district"),
    )
    op.create_index("ix_nasa_power_daily_obs_date", "nasa_power_daily", ["obs_date"])

    op.create_table(
        "spi_baselines",
        sa.Column("id",                sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("district_id",       sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.Column("calendar_month",    sa.Integer()),
        sa.Column("baseline_mean_mm",  sa.Numeric(8, 3)),
        sa.Column("baseline_std_mm",   sa.Numeric(8, 3)),
        sa.Column("years_of_data",     sa.Integer()),
        sa.Column("computed_at",       sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("district_id", "calendar_month", name="uq_spi_district_month"),
    )

    op.create_table(
        "climate_indicators",
        sa.Column("id",                 sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("indicator_date",     sa.Date(), nullable=False),
        sa.Column("district_id",        sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.Column("spi_30day",          sa.Numeric(6, 3)),
        sa.Column("et0_mm",             sa.Numeric(8, 3)),
        sa.Column("csi_maize",          sa.Numeric(5, 3)),
        sa.Column("csi_tomato",         sa.Numeric(5, 3)),
        sa.Column("csi_onion",          sa.Numeric(5, 3)),
        sa.Column("csi_cassava",        sa.Numeric(5, 3)),
        sa.Column("csi_rice",           sa.Numeric(5, 3)),
        sa.Column("csi_plantain",       sa.Numeric(5, 3)),
        sa.Column("harvest_delay_days", sa.Integer()),
        sa.Column("flag_level",         sa.Text()),
        sa.Column("computed_at",        sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("indicator_date", "district_id", name="uq_climate_indicator_date_district"),
    )
    op.create_index("ix_climate_indicators_indicator_date", "climate_indicators", ["indicator_date"])

    op.create_table(
        "farmers",
        sa.Column("id",           sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_name",    sa.Text(), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=False, unique=True),
        sa.Column("district_id",  sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.Column("registered_by",sa.BigInteger(), nullable=True),
        sa.Column("is_active",    sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "farmer_declarations",
        sa.Column("id",                    sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("farmer_id",             sa.BigInteger(), sa.ForeignKey("farmers.id"), nullable=False),
        sa.Column("submitted_by_agent",    sa.BigInteger(), nullable=True),
        sa.Column("source",                sa.Text(), nullable=False),
        sa.Column("crop",                  sa.Text(), nullable=False),
        sa.Column("quantity_kg",           sa.Numeric(10, 2), nullable=False),
        sa.Column("district_id",           sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.Column("harvest_date",          sa.Date(), nullable=False),
        sa.Column("adjusted_harvest_date", sa.Date(), nullable=True),
        sa.Column("status",                sa.Text(), nullable=False, server_default="active"),
        sa.Column("price_forecast_ghs",    sa.Numeric(10, 2), nullable=True),
        sa.Column("csi_flag",              sa.Text(), nullable=False, server_default="normal"),
        sa.Column("created_at",            sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at",            sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("farmer_id", "crop", "district_id", "harvest_date", name="uq_farmer_declaration"),
    )
    op.create_index("ix_farmer_declarations_farmer_id",   "farmer_declarations", ["farmer_id"])
    op.create_index("ix_farmer_declarations_status",       "farmer_declarations", ["status"])
    op.create_index("ix_farmer_declarations_harvest_date", "farmer_declarations", ["harvest_date"])

    op.create_table(
        "byproduct_declarations",
        sa.Column("id",                    sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("declaration_id",        sa.BigInteger(), sa.ForeignKey("farmer_declarations.id"), nullable=False),
        sa.Column("byproduct_type",        sa.Text(), nullable=False),
        sa.Column("estimated_quantity_kg", sa.Numeric(10, 2)),
        sa.Column("is_perishable",         sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("available_date",        sa.Date(), nullable=False),
        sa.Column("status",                sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at",            sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "ussd_sessions",
        sa.Column("id",           sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id",   sa.Text(), nullable=False, unique=True),
        sa.Column("phone_number", sa.Text(), nullable=False),
        sa.Column("farmer_id",    sa.BigInteger(), sa.ForeignKey("farmers.id"), nullable=True),
        sa.Column("menu_state",   sa.Text(), nullable=False, server_default="welcome"),
        sa.Column("declaration",  JSONB(), server_default="'{}'"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_activity",sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ussd_sessions_last_activity", "ussd_sessions", ["last_activity"])

    op.create_table(
        "reservations",
        sa.Column("id",             sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("declaration_id", sa.BigInteger(), sa.ForeignKey("farmer_declarations.id"), nullable=False),
        sa.Column("buyer_phone",    sa.Text(), nullable=False),
        sa.Column("buyer_name",     sa.Text(), nullable=False, server_default=""),
        sa.Column("quantity_bags",  sa.Integer(), nullable=False),
        sa.Column("unit_price_ghs", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_ghs",      sa.Numeric(10, 2), nullable=False),
        sa.Column("status",         sa.Text(), nullable=False, server_default="confirmed"),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_reservations_declaration_id", "reservations", ["declaration_id"])
    op.create_index("ix_reservations_buyer_phone",    "reservations", ["buyer_phone"])
    op.create_index("ix_reservations_status",         "reservations", ["status"])

    op.create_table(
        "momo_payments",
        sa.Column("id",             sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reservation_id", sa.BigInteger(), sa.ForeignKey("reservations.id"), nullable=False),
        sa.Column("provider",       sa.Text(), nullable=False),
        sa.Column("phone_number",   sa.Text(), nullable=False),
        sa.Column("amount_ghs",     sa.Numeric(10, 2), nullable=False),
        sa.Column("reference",      sa.Text(), nullable=False, unique=True),
        sa.Column("status",         sa.Text(), nullable=False, server_default="success"),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_momo_payments_reservation_id", "momo_payments", ["reservation_id"])

    op.create_table(
        "transport_providers",
        sa.Column("id",                sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_name",         sa.Text(), nullable=False),
        sa.Column("phone_number",      sa.Text(), nullable=False, unique=True),
        sa.Column("business_name",     sa.Text(), nullable=True),
        sa.Column("district_id",       sa.BigInteger(), nullable=True),
        sa.Column("truck_capacity_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("truck_count",       sa.Integer(), nullable=False, server_default="1"),
        sa.Column("vehicle_type",      sa.Text(), nullable=False),
        sa.Column("is_available",      sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("service_regions",   JSONB(), server_default="'[]'"),
        sa.Column("base_rate_per_km",  sa.Numeric(8, 2), nullable=True),
        sa.Column("rating",            sa.Numeric(3, 2), nullable=False, server_default="5.00"),
        sa.Column("total_jobs",        sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active",         sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("registered_at",     sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_transport_providers_district_id",  "transport_providers", ["district_id"])
    op.create_index("ix_transport_providers_availability", "transport_providers", ["is_available", "is_active"])

    op.create_table(
        "transport_jobs",
        sa.Column("id",                    sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider_id",           sa.BigInteger(), sa.ForeignKey("transport_providers.id"), nullable=False),
        sa.Column("status",                sa.Text(), nullable=False, server_default="pending"),
        sa.Column("pickup_district_id",    sa.BigInteger(), nullable=True),
        sa.Column("delivery_district_id",  sa.BigInteger(), nullable=True),
        sa.Column("scheduled_date",        sa.Date(), nullable=False),
        sa.Column("total_cargo_kg",        sa.Numeric(10, 2), nullable=True),
        sa.Column("declaration_ids",       JSONB(), server_default="'[]'"),
        sa.Column("farmer_ids",            JSONB(), server_default="'[]'"),
        sa.Column("estimated_distance_km", sa.Numeric(8, 2), nullable=True),
        sa.Column("estimated_cost_ghs",    sa.Numeric(10, 2), nullable=True),
        sa.Column("actual_cost_ghs",       sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at",            sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at",            sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_transport_jobs_status",         "transport_jobs", ["status"])
    op.create_index("ix_transport_jobs_scheduled_date", "transport_jobs", ["scheduled_date"])
    op.create_index("ix_transport_jobs_provider_id",    "transport_jobs", ["provider_id"])

    op.create_table(
        "fuel_prices",
        sa.Column("id",                  sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("price_date",          sa.Date(), nullable=False),
        sa.Column("fuel_type",           sa.Text(), nullable=False),
        sa.Column("price_ghs_per_litre", sa.Numeric(8, 3), nullable=False),
        sa.Column("source",              sa.Text(), server_default="npa"),
        sa.Column("scraped_at",          sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("price_date", "fuel_type", name="uq_fuel_price_date_type"),
    )
    op.create_index("ix_fuel_prices_price_date", "fuel_prices", ["price_date"])

    op.create_table(
        "feature_store",
        sa.Column("id",                 sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("feature_date",       sa.Date(), nullable=False),
        sa.Column("market",             sa.Text(), nullable=False),
        sa.Column("crop",               sa.Text(), nullable=False),
        sa.Column("price_ghs",          sa.Numeric(10, 2)),
        sa.Column("lag_7d",             sa.Numeric(10, 2)),
        sa.Column("lag_14d",            sa.Numeric(10, 2)),
        sa.Column("lag_30d",            sa.Numeric(10, 2)),
        sa.Column("lag_90d",            sa.Numeric(10, 2)),
        sa.Column("rolling_mean_30d",   sa.Numeric(10, 2)),
        sa.Column("rolling_std_30d",    sa.Numeric(10, 2)),
        sa.Column("rolling_mean_90d",   sa.Numeric(10, 2)),
        sa.Column("rolling_min_30d",    sa.Numeric(10, 2)),
        sa.Column("rolling_max_30d",    sa.Numeric(10, 2)),
        sa.Column("price_momentum_7d",  sa.Numeric(10, 4)),
        sa.Column("price_momentum_30d", sa.Numeric(10, 4)),
        sa.Column("sin_week",           sa.Numeric(8, 6)),
        sa.Column("cos_week",           sa.Numeric(8, 6)),
        sa.Column("sin_month",          sa.Numeric(8, 6)),
        sa.Column("cos_month",          sa.Numeric(8, 6)),
        sa.Column("spi_30day",          sa.Numeric(6, 3)),
        sa.Column("et0_mm",             sa.Numeric(8, 3)),
        sa.Column("csi_value",          sa.Numeric(5, 3)),
        sa.Column("fuel_price_diesel",  sa.Numeric(8, 3)),
        sa.Column("district_id",        sa.BigInteger(), sa.ForeignKey("ghana_districts.id")),
        sa.UniqueConstraint("feature_date", "market", "crop", name="uq_feature_store_date_market_crop"),
    )
    op.create_index("ix_feature_store_crop_market_date", "feature_store", ["crop", "market", "feature_date"])

    op.create_table(
        "district_distances",
        sa.Column("id",               sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("from_district_id", sa.BigInteger(), sa.ForeignKey("ghana_districts.id"), nullable=False),
        sa.Column("to_district_id",   sa.BigInteger(), sa.ForeignKey("ghana_districts.id"), nullable=False),
        sa.Column("straight_line_km", sa.Numeric(8, 2)),
        sa.Column("road_distance_km", sa.Numeric(8, 2)),
        sa.Column("road_quality",     sa.Text(), server_default="paved"),
        sa.Column("road_factor",      sa.Numeric(4, 2), server_default="1.3"),
        sa.UniqueConstraint("from_district_id", "to_district_id", name="uq_district_distances_pair"),
    )
    op.create_index("ix_district_distances_from", "district_distances", ["from_district_id"])

    op.create_table(
        "logistics_costs",
        sa.Column("id",               sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("from_district_id", sa.BigInteger(), sa.ForeignKey("ghana_districts.id"), nullable=False),
        sa.Column("to_district_id",   sa.BigInteger(), sa.ForeignKey("ghana_districts.id"), nullable=False),
        sa.Column("vehicle_type",     sa.Text(), nullable=False),
        sa.Column("cargo_kg",         sa.Numeric(10, 2)),
        sa.Column("base_cost_ghs",    sa.Numeric(10, 2)),
        sa.Column("total_cost_ghs",   sa.Numeric(10, 2)),
        sa.Column("cost_per_kg_ghs",  sa.Numeric(8, 4)),
        sa.Column("diesel_price_used",sa.Numeric(8, 3)),
        sa.Column("computed_at",      sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("from_district_id", "to_district_id", "vehicle_type", "cargo_kg", name="uq_logistics_costs_key"),
    )

    op.create_table(
        "model_baselines",
        sa.Column("id",            sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("crop",          sa.Text(), nullable=False),
        sa.Column("market",        sa.Text(), nullable=False),
        sa.Column("model_type",    sa.Text(), nullable=False),
        sa.Column("order_p",       sa.Integer()),
        sa.Column("order_d",       sa.Integer()),
        sa.Column("order_q",       sa.Integer()),
        sa.Column("seasonal_p",    sa.Integer()),
        sa.Column("seasonal_d",    sa.Integer()),
        sa.Column("seasonal_q",    sa.Integer()),
        sa.Column("seasonal_m",    sa.Integer()),
        sa.Column("aic",           sa.Numeric(12, 4)),
        sa.Column("bic",           sa.Numeric(12, 4)),
        sa.Column("mae_7d",        sa.Numeric(10, 4)),
        sa.Column("rmse_7d",       sa.Numeric(10, 4)),
        sa.Column("mae_30d",       sa.Numeric(10, 4)),
        sa.Column("rmse_30d",      sa.Numeric(10, 4)),
        sa.Column("mape_7d",       sa.Numeric(10, 4)),
        sa.Column("mape_30d",      sa.Numeric(10, 4)),
        sa.Column("trained_at",    sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("training_rows", sa.Integer()),
        sa.UniqueConstraint("crop", "market", "model_type", name="uq_model_baselines_crop_market_type"),
    )

    op.create_table(
        "price_forecasts",
        sa.Column("id",                   sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("crop",                 sa.Text(), nullable=False),
        sa.Column("market",               sa.Text(), nullable=False),
        sa.Column("model_type",           sa.Text(), nullable=False),
        sa.Column("forecast_date",        sa.Date(), nullable=False),
        sa.Column("horizon_days",         sa.Integer()),
        sa.Column("predicted_price_ghs",  sa.Numeric(10, 2)),
        sa.Column("lower_bound_ghs",      sa.Numeric(10, 2)),
        sa.Column("upper_bound_ghs",      sa.Numeric(10, 2)),
        sa.Column("actual_price_ghs",     sa.Numeric(10, 2)),
        sa.Column("created_at",           sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("crop", "market", "model_type", "forecast_date", "horizon_days", name="uq_price_forecast_key"),
    )

    op.create_table(
        "alerts_log",
        sa.Column("id",             sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("farmer_id",      sa.BigInteger(), sa.ForeignKey("farmers.id"), nullable=True),
        sa.Column("declaration_id", sa.BigInteger(), sa.ForeignKey("farmer_declarations.id"), nullable=True),
        sa.Column("phone_number",   sa.Text(), nullable=False),
        sa.Column("alert_type",     sa.Text(), nullable=False),
        sa.Column("message",        sa.Text(), nullable=False),
        sa.Column("status",         sa.Text(), nullable=False, server_default="sent"),
        sa.Column("sent_at",        sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("error_detail",   sa.Text(), nullable=True),
    )
    op.create_index("ix_alerts_log_farmer_id",      "alerts_log", ["farmer_id"])
    op.create_index("ix_alerts_log_declaration_id", "alerts_log", ["declaration_id"])
    op.create_index("ix_alerts_log_sent_at",        "alerts_log", ["sent_at"])


def downgrade() -> None:
    op.drop_table("alerts_log")
    op.drop_table("price_forecasts")
    op.drop_table("model_baselines")
    op.drop_table("logistics_costs")
    op.drop_table("district_distances")
    op.drop_table("feature_store")
    op.drop_table("fuel_prices")
    op.drop_table("transport_jobs")
    op.drop_table("transport_providers")
    op.drop_table("momo_payments")
    op.drop_table("reservations")
    op.drop_table("ussd_sessions")
    op.drop_table("byproduct_declarations")
    op.drop_table("farmer_declarations")
    op.drop_table("farmers")
    op.drop_table("climate_indicators")
    op.drop_table("spi_baselines")
    op.drop_table("nasa_power_daily")
    op.drop_table("chirps_daily")
    op.drop_table("ingestion_log")
    op.drop_table("price_quarantine")
    op.drop_table("clean_prices")
    op.drop_table("raw_prices")
    op.drop_table("ghana_markets")
    op.drop_table("crop_reference")
    op.drop_table("ghana_districts")
