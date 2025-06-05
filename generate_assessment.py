import os
import json
import time
import traceback
import pandas as pd
import requests
from openpyxl import load_workbook
from visualization import generate_hw_charts, generate_sw_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def process_assessment(session_id, email, files, next_action_webhook):
    try:
        session_path = os.path.join(BASE_DIR, "temp_sessions", session_id)
        os.makedirs(session_path, exist_ok=True)

        print(f"\n🚀 Processing assessment for session: {session_id}")

        # Save incoming files
        asset_files = []
        for f in files:
            response = requests.get(f['file_url'])
            if response.status_code == 200:
                file_path = os.path.join(session_path, f['file_name'])
                with open(file_path, 'wb') as local_file:
                    local_file.write(response.content)
                print(f"✅ Downloaded: {f['file_name']}")
                if f['type'] == 'asset_inventory':
                    asset_files.append(file_path)
            else:
                print(f"❌ Failed to download: {f['file_name']}")

        # Load required templates
        hw_gap_path = os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx")
        sw_gap_path = os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx")

        # Generate charts
        try:
            hw_charts = generate_hw_charts(hw_gap_path, session_id)
        except Exception as e:
            print(f"❌ Failed to read HW file: {e}")
            hw_charts = []

        try:
            sw_charts = generate_sw_charts(sw_gap_path, session_id)
        except Exception as e:
            print(f"❌ Failed to read SW file: {e}")
            sw_charts = []

        # Generate reports
        docx_report = generate_docx_report(session_id)
        pptx_report = generate_pptx_report(session_id)

        print(f"📄 Generated reports: {docx_report}, {pptx_report}")

        # Send result to next GPT module
        payload = {
            "session_id": session_id,
            "email": email,
            "docx_file": docx_report,
            "pptx_file": pptx_report
        }

        r = requests.post(next_action_webhook, json=payload)
        r.raise_for_status()
        print("📤 Sent results to next module")

    except Exception as e:
        print(f"🔥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
