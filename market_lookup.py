
import requests
import traceback

# Mocked online market lookup function
def lookup_latest_market_device(model_name):
    """
    Simulates querying the internet or API to get latest device replacements.
    You can replace this with actual API calls to vendors or aggregators.
    """
    try:
        if not model_name:
            return {}

        # Simulated response – replace with actual API call if needed
        simulated_market_data = {
            "Dell PowerEdge R730": {"replacement": "Dell PowerEdge R760", "release_year": 2023, "tier": "Excellent"},
            "HPE ProLiant DL380 Gen9": {"replacement": "HPE DL380 Gen11", "release_year": 2024, "tier": "Advanced"},
            "Cisco UCS C240 M4": {"replacement": "Cisco UCS C245 M6", "release_year": 2023, "tier": "Excellent"},
            "Lenovo ThinkSystem SR650": {"replacement": "Lenovo ThinkSystem SR670 V3", "release_year": 2024, "tier": "Excellent"},
        }

        for key in simulated_market_data:
            if key.lower() in model_name.lower():
                return simulated_market_data[key]

        # Fallback if no match found
        return {"replacement": "No current match found", "release_year": None, "tier": "Standard"}

    except Exception as e:
        print(f"❌ Market lookup failed for '{model_name}': {e}")
        traceback.print_exc()
        return {}
