# AgriMatch: Complete Backend and Data Science Technical Brief
### For Presentation Panel -- Every File, Every Layer, with Exact Line Numbers

---

## What AgriMatch Is

AgriMatch is an agricultural market-matching platform built for Ghana. It connects smallholder
farmers who have crops ready to harvest with buyers who need those crops, at the right price,
at the right time, from the nearest viable location. The platform collects satellite climate
data and market price data every day, runs machine learning models continuously in the
background, and makes all of this available through a web application and a feature-phone
menu system so that farmers without smartphones can still participate.

---

## How the Backend Is Organised

The backend is split into distinct layers. Each layer has one job and hands off to the next.

```
HTTP REQUEST (a browser or mobile app makes a request)
     |
     v
api/main.py              -- starts the server, loads models, registers all routes
     |
     v
api/security.py          -- checks that internal routes carry the correct secret key
     |
     v
api/validators.py        -- checks that phone numbers are valid Ghana numbers
     |
     v
api/routers/*.py         -- 11 route files (each group of URLs lives in its own file)
     |
     +---> api/services/      -- 4 service files (multi-step business logic lives here)
     |
     +---> models/*.py        -- 12 machine learning models + 3 business logic models
     |
     +---> db/
           |-- repositories/  -- 16 database query files (all SQL lives here, nowhere else)
           |-- models.py      -- 19 database table definitions
           +-- connection.py  -- opens and closes database connections

config/settings.py       -- reads all environment variables at startup
config/crop_map.py       -- translates 178 crop name variants into one standard name each
config/market_map.py     -- translates 65 market name variants into one standard name each
config/unit_map.py       -- converts 59 different units (bags, tubers, tins) into kilograms
config/crop_data.py      -- growth durations and peak harvest months for 14 crops

api/schemas/             -- 5 files that define the exact shape of every API response
utils/cache.py           -- stores frequently-read data in memory to avoid repeat DB calls
utils/geo.py             -- calculates straight-line distances between two GPS coordinates
utils/math_utils.py      -- safely converts any value to a number without crashing

ingestion/               -- the data pipeline (HDX prices, MoFA prices, climate, fuel, USSD)
api/payment_gateway.py   -- handles mobile money payments
alembic/                 -- manages database table creation and changes over time
tests/                   -- 20 automated test files
```

---

## LAYER 1: Application Entry Point

### File: api/main.py

This is the first file the server runs when it starts. It does four things: sets up
logging so every request is recorded, loads all machine learning models into memory
so they are ready instantly when a request arrives, registers every URL route so the
server knows where to send each request, and starts the background job scheduler
that runs daily tasks automatically.

| Item | Line | What it does |
|------|------|-------------|
| `_JsonFormatter` class | 52 | Writes every log line as a JSON object so monitoring tools can read them |
| `_configure_logging()` | 65 | Sets the log format and detail level once when the server starts |
| `lifespan()` | 85 | Runs startup code (load models) and shutdown code (stop scheduler) around the server's life |
| `_ALLOWED_ORIGINS` | 77 | Lists the web addresses that are allowed to call this API from a browser |
| `limiter` | 178 | Limits how many requests a single IP address can make per minute to prevent abuse |
| `_log_requests` middleware | 193 | Records every request with its URL, result code, and how long it took |
| `_unhandled_exception_handler` | 209 | If something goes wrong, returns a safe generic error instead of leaking internal details |
| `health()` GET /health | 220 | A simple "are you alive" check used by the hosting platform (Railway) |

#### Background jobs that run inside the server (lines 143-167)

These four jobs run on a timer inside the running server process itself. The heavier
daily jobs (price ingestion, climate data) run in a separate process managed by
`ingestion/scheduler.py`.

| Job name | When it runs | What it does |
|----------|-------------|-------------|
| delay_update | Every day at 07:30 UTC | Updates farmers' expected harvest dates based on current weather stress |
| coop_logistics | Every day at 22:00 UTC | Groups nearby farmers with similar harvest dates into shared truck trips |
| alerts_daily | Every day at 08:00 UTC | Checks all alert conditions and sends SMS messages to farmers |
| xgb_reload | Every 6 hours | Checks if new price prediction models have been trained and swaps them in |

#### All route groups registered at startup (lines 250-263)

```python
app.include_router(m3_router)          # /api/farmers/register, /api/declarations
app.include_router(admin_router)       # /api/admin/*
app.include_router(reference.router)   # /api/crops, /api/regions, /api/stats
app.include_router(forecasting.router) # /api/forecast/{crop}/{market}
app.include_router(listings.router)    # /api/listings, /api/farmers/{id}/profile
app.include_router(prices.router)      # /api/prices/history/{crop}
app.include_router(advisory.router)    # /api/planting/advisory, /api/roi
app.include_router(matchmaking.router) # /api/match/{crop}, /api/recommend/{district}
app.include_router(strategy.router)    # /api/strategy/farmer/{id}
app.include_router(logistics.router)   # /api/logistics/groups, /api/byproducts
app.include_router(alerts.router)      # /api/alerts/run, /api/alerts/log/{id}
app.include_router(reservations.router)# /api/reservations
app.include_router(demand.router)      # /api/demand
app.include_router(ussd_routes.router) # /api/ussd
```

---

## LAYER 2: Configuration

### File: config/settings.py

Environment variables are values set on the server outside the code. They store
sensitive information like database passwords and API keys without putting them in the
source code. This file reads all of those variables when the server starts. If a
required variable is missing, the server refuses to start and prints a clear error
message so the operator knows exactly what is missing.

```python
# config/settings.py line 10
class _Settings(BaseSettings): ...
```

| Variable | Purpose |
|----------|---------|
| DATABASE_URL | The address and password for the PostgreSQL database |
| AT_API_KEY | The key for Africa's Talking (sends SMS and handles USSD menus) |
| AT_CALLBACK_TOKEN | A token that proves an incoming USSD request came from Africa's Talking |
| INTERNAL_API_SECRET | A shared password that protects admin-only routes |
| LOG_LEVEL | How much detail to write to the logs |
| INGEST_CRON | The schedule for the data ingestion pipeline |

```python
# config/settings.py line 43
@model_validator(mode="after")
def _warn_missing_optional_vars(self): ...
```

If optional variables like `AT_API_KEY` are missing, the server logs a WARNING at
startup so the operator can see which features will not work, without the server
crashing entirely.

---

### File: config/crop_map.py

Market price data comes from two external sources (WFP and the Ministry of Food and
Agriculture). Each source names crops differently. This file is a lookup table that
converts 178 different crop name variations into one consistent internal name so that
price data from both sources can be compared.

```python
# config/crop_map.py line 10
CROP_MAP = {...}   # 178 entries
```

Example: "maize", "maize (yellow)", "corn", and "yellow corn" all become `"maize"`.
Any crop name not found in this table is rejected and stored separately for review.

```python
# config/crop_map.py line 182
BYPRODUCT_CROPS = [...]  # 9 crops that generate usable post-harvest material
```

Cassava, maize, rice, yam, plantain, sorghum, groundnut, cocoyam, and ginger. When a
farmer declares a harvest of any of these, the platform automatically creates a
byproduct listing (for example, cassava peels or maize stalks).

---

### File: config/market_map.py

Same idea as the crop map but for market locations. Different data sources spell market
names differently. This table maps 65 market name variants to one standard name and
also records which of Ghana's 16 administrative regions each market is in.

```python
# config/market_map.py line 10
MARKET_MAP = {...}   # 65 entries
```

Markets not found in this table are still accepted but labelled "unverified_market"
rather than rejected, because a price from an unknown market is still useful data.

---

### File: config/unit_map.py

Price data arrives in many different units: "50kg bag", "tin", "basket", "tuber",
"mudu", and many more. To compare prices across markets and crops, everything must
be converted to price per kilogram. This table maps 59 unit strings to their kilogram
equivalent.

```python
# config/unit_map.py line 15
UNIT_MAP = {...}   # 59 entries
```

Units that cannot be converted to a weight (for example, "pcs" or "bundle") map to
`None` and the price row is set aside, because there is no reliable way to compare
a per-piece price with a per-kilogram price.

---

### File: config/crop_data.py

This file stores agricultural knowledge about 14 crops: how long each takes to grow
(in days), which months are the peak harvest months, and a display label. The planting
advisory service and the crop recommendation model both use this data.

```python
# config/crop_data.py line 1
CROP_SEASONS = {...}   # 14 crops with days, peak_months, label
```

---

## LAYER 3: Security

### File: api/security.py

Some API routes should only be callable by internal services, not by the public. For
example, the route that triggers SMS alerts or updates farmer statuses should not be
accessible to anyone who discovers the URL.

This file provides a security check. Any route that uses it will first verify that
the incoming request carries the correct secret key in its header. The wrong key or
a missing key results in a 403 Forbidden response and the route code never runs.

```python
# api/security.py line 7
_INTERNAL_SECRET = settings.INTERNAL_API_SECRET

# api/security.py line 10
async def require_internal(x_api_secret: str = Header(default="")): ...
```

```python
# api/security.py line 18
hmac.compare_digest(received_secret, _INTERNAL_SECRET)
```

The comparison uses `compare_digest` instead of a simple equals check. A plain equals
check stops as soon as it finds a mismatched character, which means a well-timed
attacker can guess the secret one character at a time by measuring how long the
comparison takes. `compare_digest` always takes the same amount of time regardless
of where the mismatch is, which closes that vulnerability.

---

## LAYER 4: Input Validation

### File: api/validators.py

This file contains one reusable function that checks whether a phone number is a valid
Ghana mobile number. It is used in two different places (the reservations route and
the buyer demand schema) so the rule lives in one place rather than being copied.

```python
# api/validators.py line 5
_GHANA_PHONE = re.compile(r'^(\+233|0)[0-9]{9}$')

# api/validators.py line 8
def validate_ghana_phone(v: str) -> str: ...
```

A number that does not match the pattern causes the request to fail immediately with
a 422 Unprocessable Entity response before any business logic runs.

---

## LAYER 5: Dependency Injection

### File: api/dependencies.py

Loading a machine learning model from disk takes time (half a second to two seconds).
If the server reloaded the model for every request, it would be far too slow. Instead,
all 12 models are loaded once at startup and stored in the server's memory. This file
provides short accessor functions that route handlers use to retrieve the already-loaded
model they need.

During testing, these accessors are replaced with simple stub objects so tests do not
need real models.

| Function | Line | Returns |
|----------|------|---------|
| get_xgb | 17 | The XGBoost price prediction model |
| get_lstm | 21 | The LSTM (neural network) price prediction model |
| get_delay_clf | 25 | The harvest delay classifier |
| get_recommender | 29 | The crop recommendation model |
| get_strategy | 33 | The strategy card generator |
| get_matcher | 37 | The buyer-seller matching engine |
| get_coop | 41 | The cooperative logistics engine |
| get_byproduct | 45 | The byproduct marketplace model |
| get_alerts | 49 | The SMS alert engine |
| get_logistics | 53 | The logistics cost calculator |
| get_payment_gateway | 57 | The mobile money payment handler |
| get_ussd_handler | 61 | The feature-phone menu handler |

---

## LAYER 6: API Response Schemas

API response schemas define the exact shape of every response the server sends. If a
route handler accidentally returns the wrong field name or the wrong data type, the
server catches it before the response is sent. This guarantees that the frontend always
receives data in the format it expects.

### File: api/schemas/admin.py

