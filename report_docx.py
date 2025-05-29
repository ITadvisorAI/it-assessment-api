from docx import Document
from docx.shared import Inches
import os

def generate_docx_report(session_id):
    doc = Document()
    chart_dir = os.path.join("temp_sessions", session_id, "charts")

    doc.add_heading("IT Infrastructure Current Status Report", 0)
    doc.add_paragraph(f"Session ID: {session_id}")
    doc.add_paragraph("This report contains hardware and software gap analysis along with visual insights.")

    doc.add_heading("Hardware Analysis", level=1)
    for chart in [
        "hw_tier_distribution.png",
        "hw_environment_distribution.png",
        "hw_device_type_vs_tier.png"
    ]:
        path = os.path.join(chart_dir, chart)
        if os.path.exists(path):
            doc.add_heading(chart.replace("_", " ").replace(".png", "").title(), level=2)
            doc.add_picture(path, width=Inches(5.5))
        else:
            doc.add_paragraph(f"⚠️ Missing chart: {chart}")

    doc.add_heading("Software Analysis", level=1)
    for chart in [
        "sw_tier_distribution.png",
        "sw_environment_distribution.png"
    ]:
        path = os.path.join(chart_dir, chart)
        if os.path.exists(path):
            doc.add_heading(chart.replace("_", " ").replace(".png", "").title(), level=2)
            doc.add_picture(path, width=Inches(5.5))
        else:
            doc.add_paragraph(f"⚠️ Missing chart: {chart}")

    output_path = os.path.join("temp_sessions", session_id, f"IT_Infrastructure_Current_Status_Report_{session_id}.docx")
    doc.save(output_path)
    return output_path
