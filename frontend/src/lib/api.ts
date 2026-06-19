import axios from 'axios'

// Use relative URL so every call goes through the Next.js /api/[...path] proxy.
// This hides the backend URL from the browser and handles CORS automatically.
const API = axios.create({
  baseURL: '',
  timeout: 60_000,
})

// Retry GET requests once on network errors or 5xx responses (1 s delay).
API.interceptors.response.use(
  response => response,
  async error => {
    const config = error.config as (typeof error.config) & { _retried?: boolean }
    if (
      config &&
      config.method === 'get' &&
      !config._retried &&
      (!error.response || error.response.status >= 500)
    ) {
      config._retried = true
      await new Promise(resolve => setTimeout(resolve, 1_000))
      return API(config)
    }
    return Promise.reject(error)
  },
)

// ── Forecasts ─────────────────────────────────────────────────────────────────

export const getForecast = (crop: string, market: string) =>
  API.get(`/api/forecast/${crop}/${market}`)

export const getAllForecasts = (crop: string) =>
  API.get(`/api/forecast/${crop}`)

export const getLSTMForecast = (crop: string, market: string) =>
  API.get(`/api/forecast/lstm/${crop}/${market}`)

// ── Farmer declarations ───────────────────────────────────────────────────────

export const getDeclarations = (farmerId: number) =>
  API.get(`/api/declarations/farmer/${farmerId}`)

export const createDeclaration = (data: Record<string, unknown>) =>
  API.post('/api/declarations', data)

// ── Strategy ──────────────────────────────────────────────────────────────────

export const getFarmerStrategy = (farmerId: number) =>
  API.get(`/api/strategy/farmer/${farmerId}`)

export const getBuyerStrategy = (districtId: number, crop: string, quantityKg?: number) =>
  API.get(`/api/strategy/buyer/${districtId}/${crop}`, {
    params: quantityKg ? { quantity_kg: quantityKg } : undefined,
  })

export const getLogisticsStrategy = (declarationId: number) =>
  API.get(`/api/strategy/logistics/${declarationId}`)

// ── Market & matchmaking ──────────────────────────────────────────────────────

export const getMarketOverview = (crop: string) =>
  API.get(`/api/market/${crop}`)

export const searchListings = (
  crop: string,
  params: {
    buyer_district_id: number
    quantity_kg?: number
    max_distance_km?: number
    max_price_ghs?: number
    min_quantity_kg?: number
    exclude_high_risk?: boolean
  },
) => API.get(`/api/match/${crop}`, { params })

// ── Recommendations ───────────────────────────────────────────────────────────

export const getRecommendations = (districtId: number) =>
  API.get(`/api/recommend/${districtId}`)

export const getFarmerRecommendations = (farmerId: number) =>
  API.get(`/api/recommend/farmer/${farmerId}`)

// ── Byproducts ────────────────────────────────────────────────────────────────

export const getByproducts = () =>
  API.get('/api/byproducts')

export const getByproductListings = (
  type: string,
  params?: { buyer_district_id?: number; quantity_kg?: number },
) => API.get(`/api/byproducts/${type}`, { params })

export const getFarmerByproducts = (farmerId: number) =>
  API.get(`/api/byproducts/farmer/${farmerId}`)

// ── Logistics ─────────────────────────────────────────────────────────────────

export const getLogisticsGroups = (save = false) =>
  API.get('/api/logistics/groups', { params: { save } })

export const getFarmerLogistics = (farmerId: number) =>
  API.get(`/api/logistics/farmer/${farmerId}`)

// ── Alerts ────────────────────────────────────────────────────────────────────

export const runAlerts = () =>
  API.post('/api/alerts/run')

export const getAlertLog = (farmerId: number, limit = 50) =>
  API.get(`/api/alerts/log/${farmerId}`, { params: { limit } })

// ── Delay classifier ─────────────────────────────────────────────────────────

export const getDelayPrediction = (districtId: number) =>
  API.get(`/api/delay/${districtId}`)

// ── Models status ─────────────────────────────────────────────────────────────

export const getModelsStatus = () =>
  API.get('/api/models/status')

// ── Admin reference data (live from DB) ───────────────────────────────────────

export const getAdminFarmers   = () => API.get('/api/admin/farmers')
export const getAdminMarkets   = () => API.get('/api/admin/markets')
export const getAdminDistricts = () => API.get('/api/admin/districts')
export const getAdminCrops     = () => API.get('/api/crops')
export const getAdminStats     = () => API.get('/api/stats')
export const getAdminRegions   = () => API.get('/api/regions')
export const getModelAccuracy  = () => API.get('/api/model-accuracy')
export const getPipelineStats  = () => API.get('/api/admin/pipeline/stats')

export const updateFarmerStatus = (id: number, action: 'approve' | 'decline') =>
  API.put(`/api/admin/farmers/${id}/status`, { action })

export default API
