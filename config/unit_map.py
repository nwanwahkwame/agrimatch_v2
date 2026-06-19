# Maps raw unit strings (HDX or MoFA) to a kg conversion factor.
#
# Usage:
#   factor = UNIT_MAP.get(raw_unit.strip().lower())
#   if factor is None:
#       → send to quarantine (unit is unknown or crop-specific)
#   else:
#       price_per_kg = raw_price / factor
#
# A factor of 1.0 means the price is already per kg.
# A factor of N means the price is per N-kg bag/unit → divide by N.
# A factor of None means the unit is ambiguous or crop-specific;
# rows with these units are quarantined for manual review.

UNIT_MAP: dict[str, float | None] = {

    # ── Standard weight units ─────────────────────────────────────────────────

    "kg":           1.0,    # price is already per kg
    "1 kg":         1.0,
    "per kg":       1.0,

    "2 kg":         2.0,
    "5 kg":         5.0,
    "10 kg":        10.0,
    "16 kg":        16.0,   # HDX: small bag (e.g. rice, local)
    "20 kg":        20.0,
    "25 kg":        25.0,
    "27 kg":        27.0,   # HDX: mid-size bag
    "50 kg":        50.0,
    "52 kg":        52.0,   # HDX: variant 50 kg bag (slight overfill)
    "68 kg":        68.0,   # HDX: large grain bag
    "73 kg":        73.0,   # HDX: large grain bag
    "84 kg":        84.0,   # HDX: large grain bag
    "91 kg":        91.0,   # HDX: large grain bag
    "93 kg":        93.0,   # HDX: large grain bag
    "100 kg":       100.0,
    "109 kg":       109.0,  # HDX: large grain bag
    "250 kg":       250.0,  # HDX: bulk unit

    # ── Named bag formats (common in MoFA and market surveys) ─────────────────

    "50kg bag":     50.0,
    "50 kg bag":    50.0,
    "100kg bag":    100.0,
    "100 kg bag":   100.0,
    "25kg bag":     25.0,
    "25 kg bag":    25.0,
    "10kg bag":     10.0,
    "10 kg bag":    10.0,
    "5kg bag":      5.0,
    "5 kg bag":     5.0,
    "bag (50kg)":   50.0,
    "bag (100kg)":  100.0,

    # ── Count-based units — crop-specific, cannot convert without crop context ─
    # Rows with these units are quarantined until a crop-specific factor is added
    # to ingestion/transformers.py.

    # HDX: yam and cocoyam are priced per 100 tubers; avg weight varies by variety
    "100 tubers":   None,
    "tubers":       None,

    # HDX/MoFA: eggs, peppers priced per piece or per 30-piece tray
    "30 pcs":       None,
    "pcs":          None,
    "piece":        None,
    "pieces":       None,
    "tray":         None,   # egg tray = 30 eggs; weight not fixed

    # ── Traditional / volumetric units — crop-specific ────────────────────────
    # These are volume or local measure units whose kg equivalent depends on
    # the crop's bulk density.  Set factor = None so they go to quarantine.
    # Add crop-specific overrides in ingestion/transformers.py as data allows.

    # Mudu: traditional northern Ghana dry measure (~3–4 kg depending on crop)
    "mudu":         None,
    "1 mudu":       None,

    # Tin: standard paint tin used as a dry measure (~2–4 kg depending on crop)
    "tin":          None,
    "1 tin":        None,
    "paint tin":    None,

    # Olonka / Olonka tin: larger tin measure used in northern markets (~5–7 kg)
    "olonka":       None,
    "1 olonka":     None,

    # Basket: woven basket — varies widely by size and crop (~10–25 kg)
    "basket":       None,
    "small basket": None,
    "large basket": None,

    # Bundle: leafy veg, firewood, etc. — no standard weight
    "bundle":       None,
    "bundles":      None,

    # Bunch: plantain/banana bunch (~10–20 kg depending on variety)
    # HDX lists plantains as "Bunch"; keep None until avg weight is confirmed
    "bunch":        None,
    "bunches":      None,

    # Head: head-load unit common in MoFA field surveys (~20–30 kg)
    "head":         None,
    "head load":    None,
    "headload":     None,

    # Sack: generic term with no fixed weight
    "sack":         None,

}