| Class | Line | Purpose |
|-------|------|---------|
| AdminFarmerItem | 8 | One row in the admin farmer list |
| FarmerStatusResponse | 19 | Response after updating a farmer's active status |
| AdminMarketItem | 25 | One market with its most recent price date |
| DistrictItem | 37 | One district with its GPS coordinates |
| CropItem | 45 | One crop reference entry |
| StatsResponse | 53 | Overall platform statistics (total listings, total value) |
| RegionItem | 60 | One region with farmer and market counts |
| ModelAccuracyItem | 66 | Prediction accuracy figures for one model |
| IngestionRunItem | 74 | One data pipeline run with row counts and status |
| PipelineStatsResponse | 82 | Summary of recent pipeline health |
| USSDStatsResponse | 87 | Feature-phone session statistics |

### File: api/schemas/common.py

| Class | Line | Purpose |
|-------|------|---------|
| HealthCheck | 4 | The response shape for the /health endpoint |

### File: api/schemas/demand.py

| Class | Line | Purpose |
|-------|------|---------|
| BuyerRequestIn | 9 | What a buyer must send when posting a demand request |
| CreateDemandResponse | 24 | The ID and creation timestamp returned after a demand is posted |
| DemandItem | 29 | One open buyer request in the demand list |

The phone number field in `BuyerRequestIn` is validated at line 18 using the shared
Ghana phone validator from `api/validators.py`.

### File: api/schemas/listings.py

| Class | Line | Purpose |
|-------|------|---------|
| ListingItem | 6 | One active farm declaration (crop, quantity, price, location) |
| ListingsResponse | 25 | A paginated set of listings with a total count |

### File: api/schemas/reservations.py

| Class | Line | Purpose |
|-------|------|---------|
| ReservationResponse | 6 | The payment outcome and reservation ID returned after booking |
| BuyerReservationItem | 15 | One reservation in a buyer's booking history |

---

## LAYER 7: API Routers

Route files receive HTTP requests, validate the inputs, call the appropriate service
or model, and return a typed response. They do not contain business logic -- that
lives in the service layer. Each URL group has its own file.

### File: api/admin_router.py

All nine admin routes require the internal secret key (set at the router level at
line 26-30). A request without the correct key is rejected before it reaches any
handler.

| Route | Method | Path | Handler line | Response type |
|-------|--------|------|-------------|--------------|
| list_farmers | GET | /api/admin/farmers | 35 | List of AdminFarmerItem |
| update_farmer_status | PUT | /api/admin/farmers/{id}/status | 59 | FarmerStatusResponse |
| list_markets | GET | /api/admin/markets | 74 | List of AdminMarketItem |
| list_districts | GET | /api/admin/districts | 97 | List of DistrictItem |
| list_crops | GET | /api/admin/crops | 116 | List of CropItem |
| summary_stats | GET | /api/admin/stats | 135 | StatsResponse |
| list_regions | GET | /api/admin/regions | 150 | List of RegionItem |
| model_accuracy | GET | /api/admin/model-accuracy | 167 | List of ModelAccuracyItem |
| pipeline_stats | GET | /api/admin/pipeline/stats | 176 | PipelineStatsResponse |

```python
# api/admin_router.py line 55
class FarmerStatusBody(BaseModel): ...  # the request body for the PUT status route
```

---

### File: api/routers/reference.py

Public read-only routes that return reference data (crops, regions, stats). Results
are stored in memory for one hour so the database is not queried on every single page
load.

```python
# api/routers/reference.py line 17
_cache = TtlCache(ttl=3600)  # TTL means "time to live" -- data is kept for 3600 seconds (1 hour)
```

| Route | Method | Path | Line |
|-------|--------|------|------|
| public_crops | GET | /api/crops | 20 |
| public_regions | GET | /api/regions | 41 |
| public_stats | GET | /api/stats | 62 |
| public_model_accuracy | GET | /api/model-accuracy | 81 |
| models_status | GET | /api/models/status | 106 |

If the database is unavailable, these routes return 503 Service Unavailable. The one
exception is any route whose result is already in the memory cache, which will still
work for up to one hour.

---

### File: api/routers/prices.py

Returns historical price data and a live market bulletin.

```python
# api/routers/prices.py line 11
_cache = TtlCache(ttl=3600)
```

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| price_history | GET | /api/prices/history/{crop} | 19 | Monthly averages, default 18 months |
| price_markets | GET | /api/prices/markets/{crop} | 27 | Which markets have data for this crop |
| market_bulletin | GET | /api/market-bulletin | 34 | Latest price per crop per market, with 30-day change |

The market bulletin calculates the percentage price change by comparing today's price
against the price from 30 days ago. Division by zero is prevented using `NULLIF` in
the SQL query.

---

### File: api/routers/listings.py

Returns active farm declarations and individual farmer profiles.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| farmer_profile | GET | /api/farmers/{farmer_id}/profile | 14 | Full profile with sales history |
| all_listings | GET | /api/listings | 62 | Filter by region, crop, and result limit (1-500) |
| fresh_listings | GET | /api/listings/fresh | 75 | Only listings with harvest date in the future |
| best_prices | GET | /api/listings/best | 84 | Sorted by highest forecast price |

```python
# api/routers/listings.py line 43
def _listing_row(r): ...  # converts a raw database row into a clean typed dictionary
```

---

### File: api/routers/matchmaking.py

Finds the best available crop listings for a buyer and recommends what crops a
farmer or district should grow.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| match_listings | GET | /api/match/{crop} | 12 | Quantity capped at 500,000 kg to prevent absurd queries |
| market_overview | GET | /api/market/{crop} | 43 | Supply, demand, and price trend summary |
| recommend_for_farmer | GET | /api/recommend/farmer/{farmer_id} | 52 | Crop suggestions for a specific farmer |
| recommend_for_district | GET | /api/recommend/{district_id} | 67 | Crop suggestions for a district |

---

### File: api/routers/advisory.py

Returns planting advice and ROI (return on investment) calculations.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| planting_advisory | GET | /api/planting/advisory | 13 | Best time to plant based on weather and season |
| roi_calculator | GET | /api/roi | 19 | Net profit forecast after transport costs |

---

### File: api/routers/strategy.py

Returns human-readable strategy cards telling farmers when to sell and buyers where
to source from.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| strategy_for_farmer | GET | /api/strategy/farmer/{farmer_id} | 9 | Sell-timing strategy for all active declarations |
| strategy_for_buyer | GET | /api/strategy/buyer/{district_id}/{crop} | 24 | Sourcing options ranked by landed cost |
| strategy_logistics | GET | /api/strategy/logistics/{declaration_id} | 41 | Co-shipping opportunity for one declaration |

---

### File: api/routers/alerts.py

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| alerts_run | POST | /api/alerts/run | 11 | Manually triggers all SMS alert checks (protected route) |
| alerts_log | GET | /api/alerts/log/{farmer_id} | 17 | Returns the SMS alert history for one farmer |

---

### File: api/routers/forecasting.py

Returns price forecasts from the machine learning models.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| get_forecast | GET | /api/forecast/{crop}/{market} | 14 | XGBoost 30/60/90-day price forecast |
| get_all_forecasts | GET | /api/forecast/{crop} | 27 | Forecast for all markets for a crop |
| get_lstm_forecast | GET | /api/forecast/lstm/{crop}/{market} | 39 | Neural network price forecast |
| get_delay_prediction | GET | /api/delay/{district_id} | 52 | Predicted harvest delay due to weather stress |
| update_declarations | POST | /api/delay/update-declarations | 64 | Updates all farmer harvest dates (protected route) |

---

### File: api/routers/reservations.py

Handles crop reservations. A buyer chooses a listing, enters their mobile money
number, and the platform charges them and locks the quantity.

```python
# api/routers/reservations.py line 16
class ReservationRequest(BaseModel):
    declaration_id: int = Field(gt=0)
    buyer_phone:    str
    buyer_name:     str = Field(default="", max_length=120)
    quantity_bags:  int = Field(default=1, ge=1, le=500)
    momo_phone:     str

# line 23: both phone fields are checked against the Ghana phone number pattern
```

| Route | Method | Path | Line | Status code |
|-------|--------|------|------|------------|
| create_reservation | POST | /api/reservations | 35 | 201 Created |
| buyer_reservations | GET | /api/reservations/buyer/{phone} | 52 | 200 OK |

---

### File: api/routers/logistics.py

Returns cooperative logistics groups and byproduct marketplace listings.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| logistics_groups | GET | /api/logistics/groups | 14 | save=False runs as a preview without writing to DB |
| logistics_for_farmer | GET | /api/logistics/farmer/{farmer_id} | 29 | Groups the farmer belongs to |
| byproducts_overview | GET | /api/byproducts | 38 | All available byproduct types |
| farmer_byproducts | GET | /api/byproducts/farmer/{farmer_id} | 44 | Byproducts for one farmer |
| search_byproducts | GET | /api/byproducts/{byproduct_type} | 53 | Search byproducts with distance filter |
| run_transport_match | POST | /api/transport/match | 64 | Assigns pending jobs to providers (protected route) |

---

### File: api/routers/demand.py

Buyers can post what crops they are looking for and in what quantity.

| Route | Method | Path | Line | Status code |
|-------|--------|------|------|------------|
| post_demand | POST | /api/demand | 10 | 201 Created |
| list_demand | GET | /api/demand | 27 | 200 OK |

---

### File: api/routers/ussd_routes.py

USSD is the text-menu system that runs on feature phones. Africa's Talking sends an
HTTP POST to this route every time a farmer presses a key on their phone.

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| ussd_callback | POST | /api/ussd | 16 | Receives keypresses from Africa's Talking as form data |
| ussd_stats | GET | /api/admin/ussd/stats | 38 | Session analytics (protected route) |

The request comes as form-encoded body (not JSON) because that is the format Africa's
Talking uses. The `token` query parameter is checked against `AT_CALLBACK_TOKEN` to
confirm the request genuinely came from Africa's Talking.

---

## LAYER 8: Service Layer

Services contain multi-step business logic that is too complex for a route handler.
A route handler should do one thing: receive a request and return a response. Anything
involving multiple decisions, multiple database queries, or coordinating between
systems belongs in a service.

### File: api/services/reservation_service.py

This is the most critical service in the platform. It handles the money. The sequence
of steps is carefully ordered to protect farmers and buyers from double-charges and to
handle failures gracefully.

```python
# line 16: BAG_KG = 100      (one standard bag weighs 100 kg)
# line 19: def _generate_ref() -> str    (creates a unique reference like "AGM-1749801234-7f3a")
# line 25: class ReservationService
# line 27: @staticmethod def create(...)
```

#### The 11 steps of a reservation (lines 39-124)

```
Step 1  (39)  Generate a unique reference string for this reservation
Step 2  (46)  Read the current price from the database without locking anything
Step 3  (50)  Calculate the expected payment amount (bags x 100kg x price per kg)
Step 4  (57)  Charge the buyer's mobile money account
Step 5  (58)  If the charge fails, stop here and return a failure response
Step 6  (74)  Lock the crop declaration row so no other buyer can touch it simultaneously
Step 7  (81)  Check that there is still enough quantity available
Step 8  (94)  Re-read the price from the locked row (price may have changed since Step 2)
Step 9  (99)  Write the reservation and payment record to the database in one transaction
Step 10 (110) If the database write fails, refund the mobile money charge automatically
Step 11 (117) Return success to the buyer
```

Why charge before locking? Mobile money charges take 1-3 seconds. Holding a database
lock for that long would block every other buyer from purchasing anything during that
time. By charging first, the lock is only held for a few milliseconds while the
database writes happen. If two buyers try to buy the same last bag simultaneously,
only one succeeds and the other is automatically refunded.

---

### File: api/services/admin_service.py

```python
# line 9: class AdminService
# line 11: @staticmethod def get_model_accuracy(db, limit=20)
#   Reads model performance records and converts MAPE (mean absolute percentage error)
#   into a percentage accuracy figure that is easier to present.
# line 27: @staticmethod def get_market_status(last_price_date)
#   Returns "live" if the market has had a price in the last 3 days, "stale" otherwise.

# line 34: class UssdService
# line 36: @staticmethod def get_stats(db)
#   Returns 6 analytics figures: sessions today, sessions this week, total completed
#   declarations, average session duration in minutes, the menu step where most users
#   drop off, and how many sessions are active right now (active = last keystroke
#   within the past 10 minutes).
```

