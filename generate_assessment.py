import requests, os
from docx import Document
from pptx import Presentation

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

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🔧 Thread started for session: {session_id}")
        print(f"🔍 Files received: {[f['file_name'] for f in files]}")

        os.makedirs(session_folder, exist_ok=True)
        print(f"📁 Created session folder: {session_folder}")

        # Step 1: Download input files
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        # Step 2: Check for inventory file
        inventory_file = next((f for f in files if f['type'] in ['asset_inventory', 'gap_working']), None)
        if not inventory_file:
            print("❌ No inventory file found")
            send_result(webhook, session_id, "it_assessment", "error", "Missing asset inventory file")
            return

        # Step 3: Generate DOCX from template
        docx_name = f"Assessment_Report_{session_id}.docx"
        docx_path = os.path.join(session_folder, docx_name)
        try:
            template_docx = Document("templates/IT_Current_Status_Assesment_Template.docx")
            template_docx.paragraphs[0].text = f"Assessment Report - Session {session_id}"
            template_docx.save(docx_path)
            print(f"✅ Created DOCX: {docx_path}")
        except Exception as e:
            print(f"🔴 Failed to generate DOCX: {e}")

        # Step 4: Generate PPTX from template
        pptx_name = f"Assessment_Summary_{session_id}.pptx"
        pptx_path = os.path.join(session_folder, pptx_name)
        try:
            prs = Presentation("templates/IT_Infrastructure_Assessment_Executive_Summary.pptx")
            prs.slides[0].shapes.title.text = "Infrastructure Assessment Summary"
            prs.slides[0].placeholders[1].text = f"Session ID: {session_id}"
            prs.save(pptx_path)
            print(f"✅ Created PPTX: {pptx_path}")
        except Exception as e:
            print(f"🔴 Failed to generate PPTX: {e}")

        # Step 5: Notify via webhook
        try:
            send_result(
                webhook,
                session_id,
                "it_assessment",
                "complete",
                "",
                docx_name,
                f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{docx_name}",
                pptx_name,
                f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{pptx_name}"
            )
            print("📤 Results posted to webhook")
        except Exception as e:
            print(f"🔴 Webhook POST failed: {e}")

    except Exception as e:
        print(f"💥 Fatal error in assessment: {e}")

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
