import os
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def generate_docx_report(hw_path, sw_path, hw_charts, sw_charts, session_id):
    # Load the template
    template_path = os.path.join("templates", "IT_Current_Status_Assessment_Report_Template.docx")
    document = Document(template_path)

    # Add session heading
    document.add_heading(f"Assessment Report – Session ID: {session_id}", level=1)

    # Add Hardware GAP Analysis section
    document.add_heading("Hardware GAP Analysis", level=2)
    document.add_paragraph("This section includes the results of the hardware gap analysis...")

    for chart in hw_charts:
        document.add_picture(chart, width=Inches(5.5))
        last_paragraph = document.paragraphs[-1]
        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Add Software GAP Analysis section
    document.add_heading("Software GAP Analysis", level=2)
    document.add_paragraph("This section includes the results of the software gap analysis...")

    for chart in sw_charts:
        document.add_picture(chart, width=Inches(5.5))
        last_paragraph = document.paragraphs[-1]
        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Save the final document
    output_dir = os.path.join("temp_sessions", session_id)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"IT_Infrastructure_Current_Status_Report_{session_id}.docx")
    document.save(output_path)

    return output_path
