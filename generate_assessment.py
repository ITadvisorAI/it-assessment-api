
import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report
from drive_utils import upload_to_drive

def get_direct_download_url(file_url):
    if "drive.google.com" in file_url:
        if "id=" in file_url:
            file_id = file_url.split("id=")[-1].split("&")[0]
        elif "/d/" in file_url:
            file_id = file_url.split("/d/")[1].split("/")[0]
        else:
            raise ValueError("Invalid Google Drive link format")
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return file_url

def generate_assessment(session_id, email, goal, files, next_action_webhook):
    session_path = os.path.join("temp_sessions", session_id)
    os.makedirs(session_path, exist_ok=True)
    hw_df = sw_df = None
    hw_path = sw_path = None

    for f in files:
        file_name = f["file_name"]
        file_url = get_direct_download_url(f["file_url"])
        file_type = f.get("type", "general")

        local_path = os.path.join(session_path, file_name)
        response = requests.get(file_url)
        response.raise_for_status()
        with open(local_path, "wb") as fp:
            fp.write(response.content)

        if file_type == "hardware":
            hw_df = pd.read_excel(local_path)
            hw_path = local_path
        elif file_type == "software":
            sw_df = pd.read_excel(local_path)
            sw_path = local_path

    if hw_df is not None:
        hw_df = suggest_hw_replacements(hw_df)
        hw_gap_file = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
        hw_df.to_excel(hw_gap_file, index=False)
    else:
        hw_gap_file = None

    if sw_df is not None:
        sw_df = suggest_sw_replacements(sw_df)
        sw_gap_file = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")
        sw_df.to_excel(sw_gap_file, index=False)
    else:
        sw_gap_file = None

    docx_path = generate_docx_report(session_id, email, goal, hw_df, sw_df, hw_path, sw_path)
    pptx_path = generate_pptx_report(session_id, email, goal, hw_df, sw_df)

    uploaded_files = []
    for file_path in [hw_gap_file, sw_gap_file, docx_path, pptx_path]:
        if file_path:
            uploaded_files.append(upload_to_drive(file_path, session_id))

    return {"uploaded_files": uploaded_files}

def process_assessment(payload):
    session_id = payload.get("session_id")
    email = payload.get("email")
    goal = payload.get("goal")
    files = payload.get("files", [])
    next_action_webhook = payload.get("next_action_webhook", "")
    print("[DEBUG] Entered process_assessment()")
    return generate_assessment(session_id, email, goal, files, next_action_webhook)