---

### File: api/services/planting_service.py

```python
# line 10: def _climate_risk(flag, csi) -> tuple
#   Reads the current Crop Stress Index for the district.
#   CSI above 0.75 is classified as high risk.
#   CSI above 0.55 is moderate risk.
#   Below 0.55 is low risk.

# line 18: def _next_peak() -> date
#   Looks up the crop's peak harvest months from config/crop_data.py and
#   calculates the next date when that peak month begins.

# line 31: def _planting_advice(days_to_plant) -> tuple
#   Converts a number of days into a human-readable planting recommendation:
#   0 or fewer days  -> "plant_now"
#   Up to 14 days    -> "plant_soon"
#   Up to 45 days    -> "prepare"
#   More than 45     -> "wait"

# line 41: class PlantingService
# line 43: @staticmethod def get_advice(district_id, crop="")
#   Supports 6 crops: maize, tomato, cassava, onion, rice, plantain.
#   Returns the crop name, risk level, advice label, days until planting,
#   date of the next peak harvest window, and the current stress index value.
```

---

### File: api/services/roi_service.py

ROI means Return on Investment. Given a crop, a quantity, a source district, and a
destination market, this service forecasts the gross revenue from selling the crop,
deducts the transport cost, and returns the net profit and margin percentage.

```python
# line 7: class RoiService
# line 9: @staticmethod def calculate(crop, quantity_kg, source_district_id,
#                                      target_district_id, xgb, logistics)

# Price hierarchy (lines 28-39):
#   First choice:  XGBoost 30-day price forecast for that crop and market
#   Fallback:      The most recent actual price from the clean_prices table

# Calculations (lines 41-62):
#   gross_revenue = quantity_kg x forecast price per kg
#   transport_cost = LogisticsCostModel.get_delivery_cost(source, target, quantity)
#   net_revenue = gross_revenue minus transport_cost
#   margin = (net_revenue / gross_revenue) x 100

# Returns: crop, quantity, districts, forecast price, gross revenue, transport cost,
#          net revenue, and margin percentage
```

---

## LAYER 9: Payment Gateway

### File: api/payment_gateway.py

This file defines how mobile money payments work. It uses an abstract base class,
which is a programming pattern that says "any payment gateway must have a charge
method and a refund method, but each gateway can implement them differently." This
makes it easy to swap in a real MTN MoMo or Vodafone Cash gateway in the future
without changing any of the reservation logic.

```python
# line 7:  def _detect_provider(phone) -> str
#   Reads the phone number prefix to identify the network:
#   024/054/055/059 -> "MTN MoMo"
#   020/050         -> "Vodafone Cash"
#   027/057/026/056 -> "AirtelTigo Money"

# line 19: ChargeResult dataclass   (success flag, provider name, message)
# line 26: RefundResult dataclass   (success flag, message)
# line 32: class PaymentGateway (abstract base class -- defines the interface)

# line 46: class SimulatedGateway (the implementation used in development and testing)
# line 55:   _FAILURE_RATE = 0.10  (10% of charges randomly fail)
# line 59:   _charges dictionary   (stores completed charges by reference key)
# line 61:   charge()              (returns the cached result if the same key is used again)
# line 80:   refund()              (removes the key from the store)
```

The 10 percent failure rate is intentional. It ensures the test suite automatically
exercises the refund path, so the compensation logic is always verified.

---

## LAYER 10: Utility Layer

### File: utils/cache.py

A simple in-memory store. The server keeps a copy of frequently read data (like the
crop list or region statistics) in memory so it does not have to ask the database
every time. Each stored item has a time limit -- after the limit expires, the next
request fetches fresh data.

```python
# line 4:  class TtlCache   (TTL = Time To Live, how long data is kept in memory)
# line 7:  __init__(ttl=3600)   (default: data expires after 3600 seconds = 1 hour)
# line 11: def get(key)         -- returns stored data if not yet expired, otherwise None
# line 18: def set(key, data)   -- stores data with the current timestamp
# line 22: def get_or_set(key, fetcher)
#           If data is cached and fresh, return it.
#           If not, call fetcher() to get fresh data, cache it, and return it.
```

Used by `api/routers/reference.py` and `api/routers/prices.py`. Typical usage:
`_cache.get_or_set("crops", lambda: repo.get_crops(db))`

---

### File: utils/geo.py

Calculates the straight-line (as-the-crow-flies) distance between two points on
Earth given their latitude and longitude coordinates. Used when the road distance
between two districts has not been pre-calculated in the database.

```python
# line 4:  def haversine(lat1, lon1, lat2, lon2) -> float
#           Returns distance in kilometres.
# line 6:  R = 6371.0   (Earth's radius in kilometres)
```

---

### File: utils/math_utils.py

A single small function that converts any value to a decimal number safely. If the
value is missing, non-numeric, or the special "not a number" value, it returns 0.0
instead of crashing. Used anywhere raw database values might be empty or malformed.

```python
# line 1:  def safe_float(v) -> float
#           Returns 0.0 for any input that cannot be converted to a valid number.
```

---

## LAYER 11: Database Connection

### File: db/connection.py

Manages how the application connects to the PostgreSQL database. Database connections
are expensive to create (they involve a network handshake). A connection pool keeps
a set of connections open and ready to reuse, which makes every request faster.

```python
# line 21: def get_engine() -> Engine
#           Returns the database engine singleton (created once, reused forever)

# line 27: def get_session() -> ContextManager
#           Opens a session (a single unit of work with the database),
#           commits the work if everything succeeds,
#           rolls it back if anything fails.
```

#### Connection pool settings (lines 14-17)

| Setting | Value | Meaning |
|---------|-------|---------|
| pool_size | 10 | Keep 10 connections permanently open and ready |
| max_overflow | 5 | Allow up to 5 extra connections during busy periods |
| pool_pre_ping | True | Test each connection before using it (catches stale connections) |
| pool_recycle | 1800 | Replace connections that have been idle for 30 minutes |

`pool_pre_ping` is critical for Railway (the hosting platform). Railway closes idle
database connections after 30 minutes. Without this setting, the first request after
a quiet period would fail with a connection error.

---

## LAYER 12: Database ORM Models

### File: db/models.py

ORM stands for Object-Relational Mapper. It lets the code work with database tables
as if they were Python classes, without writing raw SQL for every operation. This file
defines all 19 database tables as class definitions. The migration tool (Alembic) reads
these class definitions to generate the SQL that creates the actual tables.

#### Reference tables (lookup data that does not change often)

| Class | Line | What it stores |
|-------|------|---------------|
| GhanaDistrict | 14 | All Ghana districts with their GPS coordinates and region name |
| GhanaMarket | 89 | All verified markets with their district, region, and hub status |
| CropReference | 102 | All supported crops with their name variants and unit conversions |

#### Price pipeline tables

| Class | Line | What it stores |
|-------|------|---------------|
| RawPrice | 28 | Original unprocessed price records exactly as received from sources |
| CleanPrice | 41 | Validated and normalised price records ready for analysis |
| PriceQuarantine | 63 | Price records that failed validation, kept for review |
| IngestionLog | 75 | A record of every data pipeline run with row counts and status |

#### Climate tables

| Class | Line | What it stores |
|-------|------|---------------|
| ChirpsDaily | 115 | Daily rainfall in mm per district (from satellite data) |
| NasaPowerDaily | 130 | Daily temperature, solar radiation, humidity, wind speed, and ET0 per district |
| SpiBaseline | 150 | Long-term average and variability of rainfall per district per month |
| ClimateIndicator | 165 | Computed daily stress indicators per district (SPI, ET0, CSI for each crop, risk flag) |

#### Farmer and declaration tables

| Class | Line | What it stores |
|-------|------|---------------|
| Farmer | 190 | Farmer accounts (name, phone, district, active status) |
| FarmerDeclaration | 205 | Crop declarations (what crop, how much, when it is ready, forecast price) |
| ByproductDeclaration | 236 | Post-harvest material available from a declaration (stalks, peels, husks) |
| UssdSession | 251 | Feature-phone session state (which menu step the user is on) |

#### Transport tables

| Class | Line | What it stores |
|-------|------|---------------|
| TransportProvider | 271 | Registered truck owners with vehicle type, capacity, and base rate |
| TransportJob | 297 | Assigned delivery jobs with pickup and destination districts |

#### Other tables

| Class | Line | What it stores |
|-------|------|---------------|
| FuelPrice | 325 | Daily diesel and petrol prices from the National Petroleum Authority |
| FeatureStore | 342 | The 24 computed input features used to train and run the ML models |
| DistrictDistance | 380 | Pre-calculated road distances between district pairs |
| LogisticsCost | 396 | Pre-calculated transport costs for common routes and cargo weights |
| ModelBaseline | 419 | Statistical baseline models (ARIMA) with their accuracy metrics |
| PriceForecast | 448 | Stored price forecasts from all models per crop and market |
| AlertLog | 472 | History of every SMS alert sent, including status and error details |
| Reservation | 493 | Confirmed crop reservations linking buyer to declaration |
| MoMoPayment | 514 | Mobile money payment records linked to reservations |

---

## LAYER 13: Repository Layer

All database queries live in repository classes and nowhere else. A repository class
has no business logic -- it just runs one query and returns the result. This rule
keeps the code clean: if you want to know what SQL the system runs, you look in one
place. If you want to change business logic, you look in a different place.

There are 16 repository files covering every part of the platform.

### File: db/repositories/listings_repo.py

```python
# line 8:  _SAFE_FILTERS = frozenset({...})
#   A whitelist of column names that are allowed to be used as filters.
#   This prevents a technique called SQL injection where an attacker sends
#   a carefully crafted filter value to read or destroy the database.

class ListingsRepo:
    # line 17: get_farmer_profile(db, farmer_id)
    #   One query that counts active listings, sales count, and total revenue
    #   for a single farmer using database-level aggregation.
    # line 42: get_all_active(db, region, crop, limit)
    # line 79: get_fresh(db, limit)       -- only listings with harvest date today or later
    # line 104: get_best_prices(db, limit) -- sorted by highest forecast price
```

---

### File: db/repositories/matchmaking_repo.py

```python
class MatchmakingRepo:
    # line 9:  get_median_price(db, crop)
    #   Calculates the middle price across all markets for a crop.
    #   Using the median instead of the average makes the result less affected
    #   by unusually high or low outliers.
    # line 22: get_road_km(db, from_did, to_did)
    # line 33: get_declaration_for_scoring(db, declaration_id)
    # line 43: search_listings(db, sql_params, exclude_csi, min_qty, max_price)
    # line 94: get_buyer_district_name(db, buyer_district_id)
    # line 102: get_market_summary(db, date_range)
    # line 117: get_csi_distribution(db, date_range)
    # line 128: get_regional_supply(db, date_range)
    # line 143: get_surge_weeks(db, date_range)  -- weeks where 5 or more new listings appeared
```

---

### File: db/repositories/reservation_repo.py

```python
class ReservationRepo:
    # line 7:  insert_reservation(db, declaration_id, buyer_phone, buyer_name,
    #                              quantity_bags, unit_price, total)
    #   Writes the reservation record and returns the new ID.
    # line 33: insert_payment(db, reservation_id, provider, phone, amount, reference)
    #   Writes the payment record in the same database transaction as the reservation.
    # line 54: get_buyer_reservations(db, phone)
    #   Returns all reservations for a buyer with crop name and location included.
```

---

### File: db/repositories/demand_repo.py

