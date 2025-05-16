import os
import shutil
import requests
import logging
from pptx import Presentation

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def download_file(url, dest_path):
    try:
        logging.info(f"⬇️ Downloading: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"✅ Downloaded: {dest_path}")
    except Exception as e:
        logging.error(f"🔴 Failed to download {url}: {e}")

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        logging.info(f"🔧 Thread started for session: {session_id}")
        logging.info(f"🔍 Files received: {[f['file_name'] for f in files]}")

        if not os.path.exists(session_folder):
            os.makedirs(session_folder)
            logging.info(f"📁 Created session folder: {session_folder}")
        else:
            logging.info(f"📁 Session folder already exists: {session_folder}")

        # Step 1: Download all files
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        # Step 2: Identify input inventory file
        inventory_file = next((f for f in files if f['type'] in ['asset_inventory', 'gap_working']), None)
        if not inventory_file:
            logging.error("❌ No inventory file found")
            send_result(webhook, session_id, "it_assessment", "error", "Missing asset inventory file")
            return

        # Step 3: Create updated Excel file
        updated_xlsx = f"Assessment_GAP_Working_{session_id}.xlsx"
        updated_path = os.path.join(session_folder, updated_xlsx)

        template_xlsx = "templates/assessment_template.xlsx"
        if os.path.exists(template_xlsx):
            shutil.copy(template_xlsx, updated_path)
            logging.info(f"✅ Created Excel file: {updated_path}")
        else:
            logging.error(f"🔴 Excel template not found: {template_xlsx}")
            send_result(webhook, session_id, "it_assessment", "error", "Missing Excel template")
            return

        # Step 4: Create PowerPoint summary
        pptx_name = f"Assessment_Summary_Deck_{session_id}.pptx"
        pptx_path = os.path.join(session_folder, pptx_name)

        template_pptx = "templates/summary_deck_template.pptx"
        if os.path.exists(template_pptx):
            prs = Presentation(template_pptx)
            slide = prs.slides[0]
            slide.shapes.title.text = "Assessment Summary"
            if slide.placeholders:
                slide.placeholders[1].text = f"Session: {session_id}"
            prs.save(pptx_path)
            logging.info(f"📊 Created PowerPoint file: {pptx_path}")
        else:
            logging.error(f"🔴 PPTX template not found: {template_pptx}")
            send_result(webhook, session_id, "it_assessment", "error", "Missing PowerPoint template")
            return

        # Step 5: POST results to webhook
        send_result(
            webhook,
            session_id,
            "it_assessment",
            "complete",
            "Assessment files generated successfully.",
            updated_xlsx,
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{updated_xlsx}",
            pptx_name,
            f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{pptx_name}"
        )
        logging.info("📤 Sent results to webhook successfully")

    except Exception as e:
        logging.exception("💥 Unhandled exception in assessment process")

def send_result(webhook, session_id, module, status, message, file1=None, url1=None, file2=None, url2=None):
    payload = {
        "session_id": session_id,
        "gpt_module": module,
        "status": status,
        "message": message
    }
    if file1 and url1:
        payload["file_name"] = file1
        payload["file_url"] = url1
    if file2 and url2:
        payload["file_2_name"] = file2
        payload["file_2_url"] = url2

    logging.info(f"📤 Posting result to webhook: {webhook}")
    try:
        response = requests.post(webhook, json=payload)
        logging.info(f"✅ Webhook response: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"🔴 Error posting to webhook: {e}")
