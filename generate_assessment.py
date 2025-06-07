import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

def generate_assessment(session_id, email, goal, files, next_action_webhook):
    session_path = os.path.join("temp_sessions", session_id)
    os.makedirs(session_path, exist_ok=True)

    hw_df = sw_df = None
    hw_file_path = sw_file_path = ""

    for file in files:
        ftype = file['type'].lower()
        file_url = file['file_url']
        file_name = file['file_name']
        local_path = os.path.join(session_path, file_name)

        # Simulate download (actual logic may involve URL fetching)
        with open(local_path, "wb") as f:
            f.write(open(file_url, "rb").read())

        if "hardware" in ftype or "hw" in file_name.lower():
            hw_file_path = local_path
        elif "software" in ftype or "sw" in file_name.lower():
            sw_file_path = local_path

    if hw_file_path:
        hw_df = pd.read_excel(hw_file_path)
        hw_df = suggest_hw_replacements(hw_df)

    if sw_file_path:
        sw_df = pd.read_excel(sw_file_path)
        sw_df = suggest_sw_replacements(sw_df)

    chart_paths = generate_charts(session_id, hw_df, sw_df)

    generate_docx_report(session_id, hw_df, sw_df, chart_paths)
    generate_pptx_report(session_id, hw_df, sw_df, chart_paths)

    # Save Excel gap files
    if hw_df is not None:
        hw_df.to_excel(os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx"), index=False)
    if sw_df is not None:
        sw_df.to_excel(os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx"), index=False)

    # Send to next GPT module
    payload = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
        "message": "Assessment completed",
        "file_1_name": f"HWGapAnalysis_{session_id}.xlsx",
        "file_1_url": f"https://it-assessment-api.onrender.com/files/HWGapAnalysis_{session_id}.xlsx",
        "file_2_name": f"SWGapAnalysis_{session_id}.xlsx",
        "file_2_url": f"https://it-assessment-api.onrender.com/files/SWGapAnalysis_{session_id}.xlsx",
        "file_3_name": "IT_Current_Status_Assessment_Report.docx",
        "file_3_url": f"https://it-assessment-api.onrender.com/files/{session_id}/IT_Current_Status_Assessment_Report.docx",
        "file_4_name": "IT_Current_Status_Executive_Report.pptx",
        "file_4_url": f"https://it-assessment-api.onrender.com/files/{session_id}/IT_Current_Status_Executive_Report.pptx"
    }

    try:
        response = requests.post(next_action_webhook, json=payload)
        print(f"📤 Sent results to next module. Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to notify next GPT module: {e}")
