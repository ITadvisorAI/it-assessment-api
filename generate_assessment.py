import requests
import os
from urllib.parse import urlparse
from openpyxl import load_workbook
from pptx import Presentation
import shutil

def download_file(url, dest_path):
    response = requests.get(url)
    with open(dest_path, 'wb') as f:
        f.write(response.content)

def process_assessment(session_id, email, files, webhook, session_folder):
    # Step 1: Download all files
    for f in files:
        file_path = os.path.join(session_folder, f['file_name'])
        download_file(f['file_url'], file_path)

    # Step 2: Identify asset inventory or gap file
    excel_file = next((f for f in files if f['type'] in ['asset_inventory', 'gap_working']), None)
    if not excel_file:
        send_result(webhook, session_id, "it_assessment", "error", "Missing asset inventory file")
        return

    input_path = os.path.join(session_folder, excel_file['file_name'])

    # Step 3: Create updated Excel file
    updated_xlsx = f"Assessment_GAP_Working_{session_id}.xlsx"
    updated_path = os.path.join(session_folder, updated_xlsx)
    shutil.copy("templates/assessment_template.xlsx", updated_path)
    # TODO: open input_path → analyze + fill updated_path

    # Step 4: Create PowerPoint deck
    pptx_name = f"Assessment_Summary_Deck_{session_id}.pptx"
    pptx_path = os.path.join(session_folder, pptx_name)
    prs = Presentation("templates/summary_deck_template.pptx")
    prs.slides[0].shapes.title.text = "Assessment Summary"
    prs.slides[0].placeholders[1].text = f"Session: {session_id}"
    prs.save(pptx_path)

    # Step 5: POST results to next_action_webhook
    send_result(
        webhook,
        session_id,
        "it_assessment",
        "complete",
        "",
        updated_xlsx,
        f"https://docx-generator-api.onrender.com/files/Temp_{session_id}/{updated_xlsx}",
        pptx_name,
        f"https://docx-generator-api.onrender.com/files/Temp_{session_id}/{pptx_name}"
    )

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

    try:
        requests.post(webhook, json=payload)
    except Exception as e:
        print(f"Failed to post to webhook: {e}")
