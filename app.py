import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from report_docx import generate_docx_report
from drive_utils import upload_file_to_drive
from report_pptx import generate_pptx_report

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

def generate_assessment(session_id, email, goal, files, next_action_webhook=""):
    session_path = os.path.join("temp_sessions", session_id)
    os.makedirs(session_path, exist_ok=True)

    hw_df = sw_df = None
    hw_file_path = sw_file_path = ""

    hw_template_path = os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx")
    sw_template_path = os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx")
    hw_base_df = pd.read_excel(hw_template_path)
    sw_base_df = pd.read_excel(sw_template_path)

    classification_df = pd.read_excel(
        os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx")
    )

    for file in files:
        ftype = file['type'].lower()
        file_url = file['file_url']
        file_name = file['file_name']
        local_path = os.path.join(session_path, file_name)

        if file_url.startswith(("http://", "https://")):
            response = requests.get(file_url)
            response.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(response.content)
        else:
            with open(file_url, "rb") as src, open(local_path, "wb") as dst:
                dst.write(src.read())

        if "hardware" in ftype or "hw" in file_name.lower():
            hw_file_path = local_path
        elif "software" in ftype or "sw" in file_name.lower():
            sw_file_path = local_path

    def merge_with_template(template_df, inventory_df):
        for col in inventory_df.columns:
            if col not in template_df.columns:
                template_df[col] = None
        inventory_df = inventory_df.reindex(columns=template_df.columns, fill_value=None)
        return pd.concat([template_df, inventory_df], ignore_index=True)

    def apply_classification(df):
        if df is not None and not df.empty and "Tier Total Score" in df.columns:
            return df.merge(classification_df, how="left", left_on="Tier Total Score", right_on="Score")
        return df
