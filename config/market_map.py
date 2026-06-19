# Maps every raw market name variant (HDX or MoFA) to a canonical entry.
# Lookup: MARKET_MAP.get(raw_name.strip().lower())
# To add a variant: drop it under the relevant market block below.
#
# Each value is a dict with:
#   canonical_name  – single standard name used throughout the pipeline
#   region          – Ghana administrative region (post-2019 boundaries)
#   is_major_hub    – True if this is a primary wholesale/distribution hub

MARKET_MAP: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════════════════════
    # GREATER ACCRA REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Accra ────────────────────────────────────────────────────────────────
    "accra":                    {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},
    "accra agbogbloshie":       {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},
    "accra (agbogbloshie)":     {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},
    "greater accra":            {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},
    "accra central":            {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},
    "agbogbloshie":             {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},
    "kaneshie":                 {"canonical_name": "Accra",          "region": "Greater Accra", "is_major_hub": True},

    # ── Tema ─────────────────────────────────────────────────────────────────
    "tema":                     {"canonical_name": "Tema",           "region": "Greater Accra", "is_major_hub": False},
    "tema community":           {"canonical_name": "Tema",           "region": "Greater Accra", "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # ASHANTI REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Kumasi ───────────────────────────────────────────────────────────────
    "kumasi":                   {"canonical_name": "Kumasi",         "region": "Ashanti",       "is_major_hub": True},
    "kumasi central":           {"canonical_name": "Kumasi",         "region": "Ashanti",       "is_major_hub": True},
    "kumasi kejetia":           {"canonical_name": "Kumasi",         "region": "Ashanti",       "is_major_hub": True},
    "kumasi asafo":             {"canonical_name": "Kumasi",         "region": "Ashanti",       "is_major_hub": True},
    "kejetia":                  {"canonical_name": "Kumasi",         "region": "Ashanti",       "is_major_hub": True},
    "asafo":                    {"canonical_name": "Kumasi",         "region": "Ashanti",       "is_major_hub": True},

    # ── Ejura ────────────────────────────────────────────────────────────────
    "ejura":                    {"canonical_name": "Ejura",          "region": "Ashanti",       "is_major_hub": False},

    # ── Obuasi ───────────────────────────────────────────────────────────────
    "obuasi":                   {"canonical_name": "Obuasi",         "region": "Ashanti",       "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # BONO REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Sunyani ──────────────────────────────────────────────────────────────
    "sunyani":                  {"canonical_name": "Sunyani",        "region": "Bono",          "is_major_hub": True},
    "sunyani central":          {"canonical_name": "Sunyani",        "region": "Bono",          "is_major_hub": True},

    # ── Berekum ──────────────────────────────────────────────────────────────
    "berekum":                  {"canonical_name": "Berekum",        "region": "Bono",          "is_major_hub": False},

    # ── Wenchi ───────────────────────────────────────────────────────────────
    "wenchi":                   {"canonical_name": "Wenchi",         "region": "Bono",          "is_major_hub": False},

    # ── Banda ────────────────────────────────────────────────────────────────
    "banda":                    {"canonical_name": "Banda",          "region": "Bono",          "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # BONO EAST REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Techiman ─────────────────────────────────────────────────────────────
    "techiman":                 {"canonical_name": "Techiman",       "region": "Bono East",     "is_major_hub": True},
    "techiman central":         {"canonical_name": "Techiman",       "region": "Bono East",     "is_major_hub": True},

    # ── Kintampo ─────────────────────────────────────────────────────────────
    "kintampo":                 {"canonical_name": "Kintampo",       "region": "Bono East",     "is_major_hub": False},

    # ── Yeji ─────────────────────────────────────────────────────────────────
    "yeji":                     {"canonical_name": "Yeji",           "region": "Bono East",     "is_major_hub": False},

    # ── Badu ─────────────────────────────────────────────────────────────────
    "badu":                     {"canonical_name": "Badu",           "region": "Bono East",     "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # CENTRAL REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Cape Coast ───────────────────────────────────────────────────────────
    "cape coast":               {"canonical_name": "Cape Coast",     "region": "Central",       "is_major_hub": True},
    "cape coast central":       {"canonical_name": "Cape Coast",     "region": "Central",       "is_major_hub": True},

    # ── Mankessim ────────────────────────────────────────────────────────────
    "mankessim":                {"canonical_name": "Mankessim",      "region": "Central",       "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # EASTERN REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Koforidua ────────────────────────────────────────────────────────────
    "koforidua":                {"canonical_name": "Koforidua",      "region": "Eastern",       "is_major_hub": True},
    "koforidua central":        {"canonical_name": "Koforidua",      "region": "Eastern",       "is_major_hub": True},
    "new juaben":               {"canonical_name": "Koforidua",      "region": "Eastern",       "is_major_hub": True},

    # ══════════════════════════════════════════════════════════════════════════
    # VOLTA REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Ho ───────────────────────────────────────────────────────────────────
    "ho":                       {"canonical_name": "Ho",             "region": "Volta",         "is_major_hub": True},
    "ho central":               {"canonical_name": "Ho",             "region": "Volta",         "is_major_hub": True},

    # ── Hohoe ────────────────────────────────────────────────────────────────
    "hohoe":                    {"canonical_name": "Hohoe",          "region": "Volta",         "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # OTI REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Dambai ───────────────────────────────────────────────────────────────
    "dambai":                   {"canonical_name": "Dambai",         "region": "Oti",           "is_major_hub": False},

    # ── Kete Krachi ──────────────────────────────────────────────────────────
    "kete krachi":              {"canonical_name": "Kete Krachi",    "region": "Oti",           "is_major_hub": False},
    "krachi":                   {"canonical_name": "Kete Krachi",    "region": "Oti",           "is_major_hub": False},

    # ── Kadjebi ──────────────────────────────────────────────────────────────
    "kadjebi":                  {"canonical_name": "Kadjebi",        "region": "Oti",           "is_major_hub": False},

    # ── Kpassa ───────────────────────────────────────────────────────────────
    "kpassa":                   {"canonical_name": "Kpassa",         "region": "Oti",           "is_major_hub": False},

    # ── Nkwanta ──────────────────────────────────────────────────────────────
    "nkwanta":                  {"canonical_name": "Nkwanta",        "region": "Oti",           "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # WESTERN REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Sekondi-Takoradi ─────────────────────────────────────────────────────
    "sekondi/takoradi":         {"canonical_name": "Sekondi-Takoradi", "region": "Western",     "is_major_hub": True},
    "sekondi-takoradi":         {"canonical_name": "Sekondi-Takoradi", "region": "Western",     "is_major_hub": True},
    "sekondi":                  {"canonical_name": "Sekondi-Takoradi", "region": "Western",     "is_major_hub": True},
    "takoradi":                 {"canonical_name": "Sekondi-Takoradi", "region": "Western",     "is_major_hub": True},

    # ══════════════════════════════════════════════════════════════════════════
    # NORTHERN REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Tamale ───────────────────────────────────────────────────────────────
    "tamale":                   {"canonical_name": "Tamale",         "region": "Northern",      "is_major_hub": True},
    "tamale central":           {"canonical_name": "Tamale",         "region": "Northern",      "is_major_hub": True},
    "tamale market":            {"canonical_name": "Tamale",         "region": "Northern",      "is_major_hub": True},

    # ── Yendi ────────────────────────────────────────────────────────────────
    "yendi":                    {"canonical_name": "Yendi",          "region": "Northern",      "is_major_hub": False},

    # ── Gushegu ──────────────────────────────────────────────────────────────
    "gushegu":                  {"canonical_name": "Gushegu",        "region": "Northern",      "is_major_hub": False},

    # ── Kpandai ──────────────────────────────────────────────────────────────
    "kpandai":                  {"canonical_name": "Kpandai",        "region": "Northern",      "is_major_hub": False},

    # ── Bimbilla ─────────────────────────────────────────────────────────────
    "bimbilla":                 {"canonical_name": "Bimbilla",       "region": "Northern",      "is_major_hub": False},

    # ── Saboba ───────────────────────────────────────────────────────────────
    "saboba":                   {"canonical_name": "Saboba",         "region": "Northern",      "is_major_hub": False},

    # ── Zabzugu ──────────────────────────────────────────────────────────────
    "zabzugu":                  {"canonical_name": "Zabzugu",        "region": "Northern",      "is_major_hub": False},

    # ── Salaga ───────────────────────────────────────────────────────────────
    "salaga":                   {"canonical_name": "Salaga",         "region": "Northern",      "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # SAVANNAH REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Damongo ──────────────────────────────────────────────────────────────
    "damongo":                  {"canonical_name": "Damongo",        "region": "Savannah",      "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # NORTH EAST REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Nalerigu ─────────────────────────────────────────────────────────────
    "nalerigu":                 {"canonical_name": "Nalerigu",       "region": "North East",    "is_major_hub": False},
    "nalerigu market":          {"canonical_name": "Nalerigu",       "region": "North East",    "is_major_hub": False},

    # ── Bunkprugu ────────────────────────────────────────────────────────────
    "bunkprugu":                {"canonical_name": "Bunkprugu",      "region": "North East",    "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # UPPER EAST REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Bolgatanga ───────────────────────────────────────────────────────────
    "bolgatanga":               {"canonical_name": "Bolgatanga",     "region": "Upper East",    "is_major_hub": True},
    "bolga":                    {"canonical_name": "Bolgatanga",     "region": "Upper East",    "is_major_hub": True},
    "bolgatanga central":       {"canonical_name": "Bolgatanga",     "region": "Upper East",    "is_major_hub": True},

    # ── Navrongo ─────────────────────────────────────────────────────────────
    "navrongo":                 {"canonical_name": "Navrongo",       "region": "Upper East",    "is_major_hub": False},

    # ── Bawku ────────────────────────────────────────────────────────────────
    "bawku":                    {"canonical_name": "Bawku",          "region": "Upper East",    "is_major_hub": False},
    "bawku central":            {"canonical_name": "Bawku",          "region": "Upper East",    "is_major_hub": False},

    # ── Bongo ────────────────────────────────────────────────────────────────
    "bongo":                    {"canonical_name": "Bongo",          "region": "Upper East",    "is_major_hub": False},

    # ── Garu ─────────────────────────────────────────────────────────────────
    "garu":                     {"canonical_name": "Garu",           "region": "Upper East",    "is_major_hub": False},

    # ── Wichau ───────────────────────────────────────────────────────────────
    "wichau":                   {"canonical_name": "Wichau",         "region": "Upper East",    "is_major_hub": False},

    # ══════════════════════════════════════════════════════════════════════════
    # UPPER WEST REGION
    # ══════════════════════════════════════════════════════════════════════════

    # ── Wa ───────────────────────────────────────────────────────────────────
    "wa":                       {"canonical_name": "Wa",             "region": "Upper West",    "is_major_hub": True},
    "wa central":               {"canonical_name": "Wa",             "region": "Upper West",    "is_major_hub": True},
    "wa market":                {"canonical_name": "Wa",             "region": "Upper West",    "is_major_hub": True},

    # ── Jirapa ───────────────────────────────────────────────────────────────
    "jirapa":                   {"canonical_name": "Jirapa",         "region": "Upper West",    "is_major_hub": False},

    # ── Lawra ────────────────────────────────────────────────────────────────
    "lawra":                    {"canonical_name": "Lawra",          "region": "Upper West",    "is_major_hub": False},

    # ── Nadowli ──────────────────────────────────────────────────────────────
    "nadowli":                  {"canonical_name": "Nadowli",        "region": "Upper West",    "is_major_hub": False},

    # ── Tumu ─────────────────────────────────────────────────────────────────
    "tumu":                     {"canonical_name": "Tumu",           "region": "Upper West",    "is_major_hub": False},

    # ── Funbisi ──────────────────────────────────────────────────────────────
    "funbisi":                  {"canonical_name": "Funbisi",        "region": "Upper West",    "is_major_hub": False},

    # ── Kajeji ───────────────────────────────────────────────────────────────
    "kajeji":                   {"canonical_name": "Kajeji",         "region": "Upper West",    "is_major_hub": False},

}
