import os
import json
import traceback
from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
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
    print("✅ Google Drive client initialized from ENV")
except Exception as e:
    print(f"❌ Google Drive setup failed: {e}")
    traceback.print_exc()

# === Utility: Create or locate session folder in Google Drive ===
def get_or_create_drive_folder(folder_name):
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        folders = results.get("files", [])
        if folders:
            return folders[0]["id"]

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        folder = drive_service.files().create(body=metadata, fields="id").execute()
        return folder["id"]
    except Exception as e:
        print(f"❌ Failed to get/create folder: {e}")
        traceback.print_exc()
        return None

# === Utility: Upload a file to Drive under the session folder ===
def upload_to_drive(file_path, session_id):
    try:
        folder_id = get_or_create_drive_folder(session_id)
        if not folder_id:
            return None

        metadata = {
            "name": os.path.basename(file_path),
            "parents": [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        uploaded = drive_service.files().create(
            body=metadata,
            media_body=media,
            fields="id"
        ).execute()

        file_id = uploaded["id"]
        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        traceback.print_exc()
        return None

# === Generate Word Report with Extended Pages ===
def generate_docx(session_id, summary, recommendations, findings, output_path):
    try:
        doc = Document()
        doc.add_heading("IT Infrastructure Assessment Report", level=1)
        doc.add_paragraph(f"Session ID: {session_id}")

        sections = [
            ("Executive Summary", summary),
            ("Infrastructure Overview", "Details on current infrastructure assets, layout, and topology."),
            ("Score Summary", summary),
            ("Key Findings", findings),
            ("Recommendations", recommendations),
            ("Security Gaps", "Analysis of identified security vulnerabilities and risks."),
            ("Compliance Overview", "How current systems align with compliance standards."),
            ("Technology Stack Gaps", "Mismatches or obsolescence in current technology stack."),
            ("Cloud Readiness", "Assessment of current systems for migration to cloud environments."),
            ("Future-State Architecture", "Suggestions for upgraded and modernized IT architecture."),
            ("Cost-Saving Opportunities", "Identified areas where cost optimization is possible."),
            ("Operational Risks", "Assessment of operational continuity and failover mechanisms."),
            ("Vendor and Platform Evaluation", "Gaps in platform support and vendor lock-in risks."),
            ("Asset Obsolescence Report", "Lists outdated or unsupported hardware/software."),
            ("Conclusion", "Summary of transformation potential and next steps.")
        ]

        for title, content in sections:
            doc.add_heading(title, level=2)
            doc.add_paragraph(content)

        doc.save(output_path)
        print(f"📝 DOCX created: {output_path}")
    except Exception as e:
        print(f"❌ DOCX generation failed: {e}")
        traceback.print_exc()

# === Generate PPTX with Dynamic Content ===
def generate_pptx(session_id, summary, recommendations, findings, output_path):
    try:
        ppt = Presentation()
        layouts = ppt.slide_layouts

        slides = [
            ("IT Executive Summary", f"Session ID: {session_id}"),
            ("Score Summary", summary),
            ("Key Findings", findings),
            ("Recommendations", recommendations),
            ("Security Gaps", "Key security vulnerabilities identified."),
            ("Compliance Risks", "Gaps in regulatory and compliance coverage."),
            ("Cloud Readiness", "Suitability of systems for cloud adoption."),
            ("Obsolete Systems", "List of legacy systems needing upgrade."),
            ("Future-State Overview", "Target architecture and capabilities."),
            ("Transformation Timeline", "Phase-wise breakdown (insert Gantt)"),
            ("Budget Highlights", "High-level cost vs. benefit insights.")
        ]

        for title, content in slides:
            slide = ppt.slides.add_slide(layouts[1])
            slide.shapes.title.text = title
            slide.placeholders[1].text = content

        ppt.save(output_path)
        print(f"📊 PPTX created: {output_path}")
    except Exception as e:
        print(f"❌ PPTX generation failed: {e}")
        traceback.print_exc()

# === Entry Point: Called via API ===
def generate_assessment_report(data):
    try:
        session_id = data["session_id"]
        summary = data["score_summary"]
        recommendations = data["recommendations"]
        findings = data.get("key_findings", "")

        output_folder = os.path.join("temp_sessions", session_id)
        os.makedirs(output_folder, exist_ok=True)

        docx_path = os.path.join(output_folder, "IT_Current_Status_Assessment_Report.docx")
        pptx_path = os.path.join(output_folder, "IT_Current_Status_Executive_Report.pptx")

        generate_docx(session_id, summary, recommendations, findings, docx_path)
        generate_pptx(session_id, summary, recommendations, findings, pptx_path)

        docx_url = upload_to_drive(docx_path, session_id)
        pptx_url = upload_to_drive(pptx_path, session_id)

        return {
            "docx_url": docx_url,
            "pptx_url": pptx_url
        }

    except Exception as e:
        print(f"❌ Error in generate_assessment_report: {e}")
        traceback.print_exc()
        return {
            "docx_url": None,
            "pptx_url": None,
            "error": str(e)
        }
