import random
import pandas as pd
import re

def pick_name(row, patterns, default):
    """
    Look through row.index for any column matching one of the regex patterns.
    Return the first non-null value found, otherwise default.
    """
    for pat in patterns:
        for col in row.index:
            if re.search(pat, col, re.IGNORECASE):
                val = row.get(col)
                if pd.notna(val):
                    return val
    return default

def fetch_market_device_data(device_name):
    """
    Simulates market data lookup for a given device.
    Replace this with real API calls or scrapers if needed.
    """
    sample_vendors = ['Dell', 'HPE', 'Lenovo', 'Cisco', 'Supermicro']
    sample_models = ['PowerEdge R750', 'ProLiant DL380', 'ThinkSystem SR650', 'UCS C240', 'SYS-620U']
    sample_prices = [4500, 5200, 6100, 4900, 5600]

    return {
        'Recommended Model': random.choice(sample_models),
        'Vendor': random.choice(sample_vendors),
        'Estimated Price (USD)': random.choice(sample_prices),
        'Availability': 'In Stock',
        'Lead Time (days)': random.randint(5, 14)
    }

def suggest_hw_replacements(hw_df):
    updated_df = hw_df.copy()
    for idx, row in updated_df.iterrows():
        device_name = pick_name(
            row,
            patterns=[r"device", r"server", r"asset"],
            default=f"Device-{idx}"
        )
        market_data = fetch_market_device_data(device_name)
        for key, value in market_data.items():
            updated_df.at[idx, key] = value
    return updated_df

def suggest_sw_replacements(sw_df):
    updated_df = sw_df.copy()
    for idx, row in updated_df.iterrows():
        software_name = pick_name(
            row,
            patterns=[r"app", r"application", r"software"],
            default=f"App-{idx}"
        )
        market_data = fetch_market_device_data(software_name)
        for key, value in market_data.items():
            updated_df.at[idx, key] = value
    return updated_df
# === Compatibility alias for expected import in generate_assessment.py ===
fetch_latest_device_replacement = fetch_market_device_data
