import requests, os, shutil
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

        # Step 1: Download all files
        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            print(f"📝 Downloading: {f['file_name']} from {f['file_url']}")
            download_file(f['file_url'], file_path)

        # Step 2: Identify input inventory file
        inventory_file = next((f for f in files if f['type'] in ['asset_inventory', 'gap_working']), None)
        if not inventory_file:
            print("❌ No inventory file found")
            send_result(webhook, session_id, "it_assessment", "error", "Missing asset inventory file")
            return

        # Step 3: Create updated Excel file
        updated_xlsx = f"Assessment_GAP_Working_{session_id}.xlsx"
        updated_path = os.path.join(session_folder, updated_xlsx)
        try:
            shutil.copy("templates/assessment_template.xlsx", updated_path)
            print(f"✅ Created Excel file: {updated_path}")
        except Exception as e:
            print(f"🔴 Failed to create XLSX: {e}")

        # Step 4: Create PowerPoint summary
        pptx_name = f"Assessment_Summary_Deck_{session_id}.pptx"
        pptx_path = os.path.join(session_folder, pptx_name)
        try:
            prs = Presentation("templates/summary_deck_template.pptx")
            prs.slides[0].shapes.title.text = "Assessment Summary"
            prs.slides[0].placeholders[1].text = f"Session: {session_id}"
            prs.save(pptx_path)
            print(f"✅ Created PowerPoint file: {pptx_path}")
        except Exception as e:
            print(f"🔴 Failed to create PPTX: {e}")

        # Step 5: POST results to webhook
        try:
            send_result(
                webhook,
                session_id,
                "it_assessment",
                "complete",
                "",
                updated_xlsx,
                f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{updated_xlsx}",
                pptx_name,
                f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{pptx_name}"
            )
            print("📤 Sent results to webhook successfully")
        except Exception as e:
            print(f"🔴 Failed to post to webhook: {e}")

    except Exception as e:
        print(f"💥 Unhandled exception in assessment process: {e}")

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

    print(f"📤 Posting result to webhook: {webhook}")
    try:
        response = requests.post(webhook, json=payload)
        print(f"🔁 Webhook response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"🔴 Error posting to webhook: {e}")
