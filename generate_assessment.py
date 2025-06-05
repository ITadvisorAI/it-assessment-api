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
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

def process_assessment(session_id, email, files, next_action_webhook):
    try:
        session_path = os.path.join(BASE_DIR, "temp_sessions", session_id)
        os.makedirs(session_path, exist_ok=True)

        print(f"🚀 Processing assessment for session: {session_id}")

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

        # Load templates
        hw_gap_path = os.path.join(TEMPLATE_DIR, "HWGapAnalysis.xlsx")
        sw_gap_path = os.path.join(TEMPLATE_DIR, "SWGapAnalysis.xlsx")

        if not os.path.exists(hw_gap_path):
            print(f"❌ HW template missing: {hw_gap_path}")
        if not os.path.exists(sw_gap_path):
            print(f"❌ SW template missing: {sw_gap_path}")

        # Generate charts
        hw_charts = generate_hw_charts(hw_gap_path, session_id)
        sw_charts = generate_sw_charts(sw_gap_path, session_id)

        # Generate DOCX and PPTX reports
        docx_report = generate_docx_report(
            hw_gap_path, sw_gap_path, hw_charts, sw_charts, session_id
        )
        pptx_report = generate_pptx_report(
            hw_gap_path, sw_gap_path, hw_charts, sw_charts, session_id
        )

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
