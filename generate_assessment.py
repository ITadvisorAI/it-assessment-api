import os
import json
import pandas as pd
import requests
import openai
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

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
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis.onrender.com/start_market_gap")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp")

# Initialize OpenAI client
client = openai.OpenAI()

# ─── Section builder helper functions ───────────────────────────────────────────

def build_score_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}


def build_section_2_overview(hw_df, sw_df):
    total_devices = len(hw_df)
    total_apps = len(sw_df)
    healthy_devices = hw_df[hw_df["Tier Total Score"] >= 75].shape[0]
    compliant_licenses = sw_df[sw_df.get("License Status") != "Expired"].shape[0] if "License Status" in sw_df.columns else 0
    return {
        "total_devices": total_devices,
        "total_applications": total_apps,
        "healthy_devices": healthy_devices,
        "compliant_licenses": compliant_licenses
    }


def build_section_3_risk(hw_df, sw_df):
    risks = []
    if not hw_df.empty:
        high_risk_hw = hw_df[hw_df["Tier Total Score"] < 30]
        risks.append({"hardware": high_risk_hw.to_dict(orient="records")})
    if not sw_df.empty:
        high_risk_sw = sw_df[sw_df["Tier Total Score"] < 30]
        risks.append({"software": high_risk_sw.to_dict(orient="records")})
    return {"risks": risks}


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


def build_section_6_distribution(hw_df, sw_df):
    return {
        "hardware_distribution": hw_df["Category"].value_counts().to_dict() if "Category" in hw_df.columns else {},
        "software_distribution": sw_df["Category"].value_counts().to_dict() if "Category" in sw_df.columns else {}
    }


def build_section_7_trend_analysis(hw_df, sw_df):
    return {"trends": []}


def build_section_8_action_items(hw_df, sw_df):
    return {"action_items": []}

# ─── Narrative generation ───────────────────────────────────────────────────────

def ai_narrative(section_name: str, summary: dict) -> str:
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

# ─── Main assessment function ──────────────────────────────────────────────────

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

    # Download & infer file types
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
            r = requests.get(url); r.raise_for_status(); content = r.content
        else:
            with open(url, 'rb') as src: content = src.read()
        with open(local_path, 'wb') as fh: fh.write(content)

        try:
            df_temp = pd.read_excel(local_path)
        except Exception as e:
            print(f"⚠️ Could not read {name} as Excel: {e}", flush=True)
            continue

        cols = {c.lower() for c in df_temp.columns}
        provided = f.get('type','').lower()
        if provided in ('hardware_inventory','asset_hardware') or {'device id','device name'}.issubset(cols):
            hw_file_path = hw_file_path or local_path
            hw_df = df_temp if hw_df.empty else pd.concat([hw_df, df_temp], ignore_index=True)
        elif provided in ('software_inventory','asset_software') or {'app id','app name','license status'}.issubset(cols):
            sw_file_path = sw_file_path or local_path
            sw_df = df_temp if sw_df.empty else pd.concat([sw_df, df_temp], ignore_index=True)
        else:
            if hw_file_path is None:
                hw_file_path = local_path; hw_df = df_temp
            else:
                sw_file_path = local_path; sw_df = df_temp

    # Enrich dataframes
    if not hw_df.empty:
        merged_hw = pd.concat([HW_BASE_DF, hw_df], ignore_index=True)
        hw_df = suggest_hw_replacements(merged_hw)
        hw_df = hw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')
    if not sw_df.empty:
        merged_sw = pd.concat([SW_BASE_DF, sw_df], ignore_index=True)
        sw_df = suggest_sw_replacements(merged_sw)
        sw_df = sw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Generate & upload visual charts
    chart_map = generate_visual_charts(hw_df, sw_df, session_id)
    uploaded_charts = {k: upload_to_drive(p, os.path.basename(p), upload_folder) for k,p in chart_map.items()}

    # Save & upload GAP analysis sheets
    file_links = {}
    for idx, df in enumerate([hw_df, sw_df], start=1):
        if not df.empty:
            label = 'HW' if idx==1 else 'SW'
            fname = f"{label}GapAnalysis_{session_id}.xlsx"
            out_path = os.path.join(session_path, fname)
            df.to_excel(out_path, index=False)
            file_links[f"file_{idx}_drive_url"] = upload_to_drive(out_path, fname, upload_folder)

    # Build section summaries and narratives
    sections = {
        'Section1_Summary': build_score_summary(hw_df, sw_df),
        'Section2_Overview': build_section_2_overview(hw_df, sw_df),
        'Section3_Risk': build_section_3_risk(hw_df, sw_df),
        'Section4_Recommendations': build_recommendations(hw_df, sw_df),
        'Section5_Key Findings': build_key_findings(hw_df, sw_df),
        'Section6_Distribution': build_section_6_distribution(hw_df, sw_df),
        'Section7_Trends': build_section_7_trend_analysis(hw_df, sw_df),
        'Section8_Actions': build_section_8_action_items(hw_df, sw_df)
    }
    narratives = {f"content_{i}": ai_narrative(sec.replace('_',' '), summary)
                  for i,(sec,summary) in enumerate(sections.items(), start=1)}

    # Construct full payload
    payload = {
        'session_id': session_id,
        'email': email,
        'goal': goal,
        **uploaded_charts,
        **file_links,
        **narratives
    }

    # Send to report generator API
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    result = resp.json()

    # Download & re-upload generated docs
    for key, link_key in [('docx_url','file_9_drive_url'),('pptx_url','file_10_drive_url')]:
        url = result.get(key)
        if url:
            fname = os.path.basename(url)
            local_doc = os.path.join(session_path, fname)
            r = requests.get(url); r.raise_for_status()
            with open(local_doc, 'wb') as fl: fl.write(r.content)
            file_links[link_key] = upload_to_drive(local_doc, fname, upload_folder)

    # Notify next module
    final_payload = { 'session_id': session_id, 'gpt_module': 'it_assessment', 'status': 'complete', **file_links }
    webhook = next_action_webhook or MARKET_GAP_WEBHOOK
    try:
        response = requests.post(webhook, json=final_payload)
        response.raise_for_status()
        print(f"[DEBUG] Successfully notified market-gap module at {webhook}", flush=True)
    except Exception as e:
        print(f"⚠️ Failed to notify market-gap webhook ({webhook}): {e}", flush=True)

    return final_payload


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id=data.get('session_id'),
        email=data.get('email'),
        goal=data.get('goal','project plan'),
        files=data.get('files', []),
        next_action_webhook=data.get('next_action_webhook',''),
        folder_id=data.get('folder_id')
    )
