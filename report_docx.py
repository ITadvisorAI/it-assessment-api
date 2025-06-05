from docx import Document
from docx.shared import Inches
import os

def generate_docx_report(session_id):
    doc = Document()

    chart_dir = os.path.join("temp_sessions", session_id, "charts")
    doc.add_heading("IT Infrastructure Current Status Report", 0)
    doc.add_paragraph(f"Session ID: {session_id}")
    doc.add_paragraph("This report contains hardware and software gap analysis along with visual insights.")

    # Hardware Section
    doc.add_heading("Hardware Analysis", level=1)
    hw_charts = [
        "hw_tier_distribution.png",
        "hw_environment_distribution.png",
        "hw_device_type_vs_tier.png"
    ]
    for chart in hw_charts:
        path = os.path.join(chart_dir, chart)
        title = chart.replace("_", " ").replace(".png", "").title()
        if os.path.exists(path):
            doc.add_heading(title, level=2)
            doc.add_picture(path, width=Inches(5.5))
        else:
            doc.add_paragraph(f"⚠️ Missing chart: {chart}")

    # Software Section
    doc.add_heading("Software Analysis", level=1)
    sw_charts = [
        "sw_tier_distribution.png",
        "sw_environment_distribution.png"
    ]
    for chart in sw_charts:
        path = os.path.join(chart_dir, chart)
        title = chart.replace("_", " ").replace(".png", "").title()
        if os.path.exists(path):
            doc.add_heading(title, level=2)
            doc.add_picture(path, width=Inches(5.5))
        else:
            doc.add_paragraph(f"⚠️ Missing chart: {chart}")

    output_path = os.path.join("temp_sessions", session_id, f"IT_Infrastructure_Current_Status_Report_{session_id}.docx")
    doc.save(output_path)
    return output_path
