from docx import Document
from docx.shared import Inches
import os

def generate_docx_report(hw_charts, sw_charts, session_id):
    try:
        document = Document()
        document.add_heading('IT Infrastructure Current Status Report', 0)

        document.add_heading('Session ID', level=1)
        document.add_paragraph(session_id)

        document.add_heading('Hardware Infrastructure GAP Summary', level=1)
        if hw_charts:
            for chart in hw_charts:
                if os.path.exists(chart):
                    document.add_picture(chart, width=Inches(5.5))
                else:
                    document.add_paragraph(f"⚠️ Missing chart file: {chart}")
        else:
            document.add_paragraph("No hardware charts available.")

        document.add_heading('Software Infrastructure GAP Summary', level=1)
        if sw_charts:
            for chart in sw_charts:
                if os.path.exists(chart):
                    document.add_picture(chart, width=Inches(5.5))
                else:
                    document.add_paragraph(f"⚠️ Missing chart file: {chart}")
        else:
            document.add_paragraph("No software charts available.")

        output_path = f"temp_sessions/{session_id}/IT_Infrastructure_Current_Status_Report_{session_id}.docx"
        document.save(output_path)
        print(f"✅ DOCX report generated: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error generating DOCX report: {e}")
        return None
