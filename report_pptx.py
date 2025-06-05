from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
import os

def generate_pptx_report(session_id):
    prs = Presentation()
    chart_dir = os.path.join("temp_sessions", session_id, "charts")

    # Title slide
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "IT Infrastructure Executive Summary"
    slide.placeholders[1].text = f"Session ID: {session_id}"

    chart_titles = {
        "hw_tier_distribution.png": "Hardware Tier Distribution",
        "hw_environment_distribution.png": "Hardware Environment Distribution",
        "hw_device_type_vs_tier.png": "Device Type vs Tier Level",
        "sw_tier_distribution.png": "Software Tier Distribution",
        "sw_environment_distribution.png": "Software Environment Distribution"
    }

    for chart_file, title in chart_titles.items():
        slide = prs.slides.add_slide(prs.slide_layouts[5])  # Blank slide
        shapes = slide.shapes

        # Always show title
        left, top, width, height = Inches(1), Inches(0.3), Inches(8), Inches(0.5)
        title_shape = shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, left, top, width, height)
        title_shape.text = title

        # Try to insert chart or fallback message
        chart_path = os.path.join(chart_dir, chart_file)
        if os.path.exists(chart_path):
            shapes.add_picture(chart_path, Inches(1), Inches(1.2), width=Inches(7.5))
        else:
            textbox = shapes.add_textbox(Inches(1), Inches(1.5), Inches(7), Inches(1))
            textbox.text_frame.text = f"⚠️ Chart not found: {chart_file}"

    output_path = os.path.join("temp_sessions", session_id, f"IT_Infrastructure_Executive_Report_{session_id}.pptx")
    prs.save(output_path)
    return output_path
