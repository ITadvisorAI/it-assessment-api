import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

"""Utilities to generate an IT assessment report.

The :func:`generate_assessment` function downloads the provided Excel files
into a per-session directory. If the ``file_url`` field of an entry starts with
``http://`` or ``https://`` the file is fetched using :func:`requests.get`.
Otherwise ``file_url`` is treated as a local path and the file is copied
directly. The downloaded files are then processed to produce reports and charts.
"""

def generate_assessment(session_id, email, goal, files, next_action_webhook):
    session_path = os.path.join("temp_sessions", session_id)
    os.makedirs(session_path, exist_ok=True)

    hw_df = sw_df = None
    hw_file_path = sw_file_path = ""

    # Load template spreadsheets as base DataFrames
    hw_template_path = os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx")
    sw_template_path = os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx")
    hw_base_df = pd.read_excel(hw_template_path)
    sw_base_df = pd.read_excel(sw_template_path)

    # Classification lookup table
    classification_df = pd.read_excel(
        os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx")
    )

    for file in files:
        ftype = file['type'].lower()
        file_url = file['file_url']
        file_name = file['file_name']
        local_path = os.path.join(session_path, file_name)

        # Download remote files or copy local ones
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
        """Ensure inventory columns match template layout and append."""
        for col in inventory_df.columns:
            if col not in template_df.columns:
                template_df[col] = None
        inventory_df = inventory_df.reindex(columns=template_df.columns, fill_value=None)
        return pd.concat([template_df, inventory_df], ignore_index=True)

    def apply_classification(df):
        if df is not None and not df.empty and "Tier Total Score" in df.columns:
            return df.merge(classification_df, how="left", left_on="Tier Total Score", right_on="Score")
        return df

    if hw_file_path:
        hw_inventory = pd.read_excel(hw_file_path)
        hw_df = merge_with_template(hw_base_df, hw_inventory)
        hw_df = suggest_hw_replacements(hw_df)
        hw_df = apply_classification(hw_df)

    if sw_file_path:
        sw_inventory = pd.read_excel(sw_file_path)
        sw_df = merge_with_template(sw_base_df, sw_inventory)
        sw_df = suggest_sw_replacements(sw_df)
        sw_df = apply_classification(sw_df)

    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    docx_path = generate_docx_report(session_id, hw_df, sw_df, chart_paths)
    pptx_path = generate_pptx_report(session_id, hw_df, sw_df, chart_paths)

    # Save Excel gap files
    hw_gap_path = sw_gap_path = None
    if hw_df is not None:
        hw_gap_path = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
        hw_df.to_excel(hw_gap_path, index=False)
    if sw_df is not None:
        sw_gap_path = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")
        sw_df.to_excel(sw_gap_path, index=False)

    # Send to next GPT module
    payload = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
        "message": "Assessment completed",
        "file_1_name": f"HWGapAnalysis_{session_id}.xlsx",
        "file_1_url": f"/files/{session_id}/HWGapAnalysis_{session_id}.xlsx",
        "file_2_name": f"SWGapAnalysis_{session_id}.xlsx",
        "file_2_url": f"/files/{session_id}/SWGapAnalysis_{session_id}.xlsx",
        "file_3_name": "IT_Current_Status_Assessment_Report.docx",
        "file_3_url": f"/files/{session_id}/IT_Current_Status_Assessment_Report.docx",
        "file_4_name": "IT_Current_Status_Executive_Report.pptx",
        "file_4_url": f"/files/{session_id}/IT_Current_Status_Executive_Report.pptx"
    }

    try:
        response = requests.post(next_action_webhook, json=payload)
        print(f"📤 Sent results to next module. Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to notify next GPT module: {e}")

    return payload

def process_assessment(data):
    session_id = data.get("session_id")
    email = data.get("email")
    goal = data.get("goal", "project plan")
    files = data.get("files", [])
    next_action_webhook = data.get("next_action_webhook", "")

    return generate_assessment(session_id, email, goal, files, next_action_webhook)
