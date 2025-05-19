import requests, os
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook
import matplotlib.pyplot as plt
from collections import Counter

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

def send_result(webhook, session_id, module, status, message,
                file1=None, url1=None, file2=None, url2=None,
                file3=None, url3=None, file4=None, url4=None):
    payload = {
        "session_id": session_id,
        "gpt_module": module,
        "status": status
    }
    if message:
        payload["message"] = message
    if file1 and url1:
        payload["file_name"] = file1
        payload["file_url"] = url1
    if file2 and url2:
        payload["file_2_name"] = file2
        payload["file_2_url"] = url2
    if file3 and url3:
        payload["file_3_name"] = file3
        payload["file_3_url"] = url3
    if file4 and url4:
        payload["file_4_name"] = file4
        payload["file_4_url"] = url4

    print(f"📤 Sending result to webhook: {webhook}")
    try:
        response = requests.post(webhook, json=payload)
        print(f"🔁 Webhook responded with: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"🔴 Webhook error: {e}")

def generate_tier_chart(ws, output_path):
    tier_col_idx = None
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    for idx, h in enumerate(headers):
        if h and "tier" in str(h).lower():
            tier_col_idx = idx
            break
    if tier_col_idx is None:
        print("⚠️ Tier column not found.")
        return

    tiers = [str(row[tier_col_idx]).strip() for row in ws.iter_rows(min_row=2, values_only=True) if row[tier_col_idx]]
    counts = Counter(tiers)
    plt.figure(figsize=(6, 4))
    plt.bar(counts.keys(), counts.values())
    plt.title("Tier Distribution")
    plt.xlabel("Tier")
    plt.ylabel("Device Count")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Chart saved: {output_path}")

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🔧 Starting assessment for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        # Step 1: Download uploaded files
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        # Step 2: Update HWGapAnalysis and SWGapAnalysis
        hw_template = "templates/HWGapAnalysis.xlsx"
        hw_output = os.path.join(session_folder, "HWGapAnalysis.xlsx")
        if os.path.exists(hw_template):
            wb = load_workbook(hw_template)
            ws = wb.active
            ws["A1"] = f"Processed by IT Assessment for session {session_id}"
            wb.save(hw_output)
            print(f"✅ HW GAP file updated: {hw_output}")
        else:
            print("⚠️ HWGapAnalysis template missing")

        sw_template = "templates/SWGapAnalysis.xlsx"
        sw_output = os.path.join(session_folder, "SWGapAnalysis.xlsx")
        if os.path.exists(sw_template):
            wb = load_workbook(sw_template)
            ws = wb.active
            ws["A1"] = f"Processed by IT Assessment for session {session_id}"
            wb.save(sw_output)
            print(f"✅ SW GAP file updated: {sw_output}")
        else:
            print("⚠️ SWGapAnalysis template missing")

        # Step 3: Generate tier chart from HWGapAnalysis
        try:
            wb = load_workbook(hw_output)
            ws = wb.active
            generate_tier_chart(ws, os.path.join(session_folder, "tier_distribution.png"))
        except Exception as e:
            print(f"⚠️ Failed to generate chart: {e}")

        # Step 4: Generate DOCX
        docx_template = "templates/IT_Current_Status_Assesment_Template.docx"
        docx_output = os.path.join(session_folder, "IT_Current_Status_Assessment_Report.docx")
        try:
            doc = Document(docx_template)
            doc.paragraphs[0].text = f"Assessment Report - Session {session_id}"
            doc.save(docx_output)
            print(f"✅ DOCX created: {docx_output}")
        except Exception as e:
            print(f"🔴 Failed to generate DOCX: {e}")

        # Step 5: Generate PPTX
        pptx_template = "templates/IT_Infrastructure_Assessment_Report.pptx"
        pptx_output = os.path.join(session_folder, "IT_Current_Status_Executive_Report.pptx")
        try:
            ppt = Presentation(pptx_template)
            slide = ppt.slides[0]
            slide.shapes.title.text = "Executive Assessment Summary"
            slide.placeholders[1].text = f"Session ID: {session_id}"
            ppt.save(pptx_output)
            print(f"✅ PPTX created: {pptx_output}")
        except Exception as e:
            print(f"🔴 Failed to generate PPTX: {e}")

        # Step 6: Send all files to webhook
        send_result(
            webhook,
            session_id,
            "it_assessment",
            "complete",
            "Assessment completed. 4 output files generated.",
            "HWGapAnalysis.xlsx",
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/HWGapAnalysis.xlsx",
            "SWGapAnalysis.xlsx",
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/SWGapAnalysis.xlsx",
            "IT_Current_Status_Assessment_Report.docx",
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/IT_Current_Status_Assessment_Report.docx",
            "IT_Current_Status_Executive_Report.pptx",
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/IT_Current_Status_Executive_Report.pptx"
        )

    except Exception as e:
        print(f"💥 Unhandled error in process_assessment: {e}")
