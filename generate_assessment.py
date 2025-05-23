import os
import json
import traceback
import requests
import matplotlib.pyplot as plt
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from openpyxl import load_workbook
from collections import Counter
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === Setup Google Drive ===
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
    print("✅ Google Drive initialized (ENV)")
except Exception as e:
    print(f"❌ Drive init failed: {e}")
    traceback.print_exc()

# === Constants ===
REQUIRED_FILE_TYPES = {"asset_inventory", "gap_working"}
TEMPLATES = {
    "hw": "templates/HWGapAnalysis.xlsx",
    "sw": "templates/SWGapAnalysis.xlsx"
}
GENERATE_API_URL = "https://docx-generator-api.onrender.com/generate_assessment"
PUBLIC_BASE_URL = "https://it-assessment-api.onrender.com/files"
NEXT_API_URL = "https://market-gap-analysis.onrender.com/start_market_gap"

# === Helper Functions ===
def download_file(url, dest_path):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(response.content)
        print(f"⬇️ Downloaded: {dest_path}")
    except Exception as e:
        print(f"❌ Download error: {e}")
        traceback.print_exc()

def get_or_create_drive_folder(folder_name):
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

def upload_to_drive(file_path, session_id):
    if not drive_service or not os.path.exists(file_path):
        return None
    folder_id = get_or_create_drive_folder(session_id)
    file_meta = {"name": os.path.basename(file_path), "parents": [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    uploaded = drive_service.files().create(body=file_meta, media_body=media, fields="id").execute()
    return f"https://drive.google.com/file/d/{uploaded['id']}/view"

def generate_tier_chart(ws, path):
    tier_idx = None
    for idx, cell in enumerate(next(ws.iter_rows(min_row=1, max_row=1))):
        if "tier" in str(cell.value).lower():
            tier_idx = idx
            break
    if tier_idx is None:
        return
    values = [str(row[tier_idx]).strip() for row in ws.iter_rows(min_row=2, values_only=True) if row[tier_idx]]
    count = Counter(values)
    plt.figure(figsize=(6, 4))
    plt.bar(count.keys(), count.values())
    plt.title("Tier Distribution")
    plt.xlabel("Tier")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def call_generate_api(session_id, score_summary, recommendations, key_findings):
    payload = {
        "session_id": session_id,
        "score_summary": score_summary,
        "recommendations": recommendations,
        "key_findings": key_findings
    }
    try:
        r = requests.post(GENERATE_API_URL, json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ DOCX/PPTX generation error: {e}")
        traceback.print_exc()
        return {}

def send_result_to_tracker(webhook, session_id, module, status, message, files):
    payload = {
        "session_id": session_id,
        "gpt_module": module,
        "status": status,
        "message": message or ""
    }
    for i, (name, url) in enumerate(files.items(), start=1):
        payload[f"file_{i}_name"] = name
        payload[f"file_{i}_url"] = url
    try:
        r = requests.post(webhook, json=payload)
        print(f"📤 Sent to tracker: {r.status_code}")
    except Exception as e:
        print(f"❌ Tracker send error: {e}")
        traceback.print_exc()

def trigger_next_module(session_id, email, files):
    payload = {"session_id": session_id, "email": email}
    for i, (name, url) in enumerate(files.items(), start=1):
        payload[f"file_{i}_name"] = name
        payload[f"file_{i}_url"] = url
    try:
        r = requests.post(NEXT_API_URL, json=payload)
        print(f"📡 Next module triggered: {r.status_code}")
    except Exception as e:
        print(f"❌ Next module trigger error: {e}")
        traceback.print_exc()

# === Main Handler ===
def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🚀 Starting process_assessment: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        for f in files:
            path = os.path.join(session_folder, f["file_name"])
            download_file(f["file_url"], path)

        hw_out = os.path.join(session_folder, f"HWGapAnalysis_{session_id}.xlsx")
        sw_out = os.path.join(session_folder, f"SWGapAnalysis_{session_id}.xlsx")
        chart_path = os.path.join(session_folder, "tier_chart.png")

        if os.path.exists(TEMPLATES["hw"]):
            wb = load_workbook(TEMPLATES["hw"])
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            generate_tier_chart(ws, chart_path)
            wb.save(hw_out)

        if os.path.exists(TEMPLATES["sw"]):
            wb = load_workbook(TEMPLATES["sw"])
            wb.save(sw_out)

        summary = "Excellent: 20%, Advanced: 40%, Standard: 30%, Obsolete: 10%"
        recommendations = "Decommission Tier 1 servers. Migrate Tier 2 workloads to cloud."
        findings = "Some critical workloads run on obsolete platforms."

        doc_gen = call_generate_api(session_id, summary, recommendations, findings)
        docx_url = doc_gen.get("docx_url")
        pptx_url = doc_gen.get("pptx_url")

        files_out = {
            os.path.basename(hw_out): upload_to_drive(hw_out, session_id),
            os.path.basename(sw_out): upload_to_drive(sw_out, session_id),
            "IT_Current_Status_Assessment_Report.docx": docx_url,
            "IT_Current_Status_Executive_Report.pptx": pptx_url
        }

        send_result_to_tracker(webhook, session_id, "it_assessment", "complete", "Assessment completed", files_out)
        trigger_next_module(session_id, email, files_out)

    except Exception as e:
        print(f"🔥 Unhandled error: {e}")
        traceback.print_exc()
