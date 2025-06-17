import os
import re
import json
import pandas as pd
import requests
import openai
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

from docx import Document
from pptx import Presentation
from pptx.util import Inches

# Configuration
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR = "temp_sessions"
DOCX_SERVICE_URL = os.getenv("DOCX_SERVICE_URL", "https://docx-generator-api.onrender.com")
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis.onrender.com/start_market_gap")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Cache templates
print("[DEBUG] Loading templates...", flush=True)
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates loaded", flush=True)


def download_spreadsheet(file_meta, dest_dir):
    url = file_meta['file_url']
    local_path = os.path.join(dest_dir, file_meta['file_name'])
    r = requests.get(url)
    r.raise_for_status()
    with open(local_path, 'wb') as f:
        f.write(r.content)
    return local_path


def call_gpt_for_section(prompt):
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an IT Transformation Advisor that writes clear, concise technical report sections."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()


def generate_assessment(session_id, email, goal, files, next_action_webhook="", folder_id=None):
    print(f"[DEBUG] Starting assessment for session {session_id}", flush=True)
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    # Load data
    hw_df = sw_df = pd.DataFrame()
    for f_meta in files:
        if f_meta['type'] == 'hardware_gap_excel':
            hw_path = download_spreadsheet(f_meta, session_path)
            hw_df = pd.read_excel(hw_path)
        elif f_meta['type'] == 'software_gap_excel':
            sw_path = download_spreadsheet(f_meta, session_path)
            sw_df = pd.read_excel(sw_path)

    # Perform analysis suggestions
    hw_suggestions = suggest_hw_replacements(hw_df)
    sw_suggestions = suggest_sw_replacements(sw_df)

    # Generate charts and upload
    chart_paths = generate_visual_charts(hw_df, sw_df, output_dir=session_path)
    chart_urls = []
    for path in chart_paths:
        url = upload_to_drive(path, folder_id)
        chart_urls.append(url)

    # Define dynamic sections and prompts
    section_prompts = {
        "introduction": f"Write an executive summary introduction for IT Infrastructure assessment with goal: {goal}.",
        "hardware_analysis": f"Analyze the hardware gap data and suggest replacements: {hw_suggestions}.",
        "software_analysis": f"Analyze the software gap data and suggest replacements: {sw_suggestions}.",
        "key_findings": "Identify key findings based on the data frames provided for hardware and software.",
        "recommendations": "Provide high-level recommendations for IT modernization based on the analyses.",
        "next_steps": "Outline the next steps and roadmap for implementing these recommendations."
    }

    # Generate content sections via GPT
    narratives = {}
    for section, prompt in section_prompts.items():
        narratives[section] = call_gpt_for_section(prompt)

    # Build payload
    payload = {
        "session_id": session_id,
        "email": email,
        "goal": goal,
        "folder_id": folder_id,
        "files": files,
        "charts": chart_urls,
        "narratives": narratives
    }

    # Trigger Market Gap Analysis
    print(f"[DEBUG] Posting payload to {MARKET_GAP_WEBHOOK}", flush=True)
    resp = requests.post(MARKET_GAP_WEBHOOK, json=payload)
    resp.raise_for_status()
    print(f"[DEBUG] Received {resp.status_code}", flush=True)
    return resp.json()


def main():
    import sys
    data = json.load(sys.stdin)
    result = generate_assessment(
        session_id=data.get('session_id'),
        email=data.get('email'),
        goal=data.get('goal'),
        files=data.get('files', []),
        next_action_webhook=data.get('next_action_webhook', ''),
        folder_id=data.get('folder_id')
    )
    print(json.dumps(result))


if __name__ == '__main__':
    main()
