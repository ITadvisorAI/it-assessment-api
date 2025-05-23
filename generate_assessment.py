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

REQUIRED_FILE_TYPES = {"asset_inventory", "gap_working"}
TEMPLATES = {
    "hw": "templates/HWGapAnalysis.xlsx",
    "sw": "templates/SWGapAnalysis.xlsx"
}
GENERATE_API_URL = "https://docx-generator-api.onrender.com/generate_assessment"
PUBLIC_BASE_URL = "https://it-assessment-api.onrender.com/files"
NEXT_API_URL = "https://market-gap-analysis.onrender.com/start_market_gap"

# === Google Drive Setup from ENV ===
drive_service = None
try:
    service_account_info = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_info:
        print("🔕 Google Drive not configured (ENV missing)")
    else:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(service_account_info), scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive_service = build("drive", "v3", credentials=creds)
        print("✅ Google Drive client initialized from ENV")
except Exception as e:
    print(f"❌ Google Drive setup failed: {e}")
    traceback.print_exc()

def download_file(url, dest_path):
    try:
        print(f"⬇️ Downloading: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded: {dest_path}")
    except Exception as e:
        print(f"🔴 Download failed: {e}")
        traceback.print_exc()

def get_or_create_drive_folder(folder_name):
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    result = drive_service.files().list(q=query, fields="files(id)").execute()
    folders = result.get("files", [])
    if folders:
        return folders[0]["id"]
    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    folder = drive_service.files().create(body=metadata, fields="id").execute()
    return folder["id"]

def upload_to_drive(local_path, session_id):
    if not drive_service:
        print("⚠️ Drive not initialized.")
        return None
    if not os.path.exists(local_path):
        print(f"⚠️ File not found: {local_path}")
        return None
    folder_id = get_or_create_drive_folder(session_id)
    file_metadata = {"name": os.path.basename(local_path), "parents": [folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = uploaded["id"]
    print(f"📤 Uploaded to Drive: {file_id}")
    return f"https://drive.google.com/file/d/{file_id}/view"

def send_result_to_tracker(webhook, session_id, module, status, message, files):
    payload = {
        "session_id": session_id,
        "gpt_module": module,
        "status": status,
        "message": message
    }
    for i, (name, url) in enumerate(files.items(), start=1):
        payload[f"file_{i}_name"] = name
        payload[f"file_{i}_url"] = url
    try:
        r = requests.post(webhook, json=payload)
        print(f"📤 Tracker response: {r.status_code}")
    except Exception as e:
        print(f"❌ Tracker call failed: {e}")
        traceback.print_exc()

def trigger_next_module(session_id, email, files):
    payload = {"session_id": session_id, "email": email}
    for i, (name, url) in enumerate(files.items(), start=1):
        payload[f"file_{i}_name"] = name
        payload[f"file_{i}_url"] = url
    try:
        r = requests.post(NEXT_API_URL, json=payload)
        print(f"📡 Triggered next module: {r.status_code}")
    except Exception as e:
        print(f"❌ Trigger failed: {e}")
        traceback.print_exc()

def generate_tier_chart(ws, output_path):
    tier_col = None
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    for idx, header in enumerate(headers):
        if header and "tier" in str(header).lower():
            tier_col = idx
            break
    if tier_col is None:
        print("⚠️ Tier column not found.")
        return False
    tiers = [str(row[tier_col]) for row in ws.iter_rows(min_row=2, values_only=True) if row[tier_col]]
    counts = Counter(tiers)
    plt.bar(counts.keys(), counts.values())
    plt.title("Tier Distribution")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Saved chart: {output_path}")
    return True

def call_generate_api(session_id, summary, recommendations, findings):
    payload = {
        "session_id": session_id,
        "score_summary": summary,
        "recommendations": recommendations,
        "key_findings": findings
    }
    try:
        r = requests.post(GENERATE_API_URL, json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ Generate API failed: {e}")
        traceback.print_exc()
        return {}

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        os.makedirs(session_folder, exist_ok=True)
        file_dict = {f['type']: f for f in files if f['type'] in REQUIRED_FILE_TYPES}
        for f in files:
            download_file(f['file_url'], os.path.join(session_folder, f['file_name']))

        hw_out = os.path.join(session_folder, f"HWGapAnalysis_{session_id}.xlsx")
        sw_out = os.path.join(session_folder, f"SWGapAnalysis_{session_id}.xlsx")
        docx_path = os.path.join(session_folder, "IT_Current_Status_Assessment_Report.docx")
        pptx_path = os.path.join(session_folder, "IT_Current_Status_Executive_Report.pptx")
        chart_path = os.path.join(session_folder, "tier_distribution.png")

        if "asset_inventory" in file_dict:
            wb = load_workbook(TEMPLATES["hw"])
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            generate_tier_chart(ws, chart_path)
            wb.save(hw_out)

        if os.path.exists(TEMPLATES["sw"]):
            wb = load_workbook(TEMPLATES["sw"])
            wb.save(sw_out)

        gen = call_generate_api(
            session_id,
            "Excellent: 20%, Advanced: 40%, Standard: 30%, Obsolete: 10%",
            "Decommission Tier 1 servers. Cloud migrate Tier 2.",
            "Legacy workloads on obsolete platforms."
        )

        docx_url = gen.get("docx_url", docx_path)
        pptx_url = gen.get("pptx_url", pptx_path)

        if os.path.exists(hw_out): upload_to_drive(hw_out, session_id)
        if os.path.exists(sw_out): upload_to_drive(sw_out, session_id)
        if not docx_url.startswith("http") and os.path.exists(docx_url): docx_url = upload_to_drive(docx_url, session_id)
        if not pptx_url.startswith("http") and os.path.exists(pptx_url): pptx_url = upload_to_drive(pptx_url, session_id)

        def get_url(p): return p if p.startswith("http") else f"{PUBLIC_BASE_URL}/{session_id}/{os.path.basename(p)}"
        files_to_send = {
            os.path.basename(hw_out): get_url(hw_out),
            os.path.basename(sw_out): get_url(sw_out),
            os.path.basename(docx_url): get_url(docx_url),
            os.path.basename(pptx_url): get_url(pptx_url)
        }

        send_result_to_tracker(webhook, session_id, "it_assessment", "complete", "Assessment completed", files_to_send)
        trigger_next_module(session_id, email, files_to_send)

    except Exception as e:
        print(f"💥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