```python
class DemandRepo:
    # line 13: create(db, crop, quantity_kg, region, target_date, buyer_name, buyer_phone, notes)
    #   Writes a new buyer demand request and returns its ID and creation timestamp.
    # line 39: list_open(db, crop, region, limit)
    #   Returns open demand requests, optionally filtered by crop and region.
```

---

### File: db/repositories/admin_repo.py

```python
class AdminRepo:
    # line 8:  list_farmers(db)
    #   Returns all farmers with their active listing count aggregated in one query.
    # line 26: update_farmer_status(db, farmer_id, status)
    # line 34: list_markets(db)
    #   Markets with no recent price data appear at the bottom of the list.
    # line 51: list_districts(db)
    # line 59: list_crops(db)
    # line 67: get_stats(db)
    #   Platform totals: active farmers, markets, declarations, and total crop value.
    # line 81: list_regions(db)
    # line 94: get_model_accuracy(db)
    # line 107: get_pipeline_stats(db)  -- most recent run per data source
```

---

### File: db/repositories/advisory_repo.py

```python
class AdvisoryRepo:
    # line 8:  get_climate(db, district_id, crop)
    #   Reads the latest climate stress indicators for a district and crop.
    # line 20: get_nearest_market(db, district_id)
    #   Finds the closest verified market to a district using pre-calculated road distances.
    # line 33: get_latest_price(db, crop, market)
    # line 40: get_district_name(db, district_id)
```

---

### File: db/repositories/alerts_repo.py

```python
class AlertsRepo:
    # line 8: get_for_farmer(db, farmer_id, limit=50)
    #   Returns the 50 most recent SMS alerts for a farmer, newest first.
```

---

### File: db/repositories/byproduct_repo.py

```python
class ByproductRepo:
    # line 10: search_with_distance(db, byproduct_type, buyer_district_id, quantity_kg)
    #   Finds available byproducts within a 90-day window, ranked by distance to buyer.
    # line 49: search_without_buyer(db, byproduct_type)
    # line 83: get_all_byproduct_types(db)
    #   Returns each byproduct type with a list of regions where it is available.
    # line 102: get_farmer_byproducts(db, farmer_id)
```

---

### File: db/repositories/cooperative_logistics_repo.py

```python
class CooperativeLogisticsRepo:
    # line 15: get_markets_with_coords(db)
    # line 26: get_or_create_platform_provider(db)
    #   Looks up the platform's own default transport provider. If it does not exist
    #   yet, creates it. The operation is safe to run multiple times without duplicating.
    # line 46: get_road_km(db, from_did, to_did)
    # line 53: get_active_declarations_in_window(db, today, window_to)
    # line 68: get_distances_for_districts(db, district_ids)
    #   Fetches road distances for a whole list of districts in one query,
    #   avoiding the N+1 problem (where a loop makes one query per district).
    # line 77: get_farmer_active_declaration_ids(db, farmer_id)
    # line 84: get_transport_jobs_for_declarations(db, declaration_ids)
    # line 96: get_job_summary(db, job_ids)
    # line 115: get_declarations_details(db, declaration_ids)
    # line 124: get_co_farmers(db, declaration_ids)
    # line 134: get_farmer_ids_for_declarations(db, declaration_ids)
    # line 141: insert_transport_job(db, ...)
    #   Saves a new transport job. Declaration and farmer ID lists are stored as JSON
    #   since PostgreSQL does not have a native array of integers in all contexts.
```

---

### File: db/repositories/crop_recommender_repo.py

```python
class CropRecommenderRepo:
    # line 11: get_climate_indicators_latest(db, district_id)
    #   Latest stress scores for all 6 supported crops in a district.
    # line 25: get_regional_supply(db, region)
    #   Total kilograms of each crop currently declared for sale in the region.
    # line 48: get_district_coords(db, district_id)
    # line 60: get_markets_with_coords(db)
    # line 72: get_bulk_data(db, district_id, region)
    #   Runs 4 queries in one database session to load all the data the recommender
    #   needs in a single round-trip instead of 4 separate round-trips.
    # line 135: get_farmer_info(db, farmer_id)
```

---

### File: db/repositories/declaration_repo.py

```python
class DeclarationRepo:
    # line 8:  get_price(db, declaration_id)
    #   Reads the forecast price without locking the row (used for preview calculations).
    # line 17: lock_active(db, declaration_id)
    #   Reads the row AND locks it so no other process can modify it until this
    #   database transaction finishes. Used during reservation to prevent overselling.
    # line 27: reserved_bags(db, declaration_id)
    #   Counts how many bags have already been reserved. Returns 0 if none.
    # line 37: get_active_by_farmer(db, farmer_id)
    # line 47: get_all_active(db)
```

---

### File: db/repositories/delay_classifier_repo.py

```python
class DelayClassifierRepo:
    # line 8:  get_climate_indicators(db, district_id)
    #   Reads the 3 most recent daily climate rows for a district.
    #   Having 3 rows provides the lag features (yesterday, day before) that the
    #   classifier uses to detect a worsening weather trend.
    # line 22: get_active_declarations(db)
    # line 34: update_declaration_delay(db, declaration_id, flag_level, delay_days, harvest_date)
    #   Writes the new adjusted harvest date and current stress flag to the declaration.
```

---

### File: db/repositories/prices_repo.py

```python
class PricesRepo:
    # line 12: get_price_history(db, crop, market, months)
    #   Groups daily prices into monthly averages, with min, max, and data point count.
    # line 47: get_markets_for_crop(db, crop)
    # line 55: get_bulletin(db)
    #   Returns the single most recent price per crop-market combination.
    #   Then joins each current price against the price from 30 days ago to calculate
    #   the percentage change. If there was no price 30 days ago, the change is NULL.
```

---

### File: db/repositories/reference_repo.py

```python
class ReferenceRepo:
    # line 8:  get_crops(db)
    # line 16: get_regions(db)
    #   Each region includes a count of its markets and districts.
    # line 29: get_stats(db)
    #   Calculates total active listings, total supply in kg, and total value
    #   (sum of quantity_kg times forecast price for every active declaration).
    # line 43: get_model_accuracy(db)
```

---

### File: db/repositories/strategy_repo.py

```python
class StrategyRepo:
    # line 9:  get_district_centroid(db, district_id)
    # line 16: get_all_markets_with_coords(db)
    # line 27: get_active_declaration(db, declaration_id)
    #   Includes the farmer's name, stress flag, and adjusted harvest date.
    # line 40: get_nearby_supplier_listings(db, crop, region, qty, limit=5)
    #   Finds listings within a 60-day harvest window sorted by lowest price first.
    # line 65: get_logistics_declaration(db, declaration_id)
    # line 76: get_nearby_declarations(db, declaration_id, window_days=3, limit=10)
    #   Finds other declarations within 3 days and 50 km -- candidates for co-shipping.
    # line 110: get_active_declaration_ids(db, farmer_id)
```

---

### File: db/repositories/ussd_repo.py

```python
class UssdRepo:
    # line 8: get_stats(db)
    #   Returns 6 analytics figures for the USSD (feature-phone) system:
    #   - Sessions started today
    #   - Sessions started this week
    #   - Total declarations completed through the phone menu
    #   - Average session duration in minutes
    #   - The menu step where most users stopped (the main drop-off point)
    #   - Sessions active right now (last keystroke within the past 10 minutes)
```

---

## LAYER 14: Database Migrations

### File: alembic/versions/0001_initial_schema.py

```
revision      = "0001"
down_revision = None   (this is the very first migration)
```

Alembic is the tool that manages changes to the database structure over time. When
the application is deployed for the first time, running `alembic upgrade head` creates
all 25 tables in the correct order (respecting foreign key dependencies). The
`downgrade()` function drops them all in reverse order if a rollback is needed.

For a database that already exists: `alembic stamp head` tells Alembic the tables
are already current without re-running the migration.

---

## LAYER 15: Ingestion Pipeline

The ingestion pipeline is responsible for bringing external data into the database
every day. It runs as a separate process managed by APScheduler (a Python job
scheduling library) with 14 registered jobs. Each job runs on a fixed schedule and
is independent of the others.

---

### File: ingestion/hdx_client.py

HDX is the Humanitarian Data Exchange, run by the United Nations World Food Programme.
It publishes weekly market price data for Ghana in CSV format. This client downloads
that data, processes it in batches of 500 rows, and stores the raw records in the
database for the validation and transformation pipeline to clean.

```python
# line 15: _HDX_API = "https://data.humdata.org/api/3/action/package_show"
#   The WFP publishes datasets through a standard API called CKAN.
#   This URL is the CKAN endpoint that returns the download link for the Ghana dataset.

# line 16: _BATCH = 500   (how many rows to insert at once to stay within DB limits)

class HDXClient:
    # line 26: get_csv_url()
    #   Calls the CKAN API to get the most recent CSV download link.
    # line 61: download_csv()
    #   Streams the CSV file in 65-kilobyte chunks to avoid loading the whole file
    #   into memory at once (the file can be several MB).
    # line 87: save_raw_rows()
    #   Writes batches of 500 rows into the raw_prices table.
    # line 125: run()
    #   Orchestrates the three steps: get link, download, save.
```

---

### File: ingestion/mofa_client.py

MoFA is Ghana's Ministry of Food and Agriculture. They publish weekly price reports
as Excel files. This client reads those Excel files, detects which row and column
contain the actual data (the header can be on any row), and saves the raw records.

```python
# line 25: _SOURCE = "mofa_srid"    (identifies this source in the ingestion log)
# line 26: _SKIP_SHEET_KEYWORDS = {"cover", "summary", "contents"}
#   Sheets whose name contains these words are skipped because they contain
#   formatting and notes, not price data.
# line 27: _BATCH = 500

class MoFAClient:
    # line 37: get_unprocessed_files()
    #   Scans the inbox folder for Excel files not yet in the ingestion log.
    # line 74: detect_header_row()
    #   Scans the first 10 rows of each sheet for the words "market" and "price"
    #   to find where the actual data table starts (it is not always row 1).
    # line 104: parse_xlsx()
    #   Reads the Excel file, skips irrelevant sheets, forward-fills merged region
    #   cells (Excel often merges the first column across several rows for a region name).
    # line 172: save_raw_rows()
    # line 207: run()
    # line 281: _write_log()   -- records the outcome of processing each file
```

---

### File: ingestion/validators.py

Before any price record is stored in the clean prices table, it must pass a set of
checks. This file runs those checks. It operates on raw records before any
transformation happens, so it works with messy, inconsistent input.

```python
# line 22: _MAX_PRICE_RAW   = 100,000
#   Any price above 100,000 (in any currency) is likely a data entry error.
# line 26: _MAX_PRICE_PER_KG_GHS = 5,000
#   After converting to GHS per kg, anything above 5,000 GHS per kg is rejected.
#   This catches unit mismatches (for example, a price recorded per tonne entered
#   as if it were per kg).

# line 89: def validate_row(row) -> (bool, reason_or_None)
#   Runs 6 checks on every row:
#   1. Date field exists and can be parsed
#   2. Date is not in the future
#   3. Market field exists and is not empty
#   4. Commodity field exists and is not empty
#   5. Price exists, is a number, is positive, and is below 100,000
#   6. Currency is GHS or USD
#   7. Price per kg (after conversion) is below 5,000 GHS
#   Returns True if all checks pass, or False with the reason for rejection.

# line 191: def validate_batch(rows)
#   Runs validate_row on every row in a batch and returns two lists:
#   the rows that passed and the rows that failed (with rejection reasons).
```

---

### File: ingestion/transformers.py

Once a row has been validated, it needs to be standardised. Different sources use
different crop names, different units, and different market names. This file converts
everything to the platform's internal standard.

