
import os
from pptx import Presentation
from pptx.util import Inches
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor

def generate_pptx_report(hw_path, sw_path, hw_charts, sw_charts, session_id):
    # Load the PPTX template
    template_path = os.path.join("templates", "IT_Current_Status_Executive_Report_Template.pptx")
    prs = Presentation(template_path)

    # Define output path
    output_dir = os.path.join("temp_sessions", session_id)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"IT_Infrastructure_Executive_Report_{session_id}.pptx")

    # Add Hardware GAP Charts
    for chart_path in hw_charts:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        title = slide.shapes.title
        title.text = "Hardware GAP Analysis Chart"
        left = Inches(1)
        top = Inches(1.5)
        height = Inches(4.5)
        slide.shapes.add_picture(chart_path, left, top, height=height)

    # Add Software GAP Charts
    for chart_path in sw_charts:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        title = slide.shapes.title
        title.text = "Software GAP Analysis Chart"
        left = Inches(1)
        top = Inches(1.5)
        height = Inches(4.5)
        slide.shapes.add_picture(chart_path, left, top, height=height)

    # Save PPTX
    prs.save(output_path)
    return output_path
