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

# ─── Inline helper functions ─────────────────────────────────────────────────
def build_score_summary(hw_df, sw_df):
    total_hw = len(hw_df)
    total_sw = len(sw_df)
    return f"Analyzed {total_hw} hardware items and {total_sw} software items."


def build_recommendations(hw_df, sw_df):
    hw_recs = suggest_hw_replacements(hw_df).head(3).to_dict() if not hw_df.empty else {}
    sw_recs = suggest_sw_replacements(sw_df).head(3).to_dict() if not sw_df.empty else {}
    return {"hardware_replacements": hw_recs, "software_replacements": sw_recs}


def build_key_findings(hw_df, sw_df):
    findings = []
    if "Tier Total Score" in hw_df.columns:
        low = hw_df[hw_df["Tier Total Score"] < 50]
        findings.append(f"{len(low)} hardware items scored below 50")
    if "License Status" in sw_df.columns:
        expired = sw_df[sw_df["License Status"] == "Expired"]
        findings.append(f"{len(expired)} expired software licenses")
    return {"findings": findings}


def build_section_2_overview(hw_df, sw_df):
    return {"hardware_count": len(hw_df), "software_count": len(sw_df)}


def build_section_3_hardware_breakdown(hw_df, sw_df):
    return hw_df["Device Type"].value_counts().to_dict() if "Device Type" in hw_df.columns else {}


def build_section_4_software_breakdown(hw_df, sw_df):
    return sw_df["Application"].value_counts().to_dict() if "Application" in sw_df.columns else {}


def build_section_5_tier_distribution(hw_df, sw_df):
    return hw_df["Tier Total Score"].value_counts().to_dict() if "Tier Total Score" in hw_df.columns else {}


def build_section_6_hardware_lifecycle(hw_df, sw_df):
    return hw_df["Lifecycle Status"].value_counts().to_dict() if "Lifecycle Status" in hw_df.columns else {}


def build_section_7_software_licensing(hw_df, sw_df):
    return sw_df["License Status"].value_counts().to_dict() if "License Status" in sw_df.columns else {}


def build_section_8_security_posture(hw_df, sw_df):
    return hw_df["Security Rating"].value_counts().to_dict() if "Security Rating" in hw_df.columns else {}


def build_section_9_performance_metrics(hw_df, sw_df):
    return {"avg_cpu": hw_df["CPU Usage"].mean() if "CPU Usage" in hw_df.columns else None,
            "avg_memory": hw_df["Memory Usage"].mean() if "Memory Usage" in hw_df.columns else None}


def build_section_10_reliability(hw_df, sw_df):
    return hw_df["Uptime Percentage"].describe().to_dict() if "Uptime Percentage" in hw_df.columns else {}


def build_section_11_scalability(hw_df, sw_df):
    return {"scalable_hw": len(hw_df[hw_df["Tier Total Score"] > 80])}


def build_section_12_legacy_debt(hw_df, sw_df):
    return {"legacy_count": len(hw_df[hw_df["Obsolete"] == True])} if "Obsolete" in hw_df.columns else {}


def build_section_13_obsolete_platforms(hw_df, sw_df):
    return {"obsolete_platforms": hw_df[hw_df["Obsolete"] == True]["Device Name"].tolist()} if "Obsolete" in hw_df.columns else {}


def build_section_14_cloud_migration(hw_df, sw_df):
    return {"eligible_for_cloud": len(hw_df[hw_df["Obsolete"] == False])}


def build_section_15_strategic_alignment(hw_df, sw_df):
    return {"aligned_projects": sw_df[sw_df["Strategic Fit"] == "High"]["Application"].tolist()} if "Strategic Fit" in sw_df.columns else {}


def build_section_17_financial_implications(hw_df, sw_df):
    return {"estimated_cost_savings": hw_df["Cost Savings"].sum() if "Cost Savings" in hw_df.columns else 0}


def build_section_18_sustainability(hw_df, sw_df):
    return {"carbon_footprint": hw_df["Carbon Emissions"].sum() if "Carbon Emissions" in hw_df.columns else 0}


def build_section_20_next_steps(hw_df, sw_df):
    return {"next_steps": [
        "Review hardware replacement options",
        "Validate software license renewals"
    ]}
