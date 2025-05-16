import requests, os
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook

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

def send_result(webhook, session_id, module, status, message, file1=None, url1=None, file2=None, url2=None):
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

    print(f"📤 Sending result to webhook: {webhook}")
    try:
        response = requests.post(webhook, json=payload)
        print(f"🔁 Webhook responded with: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"🔴 Webhook error: {e}")

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🔧 Starting assessment for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        # Step 1: Download all files
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        # Step 2: Identify inventory file
        inventory_file = next((f for f in files if f['type'] in ['asset_inventory', 'gap_working']), None)
        if not inventory_file:
            send_result(webhook, session_id, "it_assessment", "error", "Missing asset inventory file")
            return

        # Step 3: Update GapAnalysis.xlsx template
        gap_template = "templates/GapAnalysis.xlsx"
        gap_output = f"Assessment_GAP_Working_{session_id}.xlsx"
        gap_output_path = os.path.join(session_folder, gap_output)
        try:
            wb = load_workbook(gap_template)
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            ws["A1"] = f"Processed by IT Assessment for session {session_id}"
            wb.save(gap_output_path)
            print(f"✅ GAP Analysis file updated: {gap_output_path}")
        except Exception as e:
            print(f"🔴 Failed to update GapAnalysis file: {e}")

        # Step 4: Create DOCX
        docx_name = f"IT_Current_Status_Assessment_{session_id}.docx"
        docx_path = os.path.join(session_folder, docx_name)
        try:
            doc = Document("templates/IT_Current_Status_Assesment_Template.docx")
            doc.paragraphs[0].text = f"Assessment Report - Session {session_id}"
            doc.save(docx_path)
            print(f"✅ DOCX generated: {docx_path}")
        except Exception as e:
            print(f"🔴 Failed to generate DOCX: {e}")

        # Step 5: Create PPTX
        pptx_name = f"IT_Infrastructure_Assessment_Executive_Summary_{session_id}.pptx"
        pptx_path = os.path.join(session_folder, pptx_name)
        try:
            ppt = Presentation("templates/IT_Infrastructure_Assessment_Executive_Summary.pptx")
            ppt.slides[0].shapes.title.text = "Executive Assessment Summary"
            ppt.slides[0].placeholders[1].text = f"Session ID: {session_id}"
            ppt.save(pptx_path)
            print(f"✅ PPTX generated: {pptx_path}")
        except Exception as e:
            print(f"🔴 Failed to generate PPTX: {e}")

        # Step 6: Post result
        send_result(
            webhook,
            session_id,
            "it_assessment",
            "complete",
            "",
            gap_output,
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{gap_output}",
            pptx_name,
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{pptx_name}"
        )

    except Exception as e:
        print(f"💥 Unhandled error in process_assessment: {e}")
