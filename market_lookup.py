import traceback

# Simulated market response fallback
DEFAULT_RESULT = {
    "replacement": "No current match found",
    "release_year": None,
    "tier": "Standard"
}

# Mocked online market lookup function
def lookup_latest_market_device(model_name):
    """
    Simulates querying the internet or API to get latest device replacements.
    Replace this logic with actual API calls to vendors or marketplaces if needed.
    """
    try:
        if not model_name:
            return DEFAULT_RESULT

        model_name = model_name.lower()

        simulated_market_data = {
            "dell poweredge r730": {
                "replacement": "Dell PowerEdge R760",
                "release_year": 2023,
                "tier": "Excellent"
            },
            "hpe proliant dl380 gen9": {
                "replacement": "HPE DL380 Gen11",
                "release_year": 2024,
                "tier": "Advanced"
            },
            "cisco ucs c240 m4": {
                "replacement": "Cisco UCS C245 M6",
                "release_year": 2023,
                "tier": "Excellent"
            },
            "lenovo thinksystem sr650": {
                "replacement": "Lenovo ThinkSystem SR670 V3",
                "release_year": 2024,
                "tier": "Excellent"
            }
        }

        for key, value in simulated_market_data.items():
            if key in model_name:
                return value

        return DEFAULT_RESULT

    except Exception as e:
        print(f"❌ Market lookup failed for '{model_name}': {e}")
        traceback.print_exc()
        return DEFAULT_RESULT
