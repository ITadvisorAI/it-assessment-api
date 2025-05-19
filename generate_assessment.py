import requests, os
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches
from pptx import Presentation
from pptx.util import Inches
from openpyxl import load_workbook
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

def process_assessment(session_id, email, files, webhook, session_folder):
    try:
        print(f"🔧 Starting assessment for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        for f in files:
            file_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], file_path)

        # Excel template generation
        hw_template = "templates/HWGapAnalysis.xlsx"
        sw_template = "templates/SWGapAnalysis.xlsx"
        hw_output = f"HWGapAnalysis_{session_id}.xlsx"
        sw_output = f"SWGapAnalysis_{session_id}.xlsx"
        hw_output_path = os.path.join(session_folder, hw_output)
        sw_output_path = os.path.join(session_folder, sw_output)

        docx_template = "templates/IT_Current_Status_Assesment_Template.docx"
        docx_output = os.path.join(session_folder, f"IT_Current_Status_Assessment_Report.docx")
        pptx_template = "templates/IT_Infrastructure_Assessment_Report.pptx"
        pptx_output = os.path.join(session_folder, f"IT_Current_Status_Executive_Report.pptx")
        chart_path = os.path.join(session_folder, "tier_distribution.png")

        try:
            wb = load_workbook(hw_template)
            ws = wb["GAP_Working"] if "GAP_Working" in wb.sheetnames else wb.active
            generate_tier_chart(ws, chart_path)
            wb.save(hw_output_path)
            print(f"✅ HW GAP file: {hw_output_path}")
        except Exception as e:
            print(f"🔴 HW GAP failed: {e}")

        try:
            wb = load_workbook(sw_template)
            wb.save(sw_output_path)
            print(f"✅ SW GAP file: {sw_output_path}")
        except Exception as e:
            print(f"🔴 SW GAP failed: {e}")

        try:
            doc = Document(docx_template)
            doc.paragraphs[0].text = f"Assessment Report - Session {session_id}"
            if os.path.exists(chart_path):
                doc.add_paragraph("Tier Distribution Overview:")
                doc.add_picture(chart_path, width=Inches(5.5))
            doc.save(docx_output)
            print(f"✅ DOCX generated: {docx_output}")
        except Exception as e:
            print(f"🔴 DOCX failed: {e}")

        try:
            ppt = Presentation(pptx_template)
            slide = ppt.slides[0]
            slide.shapes.title.text = "Executive Assessment Summary"
            slide.placeholders[1].text = f"Session ID: {session_id}"
            chart_slide = ppt.slides.add_slide(ppt.slide_layouts[5])
            title_shape = chart_slide.shapes.title
            if title_shape:
                title_shape.text = "Tier Distribution Chart"
            if os.path.exists(chart_path):
                chart_slide.shapes.add_picture(chart_path, Inches(1), Inches(1.5), width=Inches(7))
            ppt.save(pptx_output)
            print(f"✅ PPTX generated: {pptx_output}")
        except Exception as e:
            print(f"🔴 PPTX failed: {e}")

        # Send to webhook
        files_to_send = {
            os.path.basename(hw_output_path): f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{os.path.basename(hw_output_path)}",
            os.path.basename(sw_output_path): f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{os.path.basename(sw_output_path)}",
            os.path.basename(docx_output): f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{os.path.basename(docx_output)}",
            os.path.basename(pptx_output): f"https://it-assessment-api.onrender.com/files/Temp_{session_id}/{os.path.basename(pptx_output)}",
        }
        send_result(webhook, session_id, "it_assessment", "complete", "", files_to_send)

    except Exception as e:
        print(f"💥 Unhandled error in process_assessment: {e}")