```python
# line 134: def transform_hdx_row(row, raw_id)
#   8-step pipeline for one WFP price record:
#   1. Look up the crop name in CROP_MAP to get the internal name
#   2. Look up the unit in UNIT_MAP to get the kg conversion factor
#   3. Divide the price by the kg factor to get price per kg
#   4. Convert to GHS if the currency is USD
#   5. Round to 2 decimal places
#   6. Look up the market name in MARKET_MAP to get the canonical name and region
#   7. Parse the date into a consistent format
#   8. Return a clean dictionary ready for database insertion

# line 488: def load_to_database(db, clean_rows, quarantine_rows, source, rows_fetched)
#   1. Checks which clean rows already exist in the database to avoid duplicates
#   2. Inserts the new rows in bulk (much faster than one at a time)
#   3. Inserts the rejected rows into the quarantine table with their rejection reason
#   4. Writes an ingestion log entry recording how many rows were processed
#   5. If anything fails, rolls back all changes and writes a failed log entry instead
```

---

### File: ingestion/fuel_scraper.py

The cost of transporting crops depends on diesel prices, which change weekly. This
client scrapes the National Petroleum Authority (NPA) website to get the current
official fuel prices in Ghana.

```python
# line 23: NPA_URL = "https://www.npa.gov.gh/"
# line 29: _MANUAL_SEED = {petrol: ..., diesel: ..., lpg: ...}
#   If the website is unavailable or the page layout has changed, the scraper falls
#   back to manually entered prices and logs a warning so an operator can update them.
# line 42: _PRICE_MIN = 1.0
# line 43: _PRICE_MAX = 50.0
#   Any price outside the range 1-50 GHS per litre is rejected as implausible.

class FuelScraper:
    # line 50: scrape_npa()
    #   Strategy 1: scan HTML tables on the NPA website for fuel keyword rows.
    #   Strategy 2: if fewer than 2 fuel types found, try a regular expression
    #               scan of the full page text.
    #   Fallback: use _MANUAL_SEED prices and log a warning.
    # line 148: save_to_database()
    #   Saves with a conflict rule: if a price for that fuel type and date already
    #   exists, do nothing (do not overwrite).
    # line 209: run()
```

Diesel prices feed directly into the logistics cost model as one of the 24 ML features.

---

### File: ingestion/scheduler.py

The central coordinator for all recurring data pipeline jobs. It registers 14 jobs
with APScheduler (a Python scheduling library) and defines the functions each job calls.

```python
# line 93:  run_hdx_pipeline()       -- WFP prices: fetch CSV, validate, transform, save
# line 160: run_mofa_pipeline()      -- MoFA Excel: parse files, validate, transform, save
# line 376: run_chirps_daily()       -- Download yesterday's satellite rainfall data
# line 391: run_nasa_power_daily()   -- Download last 7 days of climate data (backfill)
# line 407: run_climate_indicators_daily()  -- Compute SPI and CSI from fresh climate data
# line 420: run_fuel_price_scrape()  -- Scrape diesel prices from NPA website
# line 461: run_alerts_daily()       -- Check all alert conditions and send SMS messages
# line 477: run_cooperative_logistics() -- Group farmers into shared truck trips
# line 493: run_transport_matching() -- Assign pending jobs to available truck providers
# line 513: run_model_retrain()      -- Retrain XGBoost models from latest feature data
# line 563: start_scheduler()        -- Registers all 14 jobs with their schedules
```

#### Job schedule

| Job | Schedule |
|-----|----------|
| WFP HDX price pipeline | Daily 07:00 UTC |
| MoFA Excel price pipeline | Mondays 06:00 UTC |
| CHIRPS satellite rainfall | Daily 05:00 UTC |
| NASA POWER climate data | Daily 05:30 UTC |
| Climate stress indicators | Daily 06:00 UTC |
| Fuel price scrape | Mondays 06:30 UTC |
| CSI update | Daily 07:00 UTC |
| Cooperative logistics grouping | Daily 22:00 UTC |
| Transport job assignment | Daily 22:30 UTC |
| SMS alert checks | Daily 08:00 UTC |
| Model retraining | Sundays 10:00 UTC |

The climate jobs run in sequence (rainfall at 05:00, climate data at 05:30, indicators at
06:00) because each step needs the previous step's output to be ready.

---

### File: ingestion/alert_engine.py

Monitors all active farmers for conditions that warrant an SMS message. Runs four types
of checks every day. Has deduplication logic to avoid sending the same message twice.

```python
class AlertEngine:
    # line 70: _already_alerted()
    #   Returns True if this farmer already received this type of alert in the
    #   past 7 days, to prevent flooding their inbox.
    # line 89: _already_alerted_today()
    #   For climate stress alerts, the window is shorter: 24 hours.
    # line 140: send_sms()
    #   Sends via Africa's Talking API. Truncates message to 160 characters
    #   (the standard SMS limit) automatically.
    # line 210: check_price_alerts()
    #   Looks for farmers whose forecast price is significantly above or below
    #   their expected price, based on harvest proximity.
    # line 272: check_csi_alerts()
    #   Sends alerts when a district's Crop Stress Index reaches warning or
    #   critical level for a farmer's declared crop.
    # line 316: check_logistics_alerts()
    #   Notifies farmers when a cooperative transport group has been formed that
    #   includes their declaration.
    # line 395: check_byproduct_alerts()
    #   Reminds farmers about perishable byproducts that need to be sold soon.
    # line 445: run_all_checks()
    #   Runs all four checks and returns a summary of how many messages were sent.
```

Supports `dry_run=True` mode which runs all the logic but does not actually send any
SMS messages, useful for testing and for previewing what would be sent.

---

### File: ingestion/ussd_handler.py

USSD is the text-based menu system accessible from any mobile phone, including basic
feature phones. Africa's Talking provides the infrastructure. When a farmer dials the
platform's short code, Africa's Talking sends an HTTP request to this handler for
every keypress. The handler reads the current session state, decides what to show
next, updates the state, and returns the next menu screen as a text string.

```python
# line 14: _REGIONS list   (10 Ghana regions presented in the phone menu)
# line 27: _CROPS list     (6 supported crops: maize, tomato, cassava, onion, rice, plantain)
# line 29: _HARVEST_WEEKS  (1, 2, 3, or 4 weeks from now as harvest timing options)

class USSDHandler:
    # line 105: process(session_id, phone, full_input)
    #   The main entry point. Reads the full keypress history for the session and
    #   decides which screen to show next.
    #   Returns a string starting with "CON" (continue, show next menu) or
    #   "END" (close session, job is done).
    # line 172: _reg_flow()   -- 4 steps: enter name, select region, confirm, save farmer
    # line 264: _main_flow()  -- main menu: 1=list produce, 2=check prices, 3=my listings
    # line 308: _produce_flow() -- 5 steps: select crop, enter bags, enter harvest timing,
    #                              confirm, save declaration and send confirmation SMS
```

#### USSD session state machine

```
New caller (phone number not in database):
  Step 1: "Welcome to AgriMatch. Enter your full name:"
  Step 2: "Select your region:" [numbered list of regions]
  Step 3: "Confirm: [name], [region]? 1=Yes 2=No"
  Step 4: Saves farmer, shows main menu

Returning farmer main menu:
  1. List produce for sale -> produce declaration flow
  2. Check prices (stub)
  3. My listings (stub)

Produce declaration flow:
  Step 1: Select crop from numbered list
  Step 2: "How many bags?"
  Step 3: "Harvest in how many weeks? 1/2/3/4"
  Step 4: "Confirm: [crop] [bags] bags ready in [weeks] weeks? 1=Yes 2=No"
  Step 5: Saves declaration, sends confirmation SMS with reference number, END
```

The session's current step and partial input are stored in the `UssdSession` database
table (db/models.py line 251) so the farmer can interrupt and resume across dropped
network connections.

---

### File: ingestion/m3_api.py

The programmatic API for registering farmers and posting declarations. Used by field
agents with smartphones rather than the feature phone menu. Also used by the frontend.
This is a FastAPI router mounted directly in `api/main.py`.

```python
# line 16: _DEFAULT_BAG_KG = 100.0    (one standard bag = 100 kg)
# line 17: _MAX_BULK = 50             (maximum declarations in one bulk request)
```

#### API routes

| Route | Method | Path | Line | Notes |
|-------|--------|------|------|-------|
| register_farmer | POST | /api/farmers/register | 447 | Returns 201 if new farmer, 200 if already exists |
| create_declaration | POST | /api/declarations | 502 | Validates, saves, auto-generates byproducts |
| list_farmer_declarations | GET | /api/declarations/farmer/{id} | 546 | All active declarations for a farmer |
| get_declaration | GET | /api/declarations/{id} | 586 | Full detail for one declaration |
| bulk_declarations | POST | /api/declarations/bulk | 891 | Up to 50 declarations in one request |
| register_transport_provider | POST | /api/transport/register | 713 | Validates vehicle type and capacity |
| available_transport | GET | /api/transport/available | 795 | Filters by capacity and service region |

Duplicate declaration check (line 370): if a farmer submits a declaration for the
same crop and district with a harvest date within 7 days of an existing declaration,
a 409 Conflict response is returned with the existing declaration's ID rather than
creating a duplicate.

---

### File: ingestion/retrain.py

Retrains the XGBoost price prediction models every Sunday using the latest data in
the feature store. The pipeline has three stages: refresh the input features, train
one model per crop-market pair, and save the new model weights to the database.

```python
# line 23: MIN_ROWS = 60
#   A crop-market pair needs at least 60 weeks of data to be worth training.
#   Fewer rows than this would produce an unreliable model.

# line 168: def refresh_feature_store()
#   Rebuilds the 24-column feature table from raw price and climate data.
#   Computes: price lag features (7, 14, 30, 90 days ago), rolling averages and
#   standard deviations over 30 and 90 days, price momentum, sin/cos encodings
#   of week and month (so the model understands seasonality), current climate
#   stress values, and current fuel prices.

# line 183: def _fetch_pair_data(crop, market)
#   Loads feature data for one crop-market pair.
#   Converts raw prices into percentage returns (this week vs last week).
#   The model predicts returns rather than raw prices because returns are more
#   consistent across different crops and markets (a statistical property called
#   stationarity). Returns that are more than 50% up or down are treated as
#   data errors and removed.

# line 254: def _train_one(crop, market)
#   Trains one XGBoost model:
#   - 80% of data is used for training, 20% for evaluating accuracy
#   - XGBoost settings: 200 trees, learning rate 0.05, max tree depth 4,
#     80% row sampling and 80% column sampling per tree
#   - Reports MAE (mean absolute error), RMSE (root mean squared error),
#     and MAPE (mean absolute percentage error) on the test portion

# line 309: def _save_to_db(info)
#   Saves the trained model weights and accuracy metrics to the model_store table.
#   If a model for that crop-market already exists, it is replaced.

# line 375: def run_full_retrain()
#   The complete pipeline: refresh features, train all pairs, return a summary
#   of how many models were trained, skipped (not enough data), and failed.
```

---

## LAYER 16: Business Models

These three model files contain business logic that does not fit into the service layer
because they require direct access to machine learning model outputs.

### File: models/strategy_generator.py

Generates human-readable strategy cards: guidance that tells a farmer the best time
to sell their crop and guidance that tells a buyer where to source a crop most cheaply.

