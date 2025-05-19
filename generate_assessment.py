import requests, os, json
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook
import traceback
import re

def sanitize_session_id(session_id):
    return re.sub(r"[^\w\-]", "_", session_id)

def download_file(url, dest_path):
    try:
        print(f"⬇️ Downloading: {url}")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded: {dest_path}")
    except Exception as e:
        print(f"🔴 Failed to download {url}: {e}")
        traceback.print_exc()

def send_result(webhook, session_id, module, status, message, file1=None, url1=None, file2=None, url2=None):
    payload = {
        "session_id": session_id,
        "gpt_module": module,
        "status": status,
        "message": message or ""
    }
    if file1 and url1:
        payload["file_name"] = file1
        payload["file_url"] = url1
    if file2 and url2:
        payload["file_2_name"] = file2
        payload["file_2_url"] = url2

    print(f"📤 Sending result to webhook: {webhook}")
    try:
        response = requests.post(webhook, json=payload)
        print(f"🔁 Webhook responded with: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"🔴 Webhook error: {e}")
        traceback.print_exc()

def process_assessment(session_id, email, files, webhook):
    try:
        print(f"\n🔧 Starting IT Assessment for: {session_id}")
        safe_session_id = sanitize_session_id(session_id)
        session_folder = os.path.join("temp_sessions", f"Temp_{safe_session_id}")
        os.makedirs(session_folder, exist_ok=True)

        # 🔽 Step 1: Download all files
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        # 🔍 Step 2: Identify asset inventory or GAP input
        inventory_file = next((f for f in files if f['type'] in ['asset_inventory', 'gap_working']), None)
        if not inventory_file:
            send_result(webhook, session_id, "it_assessment", "error", "Missing asset inventory file")
            return

        # 📊 Step 3a: HW GAP Excel
        try:
            hw_template = "templates/HWGapAnalysis.xlsx"
            hw_output_name = f"HWGapAnalysis_{safe_session_id}.xlsx"
            hw_output_path = os.path.join(session_folder, hw_output_name)

            wb = load_workbook(hw_template)
            ws = wb.active
            ws["A1"] = f"HW Assessment for {session_id}"
            wb.save(hw_output_path)
            print(f"✅ HW GAP Excel created: {hw_output_path}")
        except Exception as e:
            print(f"🔴 Failed to generate HW GAP Excel: {e}")
            traceback.print_exc()

        # 📊 Step 3b: SW GAP Excel
        try:
            sw_template = "templates/SWGapAnalysis.xlsx"
            sw_output_name = f"SWGapAnalysis_{safe_session_id}.xlsx"
            sw_output_path = os.path.join(session_folder, sw_output_name)

            wb = load_workbook(sw_template)
            ws = wb.active
            ws["A1"] = f"SW Assessment for {session_id}"
            wb.save(sw_output_path)
            print(f"✅ SW GAP Excel created: {sw_output_path}")
        except Exception as e:
            print(f"🔴 Failed to generate SW GAP Excel: {e}")
            traceback.print_exc()

        # 📄 Step 4: DOCX
        try:
            docx_template = "templates/IT_Current_Status_Assesment_Template.docx"
            docx_name = f"IT_Current_Status_Assessment_{safe_session_id}.docx"
            docx_path = os.path.join(session_folder, docx_name)

            doc = Document(docx_template)
            doc.paragraphs[0].text = f"Assessment Report – Session: {session_id}"
            doc.save(docx_path)
            print(f"✅ DOCX report created: {docx_path}")
        except Exception as e:
            print(f"🔴 Failed to generate DOCX: {e}")
            traceback.print_exc()

        # 📊 Step 5: PPTX
        try:
            pptx_template = "templates/IT_Infrastructure_Assessment_Report.pptx"
            pptx_name = f"IT_Infrastructure_Assessment_Report_{safe_session_id}.pptx"
            pptx_path = os.path.join(session_folder, pptx_name)

            ppt = Presentation(pptx_template)
            ppt.slides[0].shapes.title.text = "Executive Assessment Summary"
            ppt.slides[0].placeholders[1].text = f"Session ID: {session_id}"
            ppt.save(pptx_path)
            print(f"✅ PPTX summary created: {pptx_path}")
        except Exception as e:
            print(f"🔴 Failed to create PPTX: {e}")
            traceback.print_exc()

        # 🔁 Step 6: Send results – default: HW GAP + PPTX
        send_result(
            webhook,
            session_id,
            "it_assessment",
            "complete",
            "",
            hw_output_name,
            f"https://gpt-api-server-7wu8.onrender.com/files/Temp_{safe_session_id}/{hw_output_name}",
            pptx_name,
            f"https://gpt-api-server-7wu8.onrender.com/files/Temp_{safe_session_id}/{pptx_name}"
        )

    except Exception as e:
        print("💥 Fatal error in process_assessment:")
        traceback.print_exc()
