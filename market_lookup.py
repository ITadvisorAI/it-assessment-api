
import random
import pandas as pd

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
        device_name = row.get('Device Name') or row.get('Model') or f"Device-{idx}"
        market_data = fetch_market_device_data(device_name)
        for key, value in market_data.items():
            updated_df.at[idx, key] = value
    return updated_df

def suggest_sw_replacements(sw_df):
    updated_df = sw_df.copy()
    for idx, row in updated_df.iterrows():
        software_name = row.get('Software Name') or row.get('Application') or f"App-{idx}"
        market_data = fetch_market_device_data(software_name)
        for key, value in market_data.items():
            updated_df.at[idx, key] = value
    return updated_df