```python
class StrategyGenerator:
    # line 25: __init__(xgb, lstm)
    #   Takes the two price prediction models as inputs so it can generate forecasts.

    # line 77: farmer_sell_strategy(farmer_id)
    #   For each active declaration by this farmer:
    #   - Gets price forecasts for 30, 60, and 90 days ahead
    #   - Averages the XGBoost and LSTM forecasts together for a more stable estimate
    #     (lines 107-111: this is called ensemble averaging)
    #   - Deducts the transport cost from each forecast price
    #   - Picks the horizon with the best net return
    #   - Returns a card with: best timing, expected net price, price direction,
    #     urgency level, and a plain text recommendation

    # line 194: buyer_sourcing_strategy(district_id, crop, quantity_kg)
    #   Finds nearby listings within a 60-day harvest window.
    #   Calculates the total landed cost (price plus transport) for each option.
    #   Returns options ranked from cheapest to most expensive.

    # line 294: logistics_strategy(declaration_id)
    #   Checks whether this declaration can be grouped with others nearby
    #   (same 3-day harvest window, within 50 km).
    #   Calculates the individual truck cost vs the shared truck cost.
    #   Returns savings in GHS if co-shipping is available.

    # line 379: generate_all_for_farmer(farmer_id)
    #   Combines sell strategy and logistics strategy for all active declarations
    #   and returns them sorted by urgency.
```

---

### File: models/byproduct_marketplace.py

Searches and ranks post-harvest material listings (cassava peels, maize stalks, etc.)
by how urgently they need to be sold and how close they are to the buyer.

```python
# line 22: def _urgency(byproduct_row) -> str
#   Classifies each listing as "critical", "high", "medium", or "low" urgency
#   based on the available date and whether the material is perishable.

class ByproductMarketplace:
    # line 38: search(byproduct_type, buyer_district_id, quantity_kg)
    #   Finds available listings within a 90-day window.
    #   Listings in the same district as the buyer have zero transport cost.
    #   Results are sorted: most urgent first, then by distance, then by quantity.
    # line 117: get_all_byproduct_types()
    #   Overview of all byproduct types currently available, grouped by region.
    # line 139: get_farmer_byproducts(farmer_id)
```

---

### File: models/transport_matcher.py

Assigns pending delivery jobs to the best available transport provider using a
four-factor scoring formula.

```python
class TransportMatcher:
    # line 53: def _score_provider(provider, job, road_km_to_pickup, road_km_route)
    #   Scores each eligible provider on a scale of 0 to 1:
    #   40% -- how close the provider is to the pickup point (max 500 km range)
    #   30% -- how well the vehicle capacity matches the cargo weight
    #           (over-sizing is penalised because it wastes capacity)
    #   20% -- the provider's rating (out of 5 stars)
    #   10% -- the provider's cost per km (cheaper scores higher, capped at 10 GHS/km)

    # line 92: match_pending_jobs()
    #   Loads all pending transport jobs and all available providers.
    #   Filters providers by their declared service regions if set.
    #   For each job, scores every eligible provider and assigns the highest scorer.
    #   Updates the job status from "pending" to "assigned".
    #   Returns a summary: matched count, unmatched count, total.
```

---

## LAYER 17: The 12 Machine Learning Components

---

### DS-1. CHIRPS Satellite Rainfall Client

**File:** `ingestion/climate/chirps_client.py`

CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) is a satellite
dataset from the University of California, Santa Barbara. It provides daily rainfall
estimates at roughly 5 km resolution across Africa. This client downloads the Ghana
bounding box, clips it to district boundaries, calculates the mean rainfall per
district, and saves it to `chirps_daily`.

- Bounding box: longitude -3.25 to 1.20, latitude 4.50 to 11.20
- Missing data value: -9999 (filtered out before averaging)
- Output table: `db/models.py` line 115 -- `class ChirpsDaily`

---

### DS-2. NASA POWER ET0 Client

**File:** `ingestion/climate/nasa_power_client.py`

ET0 is evapotranspiration -- the rate at which water evaporates from soil and
transpires through plant leaves. High ET0 combined with low rainfall means crops are
under water stress even when it has recently rained. This client fetches 6 daily
weather variables from NASA's POWER dataset and computes ET0 using the FAO-56
Penman-Monteith formula, which is the international standard for estimating crop
water demand.

- Missing value sentinel: -999.0 (filtered before calculation)
- Output table: `db/models.py` line 130 -- `class NasaPowerDaily`

---

### DS-3. SPI and CSI Engine

**File:** `ingestion/csi_engine.py`

SPI (Standardised Precipitation Index) measures how unusual the current rainfall is
compared to the long-term average for that district and month. An SPI of -2.0 means
the rainfall is two standard deviations below normal, which is a severe drought signal.

CSI (Crop Stress Index) combines the SPI with ET0 to produce a single crop-specific
stress score between 0 and 1. A CSI above 0.75 means the crop is at high risk of
yield loss. Different crops have different CSI thresholds because some (like cassava)
are more drought-tolerant than others (like tomato).

```
SPI = (observed 30-day rainfall - long-term average for that month) / standard deviation
```

- Class: `ingestion/csi_engine.py` line 29
- Flag levels: line 56 (normal, watch, warning, critical)
- Output table: `db/models.py` line 165 -- `class ClimateIndicator`

---

### DS-4. Feature Engineering Pipeline

**File:** `ingestion/feature_engineering.py`

Machine learning models need clean, consistent numerical inputs. Raw price data is
not directly usable -- the model needs carefully computed features that summarise
past price behaviour and current conditions. This pipeline computes 24 features from
the raw price and climate data and stores them in the feature store.

The 24 features are:
- Price lags: what was the price 7, 14, 30, and 90 days ago?
- Rolling statistics: average and standard deviation over the past 30 and 90 days
- Momentum: how fast is the price changing?
- Seasonality: sin and cosine encodings of week-of-year and month (so the model
  understands that maize always peaks in October without seeing the word "October")
- Climate: current SPI, ET0, and CSI for the relevant crop
- Fuel: current diesel price per litre

- Class: `ingestion/feature_engineering.py` line 86
- Output table: `db/models.py` line 342 -- `class FeatureStore`

---

### DS-5. ARIMA / SARIMA Statistical Baseline

**File:** `models/arima_baseline.py`

ARIMA (AutoRegressive Integrated Moving Average) is a classical statistical method
for forecasting time series data. It does not learn from other features -- it only
looks at the historical price sequence itself and identifies repeating patterns.
The SARIMA variant adds a seasonal component, which captures annual price cycles
(for example, tomatoes being cheap at harvest time and expensive in the off-season).

`auto_arima` automatically searches for the best model configuration by testing
different parameter combinations and selecting the one with the lowest AIC score
(a measure of model quality that penalises complexity).

- Minimum 156 weeks of data required before fitting
- Maximum parameters tested: p=3, d=2, q=3, seasonal period=52 weeks
- Output tables: `db/models.py` line 419 (ModelBaseline), line 448 (PriceForecast)

---

### DS-6. XGBoost Return-Based Price Predictor

**File:** `models/xgboost_predictor.py`

XGBoost is a gradient-boosted decision tree algorithm. It is one of the most
consistently accurate algorithms for structured tabular data. Rather than predicting
the raw price, it predicts the percentage return (how much the price will change
from now to a future date). This is more reliable because the statistical properties
of price returns are consistent across different crops and markets, whereas raw prices
vary enormously.

| Item | Line | What it does |
|------|------|-------------|
| Class XGBoostPredictor | 60 | Loads models from the database and manages predictions |
| Return decay factors | 32 | 30-day: 1.0x, 60-day: 0.9x, 90-day: 0.8x (longer forecasts are less confident) |
| Stable band | 53 | Returns between -2% and +2% are treated as "stable" (not predicted as moving) |
| predict() | 251 | Builds a feature vector, runs the model, converts the return back to a price |
| maybe_reload_from_db() | 182 | Checks every 6 hours whether new model weights have been trained |
| Confidence formula | 313 | confidence = 1 / (1 + MAPE / 100) |
| Interval margin | 327 | Upper and lower bounds = forecast +/- 1.5 x rolling standard deviation |

MAPE stands for Mean Absolute Percentage Error -- the average percentage by which the
model's past predictions were wrong. A model with MAPE of 5% is right to within 5% on average.

---

### DS-7. LSTM Neural Network Price Predictor

**File:** `models/lstm_predictor.py`

LSTM stands for Long Short-Term Memory. It is a type of neural network designed to
learn patterns in sequences. While XGBoost looks at the current feature values,
the LSTM looks at the last 24 weeks of price history to understand trends and
multi-week patterns that a feature-based model might miss.

The two models (XGBoost and LSTM) are used together. Their predictions are averaged
to produce a more stable final forecast than either model alone.

| Item | Line | What it does |
|------|------|-------------|
| Class LSTMPredictor | 36 | Loads the neural network and manages predictions |
| lookback = 24 | 43 | The model sees the past 24 weeks of data as context |
| predict() | 152 | Builds a 3D input array, runs the network, returns a 3-step forecast |
| RobustScaler | 194 | Scales input data using median and IQR instead of mean and standard deviation, so extreme price spikes do not distort the scaling |

---

### DS-8. Harvest Delay Classifier

**File:** `models/delay_classifier.py`

When weather stress is detected, crops take longer to reach harvest than expected.
This classifier predicts whether a declared crop's harvest will be on time or delayed,
and if delayed, by how much. It outputs one of four classes.

| Class | Meaning | Days adjustment |
|-------|---------|----------------|
| 0 | Normal conditions, harvest on time | +0 days |
| 1 | Watch level, minor stress | +3 days |
| 2 | Warning level, moderate stress | +9 days |
| 3 | Critical level, severe stress | +18 days |

The 6 input features are: SPI (30-day), ET0, month of year, day of year, SPI from
yesterday, and SPI from three days ago. The lag values help the model detect whether
stress is worsening or recovering.

| Item | Line | What it does |
|------|------|-------------|
| Class HarvestDelayClassifier | 38 | Manages the classifier and updates declarations |
| delay_days_map | 45 | Maps class 0/1/2/3 to 0/3/9/18 day adjustments |
| _build_feature_vector() | 69 | Assembles the 6 inputs from climate data |
| Zero-fill for short series | 86 | If fewer than 3 days of data are available, fills missing lags with zero |
| predict_delay() | 102 | Returns the predicted class and adjustment days for one district |
| update_all_active_declarations() | 136 | Runs predictions for every active declaration and updates their adjusted harvest dates |

---

### DS-9. Matchmaking Engine

**File:** `models/matchmaking_engine.py`

When a buyer searches for a crop, the engine scores every available listing against
the buyer's requirements and returns them ranked from best to worst match. The score
is a weighted average of five factors.

| Factor | Weight | How it is scored |
|--------|--------|-----------------|
| Quantity match | 25% | How closely the available quantity matches the buyer's need |
| Distance | 25% | Closer listings score higher (0 km = 1.0, 500+ km = 0.0) |
| Price | 20% | Listings priced below the market median score higher |
| Reliability | 20% | Adjusted downward if the district has a weather stress flag |
| Timing | 10% | Listings with harvest dates closest to the buyer's target score higher |

Climate penalties applied to the reliability score:

| Stress level | Score deduction |
|-------------|----------------|
| Watch | -0.10 |
| Warning | -0.30 |
| Critical | -0.60 |

| Item | Line | What it does |
|------|------|-------------|
| Weight constants | 20 | The five weights above |
| Reliability penalties | 30 | The climate deductions above |
| Timing lookup table | 38 | Maps days-until-harvest to timing score |
| ScoringContext dataclass | 65 | Bundles all scoring inputs into one typed object |
| Class MatchmakingEngine | 80 | Manages search and scoring |
| search() | 200 | Runs the full scoring pipeline and returns ranked results |

---

### DS-10. Crop Recommender

**File:** `models/crop_recommender.py`

Given a district or farmer, this model recommends which crops to grow next season.
It scores all supported crops on three dimensions and returns them ranked.

```
Final score = 40% x climate score + 35% x supply scarcity score + 25% x price momentum score
```

- Climate score: how favourable are the current SPI, ET0, and CSI values for this crop?
- Supply scarcity score: is this crop currently undersupplied in the region compared
  to historical baseline demand?
- Price momentum score: is the price trending upward over the past 30 and 90 days?

