# M1 Handover Notes — AgriMatch Data Pipeline

Generated: 2026-05-25
Pipeline state: M1 complete, 37,933 clean rows, 0 quarantined

---

## 1. Crop Coverage Tiers

| Tier | Years | Period | Crops | Markets |
|------|-------|--------|-------|---------|
| Tier 1 | 17.5 yrs | Jan 2006 - Jul 2023 | cassava, maize, millet, rice, sorghum, yam | 44 |
| Tier 2 | 15.5 yrs | Jan 2008 - Jul 2023 | plantain | 20 |
| Tier 3 | 3.9 yrs  | Aug 2019 - Jul 2023 | tomato, onion, pepper, chicken, cowpea, eggs, fish_mackerel, soybean, garden_egg | 20 |

Tier 1 and Tier 2 crops are the HDX long-run staple series. Tier 3 crops all share the same start date (Aug 2019), indicating a single HDX data collection expansion in that round.

---

## 2. Sparse Regions — Handle Carefully in Modelling

| Region | Rows | Markets | Crops | Recommendation |
|--------|------|---------|-------|----------------|
| North East | 6 | 2 | 3 | Exclude from early models — effectively absent |
| Oti | 448 | 5 | 16 | Include but flag forecasts as low confidence |

All other 11 regions have 1,782+ rows and full 16-crop coverage.

---

## 3. Known Data Gaps and Causes

### 2014-2018: Structural survey absence — Northern markets
Long multi-year gaps with no HDX data collected for several northern markets.

| Market | Crop(s) | Gap | Duration |
|--------|---------|-----|----------|
| Nkwanta | cassava, maize, rice | Oct 2014 - Aug 2022 | 93 months |
| Yendi | cassava | Oct 2014 - Aug 2019 | 57 months |
| Garu | maize, rice | Oct 2014 - Feb 2018 | 39 months |
| Kintampo | cassava, maize, rice | Oct 2014 - Feb 2018 | 39 months |
| Yendi | maize, rice | Oct 2014 - Dec 2017 | 37 months |

### 2017-2019: HDX collection interruption — 8+ markets
Systematic gaps all ending at exactly August 2019, indicating a single HDX data collection event that resumed after a break. Markets affected include Ho, Obuasi, Mankessim, Tamale, Wa, Sekondi-Takoradi, Cape Coast, and Ejura (18-24 month gaps each).

### 2020-2022: COVID disruption
- fish_mackerel: 4-7 month gaps across almost all markets (May-Oct 2020 lockdown period)
- eggs, chicken: 9-11 month gaps at Tamale, Tema, Bolgatanga (2020-2021)
- Ejura: entire market offline Jan 2022 - Dec 2022 (11-month gap, all 16 crops)
- Koforidua: entire market offline May 2022 - Feb 2023 (8-month gap, all crops)

---

## 4. Price Data Note — GHS Inflation

Seven crops were flagged by the price sanity check (max > 10x average):
cassava, cowpea, onion, pepper, plantain, soybean, tomato.

These are **not unit conversion errors**. The data spans 17.5 years (2006-2023) during which the Ghana Cedi (GHS) depreciated significantly. Prices from 2006 (e.g., cassava at 0.06 GHS/kg) are not comparable in nominal terms to 2023 prices (51.86 GHS/kg).

**Modelling requirement:** Do not use absolute price_ghs values as features across the full time range without adjustment. Use one of:
- Inflation-adjusted real prices (deflate by Ghana CPI)
- Price-change features (month-on-month or year-on-year % change)
- Relative prices (crop price vs. basket average at same market/date)

---

## 5. Summary Statistics

| Metric | Value |
|--------|-------|
| Total clean rows | 37,933 |
| Quarantined rows | 0 |
| Distinct markets | 44 |
| Distinct crops | 16 |
| Distinct regions | 13 |
| Date range | Jan 2006 - Jul 2023 |
| Sources | HDX (all rows); MoFA not yet loaded |

---

## District Matching Notes

All 44 markets successfully matched to ghana_districts with
district_id, centroid_lat, and centroid_lon.

### Corrections applied
- Bunkprugu -> Bunkpurugu Nakpanduri
- Sekondi-Takoradi -> Sekondi Takoradi
- Kete Krachi -> Krachi East
- Kajeji -> Kadjebi
- Wa -> Wa Municipal (was incorrectly matched to Asokwa/Kumasi)
- Ho -> Ho Municipal (was incorrectly matched to Hohoe)
- Navrongo -> Kasena Nankana West
- Yeji -> Pru East
- Mankessim -> Mfantseman
- Koforidua -> New Juaben South
- Nalerigu -> East Mamprusi
- Bimbilla -> Nanumba North
- Dambai -> Biakoye
- Kpassa -> Jasikan
- Tumu -> Sissala East
- Funbisi -> Wa East

### Two known region mismatches in source data
These are errors in the original HDX data, not fixable at the
ghana_markets level:

1. Wichau -- clean_prices.region shows Upper East but the correct
   region is Upper West (Wechiau is in Upper West). District
   matched correctly to Wa East. If any geospatial query filters
   by region, Wichau will appear in the wrong region bucket.

2. Badu -- clean_prices.region shows Bono East but the correct
   region is Bono (Tain district is in Bono region). District
   matched correctly to Tain. Same caveat applies for
   region-filtered queries.

### Action for M2
Any NASA POWER API call or CSI calculation that filters markets
by region should use ghana_markets.district_id to join to
ghana_districts.region_name rather than using the region column
in clean_prices directly. The district table has the correct
region for all 44 markets.
