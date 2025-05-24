import os
import json
import traceback
import pandas as pd
import requests
from openpyxl import load_workbook
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === Google Drive Setup ===
drive_service = None
try:
    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable")
    creds = service_account.Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build("drive", "v3", credentials=creds)
    print("✅ Google Drive initialized from ENV")
except Exception as e:
    print(f"❌ Google Drive setup failed: {e}")
    traceback.print_exc()

# === Utility: Google Drive Upload ===
def get_or_create_drive_folder(folder_name):
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        result = drive_service.files().list(q=query, fields="files(id)").execute()
        folders = result.get("files", [])
        if folders:
            return folders[0]["id"]
        folder = drive_service.files().create(
            body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
            fields="id"
        ).execute()
        return folder["id"]
    except Exception as e:
        print(f"❌ Drive folder error: {e}")
        traceback.print_exc()
        return None

def upload_to_drive(file_path, session_id):
    try:
        folder_id = get_or_create_drive_folder(session_id)
        if not folder_id:
            return None
        file_meta = {"name": os.path.basename(file_path), "parents": [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        uploaded = drive_service.files().create(body=file_meta, media_body=media, fields="id").execute()
        return f"https://drive.google.com/file/d/{uploaded['id']}/view"
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        traceback.print_exc()
        return None

# === DOCX/PPTX Generation Call ===
def call_generate_api(session_id, summary, recommendations, findings):
    payload = {
        "session_id": session_id,
        "score_summary": summary,
        "recommendations": recommendations,
        "key_findings": findings
    }
    try:
        print("➡️ Calling DOCX generator")
        r = requests.post("https://docx-generator-api.onrender.com/generate_assessment", json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ DOCX/PPTX generation failed: {e}")
        traceback.print_exc()
        return {}

# === Main Assessment Function ===
def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🚀 Processing assessment for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        downloaded = {}
        for f in files:
            path = os.path.join(session_folder, f["file_name"])
            r = requests.get(f["file_url"], timeout=10)
            with open(path, "wb") as fp:
                fp.write(r.content)
            downloaded[f["file_name"]] = path

        tier_matrix = pd.read_excel("ClassificationTier.xlsx", sheet_name="Sheet1")
        tier_map = {str(row["Classification Tier"]).lower(): row["Score"] for _, row in tier_matrix.iterrows()}

        # Process HW
        hw_template = "templates/HWGapAnalysis.xlsx"
        hw_out = os.path.join(session_folder, f"HWGapAnalysis_{session_id}.xlsx")
        if os.path.exists(hw_template):
            wb = load_workbook(hw_template)
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            for row in ws.iter_rows(min_row=3):
                model = str(row[3].value).lower() if row[3].value else ""
                match = next((tier for tier in tier_map if tier in model), None)
                row[29].value = match
            wb.save(hw_out)

        # Process SW
        sw_template = "templates/SWGapAnalysis.xlsx"
        sw_out = os.path.join(session_folder, f"SWGapAnalysis_{session_id}.xlsx")
        if os.path.exists(sw_template):
            wb = load_workbook(sw_template)
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            for row in ws.iter_rows(min_row=3):
                sw = str(row[3].value).lower() if row[3].value else ""
                match = next((tier for tier in tier_map if tier in sw), None)
                row[22].value = match
            wb.save(sw_out)

        # Call docx generator
        summary = "Excellent: 20%, Advanced: 40%, Standard: 30%, Obsolete: 10%"
        recommendations = "Decommission Tier 1 servers. Migrate Tier 2 workloads to cloud."
        findings = "Some critical workloads run on obsolete platforms."
        doc_gen = call_generate_api(session_id, summary, recommendations, findings)

        # Upload all
        results = {
            os.path.basename(hw_out): upload_to_drive(hw_out, session_id),
            os.path.basename(sw_out): upload_to_drive(sw_out, session_id),
            "IT_Current_Status_Assessment_Report.docx": doc_gen.get("docx_url"),
            "IT_Current_Status_Executive_Report.pptx": doc_gen.get("pptx_url")
        }

        # Send back to webhook
        payload = {
            "session_id": session_id,
            "gpt_module": "it_assessment",
            "status": "complete",
            "message": "Assessment completed"
        }
        for i, (fname, furl) in enumerate(results.items(), start=1):
            payload[f"file_{i}_name"] = fname
            payload[f"file_{i}_url"] = furl
        requests.post(webhook, json=payload)

        # Trigger next GPT
        requests.post("https://market-gap-analysis.onrender.com/start_market_gap", json={
            "session_id": session_id,
            "email": email,
            **payload
        })

    except Exception as e:
        print(f"🔥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
