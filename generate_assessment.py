import os
import pandas as pd
import requests
import json
import logging
from market_lookup import fetch_latest_device_replacement
from visualization import generate_visual_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

logging.basicConfig(level=logging.INFO)

TEMPLATE_DIR = "templates"
OUTPUT_DIR = "output"

def classify_device(device_name, tier_matrix):
    device_name = device_name.lower()
    for keyword, tier in tier_matrix.items():
        if keyword in device_name:
            return tier
    return "Unknown"

def load_tier_matrix(filepath):
    df = pd.read_excel(filepath)
    tier_mapping = dict(zip(df['Keyword'].str.lower(), df['Tier']))
    return tier_mapping

def process_excel_file(file_info, tier_matrix):
    file_path = file_info["file_path"]
    logging.info(f"📂 Processing Excel file: {file_path}")
    df = pd.read_excel(file_path)

    if 'Device Name' in df.columns:
        df['Tier'] = df['Device Name'].apply(lambda name: classify_device(name, tier_matrix))
        df['Recommended Replacement'] = df['Device Name'].apply(fetch_latest_device_replacement)

    output_path = os.path.join(OUTPUT_DIR, f"classified_{os.path.basename(file_path)}")
    df.to_excel(output_path, index=False)
    logging.info(f"✅ Saved classified Excel to: {output_path}")
    return output_path, df

def generate_assessment(session_id, email, files, output_folder_url):
    logging.info("🚀 Starting infrastructure assessment generation...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    hw_gap_file = None
    sw_gap_file = None
    hw_data = None
    sw_data = None

    tier_matrix_path = os.path.join(TEMPLATE_DIR, "ClassificationTier.xlsx")
    tier_matrix = load_tier_matrix(tier_matrix_path)

    for f in files:
        if f["type"] == "asset_inventory" and "hardware" in f["file_name"].lower():
            hw_gap_file, hw_data = process_excel_file(f, tier_matrix)
        elif f["type"] == "asset_inventory" and "software" in f["file_name"].lower():
            sw_gap_file, sw_data = process_excel_file(f, tier_matrix)

    docx_path = generate_docx_report(session_id, email, hw_data, sw_data)
    pptx_path = generate_pptx_summary(session_id, email, hw_data, sw_data)

    charts = generate_visual_charts(hw_data, sw_data)
    logging.info(f"📊 Charts generated: {charts}")

    logging.info("🎉 Infrastructure assessment completed.")
    return {
        "session_id": session_id,
        "email": email,
        "hw_gap_file": hw_gap_file,
        "sw_gap_file": sw_gap_file,
        "docx_report": docx_path,
        "pptx_summary": pptx_path
    }
