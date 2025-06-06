
import os
import json
import traceback
import pandas as pd
import requests
import time
from openpyxl import load_workbook
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = "temp_sessions"
TIER_MATRIX_PATH = "ClassificationTier.xlsx"
HW_TEMPLATE = "templates/HWGapAnalysis.xlsx"
SW_TEMPLATE = "templates/SWGapAnalysis.xlsx"

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

# === Drive Utilities ===
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

# === DOCX/PPTX API Call ===
def wait_for_docx_service(url, timeout=60):
    print("⏳ Waiting for DOCX service to warm up...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.head(url, timeout=5)
            if r.status_code == 200:
                print("✅ DOCX service is ready")
                return True
        except:
            pass
        time.sleep(3)
    raise Exception("❌ DOCX service did not become ready")

def call_generate_api(session_id, summary, recommendations, findings):
    payload = {
        "session_id": session_id,
        "score_summary": summary,
        "recommendations": recommendations,
        "key_findings": findings
    }
    try:
        wait_for_docx_service("https://docx-generator-api.onrender.com/")
        for attempt in range(3):
            try:
                print(f"➡️ Attempt {attempt+1}: Calling DOCX generator...")
                r = requests.post("https://docx-generator-api.onrender.com/generate_assessment", json=payload, timeout=30)
                r.raise_for_status()
                return r.json()
            except requests.exceptions.RequestException as e:
                print(f"❌ Attempt {attempt+1} failed: {e}")
                time.sleep(5 * (attempt + 1))
        raise Exception("❌ All retries failed for DOCX generator API")
    except Exception as e:
        print(f"❌ DOCX/PPTX generation failed: {e}")
        return {}

# === Main Assessment Processor ===
def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🚀 Processing assessment for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        downloaded = {}
        for f in files:
            if not f.get("file_url"):
                continue
            path = os.path.join(session_folder, f["file_name"])
            r = requests.get(f["file_url"], timeout=10)
            with open(path, "wb") as fp:
                fp.write(r.content)
            downloaded[f["file_name"]] = path

        tier_matrix = pd.read_excel(TIER_MATRIX_PATH, sheet_name="Sheet1")
        tier_keywords = tier_matrix["Keyword"].str.lower().tolist()
        tier_values = tier_matrix["Tier"].str.lower().tolist()
        tier_map = dict(zip(tier_keywords, tier_values))
        tier_counts = {"excellent": 0, "advanced": 0, "standard": 0, "obsolete": 0}

        # Process HW
        hw_out = os.path.join(session_folder, f"HWGapAnalysis_{session_id}.xlsx")
        if os.path.exists(HW_TEMPLATE):
            wb = load_workbook(HW_TEMPLATE)
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            for row in ws.iter_rows(min_row=3):
                model = str(row[3].value).lower() if row[3].value else ""
                match = next((tier for keyword, tier in tier_map.items() if keyword in model), None)
                if match in tier_counts:
                    tier_counts[match] += 1
                row[29].value = match
            wb.save(hw_out)

        # Process SW
        sw_out = os.path.join(session_folder, f"SWGapAnalysis_{session_id}.xlsx")
        if os.path.exists(SW_TEMPLATE):
            wb = load_workbook(SW_TEMPLATE)
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            for row in ws.iter_rows(min_row=3):
                sw = str(row[3].value).lower() if row[3].value else ""
                match = next((tier for keyword, tier in tier_map.items() if keyword in sw), None)
                if match in tier_counts:
                    tier_counts[match] += 1
                row[22].value = match
            wb.save(sw_out)

        total = sum(tier_counts.values()) or 1
        summary = ", ".join([f"{tier.capitalize()}: {round(100 * count / total)}%" for tier, count in tier_counts.items()])
        recommendations = "Decommission Obsolete assets, upgrade Standard, and monitor Advanced systems."
        findings = "Tier scores were calculated from HW and SW asset inventory."

        doc_gen = call_generate_api(session_id, summary, recommendations, findings)

        results = {
            os.path.basename(hw_out): upload_to_drive(hw_out, session_id),
            os.path.basename(sw_out): upload_to_drive(sw_out, session_id),
            "IT_Current_Status_Assessment_Report.docx": doc_gen.get("docx_url"),
            "IT_Current_Status_Executive_Report.pptx": doc_gen.get("pptx_url")
        }

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
        files_for_gpt3 = [
            {"file_name": os.path.basename(hw_out), "file_url": results[os.path.basename(hw_out)], "file_type": "gap_hw"},
            {"file_name": os.path.basename(sw_out), "file_url": results[os.path.basename(sw_out)], "file_type": "gap_sw"},
            {"file_name": "IT_Current_Status_Assessment_Report.docx", "file_url": results["IT_Current_Status_Assessment_Report.docx"], "file_type": "docx"},
            {"file_name": "IT_Current_Status_Executive_Report.pptx", "file_url": results["IT_Current_Status_Executive_Report.pptx"], "file_type": "pptx"}
        ]

        requests.post("https://market-gap-analysis.onrender.com/start_market_gap", json={
            "session_id": session_id,
            "email": email,
            "gpt_module": "gap_market",
            "files": files_for_gpt3,
            "next_action_webhook": webhook
        })

        print("✅ Assessment process complete")
        return True

    except Exception as e:
        print(f"🔥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
        return False
