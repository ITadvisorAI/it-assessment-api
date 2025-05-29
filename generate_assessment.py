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
from visualization import generate_hw_charts, generate_sw_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

BASE_DIR = "temp_sessions"
tier_matrix_path = "ClassificationTier.xlsx"

# === README-Based Instruction Mapping (simplified from docx)
REQUIRED_COLUMNS_HW = [
    "Asset ID", "Hardware Type", "Manufacturer", "Model",
    "Processor / CPU Specs", "RAM (GB)", "Storage Capacity (Raw & Usable)",
    "RAID / Disk Configuration", "Tier Classification", "Calculation",
    "Latest Hardware Make", "Latest Hardware Model", "Latest HW Score 5",
    "GAP Remediation cost"
]

REQUIRED_COLUMNS_SW = [
    "Application ID", "Application Name", "Business Function", "Criticality",
    "Hosting Type", "Cloud Provider", "Number of Users", "Authentication Method",
    "Dependent Systems", "Tier Classification referencing tier metrix in ClassificationTier.xlsx",
    "Total Score", "Latest operating System", "Latest OS Score (5)", "GAP Remediation cost"
]

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

def validate_columns(df, expected_columns, label="HW"):
    missing = [col for col in expected_columns if col not in df.columns]
    if missing:
        print(f"❌ Missing columns in {label} file: {missing}")
        return False, missing
    print(f"✅ {label} columns validated")
    return True, []

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

        # ✅ Validate columns before processing
        valid_hw, missing_hw = validate_columns(hw_df, REQUIRED_COLUMNS_HW, label="HW") if not hw_df.empty else (True, [])
        valid_sw, missing_sw = validate_columns(sw_df, REQUIRED_COLUMNS_SW, label="SW") if not sw_df.empty else (True, [])

        if not valid_hw or not valid_sw:
            return {
                "status": "error",
                "message": "Missing columns in uploaded files.",
                "missing_hw": missing_hw,
                "missing_sw": missing_sw
            }

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

        api_result = call_generate_api(session_id, summary, recommendations, findings)

        # ✅ Generate DOCX and PPTX reports with charts
        docx_path = generate_docx_report(session_id)
        pptx_path = generate_pptx_report(session_id)

        # ✅ Upload all outputs
        upload_to_drive(hw_gap_path, session_id)
        upload_to_drive(sw_gap_path, session_id)
        upload_to_drive(docx_path, session_id)
        upload_to_drive(pptx_path, session_id)

        print("✅ Assessment completed for session:", session_id)
        return {
            "status": "complete",
            "docx": docx_path,
            "pptx": pptx_path,
            "api_response": api_result
        }
    except Exception as e:
        print(f"🔥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
        return {}