# ───────────────────────────────────────────────────────────────────────────────

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
    print(f"[DEBUG] Start assessment for {session_id}", flush=True)
    upload_folder = folder_id or session_id
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    # Download files
    hw_df = pd.DataFrame()
    sw_df = pd.DataFrame()
    hw_file_path = None
    sw_file_path = None
    for f in files:
        url, name = f['file_url'], f['file_name']
        local = os.path.join(session_path, name)
        print(f"[DEBUG] Download {name}", flush=True)
        response = requests.get(url) if url.startswith("http") else open(url, 'rb')
        content = getattr(response, 'content', response.read())
        with open(local, 'wb') as fh:
            fh.write(content)
        if f.get('type') == 'asset_inventory':
            if not hw_file_path:
                hw_file_path = local
            else:
                sw_file_path = local
        elif f.get('type') == 'gap_working' and not sw_file_path:
            sw_file_path = local

    # Merge & classify
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

    # Generate & upload charts
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    for k, p in chart_paths.items():
        chart_paths[k] = upload_to_drive(p, os.path.basename(p), upload_folder)

    # Save & upload GAP sheets
    links = {}
    for idx, df in enumerate((hw_df, sw_df), start=1):
        if not df.empty:
            label = ['HW','SW'][idx-1]
            path = os.path.join(session_path, f"{label}GapAnalysis_{session_id}.xlsx")
            df.to_excel(path, index=False)
            links[f"file_{idx}_drive_url"] = upload_to_drive(path, os.path.basename(path), upload_folder)

    # Core metrics and summaries
    score_summary = build_score_summary(hw_df, sw_df)
    recommendations = build_recommendations(hw_df, sw_df)
    key_findings = build_key_findings(hw_df, sw_df)

    # AI narratives for all sections
    payload_content = {
        'content_1': score_summary,
        'content_2': ai_narrative('IT Landscape Overview', build_section_2_overview(hw_df, sw_df)),
        'content_3': ai_narrative('Hardware Breakdown', build_section_3_hardware_breakdown(hw_df, sw_df)),
        'content_4': ai_narrative('Software Breakdown', build_section_4_software_breakdown(hw_df, sw_df)),
        'content_5': ai_narrative('Tier Distribution', build_section_5_tier_distribution(hw_df, sw_df)),
        'content_6': ai_narrative('Hardware Lifecycle Status', build_section_6_hardware_lifecycle(hw_df, sw_df)),
        'content_7': ai_narrative('Software Licensing Status', build_section_7_software_licensing(hw_df, sw_df)),
        'content_8': ai_narrative('Security Posture', build_section_8_security_posture(hw_df, sw_df)),
        'content_9': ai_narrative('Performance Metrics', build_section_9_performance_metrics(hw_df, sw_df)),
        'content_10': ai_narrative('System Reliability Overview', build_section_10_reliability(hw_df, sw_df)),
        'content_11': ai_narrative('Scalability Insights', build_section_11_scalability(hw_df, sw_df)),
        'content_12': ai_narrative('Legacy Systems & Technical Debt', build_section_12_legacy_debt(hw_df, sw_df)),
        'content_13': ai_narrative('Obsolete Platforms', build_section_13_obsolete_platforms(hw_df, sw_df)),
        'content_14': ai_narrative('Cloud Migration Potential', build_section_14_cloud_migration(hw_df, sw_df)),
        'content_15': ai_narrative('Strategic IT Alignment', build_section_15_strategic_alignment(hw_df, sw_df)),
        'content_16': key_findings,
        'content_17': ai_narrative('Financial Implications Analysis', build_section_17_financial_implications(hw_df, sw_df)),
        'content_18': ai_narrative('Sustainability & Green IT', build_section_18_sustainability(hw_df, sw_df)),
        'content_19': recommendations,
        'content_20': ai_narrative('Recommended Next Steps & Roadmap', build_section_20_next_steps(hw_df, sw_df))
    }

    # Appendices
    try:
        appendix_matrix = CLASSIFICATION_DF.to_markdown(index=False)
    except Exception:
        appendix_matrix = CLASSIFICATION_DF.to_csv(index=False)
    appendices = {
        'appendix_classification_matrix': appendix_matrix,
        'appendix_data_sources': 'Data sources: inventory files, GAP templates, classification tiers.'
    }

    # Build full payload
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

    # Map slide_* keys for PPTX
    payload.update({
        'slide_executive_summary': payload_content['content_1'],
        'slide_it_landscape_overview': payload_content['content_2'],
        'slide_hardware_analysis': payload_content['content_3'],
        'slide_software_analysis': payload_content['content_4'],
        'slide_tier_classification_summary': payload_content['content_5'],
        'slide_hardware_lifecycle_chart': payload_content['content_6'],
        'slide_software_licensing_review': payload_content['content_7'],
        'slide_security_vulnerability_heatmap': payload_content['content_8'],
        'slide_performance_&_uptime_trends': payload_content['content_9'],
        'slide_system_reliability_overview': payload_content['content_10'],
        'slide_scalability_insights': payload_content['content_11'],
        'slide_legacy_system_exposure': payload_content['content_12'],
        'slide_obsolete_platform_matrix': payload_content['content_13'],
        'slide_cloud_migration_targets': payload_content['content_14'],
        'slide_strategic_it_alignment': payload_content['content_15'],
        'slide_business_impact_of_gaps': payload_content['content_16'],
        'slide_cost_of_obsolescence': payload_content['content_17'],
        'slide_sustainability_&_green_it': payload_content['content_18'],
        'slide_remediation_recommendations': payload_content['content_19'],
        'slide_roadmap_&_next_steps': payload_content['content_20']
    })

    # Send to DOCX/PPTX service
    print(f"[DEBUG] POST to DOCX service: {DOCX_SERVICE_URL}", flush=True)
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    result_json = resp.json()

    # Download & upload outputs
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
        data.get('goal','project plan'),
        data.get('files', []),
        data.get('next_action_webhook',''),
        data.get('folder_id')
    )
