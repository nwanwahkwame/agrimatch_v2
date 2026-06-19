# Maps every raw name variant (HDX or MoFA) to an internal standard name.
# Lookup: CROP_MAP.get(raw_name.strip().lower(), None)
# To add a variant: drop it under the relevant crop block below.
#
# Internal names (canonical set):
#   maize, tomato, onion, cassava, yam, plantain, rice,
#   sorghum, groundnut, pepper, cowpea, millet, cocoyam,
#   garden_egg, ginger, soybean

CROP_MAP: dict[str, str] = {

    # ── Maize ────────────────────────────────────────────────────────────────
    "maize":                    "maize",
    "maize (yellow)":           "maize",
    "maize (white)":            "maize",
    "corn":                     "maize",
    "yellow corn":              "maize",
    "white corn":               "maize",
    "maize grain":              "maize",
    "maize-yellow":             "maize",

    # ── Tomato ───────────────────────────────────────────────────────────────
    "tomatoes (local)":         "tomato",
    "tomatoes (navrongo)":      "tomato",
    "tomato":                   "tomato",
    "tomatoes":                 "tomato",
    "tomato (fresh)":           "tomato",
    "tomato (local)":           "tomato",
    "fresh tomatoes":           "tomato",

    # ── Onion ────────────────────────────────────────────────────────────────
    "onions":                   "onion",
    "onion":                    "onion",
    "onions (local)":           "onion",
    "onions (imported)":        "onion",
    "dry onion":                "onion",
    "red onion":                "onion",

    # ── Cassava ──────────────────────────────────────────────────────────────
    "cassava":                  "cassava",
    "cassava (fresh)":          "cassava",
    "cassava roots":            "cassava",
    "cassava tuber":            "cassava",
    "fresh cassava":            "cassava",
    "gari":                     "cassava",   # processed cassava byproduct
    "gari (cassava)":           "cassava",
    "cassava flour":            "cassava",

    # ── Yam ──────────────────────────────────────────────────────────────────
    "yam":                      "yam",
    "yam (puna)":               "yam",
    "yam (water)":              "yam",
    "puna yam":                 "yam",
    "white yam":                "yam",
    "yams":                     "yam",
    "yam tubers":               "yam",

    # ── Plantain ─────────────────────────────────────────────────────────────
    "plantains (apem)":         "plantain",
    "plantains (apentu)":       "plantain",
    "plantain":                 "plantain",
    "plantains":                "plantain",
    "apem plantain":            "plantain",
    "apentu plantain":          "plantain",
    "cooking plantain":         "plantain",

    # ── Rice ─────────────────────────────────────────────────────────────────
    "rice (imported)":          "rice",
    "rice (local)":             "rice",
    "rice (paddy)":             "rice",
    "rice":                     "rice",
    "local rice":               "rice",
    "imported rice":            "rice",
    "paddy rice":               "rice",
    "rice (milled)":            "rice",
    "milled rice":              "rice",

    # ── Sorghum ──────────────────────────────────────────────────────────────
    "sorghum":                  "sorghum",
    "sorghum (white)":          "sorghum",
    "sorghum (red)":            "sorghum",
    "guinea corn":              "sorghum",
    "white sorghum":            "sorghum",
    "red sorghum":              "sorghum",
    "dawa":                     "sorghum",

    # ── Groundnut ────────────────────────────────────────────────────────────
    "groundnuts":               "groundnut",
    "groundnut":                "groundnut",
    "groundnuts (shelled)":     "groundnut",
    "groundnuts (unshelled)":   "groundnut",
    "peanuts":                  "groundnut",
    "peanut":                   "groundnut",
    "groundnut (shelled)":      "groundnut",
    "groundnut (unshelled)":    "groundnut",

    # ── Pepper ───────────────────────────────────────────────────────────────
    "peppers (fresh)":          "pepper",
    "peppers (dried)":          "pepper",
    "pepper (fresh)":           "pepper",
    "pepper (dried)":           "pepper",
    "pepper":                   "pepper",
    "fresh pepper":             "pepper",
    "dried pepper":             "pepper",
    "chili pepper":             "pepper",

    # ── Cowpea ───────────────────────────────────────────────────────────────
    "cowpeas":                  "cowpea",
    "cowpeas (white)":          "cowpea",
    "cowpea":                   "cowpea",
    "white beans":              "cowpea",
    "black-eyed peas":          "cowpea",
    "beans (cowpea)":           "cowpea",
    "brown beans":              "cowpea",

    # ── Millet ───────────────────────────────────────────────────────────────
    "millet":                   "millet",
    "millet (pearl)":           "millet",
    "pearl millet":             "millet",
    "bulrush millet":           "millet",
    "finger millet":            "millet",
    "fonio":                    "millet",

    # ── Cocoyam ──────────────────────────────────────────────────────────────
    "cocoyam":                  "cocoyam",
    "cocoyams":                 "cocoyam",
    "taro":                     "cocoyam",
    "taro (cocoyam)":           "cocoyam",
    "old cocoyam":              "cocoyam",
    "new cocoyam":              "cocoyam",
    "eddoes":                   "cocoyam",

    # ── Garden Egg (Eggplant) ─────────────────────────────────────────────────
    "eggplants":                "garden_egg",
    "eggplant":                 "garden_egg",
    "garden egg":               "garden_egg",
    "garden eggs":              "garden_egg",
    "garden_egg":               "garden_egg",
    "aubergine":                "garden_egg",
    "african eggplant":         "garden_egg",

    # ── Soybean ──────────────────────────────────────────────────────────────
    "soybeans":                 "soybean",
    "soybean":                  "soybean",
    "soya beans":               "soybean",
    "soya":                     "soybean",
    "soya bean":                "soybean",

    # ── Ginger ───────────────────────────────────────────────────────────────
    "ginger":                   "ginger",
    "ginger (fresh)":           "ginger",
    "ginger (dried)":           "ginger",
    "fresh ginger":             "ginger",
    "dried ginger":             "ginger",
    "ginger root":              "ginger",

    # ── Fish ─────────────────────────────────────────────────────────────────
    "fish (mackerel, fresh)":   "fish_mackerel",
    "mackerel (fresh)":         "fish_mackerel",
    "fresh mackerel":           "fish_mackerel",
    "mackerel":                 "fish_mackerel",

    # ── Chicken / Meat ───────────────────────────────────────────────────────
    "meat (chicken)":           "chicken",
    "meat (chicken, local)":    "chicken",
    "chicken":                  "chicken",
    "chicken (live)":           "chicken",
    "live chicken":             "chicken",
    "broiler":                  "chicken",

    # ── Eggs ─────────────────────────────────────────────────────────────────
    # HDX records egg prices per 30-piece tray; stored in clean_prices with
    # unit='tray' and price_ghs = price per tray (no per-kg conversion).
    "eggs":                     "eggs",
    "egg":                      "eggs",
    "eggs (tray)":              "eggs",

}

# Crops whose post-harvest residues are candidates for the waste-to-wealth
# feature (e.g. peels, husks, stalks fed into biogas or animal feed flows).
BYPRODUCT_CROPS: list[str] = [
    "cassava",      # peels → biogas / animal feed
    "maize",        # cobs, stalks → animal feed / biogas
    "rice",         # husks → fuel / building material
    "yam",          # peels → animal feed
    "plantain",     # peels → compost / animal feed
    "sorghum",      # stalks → animal feed / biogas
    "groundnut",    # shells → fuel / oil pressing residue
    "cocoyam",      # peels → compost
    "ginger",       # spent pulp → compost / extraction residue
]
