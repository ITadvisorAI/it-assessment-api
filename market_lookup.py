import requests
import random

def fetch_market_device_data(device_name):
    """
    Simulates market data lookup for a given device.
    Replace this stub with real API calls or database queries as needed.
    """
    sample_vendors = ['Dell', 'HPE', 'Lenovo', 'Cisco', 'Supermicro']
    sample_models = ['PowerEdge R750', 'ProLiant DL380', 'ThinkSystem SR650', 'UCS C240', 'SYS-620U']
    sample_prices = [4500, 5200, 6100, 4900, 5600]

    data = {
        'Recommended Model': random.choice(sample_models),
        'Vendor': random.choice(sample_vendors),
        'Estimated Price (USD)': random.choice(sample_prices),
        'Availability': 'In Stock',
        'Lead Time (days)': random.randint(5, 14)
    }

    return data
