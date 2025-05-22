
import os
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
    "sw": "templates/SWGapAnalysis.xlsx",
    "docx": "templates/IT_Current_Status_Assessment_Template.docx",
    "pptx": "templates/IT_Infrastructure_Assessment_Report.pptx"
}

GENERATE_API_URL = "https://docx-generator-api.onrender.com/generate_assessment"
PUBLIC_BASE_URL = "https://it-assessment-api.onrender.com/files"
NEXT_API_URL = "https://market-gap-analysis.onrender.com/start_market_gap"

try:
    SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)
    print("✅ Google Drive client initialized.")
except Exception as e:
    drive_service = None
    print(f"❌ Failed to initialize Google Drive: {e}")

def download_file(url, dest_path):
    try:
        print(f"⬇️ Downloading: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded: {dest_path}")
    except Exception as e:
        print(f"🔴 Failed to download {url}: {e}")
        traceback.print_exc()

def get_or_create_drive_folder(folder_name):
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    response = drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
    if response['files']:
        return response['files'][0]['id']
    file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    folder = drive_service.files().create(body=file_metadata, fields='id').execute()
    return folder['id']

def upload_to_drive(local_path, session_id):
    if not drive_service:
        print("❌ Drive not initialized. Skipping upload.")
        return None
    if not os.path.exists(local_path):
        print(f"⚠️ File not found for upload: {local_path}")
        return None
    file_metadata = {'name': os.path.basename(local_path), 'parents': [get_or_create_drive_folder(session_id)]}
    media = MediaFileUpload(local_path, resumable=True)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded_file.get("id")
    print(f"📤 Uploaded to Drive: {local_path} (ID: {file_id})")
    return f"https://drive.google.com/file/d/{file_id}/view"

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
        response = requests.post(webhook, json=payload)
        print(f"📤 Sent result to tracker: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"🔴 Tracker error: {e}")
        traceback.print_exc()

def trigger_next_module(session_id, email, files):
    payload = {"session_id": session_id, "email": email}
    for i, (name, url) in enumerate(files.items(), start=1):
        payload[f"file_{i}_name"] = name
        payload[f"file_{i}_url"] = url
    try:
        response = requests.post(NEXT_API_URL, json=payload)
        print(f"📡 Triggered next module: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error calling next module: {e}")
        traceback.print_exc()

def generate_tier_chart(ws, output_path):
    tier_col_idx = None
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    for idx, h in enumerate(headers):
        if h and "tier" in str(h).lower():
            tier_col_idx = idx
            break
    if tier_col_idx is None:
        print("⚠️ Tier column not found.")
        return False
    tiers = [str(row[tier_col_idx]).strip() for row in ws.iter_rows(min_row=2, values_only=True) if row[tier_col_idx]]
    if not tiers:
        print("⚠️ No tier values found.")
        return False
    counts = Counter(tiers)
    plt.figure(figsize=(6, 4))
    plt.bar(counts.keys(), counts.values())
    plt.title("Tier Distribution")
    plt.xlabel("Tier")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Tier chart saved to: {output_path}")
    return True

def call_generate_api(session_id, score_summary, recommendations, key_findings):
    payload = {
        "session_id": session_id,
        "score_summary": score_summary,
        "recommendations": recommendations,
        "key_findings": key_findings or ""
    }
    try:
        response = requests.post(GENERATE_API_URL, json=payload)
        response.raise_for_status()
        print(f"✅ Generate API responded: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"🔴 Error calling generate_assessment: {e}")
        traceback.print_exc()
        return {}

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🔧 Starting assessment for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        file_dict = {f['type']: f for f in files if f.get('type') in REQUIRED_FILE_TYPES}
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        hw_output = os.path.join(session_folder, f"HWGapAnalysis_{session_id}.xlsx")
        sw_output = os.path.join(session_folder, f"SWGapAnalysis_{session_id}.xlsx")
        docx_output = os.path.join(session_folder, "IT_Current_Status_Assessment_Report.docx")
        pptx_output = os.path.join(session_folder, "IT_Current_Status_Executive_Report.pptx")
        chart_path = os.path.join(session_folder, "tier_distribution.png")

        if "asset_inventory" in file_dict and os.path.exists(TEMPLATES["hw"]):
            wb = load_workbook(TEMPLATES["hw"])
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            generate_tier_chart(ws, chart_path)
            wb.save(hw_output)

        if os.path.exists(TEMPLATES["sw"]):
            wb = load_workbook(TEMPLATES["sw"])
            wb.save(sw_output)

        score_summary = "Excellent: 20%, Advanced: 40%, Standard: 30%, Obsolete: 10%"
        recommendations = "Decommission Tier 1 servers and move Tier 2 apps to cloud."
        key_findings = "Some business-critical workloads are hosted on obsolete hardware."

        gen_result = call_generate_api(session_id, score_summary, recommendations, key_findings)
        if 'docx_url' in gen_result:
            docx_output = gen_result['docx_url']
        if 'pptx_url' in gen_result:
            pptx_output = gen_result['pptx_url']

        if os.path.exists(hw_output): upload_to_drive(hw_output, session_id)
        if os.path.exists(sw_output): upload_to_drive(sw_output, session_id)
        if os.path.exists(docx_output): upload_to_drive(docx_output, session_id)
        if os.path.exists(pptx_output): upload_to_drive(pptx_output, session_id)

        def get_url(path): return path if path.startswith("http") else f"{PUBLIC_BASE_URL}/{session_id}/{os.path.basename(path)}"

        files_to_send = {
            os.path.basename(hw_output): get_url(hw_output),
            os.path.basename(sw_output): get_url(sw_output),
            os.path.basename(docx_output): get_url(docx_output),
            os.path.basename(pptx_output): get_url(pptx_output)
        }

        send_result_to_tracker(webhook, session_id, "it_assessment", "complete", "Assessment completed", files_to_send)
        trigger_next_module(session_id, email, files_to_send)

    except Exception as e:
        print(f"💥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
