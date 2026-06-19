// API response types for AgriMatch backend

// ── Reference ────────────────────────────────────────────────────────────────

export interface Crop {
  id: number
  name: string
  is_byproduct_source: boolean
}

export interface Region {
  region: string
  market_count: number
  district_count: number
}

export interface PlatformStats {
  active_farmers: number
  total_markets: number
  active_declarations: number
  total_value_ghs: number
}

export interface ModelAccuracy {
  market: string
  xgb?: number
  xgb_mae?: number
  lstm?: number
  training_rows?: number
}

export interface ModelsStatus {
  xgboost_models: number
  lstm_models: number
  delay_classifier: boolean
  api_version: string
  last_updated: string
}

// ── Prices ───────────────────────────────────────────────────────────────────

export interface PriceHistory {
  month: string
  market: string
  avg_price: number
  min_price: number
  max_price: number
  data_points: number
}

export interface BulletinEntry {
  crop: string
  market: string
  region: string
  latest_price: number
  latest_date: string
  price_30d_ago: number | null
  change_pct: number | null
}

// ── Forecasting ──────────────────────────────────────────────────────────────

export interface ForecastHorizon {
  horizon_days: number
  predicted_price_ghs: number
  lower_bound: number
  upper_bound: number
}

export interface Forecast {
  crop: string
  market: string
  last_known_price: number
  confidence: number
  forecasts: ForecastHorizon[]
}

export interface LSTMForecast {
  crop: string
  market: string
  steps: Array<{ day: number; predicted_price_ghs: number }>
}

export interface DelayPrediction {
  declaration_id: number
  delay_probability: number
  delay_risk: 'low' | 'medium' | 'high'
  predicted_delay_days: number
  factors: string[]
}

// ── Listings ─────────────────────────────────────────────────────────────────

export interface Listing {
  declaration_id: number
  farmer_id: number
  farmer_name: string
  crop: string
  quantity_kg: number
  price_forecast_ghs: number | null
  harvest_date: string
  adjusted_harvest_date: string | null
  district_name: string
  region_name: string
  csi_flag: string | null
  status: string
}

export interface FarmerProfile {
  farmer_id: number
  full_name: string
  phone: string
  district_id: number
  district_name: string
  region_name: string
  is_active: boolean
  declarations: Listing[]
}

// ── Matchmaking ──────────────────────────────────────────────────────────────

export interface MatchResult {
  declaration_id: number
  farmer_name: string
  crop: string
  quantity_kg: number
  price_forecast_ghs: number | null
  harvest_date: string
  district_name: string
  match_score: number
  quantity_score: number
  distance_score: number
  price_score: number
  reliability_score: number
  timing_score: number
  distance_km: number
  logistics_cost_ghs?: number
}

export interface MarketOverview {
  market: string
  region: string
  crop: string
  listing_count: number
  total_kg: number
  avg_price_ghs: number | null
  median_price_ghs: number | null
}

// ── Recommendations ──────────────────────────────────────────────────────────

export interface CropRecommendation {
  crop: string
  composite_score: number
  climate_score: number
  supply_score: number
  price_score: number
  recommendation_strength: 'strongly recommended' | 'recommended' | 'consider' | 'caution' | 'avoid'
  reason: string
}

export interface FarmerRecommendations {
  farmer_id: number
  farmer_name: string
  district_id: number
  district_name: string
  recommendations: CropRecommendation[]
}

// ── Strategy ─────────────────────────────────────────────────────────────────

export interface FarmerStrategy {
  farmer_id: number
  farmer_name: string
  declarations: Array<{
    declaration_id: number
    crop: string
    quantity_kg: number
    harvest_date: string
    strategy: string
    action_items: string[]
    risk_level: 'low' | 'medium' | 'high'
  }>
}

// ── Logistics ────────────────────────────────────────────────────────────────

export interface LogisticsGroup {
  group_id: string
  crop: string
  total_kg: number
  farmer_count: number
  vehicle_type: 'pickup' | 'medium_truck' | 'large_truck'
  estimated_cost_ghs: number
  farmers: Array<{ farmer_id: number; farmer_name: string; quantity_kg: number }>
}

export interface FarmerLogistics {
  farmer_id: number
  transport_jobs: Array<{
    job_id: number
    crop: string
    vehicle_type: string
    status: string
    group_size: number
    cost_share_ghs: number
  }>
}

export interface ByproductListing {
  byproduct_type: string
  crop: string
  quantity_kg: number
  price_ghs_per_kg: number | null
  farmer_id: number
  farmer_name: string
  district_name: string
  region_name: string
  declaration_id: number
}

// ── Advisory ─────────────────────────────────────────────────────────────────

export interface PlantingAdvisory {
  district_id: number
  district_name: string
  crop: string
  recommended_window: string
  climate_risk: 'low' | 'medium' | 'high'
  csi_score: number
  notes: string
}

export interface ROIEstimate {
  crop: string
  market: string
  quantity_kg: number
  transport_cost_ghs: number
  expected_revenue_ghs: number
  expected_profit_ghs: number
  roi_pct: number
}

// ── Alerts ───────────────────────────────────────────────────────────────────

export interface AlertLogEntry {
  id: number
  farmer_id: number
  alert_type: string
  message: string
  severity: 'info' | 'warning' | 'critical'
  sent_at: string
  channel: 'sms' | 'ussd' | 'platform'
}

// ── Demand ───────────────────────────────────────────────────────────────────

export interface BuyerDemand {
  id: number
  buyer_name: string
  phone: string
  crop: string
  quantity_kg: number
  district_id: number
  max_price_ghs: number | null
  created_at: string
  status: 'open' | 'matched' | 'closed'
}

// ── Reservations ─────────────────────────────────────────────────────────────

export interface Reservation {
  reservation_id: number
  declaration_id: number
  buyer_phone: string
  quantity_kg: number
  total_price_ghs: number
  payment_ref: string
  status: 'pending' | 'confirmed' | 'cancelled'
  created_at: string
}
