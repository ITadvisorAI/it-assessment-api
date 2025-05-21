import requests, os, traceback
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches
from pptx import Presentation
from pptx.util import Inches
from openpyxl import load_workbook
from collections import Counter

REQUIRED_FILE_TYPES = {"asset_inventory", "gap_working"}
TEMPLATES = {
    "hw": "templates/HWGapAnalysis.xlsx",
    "sw": "templates/SWGapAnalysis.xlsx",
    "docx": "templates/IT_Current_Status_Assesment_Template.docx",
    "pptx": "templates/IT_Infrastructure_Assessment_Report.pptx"
}
GENERATE_API_URL = "https://docx-generator-api.onrender.com/generate_assessment"

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

def send_result(webhook, session_id, module, status, message, files):
    payload = {
        "session_id": session_id,
        "gpt_module": module,
        "status": status,
        "message": message or ""
    }
    for i, (name, url) in enumerate(files.items(), start=1):
        payload[f"file_{i}_name"] = name
        payload[f"file_{i}_url"] = url

    print(f"📤 Sending result to webhook: {webhook}")
    try:
        response = requests.post(webhook, json=payload)
        print(f"🔁 Webhook responded with: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"🔴 Webhook error: {e}")
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
    plt.bar(counts.keys(), counts.values(), color='skyblue')
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
    print(f"📤 Calling generate_assessment API: {GENERATE_API_URL}")
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

        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"

        file_dict = {f['type']: f for f in files if f.get('type') in REQUIRED_FILE_TYPES}
        missing = REQUIRED_FILE_TYPES - file_dict.keys()
        if missing:
            raise ValueError(f"Missing required file types: {', '.join(missing)}")

        for key, path in TEMPLATES.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing template: {path}")

        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        hw_output = os.path.join(session_folder, f"HWGapAnalysis_{session_id}.xlsx")
        sw_output = os.path.join(session_folder, f"SWGapAnalysis_{session_id}.xlsx")
        docx_output = os.path.join(session_folder, "IT_Current_Status_Assessment_Report.docx")
        pptx_output = os.path.join(session_folder, "IT_Current_Status_Executive_Report.pptx")
        chart_path = os.path.join(session_folder, "tier_distribution.png")

        try:
            wb = load_workbook(TEMPLATES["hw"])
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            generate_tier_chart(ws, chart_path)
            wb.save(hw_output)
            print(f"✅ HW GAP file: {hw_output}")
        except Exception as e:
            print(f"🔴 HW GAP failed: {e}")
            traceback.print_exc()

        try:
            wb = load_workbook(TEMPLATES["sw"])
            wb.save(sw_output)
            print(f"✅ SW GAP file: {sw_output}")
        except Exception as e:
            print(f"🔴 SW GAP failed: {e}")
            traceback.print_exc()

        try:
            score_summary = "Excellent: 20%, Advanced: 40%, Standard: 30%, Obsolete: 10%"
            recommendations = "Decommission Tier 1 servers and move Tier 2 apps to cloud."
            key_findings = "Some business-critical workloads are hosted on obsolete hardware."
            gen_result = call_generate_api(session_id, score_summary, recommendations, key_findings)

            if 'docx_url' in gen_result:
                docx_output = gen_result['docx_url']
            if 'pptx_url' in gen_result:
                pptx_output = gen_result['pptx_url']

        except Exception as e:
            print(f"🔴 External DOCX/PPTX generation failed: {e}")
            traceback.print_exc()

        files_to_send = {
            os.path.basename(hw_output): f"https://it-assessment-api.onrender.com/files/{folder_name}/{os.path.basename(hw_output)}",
            os.path.basename(sw_output): f"https://it-assessment-api.onrender.com/files/{folder_name}/{os.path.basename(sw_output)}",
            os.path.basename(docx_output): docx_output if docx_output.startswith("http") else f"https://it-assessment-api.onrender.com/files/{folder_name}/{os.path.basename(docx_output)}",
            os.path.basename(pptx_output): pptx_output if pptx_output.startswith("http") else f"https://it-assessment-api.onrender.com/files/{folder_name}/{os.path.basename(pptx_output)}"
        }

        send_result(webhook, session_id, "it_assessment", "complete", "Assessment completed", files_to_send)

    except Exception as e:
        print(f"💥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
