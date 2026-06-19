from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime,
    ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class GhanaDistrict(Base):
    __tablename__ = "ghana_districts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    district_code = Column(Text)
    district_name = Column(Text)
    region_name = Column(Text)
    variant_names = Column(Text)
    district_type = Column(Text)
    hasc_code = Column(Text)
    centroid_lat = Column(Numeric(10, 6))
    centroid_lon = Column(Numeric(10, 6))


class RawPrice(Base):
    __tablename__ = "raw_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(Text)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_payload = Column(JSONB)
    file_ref = Column(Text)

    clean_prices = relationship("CleanPrice", back_populates="raw")
    quarantined = relationship("PriceQuarantine", back_populates="raw")


class CleanPrice(Base):
    __tablename__ = "clean_prices"
    __table_args__ = (
        Index("ix_clean_prices_price_date", "price_date"),
        Index("ix_clean_prices_crop_market", "crop", "market"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    raw_id = Column(BigInteger, ForeignKey("raw_prices.id"), nullable=False)
    market = Column(Text)
    region = Column(Text)
    district_id = Column(BigInteger)
    crop = Column(Text)
    unit = Column(Text)
    price_ghs = Column(Numeric(10, 2))
    price_date = Column(Date)
    source = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raw = relationship("RawPrice", back_populates="clean_prices")


class PriceQuarantine(Base):
    __tablename__ = "price_quarantine"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    raw_id = Column(BigInteger, ForeignKey("raw_prices.id"), nullable=False)
    rejection_reason = Column(Text)
    raw_payload = Column(JSONB)
    quarantined_at = Column(DateTime(timezone=True), server_default=func.now())

    raw = relationship("RawPrice", back_populates="quarantined")


class IngestionLog(Base):
    __tablename__ = "ingestion_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(Text)
    run_at = Column(DateTime(timezone=True), server_default=func.now())
    rows_fetched = Column(Integer)
    rows_clean = Column(Integer)
    rows_quarantined = Column(Integer)
    status = Column(Text)
    error_detail = Column(Text)
    file_ref = Column(Text)     # populated by MoFA runs to track which file was ingested


class GhanaMarket(Base):
    __tablename__ = "ghana_markets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    market_name = Column(Text)
    canonical_name = Column(Text)
    district_id = Column(BigInteger)
    region = Column(Text)
    is_major_hub = Column(Boolean)
    hdx_names = Column(ARRAY(Text))
    mofa_names = Column(ARRAY(Text))


class CropReference(Base):
    __tablename__ = "crop_reference"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    internal_name = Column(Text)
    hdx_names = Column(ARRAY(Text))
    mofa_names = Column(ARRAY(Text))
    default_unit = Column(Text)
    unit_conversions = Column(JSONB)
    is_byproduct_source = Column(Boolean, server_default="false")
    byproduct_types = Column(JSONB, server_default=text("'[]'"))


class ChirpsDaily(Base):
    __tablename__ = "chirps_daily"
    __table_args__ = (
        UniqueConstraint("obs_date", "district_id", name="uq_chirps_obs_date_district"),
        Index("ix_chirps_daily_obs_date", "obs_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    obs_date = Column(Date, nullable=False)
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))
    mean_rainfall_mm = Column(Numeric(8, 3))
    cell_count = Column(Integer)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class NasaPowerDaily(Base):
    __tablename__ = "nasa_power_daily"
    __table_args__ = (
        UniqueConstraint("obs_date", "district_id", name="uq_nasa_obs_date_district"),
        Index("ix_nasa_power_daily_obs_date", "obs_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    obs_date = Column(Date, nullable=False)
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))
    temp_mean = Column(Numeric(6, 2))
    temp_max = Column(Numeric(6, 2))
    temp_min = Column(Numeric(6, 2))
    solar_mj = Column(Numeric(8, 3))
    humidity_pct = Column(Numeric(5, 2))
    wind_ms = Column(Numeric(6, 3))
    et0_mm = Column(Numeric(8, 3))
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class SpiBaseline(Base):
    __tablename__ = "spi_baselines"
    __table_args__ = (
        UniqueConstraint("district_id", "calendar_month", name="uq_spi_district_month"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))
    calendar_month = Column(Integer)
    baseline_mean_mm = Column(Numeric(8, 3))
    baseline_std_mm = Column(Numeric(8, 3))
    years_of_data = Column(Integer)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


class ClimateIndicator(Base):
    __tablename__ = "climate_indicators"
    __table_args__ = (
        UniqueConstraint("indicator_date", "district_id", name="uq_climate_indicator_date_district"),
        Index("ix_climate_indicators_indicator_date", "indicator_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    indicator_date = Column(Date, nullable=False)
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))
    spi_30day = Column(Numeric(6, 3))
    et0_mm = Column(Numeric(8, 3))
    csi_maize = Column(Numeric(5, 3))
    csi_tomato = Column(Numeric(5, 3))
    csi_onion = Column(Numeric(5, 3))
    csi_cassava = Column(Numeric(5, 3))
    csi_rice = Column(Numeric(5, 3))
    csi_plantain = Column(Numeric(5, 3))
    harvest_delay_days = Column(Integer)
    flag_level = Column(Text)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


# ── M3: Farmer-facing tables ──────────────────────────────────────────────────

class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    full_name = Column(Text, nullable=False)
    phone_number = Column(Text, nullable=False, unique=True)
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))
    registered_by = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    declarations = relationship("FarmerDeclaration", back_populates="farmer")
    ussd_sessions = relationship("UssdSession", back_populates="farmer")


