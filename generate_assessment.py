import os
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

# Base dataframes for merging inventory data
HW_BASE_DF = pd.DataFrame(columns=["Device ID", "Device Name", "Current Model", "Tier Total Score"])
SW_BASE_DF = pd.DataFrame(columns=["App ID", "App Name", "License Status", "Tier Total Score"])
CLASSIFICATION_DF = pd.DataFrame([
    {"Score": 0, "Category": "Critical"},
    {"Score": 50, "Category": "High"},
    {"Score": 75, "Category": "Medium"},
    {"Score": 90, "Category": "Low"}
])

# Service endpoints (env var overrides available)
DOCX_SERVICE_URL = os.getenv("DOCX_SERVICE_URL", "https://docx-generator-api.onrender.com")
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis-api.onrender.com/start_gap_analysis")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp")

# Initialize OpenAI client
client = openai.OpenAI()

# ─── Inline helper functions ─────────────────────────────────────────────────

def build_score_summary(hw_df, sw_df):
    total_hw = len(hw_df)
    total_sw = len(sw_df)
    return f"Analyzed {total_hw} hardware items and {total_sw} software items."

def build_recommendations(hw_df, sw_df):
    hw_recs = suggest_hw_replacements(hw_df).head(3).to_dict(orient="records") if not hw_df.empty else []
    sw_recs = suggest_sw_replacements(sw_df).head(3).to_dict(orient="records") if not sw_df.empty else []
    return {"hardware_replacements": hw_recs, "software_replacements": sw_recs}

def build_key_findings(hw_df, sw_df):
    findings = []
    if "Tier Total Score" in hw_df.columns:
        low = hw_df[hw_df["Tier Total Score"] < 50]
        findings.append({"text": f"{len(low)} hardware items scored below 50", "severity": "High"})
    if "License Status" in sw_df.columns:
        expired = sw_df[sw_df["License Status"] == "Expired"]
        findings.append({"text": f"{len(expired)} expired software licenses", "severity": "Critical"})
    return {"findings": findings}

def build_section_1_summary(hw_df, sw_df):
    """Build a detailed summary for section 1"""
    return {
        "devices_analyzed": len(hw_df),
        "applications_analyzed": len(sw_df),
        "timestamp": pd.Timestamp.now().isoformat()
    }

def build_section_2_overview(hw_df, sw_df):
    """Build IT landscape overview for section 2"""
    total_devices = len(hw_df)
    total_apps = len(sw_df)
    infra_health = hw_df[hw_df["Tier Total Score"] >= 75].shape[0]
    license_compliance = sw_df[sw_df["License Status"] != "Expired"].shape[0]
    return {
        "total_devices": total_devices,
        "total_applications": total_apps,
        "healthy_devices": infra_health,
        "compliant_licenses": license_compliance
    }

def build_section_3_risk(hw_df, sw_df):
    """Identify high-risk items for section 3"""
    risks = []
    if not hw_df.empty:
        high_risk_hw = hw_df[hw_df["Tier Total Score"] < 30]
        risks.append({"hardware": high_risk_hw.to_dict(orient="records")})
    if not sw_df.empty:
        high_risk_sw = sw_df[sw_df["Tier Total Score"] < 30]
        risks.append({"software": high_risk_sw.to_dict(orient="records")})
    return {"risks": risks}

# ... (additional section builders here up to section 8) ...

def ai_narrative(section_name: str, summary: dict) -> str:
    """
    Turn a summary dict into a narrative using the new OpenAI client interface.
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
    resp = client.chat.completions.create(
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
    print(f"[DEBUG] Start assessment for {session_id}", flush=True)
    upload_folder = folder_id or session_id
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    # Download and classify files
    hw_df = pd.DataFrame()
    sw_df = pd.DataFrame()
    hw_file_path = None
    sw_file_path = None
    for f in files:
        url = f.get('file_url')
        name = f.get('file_name')
        local_path = os.path.join(session_path, name)
        print(f"[DEBUG] Downloading {name} from {url}", flush=True)
        if url and url.startswith("http"):
            r = requests.get(url)
            r.raise_for_status()
            content = r.content
        else:
            with open(url, 'rb') as src:
                content = src.read()
        with open(local_path, 'wb') as fh:
            fh.write(content)
        f_type = f.get('type')
        if f_type == 'asset_inventory':
            hw_file_path = hw_file_path or local_path
        elif f_type == 'gap_working':
            sw_file_path = sw_file_path or local_path

    def merge_df(base_df, path):
        df_new = pd.read_excel(path)
        return pd.concat([base_df, df_new.reindex(columns=base_df.columns)], ignore_index=True)

    # Process hardware
    if hw_file_path:
        hw_df = merge_df(HW_BASE_DF.copy(), hw_file_path)
        hw_df = suggest_hw_replacements(hw_df)
        hw_df = hw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Process software
    if sw_file_path:
        sw_df = merge_df(SW_BASE_DF.copy(), sw_file_path)
        sw_df = suggest_sw_replacements(sw_df)
        sw_df = sw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Charts
    chart_map = generate_visual_charts(hw_df, sw_df, session_id)
    uploaded_chart_urls = {k: upload_to_drive(p, os.path.basename(p), upload_folder) for k, p in chart_map.items()}

    # Save and upload GAP sheets
    file_links = {}
    for idx, df in enumerate([hw_df, sw_df], start=1):
        if not df.empty:
            label = 'HW' if idx == 1 else 'SW'
            fname = f"{label}GapAnalysis_{session_id}.xlsx"
            path = os.path.join(session_path, fname)
            df.to_excel(path, index=False)
            file_links[f"file_{idx}_drive_url"] = upload_to_drive(path, fname, upload_folder)

    # Build narratives
    sections = {
        'Section1_Summary': build_section_1_summary(hw_df, sw_df),
        'Section2_Overview': build_section_2_overview(hw_df, sw_df),
        'Section3_Risk': build_section_3_risk(hw_df, sw_df),
        # ... include builders up to section 8
    }
    content_narratives = {}
    for i, (sec, summary) in enumerate(sections.items(), start=1):
        content_narratives[f"content_{i}"] = ai_narrative(sec.replace('_', ' '), summary)

    # Payload to document service
    payload = {
        **uploaded_chart_urls,
        **file_links,
        **content_narratives,
        'session_id': session_id,
        'email': email,
        'goal': goal
    }
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    result = resp.json()

    # Download and upload generated docs
    for key, link_key in [('docx_url', 'file_9_drive_url'), ('pptx_url', 'file_10_drive_url')]:
        url = result.get(key)
        if url:
            fname = os.path.basename(url)
            local_file = os.path.join(session_path, fname)
            r = requests.get(url)
            r.raise_for_status()
            with open(local_file, 'wb') as fl:
                fl.write(r.content)
            file_links[link_key] = upload_to_drive(local_file, fname, upload_folder)

    # Final notification
    final_payload = {
        'session_id': session_id,
        'gpt_module': 'it_assessment',
        'status': 'complete',
        **file_links
    }
    try:
        requests.post(MARKET_GAP_WEBHOOK, json=final_payload)
    except Exception as e:
        print(f"Error notifying market gap gateway: {e}", flush=True)

    return final_payload


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        data.get('session_id'),
        data.get('email'),
        data.get('goal', 'project plan'),
        data.get('files', []),
        data.get('next_action_webhook', ''),
        data.get('folder_id')
    )