| Item | Line | What it does |
|------|------|-------------|
| Supply benchmark dict | 33 | Historical normal supply level per crop per region |
| Weight constants | 55 | The three weights above |
| Class CropRecommender | 67 | Manages recommendations |
| recommend() | 276 | Returns all crops ranked by composite score |

---

### DS-11. Logistics Cost Model

**File:** `models/logistics_cost.py`

Calculates the total cost of transporting a crop from a source district to a
destination market, broken down into fuel, driver, and loading components.

```
fuel_cost    = (road distance / 100) x fuel consumption rate x diesel price per litre
driver_cost  = road distance x 0.50 GHS per km
loading_cost = cargo weight x 0.02 GHS per kg
total_cost   = fuel + driver + loading
```

| Item | Line | What it does |
|------|------|-------------|
| Vehicle specs dict | 26 | Fuel consumption and capacity per vehicle type |
| Class LogisticsCostModel | 72 | Manages cost calculations |
| get_delivery_cost() | 251 | Main calculation entry point |

---

### DS-12. Cooperative Logistics Engine

**File:** `models/cooperative_logistics.py`

A single farmer declaring 50 bags cannot afford to hire a truck alone. But five
farmers in the same area with similar harvest dates can share a truck and split the
cost. This engine finds those groupings automatically.

The algorithm is a greedy spatial-temporal cluster:
1. Pick any unassigned declaration as the group anchor
2. Find all other unassigned declarations within 50 km and within 3 days harvest window
3. Form a group, assign them to the nearest market
4. Repeat until all declarations are processed

This runs in seconds. The mathematically optimal solution (Vehicle Routing Problem)
is an NP-hard problem that would take days to compute for large inputs. The greedy
approach is economically sound in practice because the groupings are based on
physical proximity, which naturally produces efficient routes.

| Item | Line | What it does |
|------|------|-------------|
| Max distance: 50 km | 22 | Declarations farther apart than this are not grouped |
| Harvest window: 3 days | 23 | Declarations with harvest dates more than 3 days apart are not grouped |
| Class CooperativeLogistics | 51 | Manages the grouping process |
| _cluster_declarations() | 110 | The greedy clustering algorithm |
| find_groups() | 225 | Entry point: returns all groups with cost savings |

---

## LAYER 18: Tests

The test suite uses pytest. Unit tests run against an in-memory SQLite database so
no real database connection is needed. Integration tests make real HTTP calls to a
running server at localhost:8000.

### File: tests/conftest.py

```python
# lines 10-31: Patches PostgreSQL-specific types (ARRAY, JSONB, BigInteger)
#   with SQLite-compatible equivalents so the ORM models work in both databases.
# line 54: db_session() fixture
#   Creates a fresh in-memory database for each test function.
# line 69: patch_get_session() fixture
#   Replaces the database session used by the ingestion pipeline with the test session.
```

---

### Unit Tests

| File | What is tested |
|------|---------------|
| test_ingestion.py | CROP_MAP covers 12 name variants, UNIT_MAP returns correct kg factors, validate_row rejects negative prices and future dates and missing markets, duplicate detection, quarantine on unknown crop |
| test_matchmaking_engine.py | All 5 sub-scores individually: quantity (exact match, surplus, partial, zero-divide safety), distance (0km, 500km, 250km, over 500km), price (at median, above, double, no median), reliability (normal, watch, warning, critical penalties, adjusted date, clamped range), timing; final score is between 0 and 1, has correct keys, rounds to 4 decimal places -- 21 tests in total |
| test_payment_gateway.py | charge() returns a ChargeResult, same reference key returns the same result (idempotency), different keys are independent, refund success, refund unknown key, reuse after refund, provider detection for MTN/Vodafone/AirtelTigo numbers, FAILURE_RATE=1.0 forces every charge to fail |
| test_csi_engine.py | get_csi_for_declaration, update_declaration_csi, run_all_active (4 crops processed, 1 inactive skipped), district_risk_summary (all 16 Ghana regions), normal flag produces no alert |
| test_reservation_service.py | payment declined stops before DB write, declaration not found triggers refund, overbooking (5 bags total, 4 reserved, request for 2 more is rejected) triggers refund, DB failure after charge triggers refund, happy path (5 bags at 5 GHS/kg = 2500 GHS total), reference string starts with "AGM-", idempotency key equals the reference |
| test_roi_service.py | uses XGBoost forecast when model exists, falls back to database price when no model, margin percentage calculation is correct, response contains all required keys |

---

### Router Tests

| File | What is tested |
|------|---------------|
| test_reservation_router.py | POST returns 201 with status and reservation_id, correct arguments passed to service, invalid phone number returns 422, zero bags returns 422, name over 120 characters returns 422, negative declaration ID returns 422, GET buyer list returns 200 |
| test_reference_router.py | GET /api/crops returns 200 with name field, 503 on database failure for crops/stats/regions/model-accuracy, GET /api/models/status returns 200 with required keys, cache is cleared between tests |

---

### Smoke and Integration Tests

These tests require a running server or a real external connection.

| File | What is tested |
|------|---------------|
| test_chirps_single_day.py | Downloads CHIRPS data for 2023-01-15, expects at least 200 district rows, verifies no negative rainfall values |
| test_nasa_power_single_district.py | Downloads 31 daily rows for Kumasi in January 2023, verifies temperature is between 20-35 degrees C, ET0 is between 3-7 mm per day, no missing values |
| test_m3_endpoints.py | Register farmer returns 201, sending the same phone again returns 200 with the same ID, create declaration returns 201 with correct kg calculation and SMS under 160 characters, duplicate within 7 days returns 409, past harvest date returns 400, get by ID, list farmer declarations, bulk request with 2 valid and 1 invalid |
| test_transport_endpoints.py | Register provider returns 201, duplicate phone returns 409, invalid vehicle type returns 400, capacity out of range returns 400, invalid district returns 400, GET available providers, query for large cargo returns empty when no provider is big enough, pickup truck is filtered out for 2000 kg cargo |
| test_ussd_handler.py | New farmer full registration flow across 4 keypresses, returning farmer produce declaration across 5 keypresses, invalid quantity entry shows error and stays on same step |

---

## Complete End-to-End Data Flow

This diagram shows how data moves through the entire platform from collection to delivery.

```
EXTERNAL SOURCES
  WFP HDX website        --> ingestion/hdx_client.py        (weekly price CSV)
  MoFA Excel inbox       --> ingestion/mofa_client.py       (weekly price Excel)
  NPA website            --> ingestion/fuel_scraper.py      (weekly fuel prices)
  CHIRPS satellite FTP   --> ingestion/climate/chirps_client.py (daily rainfall)
  NASA POWER API         --> ingestion/climate/nasa_power_client.py (daily climate)

         | All scheduled by ingestion/scheduler.py (14 jobs)
         v

RAW STORAGE
  raw_prices, price_quarantine, ingestion_log (every incoming row saved first)
  chirps_daily, nasa_power_daily, fuel_prices

         | ingestion/validators.py checks each row
         | ingestion/transformers.py normalises names and units
         v

CLEAN STORAGE
  clean_prices        (validated, normalised, de-duplicated price records)
  climate_indicators  (SPI and CSI per district per day)
  spi_baselines       (long-term monthly rainfall averages used for SPI calculation)

         | ingestion/feature_engineering.py computes 24 features
         v

feature_store (one row per crop-market-day with all 24 ML input features)

         | ingestion/retrain.py (runs every Sunday)
         v

model_store (XGBoost model weights per crop-market pair, with accuracy metrics)

         | models/xgboost_predictor.py reloads every 6 hours
         | models/lstm_predictor.py (loaded from .keras files at startup)
         | models/arima_baseline.py (fitted from clean_prices)
         v

price_forecasts (30, 60, and 90-day predictions per crop and market)

FARMER DATA ENTRY
  Feature phone (USSD) --> ingestion/ussd_handler.py
  Smartphone / API     --> ingestion/m3_api.py
         v
  farmers, farmer_declarations, byproduct_declarations, ussd_sessions

DAILY BACKGROUND JOBS
  07:30 UTC: delay_classifier updates adjusted harvest dates
  08:00 UTC: alert_engine checks conditions and sends SMS via Africa's Talking
  22:00 UTC: cooperative_logistics groups nearby farmers for shared truck trips
  Every 6h:  xgboost_predictor checks for new model weights and hot-swaps them

REST API (14 route groups registered in api/main.py)
  Buyer search    --> api/routers/matchmaking.py    --> models/matchmaking_engine.py
  Price forecast  --> api/routers/forecasting.py    --> models/xgboost_predictor.py
  Farmer profile  --> api/routers/listings.py       --> db/repositories/listings_repo.py
  Book a crop     --> api/routers/reservations.py   --> api/services/reservation_service.py
                                                    --> api/payment_gateway.py
  Strategy cards  --> api/routers/strategy.py       --> models/strategy_generator.py
  ROI calculation --> api/routers/advisory.py       --> api/services/roi_service.py
  Logistics plan  --> api/routers/logistics.py      --> models/cooperative_logistics.py
  Byproducts      --> api/routers/logistics.py      --> models/byproduct_marketplace.py
  Admin panel     --> api/admin_router.py            --> db/repositories/admin_repo.py
  Planting advice --> api/routers/advisory.py       --> api/services/planting_service.py
```

---

## Complete File and Line Number Reference Card

