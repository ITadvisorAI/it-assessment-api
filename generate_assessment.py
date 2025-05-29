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
from visualization import generate_hw_charts, generate_sw_charts  # Chart module

BASE_DIR = "temp_sessions"
tier_matrix_path = "ClassificationTier.xlsx"

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

def classify_devices(df, tier_df, is_hw=True):
    if df.empty:
        return df
    df['Tier'] = 'Unknown'
    for _, row in tier_df.iterrows():
        keyword = row['Keyword'].lower()
        tier = row['Tier']
        mask = df.apply(lambda x: keyword in str(x).lower(), axis=1)
        df.loc[mask, 'Tier'] = tier
    return df

def process_assessment(session_id, files, email):
    try:
        print(f"🚀 Processing assessment for session: {session_id}")
        session_path = os.path.join(BASE_DIR, session_id)
        os.makedirs(session_path, exist_ok=True)

        hw_file = next((f["path"] for f in files if "hardware" in f["type"]), None)
        sw_file = next((f["path"] for f in files if "software" in f["type"]), None)

        hw_df = pd.read_excel(hw_file, header=1) if hw_file else pd.DataFrame()
        sw_df = pd.read_excel(sw_file, header=1) if sw_file else pd.DataFrame()

        print("📥 HW Columns:", hw_df.columns.tolist())
        print("📥 SW Columns:", sw_df.columns.tolist())

        tier_df = pd.read_excel(tier_matrix_path)

        hw_df = classify_devices(hw_df, tier_df, is_hw=True)
        sw_df = classify_devices(sw_df, tier_df, is_hw=False)

        hw_gap_path = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
        sw_gap_path = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")
        hw_df.to_excel(hw_gap_path, index=False)
        sw_df.to_excel(sw_gap_path, index=False)

        # ✅ Generate charts
        hw_charts = generate_hw_charts(hw_gap_path, session_id)
        sw_charts = generate_sw_charts(sw_gap_path, session_id)
        print("📊 Charts generated:", hw_charts + sw_charts)

        # ✅ Summary logic with safety
        if 'Tier' in hw_df.columns and hw_df['Tier'].notnull().any():
            hw_tier_summary = hw_df['Tier'].value_counts().to_dict()
            total_hw = sum(hw_tier_summary.values())
            summary = ", ".join([f"{k}: {int(v/total_hw*100)}%" for k, v in hw_tier_summary.items()]) if total_hw > 0 else "No hardware data available"
        else:
            summary = "Tier column missing or empty in HW data."

        recommendations = "Upgrade all devices marked as Tier 4 or 'Unknown'. Consider phasing out legacy systems."
        findings = f"{len(hw_df)} hardware entries and {len(sw_df)} software entries processed and classified."

        result = call_generate_api(session_id, summary, recommendations, findings)

        upload_to_drive(hw_gap_path, session_id)
        upload_to_drive(sw_gap_path, session_id)

        print("✅ Assessment completed for session:", session_id)
        return result
    except Exception as e:
        print(f"🔥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
        return {}
