import os
import json
import time
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

# === Google Drive Utility Functions ===
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

# === DOCX/PPTX Generator Call ===
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

# === Process Assessment ===
def process_assessment(session_id, email, files):
    try:
        print(f"🚀 Starting assessment for {session_id}")

        # Step 1: Filter asset inventory files
        inventory_files = [f for f in files if f.get("type") in ["hardware_inventory", "software_inventory"]]
        if not inventory_files:
            raise Exception("No inventory files provided")

        # Placeholder: perform infrastructure analysis
        summary_count = {"basic": 5, "standard": 3, "advanced": 1, "excellent": 1}
        total = sum(summary_count.values()) or 1  # Prevent ZeroDivisionError
        summary = ", ".join([f"{tier.capitalize()}: {int((count / total) * 100)}%" for tier, count in summary_count.items()])
        findings = "Obsolete systems, legacy platforms, and performance bottlenecks identified."
        recommendations = "Migrate to hybrid infrastructure, replace legacy systems, enhance monitoring."

        # Step 2: Generate documents
        result = call_generate_api(session_id, summary, recommendations, findings)

        print("✅ Assessment completed")
        return result

    except Exception as e:
        print(f"❌ Error in process_assessment: {e}")
        traceback.print_exc()
        return {"error": str(e)}