| What to show | File | Line |
|---|---|---|
| App creation and lifespan | api/main.py | 85 |
| Request logging middleware | api/main.py | 193 |
| Scheduler jobs (4 in-process) | api/main.py | 143 |
| All router registrations | api/main.py | 250 |
| Health endpoint | api/main.py | 220 |
| Settings class | config/settings.py | 10 |
| Startup validator for missing vars | config/settings.py | 43 |
| Crop name map (178 entries) | config/crop_map.py | 10 |
| Market name map (65 entries) | config/market_map.py | 10 |
| Unit conversion map (59 entries) | config/unit_map.py | 15 |
| Crop seasons metadata | config/crop_data.py | 1 |
| Secret key check | api/security.py | 10 |
| Timing-safe comparison | api/security.py | 18 |
| Ghana phone regex | api/validators.py | 5 |
| validate_ghana_phone() | api/validators.py | 8 |
| All 12 dependency accessors | api/dependencies.py | 17 |
| Admin router (9 routes, all protected) | api/admin_router.py | 26 |
| FarmerStatusBody request schema | api/admin_router.py | 55 |
| Prices router in-memory cache | api/routers/prices.py | 11 |
| Market bulletin route | api/routers/prices.py | 34 |
| Planting advisory route | api/routers/advisory.py | 13 |
| ROI calculator route | api/routers/advisory.py | 19 |
| Strategy farmer route | api/routers/strategy.py | 9 |
| Strategy buyer route | api/routers/strategy.py | 24 |
| Alerts manual trigger route | api/routers/alerts.py | 11 |
| USSD callback route | api/routers/ussd_routes.py | 16 |
| Demand POST route | api/routers/demand.py | 10 |
| Reference router in-memory cache | api/routers/reference.py | 17 |
| Crops endpoint | api/routers/reference.py | 20 |
| Farmer profile endpoint | api/routers/listings.py | 14 |
| Match listings with quantity cap | api/routers/matchmaking.py | 12 |
| ReservationRequest schema | api/routers/reservations.py | 16 |
| Phone validator on both fields | api/routers/reservations.py | 23 |
| Create reservation (201 Created) | api/routers/reservations.py | 35 |
| XGBoost forecast route | api/routers/forecasting.py | 14 |
| LSTM forecast route | api/routers/forecasting.py | 39 |
| Delay prediction route | api/routers/forecasting.py | 52 |
| Logistics groups route | api/routers/logistics.py | 14 |
| Admin schema file | api/schemas/admin.py | 8 |
| ReservationResponse schema | api/schemas/reservations.py | 6 |
| BuyerRequestIn schema | api/schemas/demand.py | 9 |
| Bag weight constant (100 kg) | api/services/reservation_service.py | 16 |
| Unique reference generator | api/services/reservation_service.py | 19 |
| ReservationService.create() | api/services/reservation_service.py | 27 |
| Charge before lock (step 4) | api/services/reservation_service.py | 57 |
| Database lock (step 6) | api/services/reservation_service.py | 74 |
| Refund on database failure (step 10) | api/services/reservation_service.py | 110 |
| Model accuracy pivot | api/services/admin_service.py | 11 |
| Market staleness check (3 days) | api/services/admin_service.py | 27 |
| USSD session analytics | api/services/admin_service.py | 36 |
| Climate risk thresholds | api/services/planting_service.py | 10 |
| PlantingService.get_advice() | api/services/planting_service.py | 43 |
| ROI price fallback hierarchy | api/services/roi_service.py | 28 |
| ROI calculation | api/services/roi_service.py | 41 |
| Provider detection by phone prefix | api/payment_gateway.py | 7 |
| Abstract payment gateway | api/payment_gateway.py | 32 |
| SimulatedGateway | api/payment_gateway.py | 46 |
| 10% failure rate | api/payment_gateway.py | 55 |
| TTL cache class | utils/cache.py | 4 |
| get_or_set pattern | utils/cache.py | 22 |
| Haversine formula | utils/geo.py | 4 |
| safe_float() | utils/math_utils.py | 1 |
| Connection pool settings | db/connection.py | 14 |
| get_session() context manager | db/connection.py | 27 |
| GhanaDistrict ORM table | db/models.py | 14 |
| CleanPrice ORM table | db/models.py | 41 |
| ClimateIndicator ORM table | db/models.py | 165 |
| FarmerDeclaration ORM table | db/models.py | 205 |
| UssdSession ORM table | db/models.py | 251 |
| TransportJob ORM table | db/models.py | 297 |
| FeatureStore ORM table (24 cols) | db/models.py | 342 |
| ModelBaseline ORM table | db/models.py | 419 |
| Reservation ORM table | db/models.py | 493 |
| MoMoPayment ORM table | db/models.py | 514 |
| SQL injection whitelist | db/repositories/listings_repo.py | 8 |
| Farmer profile aggregation query | db/repositories/listings_repo.py | 17 |
| Median price calculation | db/repositories/matchmaking_repo.py | 9 |
| Listing search query | db/repositories/matchmaking_repo.py | 43 |
| Database lock in repo | db/repositories/declaration_repo.py | 17 |
| Insert reservation | db/repositories/reservation_repo.py | 7 |
| Insert payment (same transaction) | db/repositories/reservation_repo.py | 33 |
| Bulk distance lookup | db/repositories/cooperative_logistics_repo.py | 68 |
| Create-or-find platform provider | db/repositories/cooperative_logistics_repo.py | 26 |
| All 4 queries in one session | db/repositories/crop_recommender_repo.py | 72 |
| USSD analytics query | db/repositories/ussd_repo.py | 8 |
| Monthly price history query | db/repositories/prices_repo.py | 12 |
| Market bulletin latest price query | db/repositories/prices_repo.py | 55 |
| HDX CKAN API call | ingestion/hdx_client.py | 26 |
| HDX batch size | ingestion/hdx_client.py | 16 |
| MoFA header detection | ingestion/mofa_client.py | 74 |
| Maximum price validation constant | ingestion/validators.py | 22 |
| validate_row() | ingestion/validators.py | 89 |
| HDX row transformation pipeline | ingestion/transformers.py | 134 |
| load_to_database() | ingestion/transformers.py | 488 |
| NPA website URL | ingestion/fuel_scraper.py | 23 |
| Manual seed fallback prices | ingestion/fuel_scraper.py | 29 |
| Scheduler registration (14 jobs) | ingestion/scheduler.py | 563 |
| HDX pipeline function | ingestion/scheduler.py | 93 |
| Alert engine class | ingestion/alert_engine.py | 20 |
| 7-day deduplication window | ingestion/alert_engine.py | 70 |
| SMS send (160 char truncation) | ingestion/alert_engine.py | 140 |
| run_all_checks() | ingestion/alert_engine.py | 445 |
| USSD region menu list | ingestion/ussd_handler.py | 14 |
| USSD crops list | ingestion/ussd_handler.py | 27 |
| USSDHandler.process() | ingestion/ussd_handler.py | 105 |
| Registration flow | ingestion/ussd_handler.py | 172 |
| Produce declaration flow | ingestion/ussd_handler.py | 308 |
| Duplicate check (7 days) | ingestion/m3_api.py | 370 |
| Auto-generate byproducts | ingestion/m3_api.py | 332 |
| Bulk declarations (max 50) | ingestion/m3_api.py | 891 |
| Minimum rows for training | ingestion/retrain.py | 23 |
| XGBoost hyperparameters | ingestion/retrain.py | 254 |
| refresh_feature_store() | ingestion/retrain.py | 168 |
| run_full_retrain() | ingestion/retrain.py | 375 |
| StrategyGenerator class | models/strategy_generator.py | 23 |
| XGBoost and LSTM ensemble average | models/strategy_generator.py | 107 |
| Transport cost deduction from forecast | models/strategy_generator.py | 118 |
| Byproduct urgency classifier | models/byproduct_marketplace.py | 22 |
| Byproduct search() | models/byproduct_marketplace.py | 38 |
| Transport provider scoring formula | models/transport_matcher.py | 53 |
| match_pending_jobs() | models/transport_matcher.py | 92 |
| XGBoost predictor class | models/xgboost_predictor.py | 60 |
| Return decay factors | models/xgboost_predictor.py | 32 |
| Confidence formula | models/xgboost_predictor.py | 313 |
| LSTM predictor class | models/lstm_predictor.py | 36 |
| Lookback window (24 weeks) | models/lstm_predictor.py | 43 |
| RobustScaler usage | models/lstm_predictor.py | 194 |
| Delay classifier class | models/delay_classifier.py | 38 |
| Delay class to days mapping | models/delay_classifier.py | 45 |
| Zero-fill for missing lag data | models/delay_classifier.py | 86 |
| ScoringContext dataclass | models/matchmaking_engine.py | 65 |
| Matchmaking score weights | models/matchmaking_engine.py | 20 |
| Climate reliability penalties | models/matchmaking_engine.py | 30 |
| Crop recommender score weights | models/crop_recommender.py | 55 |
| Supply benchmark values | models/crop_recommender.py | 33 |
| Vehicle fuel consumption specs | models/logistics_cost.py | 26 |
| Maximum grouping distance (50 km) | models/cooperative_logistics.py | 22 |
| Greedy clustering algorithm | models/cooperative_logistics.py | 110 |
| Seasonality sin/cos encoding | ingestion/feature_engineering.py | 114 |

---

## Questions the Panel May Ask

**Q: Why is the payment charged before the database row is locked?**

Mobile money charges take between 1 and 3 seconds while the network and the payment
provider communicate. If the database row were locked first, no other buyer could
book anything during those 3 seconds. By charging first, the database lock is only
held for a few milliseconds while the final record is written. If two buyers
simultaneously try to buy the last available bags, only one gets past the lock check
and the other receives an automatic refund.

Show: `api/services/reservation_service.py` lines 57 (charge), 74 (lock), 110 (refund).

**Q: Why is the secret key comparison timing-safe?**

A normal equals check stops as soon as it finds the first mismatched character. An
attacker making thousands of requests and measuring response times can determine, one
character at a time, where the correct characters end and wrong ones begin. Over enough
requests they can reconstruct the secret. `compare_digest` always takes exactly the same
amount of time regardless of how many characters match, which makes this attack impossible.

Show: `api/security.py` line 18.

**Q: Why is all SQL kept in repository files only?**

Spreading SQL across route handlers, service files, and models makes the codebase hard
to audit for security issues and hard to optimise for performance. Keeping every query in
one layer means a security reviewer only needs to read 16 files to verify that no SQL
injection vulnerabilities exist anywhere in the platform.

Show: `db/repositories/listings_repo.py` line 8 (whitelist), line 17 (parameterised query).

**Q: Why are machine learning models loaded once at startup rather than per request?**

Loading an XGBoost or LSTM model from disk takes between 0.5 and 2 seconds. Loading it
on every API request would make the forecast endpoint 100 to 200 times slower. Models
are loaded during the server startup sequence, stored in the server's memory, and
accessed in microseconds for every subsequent request.

Show: `api/main.py` line 85 (startup sequence), `api/dependencies.py` line 17 (accessor).

**Q: What happens if the database goes down?**

Reference endpoints (crops, regions, statistics) return the last cached result for up
to one hour from memory. After the cache expires they return 503 Service Unavailable.
Forecasting and matchmaking return 503 immediately. The health endpoint at /health
reports `db: degraded`. No data is lost -- the server simply stops serving requests
that require live database access until the database recovers.

Show: `api/routers/reference.py` line 20 (try/except), `utils/cache.py` line 22 (get_or_set).

**Q: Why does the XGBoost model predict price changes instead of the actual price?**

Raw crop prices vary enormously across crops (maize is cheap, ginger is expensive) and
across markets (urban markets have different price levels than rural ones). A model
trained to predict a raw price would need separate calibration for every crop-market
combination. Price returns (percentage change from one week to the next) have similar
statistical behaviour across all crops and markets, which means one model architecture
works well for all pairs. This is the statistical concept of stationarity.

Show: `models/xgboost_predictor.py` line 32 (decay), line 251 (predict).

**Q: Why is the cooperative logistics algorithm described as greedy?**

The mathematically optimal way to group farmers and assign routes is called the Vehicle
Routing Problem. It is classified as NP-hard, meaning the computation time grows
exponentially with the number of farmers. For 500 active declarations, finding the
optimal grouping could take hours or days. The greedy algorithm picks an anchor, groups
nearby farmers, and moves on. It runs in seconds and produces groupings that are
economically sensible in practice because geographic proximity naturally leads to
efficient routes.

Show: `models/cooperative_logistics.py` line 22 (distance constant), line 110 (algorithm).

**Q: How does the platform serve farmers with basic feature phones?**

Africa's Talking provides a USSD gateway. When a farmer dials the platform's short code,
Africa's Talking sends an HTTP POST to `/api/ussd` for every keypress. The handler reads
the farmer's session state from the database, decides what to display next, updates the
state, and returns the next menu screen as a text string. Sessions survive network
interruptions because the state is in the database, not in the server's memory.

Show: `db/models.py` line 251 (UssdSession), `ingestion/ussd_handler.py` line 105 (process).

**Q: How does the platform know which crops are undersupplied in a district?**

The crop recommender compares the current active supply (total kilograms declared by
farmers in the region) against a historical baseline of typical supply for each crop.
If the current supply is well below the baseline, that crop scores high on the scarcity
dimension (35% of the total recommendation score). A high scarcity score means there is
likely unmet buyer demand and higher prices.

Show: `models/crop_recommender.py` line 33 (benchmarks), line 55 (weights).

**Q: How are model weights updated without restarting the server?**

The retrain pipeline runs every Sunday and saves new XGBoost model weights to the
`model_store` database table along with the timestamp of when training finished. Every
6 hours, `maybe_reload_from_db()` checks whether the timestamp in the database is newer
than the last time models were loaded. If it is, it swaps the in-memory model objects
for the newly trained ones. No server restart is needed and no requests are interrupted.

Show: `models/xgboost_predictor.py` line 182 (reload check), `api/main.py` line 143 (job schedule).

---

*All file paths and line numbers reference the production codebase directly.*
*Open any file listed and navigate to the line shown -- the code matches what is described.*