class FarmerDeclaration(Base):
    __tablename__ = "farmer_declarations"
    __table_args__ = (
        UniqueConstraint(
            "farmer_id", "crop", "district_id", "harvest_date",
            name="uq_farmer_declaration",
        ),
        Index("ix_farmer_declarations_farmer_id",   "farmer_id"),
        Index("ix_farmer_declarations_status",       "status"),
        Index("ix_farmer_declarations_harvest_date", "harvest_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    farmer_id = Column(BigInteger, ForeignKey("farmers.id"), nullable=False)
    submitted_by_agent = Column(BigInteger, nullable=True)
    source = Column(Text, nullable=False)
    crop = Column(Text, nullable=False)
    quantity_kg = Column(Numeric(10, 2), nullable=False)
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))
    harvest_date = Column(Date, nullable=False)
    adjusted_harvest_date = Column(Date, nullable=True)
    status = Column(Text, nullable=False, server_default="active")
    price_forecast_ghs = Column(Numeric(10, 2), nullable=True)
    csi_flag = Column(Text, nullable=False, server_default="normal")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    farmer = relationship("Farmer", back_populates="declarations")
    byproducts = relationship("ByproductDeclaration", back_populates="declaration")


class ByproductDeclaration(Base):
    __tablename__ = "byproduct_declarations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    declaration_id = Column(BigInteger, ForeignKey("farmer_declarations.id"), nullable=False)
    byproduct_type = Column(Text, nullable=False)
    estimated_quantity_kg = Column(Numeric(10, 2))
    is_perishable = Column(Boolean, nullable=False, server_default="false")
    available_date = Column(Date, nullable=False)
    status = Column(Text, nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    declaration = relationship("FarmerDeclaration", back_populates="byproducts")


class UssdSession(Base):
    __tablename__ = "ussd_sessions"
    __table_args__ = (
        Index("ix_ussd_sessions_last_activity", "last_activity"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(Text, nullable=False, unique=True)
    phone_number = Column(Text, nullable=False)
    farmer_id = Column(BigInteger, ForeignKey("farmers.id"), nullable=True)
    menu_state = Column(Text, nullable=False, server_default="welcome")
    declaration = Column(JSONB, server_default=text("'{}'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())

    farmer = relationship("Farmer", back_populates="ussd_sessions")


# ── M3: Transport tables ───────────────────────────────────────────────────────

class TransportProvider(Base):
    __tablename__ = "transport_providers"
    __table_args__ = (
        Index("ix_transport_providers_district_id", "district_id"),
        Index("ix_transport_providers_availability", "is_available", "is_active"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    full_name = Column(Text, nullable=False)
    phone_number = Column(Text, nullable=False, unique=True)
    business_name = Column(Text, nullable=True)
    district_id = Column(BigInteger, nullable=True)
    truck_capacity_kg = Column(Numeric(10, 2), nullable=False)
    truck_count = Column(Integer, nullable=False, server_default="1")
    vehicle_type = Column(Text, nullable=False)
    is_available = Column(Boolean, nullable=False, server_default="true")
    service_regions = Column(JSONB, server_default=text("'[]'"))
    base_rate_per_km = Column(Numeric(8, 2), nullable=True)
    rating = Column(Numeric(3, 2), nullable=False, server_default="5.00")
    total_jobs = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("TransportJob", back_populates="provider")


class TransportJob(Base):
    __tablename__ = "transport_jobs"
    __table_args__ = (
        Index("ix_transport_jobs_status",         "status"),
        Index("ix_transport_jobs_scheduled_date", "scheduled_date"),
        Index("ix_transport_jobs_provider_id",    "provider_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_id = Column(BigInteger, ForeignKey("transport_providers.id"), nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    pickup_district_id = Column(BigInteger, nullable=True)
    delivery_district_id = Column(BigInteger, nullable=True)
    scheduled_date = Column(Date, nullable=False)
    total_cargo_kg = Column(Numeric(10, 2), nullable=True)
    declaration_ids = Column(JSONB, server_default=text("'[]'"))
    farmer_ids = Column(JSONB, server_default=text("'[]'"))
    estimated_distance_km = Column(Numeric(8, 2), nullable=True)
    estimated_cost_ghs = Column(Numeric(10, 2), nullable=True)
    actual_cost_ghs = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    provider = relationship("TransportProvider", back_populates="jobs")


# ── M4: Fuel price table ──────────────────────────────────────────────────────

class FuelPrice(Base):
    __tablename__ = "fuel_prices"
    __table_args__ = (
        UniqueConstraint("price_date", "fuel_type", name="uq_fuel_price_date_type"),
        Index("ix_fuel_prices_price_date", "price_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    price_date = Column(Date, nullable=False)
    fuel_type = Column(Text, nullable=False)
    price_ghs_per_litre = Column(Numeric(8, 3), nullable=False)
    source = Column(Text, server_default="npa")
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())


# ── M5: Feature store table ───────────────────────────────────────────────────

class FeatureStore(Base):
    __tablename__ = "feature_store"
    __table_args__ = (
        UniqueConstraint("feature_date", "market", "crop", name="uq_feature_store_date_market_crop"),
        Index("ix_feature_store_crop_market_date", "crop", "market", "feature_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    feature_date = Column(Date, nullable=False)
    market = Column(Text, nullable=False)
    crop = Column(Text, nullable=False)
    price_ghs = Column(Numeric(10, 2))
    lag_7d = Column(Numeric(10, 2))
    lag_14d = Column(Numeric(10, 2))
    lag_30d = Column(Numeric(10, 2))
    lag_90d = Column(Numeric(10, 2))
    rolling_mean_30d = Column(Numeric(10, 2))
    rolling_std_30d = Column(Numeric(10, 2))
    rolling_mean_90d = Column(Numeric(10, 2))
    rolling_min_30d = Column(Numeric(10, 2))
    rolling_max_30d = Column(Numeric(10, 2))
    price_momentum_7d = Column(Numeric(10, 4))
    price_momentum_30d = Column(Numeric(10, 4))
    sin_week = Column(Numeric(8, 6))
    cos_week = Column(Numeric(8, 6))
    sin_month = Column(Numeric(8, 6))
    cos_month = Column(Numeric(8, 6))
    spi_30day = Column(Numeric(6, 3))
    et0_mm = Column(Numeric(8, 3))
    csi_value = Column(Numeric(5, 3))
    fuel_price_diesel = Column(Numeric(8, 3))
    district_id = Column(BigInteger, ForeignKey("ghana_districts.id"))


# ── M7: ARIMA / SARIMA baseline forecasting tables ────────────────────────────

# ── M8: Logistics cost tables ─────────────────────────────────────────────────

class DistrictDistance(Base):
    __tablename__ = "district_distances"
    __table_args__ = (
        UniqueConstraint("from_district_id", "to_district_id", name="uq_district_distances_pair"),
        Index("ix_district_distances_from", "from_district_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_district_id = Column(BigInteger, ForeignKey("ghana_districts.id"), nullable=False)
    to_district_id = Column(BigInteger, ForeignKey("ghana_districts.id"), nullable=False)
    straight_line_km = Column(Numeric(8, 2))
    road_distance_km = Column(Numeric(8, 2))
    road_quality = Column(Text, server_default="paved")
    road_factor = Column(Numeric(4, 2), server_default="1.3")


class LogisticsCost(Base):
    __tablename__ = "logistics_costs"
    __table_args__ = (
        UniqueConstraint(
            "from_district_id", "to_district_id", "vehicle_type", "cargo_kg",
            name="uq_logistics_costs_key",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_district_id = Column(BigInteger, ForeignKey("ghana_districts.id"), nullable=False)
    to_district_id = Column(BigInteger, ForeignKey("ghana_districts.id"), nullable=False)
    vehicle_type = Column(Text, nullable=False)
    cargo_kg = Column(Numeric(10, 2))
    base_cost_ghs = Column(Numeric(10, 2))
    total_cost_ghs = Column(Numeric(10, 2))
    cost_per_kg_ghs = Column(Numeric(8, 4))
    diesel_price_used = Column(Numeric(8, 3))
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


# ── M7: ARIMA / SARIMA baseline forecasting tables ────────────────────────────

class ModelBaseline(Base):
    __tablename__ = "model_baselines"
    __table_args__ = (
        UniqueConstraint("crop", "market", "model_type", name="uq_model_baselines_crop_market_type"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    crop = Column(Text, nullable=False)
    market = Column(Text, nullable=False)
    model_type = Column(Text, nullable=False)
    order_p = Column(Integer)
    order_d = Column(Integer)
    order_q = Column(Integer)
    seasonal_p = Column(Integer)
    seasonal_d = Column(Integer)
    seasonal_q = Column(Integer)
    seasonal_m = Column(Integer)
    aic = Column(Numeric(12, 4))
    bic = Column(Numeric(12, 4))
    mae_7d = Column(Numeric(10, 4))
    rmse_7d = Column(Numeric(10, 4))
    mae_30d = Column(Numeric(10, 4))
    rmse_30d = Column(Numeric(10, 4))
    mape_7d = Column(Numeric(10, 4))
    mape_30d = Column(Numeric(10, 4))
    trained_at = Column(DateTime(timezone=True), server_default=func.now())
    training_rows = Column(Integer)


class PriceForecast(Base):
    __tablename__ = "price_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "crop", "market", "model_type", "forecast_date", "horizon_days",
            name="uq_price_forecast_key",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    crop = Column(Text, nullable=False)
    market = Column(Text, nullable=False)
    model_type = Column(Text, nullable=False)
    forecast_date = Column(Date, nullable=False)
    horizon_days = Column(Integer)
    predicted_price_ghs = Column(Numeric(10, 2))
    lower_bound_ghs = Column(Numeric(10, 2))
    upper_bound_ghs = Column(Numeric(10, 2))
    actual_price_ghs = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── M17: Alert log table ──────────────────────────────────────────────────────

class AlertLog(Base):
    __tablename__ = "alerts_log"
    __table_args__ = (
        Index("ix_alerts_log_farmer_id",      "farmer_id"),
        Index("ix_alerts_log_declaration_id", "declaration_id"),
        Index("ix_alerts_log_sent_at",        "sent_at"),
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    farmer_id      = Column(BigInteger, ForeignKey("farmers.id"), nullable=True)
    declaration_id = Column(BigInteger, ForeignKey("farmer_declarations.id"), nullable=True)
    phone_number   = Column(Text, nullable=False)
    alert_type     = Column(Text, nullable=False)
    message        = Column(Text, nullable=False)
    status         = Column(Text, nullable=False, server_default="sent")
    sent_at        = Column(DateTime(timezone=True), server_default=func.now())
    error_detail   = Column(Text, nullable=True)


# ── M3: Reservation / payment tables ─────────────────────────────────────────

class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_reservations_declaration_id", "declaration_id"),
        Index("ix_reservations_buyer_phone",    "buyer_phone"),
        Index("ix_reservations_status",         "status"),
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    declaration_id = Column(BigInteger, ForeignKey("farmer_declarations.id"), nullable=False)
    buyer_phone    = Column(Text, nullable=False)
    buyer_name     = Column(Text, nullable=False, server_default="")
    quantity_bags  = Column(Integer, nullable=False)
    unit_price_ghs = Column(Numeric(10, 2), nullable=False)
    total_ghs      = Column(Numeric(10, 2), nullable=False)
    status         = Column(Text, nullable=False, server_default="confirmed")
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    payments = relationship("MoMoPayment", back_populates="reservation")


class MoMoPayment(Base):
    __tablename__ = "momo_payments"
    __table_args__ = (
        Index("ix_momo_payments_reservation_id", "reservation_id"),
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id = Column(BigInteger, ForeignKey("reservations.id"), nullable=False)
    provider       = Column(Text, nullable=False)
    phone_number   = Column(Text, nullable=False)
    amount_ghs     = Column(Numeric(10, 2), nullable=False)
    reference      = Column(Text, nullable=False, unique=True)
    status         = Column(Text, nullable=False, server_default="success")
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    reservation = relationship("Reservation", back_populates="payments")
