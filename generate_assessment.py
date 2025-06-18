import os
import json
import pandas as pd
import requests
import openai
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive
from report_helpers import (
    build_score_summary,
    build_recommendations,
    build_key_findings,
    build_section_2_overview,
    build_section_3_hardware_breakdown,
    build_section_4_software_breakdown,
    build_section_5_tier_distribution,
    build_section_6_hardware_lifecycle,
    build_section_7_software_licensing,
    build_section_8_security_posture,
    build_section_9_performance_metrics,
    build_section_10_reliability,
    build_section_11_scalability,
    build_section_12_legacy_debt,
    build_section_13_obsolete_platforms,
    build_section_14_cloud_migration,
    build_section_15_strategic_alignment,
    build_section_17_financial_implications,
    build_section_18_sustainability,
    build_section_20_next_steps
)
from docx import Document
from pptx import Presentation
from pptx.util import Inches

# Initialize OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Directories
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR = "temp_sessions"

# Cache templates once
print("[DEBUG] Loading templates...", flush=True)
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates loaded", flush=True)

# External services
DOCX_SERVICE_URL = os.getenv(
    "DOCX_SERVICE_URL",
    "https://docx-generator-api.onrender.com"
)
MARKET_GAP_WEBHOOK = "https://market-gap-analysis.onrender.com/start_market_gap"


def ai_narrative(section_name: str, summary: dict) -> str:
    """
    Turn a summary dict into a narrative using OpenAI.
    """
    messages = [
        {"role": "system", "content": (
            "You are a senior IT transformation advisor. "
            "Given the data summary, write a concise, professional narrative for the report section."
        )},
        {"role": "user", "content": (
            f"Section: {section_name}\n"
            f"Data: {json.dumps(summary)}"
        )}
    ]
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()


def generate_assessment(
    session_id: str,
    email: str,
    goal: str,
    files: list,
    next_action_webhook: str = "",
    folder_id: str = None
) -> dict:
    """
    Process asset inventory files, generate narratives, charts, and send payload to DOCX service.
    """
    print(f"[DEBUG] Start assessment for {session_id}", flush=True)
    upload_folder = folder_id or session_id
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    # Download files
    hw_df = sw_df = pd.DataFrame()
    hw_file_path = sw_file_path = None
    for f in files:
        url, name = f['file_url'], f['file_name']
        local = os.path.join(session_path, name)
        print(f"[DEBUG] Download {name}", flush=True)
        r = requests.get(url) if url.startswith("http") else open(url, 'rb')
        content = r.content if hasattr(r, 'content') else r.read()
        with open(local, 'wb') as fh:
            fh.write(content)
        if f.get('type') == 'asset_inventory':
            if hw_file_path is None:
                hw_file_path = local
            else:
                sw_file_path = local
        elif f.get('type') == 'gap_working' and sw_file_path is None:
            sw_file_path = local

    # Merge, classify
    def merge(df_base, path):
        df_inv = pd.read_excel(path)
        for c in df_inv.columns:
            if c not in df_base.columns:
                df_base[c] = None
        return pd.concat([df_base, df_inv.reindex(columns=df_base.columns)], ignore_index=True)

    if hw_file_path:
        hw_df = merge(HW_BASE_DF.copy(), hw_file_path)
        hw_df = suggest_hw_replacements(hw_df)
        hw_df = hw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')
    if sw_file_path:
        sw_df = merge(SW_BASE_DF.copy(), sw_file_path)
        sw_df = suggest_sw_replacements(sw_df)
        sw_df = sw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Charts
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    for k, p in chart_paths.items():
        chart_paths[k] = upload_to_drive(p, os.path.basename(p), upload_folder)

    # GAP sheets
    links = {}
    for idx, df in enumerate((hw_df, sw_df), start=1):
        if not df.empty:
            label = ['HW', 'SW'][idx-1]
            path = os.path.join(session_path, f"{label}GapAnalysis_{session_id}.xlsx")
            df.to_excel(path, index=False)
            links[f"file_{idx}_drive_url"] = upload_to_drive(path, os.path.basename(path), upload_folder)

    # Core metrics
    score_summary   = build_score_summary(hw_df, sw_df)
    recommendations = build_recommendations(hw_df, sw_df)
    key_findings    = build_key_findings(hw_df, sw_df)

    # AI narratives
    payload_content = {
        'content_1': score_summary,
        'content_2': ai_narrative('IT Landscape Overview', build_section_2_overview(hw_df, sw_df)),
        'content_3': ai_narrative('Hardware Breakdown', build_section_3_hardware_breakdown(hw_df, sw_df)),
        'content_4': ai_narrative('Software Breakdown', build_section_4_software_breakdown(hw_df, sw_df)),
        # ... include additional sections as needed ...
        'content_20': ai_narrative('Next Steps & Roadmap', build_section_20_next_steps(hw_df, sw_df))
    }

    # Appendices
    try:
        appendix_matrix = CLASSIFICATION_DF.to_markdown(index=False)
    except:
        appendix_matrix = CLASSIFICATION_DF.to_csv(index=False)
    appendices = {
        'appendix_classification_matrix': appendix_matrix,
        'appendix_data_sources': 'Data sources: inventory files, GAP templates, classification tiers.'
    }

    # Build payload
    payload = {
        'session_id': session_id,
        'email': email,
        'goal': goal,
        'hw_gap_url': links.get('file_1_drive_url'),
        'sw_gap_url': links.get('file_2_drive_url'),
        'chart_paths': chart_paths,
        **payload_content,
        **appendices
    }

    # Send to DOCX service
    print(f"[DEBUG] POST to DOCX_SERVICE: {DOCX_SERVICE_URL}", flush=True)
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    result_json = resp.json()

    # Download & re-upload
    for key in ['docx_url', 'pptx_url']:
        url = result_json.get(key)
        if url:
            name = os.path.basename(url)
            local = os.path.join(session_path, name)
            r = requests.get(url)
            with open(local, 'wb') as f:
                f.write(r.content)
            links[f"file_{3 if key=='docx_url' else 4}_drive_url"] = upload_to_drive(local, name, upload_folder)

    # Notify next module
    final = {
        'session_id': session_id,
        'gpt_module': 'it_assessment',
        'status': 'complete',
        **links
    }
    try:
        requests.post(MARKET_GAP_WEBHOOK, json=final)
    except Exception as e:
        print(f"❌ Market-GAP notify failed: {e}", flush=True)

    return final


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        data.get('session_id'),
        data.get('email'),
        data.get('goal', 'project plan'),
        data.get('files', []),
        data.get('next_action_webhook', ''),
        data.get('folder_id')
    )
