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

# Section builder functions

def build_score_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}


def build_section_2_overview(hw_df, sw_df):
    total_devices = len(hw_df)
    total_apps = len(sw_df)
    healthy_devices = hw_df[hw_df.get("Tier Total Score", 0) >= 75].shape[0]
    compliant_licenses = sw_df[sw_df.get("License Status") != "Expired"].shape[0] if "License Status" in sw_df.columns else 0
    return {
        "total_devices": total_devices,
        "total_applications": total_apps,
        "healthy_devices": healthy_devices,
        "compliant_licenses": compliant_licenses
    }


def build_section_3_inventory_hardware(hw_df, sw_df):
    return {"hardware_items": hw_df.to_dict(orient="records")}  # stub: list all hardware


def build_section_4_inventory_software(hw_df, sw_df):
    return {"software_items": sw_df.to_dict(orient="records")}  # stub: list all software


def build_section_5_classification_distribution(hw_df, sw_df):
    dist = hw_df.get("Category", pd.Series()).value_counts().to_dict() if "Category" in hw_df.columns else {}
    return {"classification_distribution": dist}


def build_section_6_lifecycle_status(hw_df, sw_df):
    # stub: summarize lifecycle if available
    return {"lifecycle_status": []}


def build_section_7_software_compliance(hw_df, sw_df):
    compliant = sw_df[sw_df.get("License Status") != "Expired"].shape[0] if "License Status" in sw_df.columns else 0
    expired = sw_df[sw_df.get("License Status") == "Expired"].shape[0] if "License Status" in sw_df.columns else 0
    return {"compliant_count": compliant, "expired_count": expired}


def build_section_8_security_posture(hw_df, sw_df):
    # stub
    return {"vulnerabilities": []}


def build_section_9_performance(hw_df, sw_df):
    # stub
    return {"performance_metrics": []}


def build_section_10_reliability(hw_df, sw_df):
    # stub
    return {"reliability_metrics": []}


def build_section_11_scalability(hw_df, sw_df):
    # stub
    return {"scalability_opportunities": []}


def build_section_12_legacy_technical_debt(hw_df, sw_df):
    # stub
    return {"legacy_issues": []}


def build_section_13_obsolete_risk(hw_df, sw_df):
    # Inline risk logic instead of importing non-existent function
    risks = []
    if not hw_df.empty:
        high_risk_hw = hw_df[hw_df.get("Tier Total Score", 0) < 30]
        risks.append({"hardware": high_risk_hw.to_dict(orient="records")})
    if not sw_df.empty:
        high_risk_sw = sw_df[sw_df.get("Tier Total Score", 0) < 30]
        risks.append({"software": high_risk_sw.to_dict(orient="records")})
    return {"risks": risks}


def build_section_14_cloud_migration(hw_df, sw_df):
    # stub
    return {"cloud_migration": []}


def build_section_15_strategic_alignment(hw_df, sw_df):
    # stub
    return {"alignment": []}


def build_section_16_business_impact(hw_df, sw_df):
    # stub
    return {"business_impact": []}


def build_section_17_financial_implications(hw_df, sw_df):
    # stub
    return {"financial_implications": []}


def build_section_18_environmental_sustainability(hw_df, sw_df):
    # stub
    return {"environmental_sustainability": []}


def build_recommendations(hw_df, sw_df):
    hw_recs = suggest_hw_replacements(hw_df).head(3).to_dict(orient="records") if not hw_df.empty else []
    sw_recs = suggest_sw_replacements(sw_df).head(3).to_dict(orient="records") if not sw_df.empty else []
    return {"hardware_replacements": hw_recs, "software_replacements": sw_recs}


def build_section_20_next_steps(hw_df, sw_df):
    return build_section_8_action_items(hw_df, sw_df)


def build_key_findings(hw_df, sw_df):
    findings = []
    if "Tier Total Score" in hw_df.columns:
        low = hw_df[hw_df.get("Tier Total Score", 0) < 50]
        findings.append({"hardware_low_score": low.to_dict(orient="records")})
    if "Tier Total Score" in sw_df.columns:
        low_sw = sw_df[sw_df.get("Tier Total Score", 0) < 50]
        findings.append({"software_low_score": low_sw.to_dict(orient="records")})
    return {"findings": findings}


def build_section_6_distribution(hw_df, sw_df):
    dist_hw = hw_df.get("Category", pd.Series()).value_counts().to_dict() if "Category" in hw_df.columns else {}
    return {"hardware_distribution": dist_hw}


def build_section_7_trend_analysis(hw_df, sw_df):
    return {"trends": []}


def build_section_8_action_items(hw_df, sw_df):
    return {"action_items": []}


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
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()


def generate_assessment(session_id: str, email: str, goal: str, files: list, next_action_webhook: str, folder_id: str) -> dict:
    # Prepare dataframes
    hw_df = pd.DataFrame()
    sw_df = pd.DataFrame()
    session_path = f"./{session_id}"
    os.makedirs(session_path, exist_ok=True)

    # Download, read, and classify files
    for f in files:
        name = f.get('file_name')
        url = f.get('file_url')
        local_path = os.path.join(session_path, name)
        try:
            r = requests.get(url); r.raise_for_status()
            with open(local_path, 'wb') as fl:
                fl.write(r.content)
            df_temp = pd.read_excel(local_path)
        except Exception as e:
            print(f"⚠️ Error downloading or reading {name}: {e}", flush=True)
            continue

        cols = {c.lower() for c in df_temp.columns}
        provided = f.get('type', '').lower()
        # Refined type inference
        if provided == 'asset_inventory':
            lname = name.lower()
            if 'server' in lname or 'hardware' in lname or {'device id','device name'}.issubset(cols):
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True) if not hw_df.empty else df_temp
            elif 'application' in lname or 'app' in lname or {'app id','app name','license status'}.issubset(cols):
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True) if not sw_df.empty else df_temp
            else:
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True) if not hw_df.empty else df_temp
        elif provided in ('hardware_inventory','asset_hardware') or {'device id','device name'}.issubset(cols):
            hw_df = pd.concat([hw_df, df_temp], ignore_index=True) if not hw_df.empty else df_temp
        elif provided in ('software_inventory','asset_software') or {'app id','app name','license status'}.issubset(cols):
            sw_df = pd.concat([sw_df, df_temp], ignore_index=True) if not sw_df.empty else df_temp
        else:
            hw_df = pd.concat([hw_df, df_temp], ignore_index=True) if not hw_df.empty else df_temp

    # Enrich & classify
    if not hw_df.empty:
        merged_hw = pd.concat([HW_BASE_DF, hw_df], ignore_index=True)
        hw_df = suggest_hw_replacements(merged_hw)
        hw_df = hw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')
    if not sw_df.empty:
        merged_sw = pd.concat([SW_BASE_DF, sw_df], ignore_index=True)
        sw_df = suggest_sw_replacements(merged_sw)
        sw_df = sw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Generate and upload charts
    uploaded_charts = generate_visual_charts(hw_df, sw_df, session_path)

    # Prepare content sections for narrative
    sections = {
        'Executive Summary': build_score_summary(hw_df, sw_df),
        'Organization IT Landscape Overview': build_section_2_overview(hw_df, sw_df),
        'Inventory Breakdown – Hardware': build_section_3_inventory_hardware(hw_df, sw_df),
        'Inventory Breakdown – Software': build_section_4_inventory_software(hw_df, sw_df),
        'Classification Tier Distribution': build_section_5_classification_distribution(hw_df, sw_df),
        'Hardware Lifecycle Status': build_section_6_lifecycle_status(hw_df, sw_df),
        'Software Licensing and Compliance': build_section_7_software_compliance(hw_df, sw_df),
        'Security Posture and Vulnerabilities': build_section_8_security_posture(hw_df, sw_df),
        'Performance Bottlenecks & Uptime Metrics': build_section_9_performance(hw_df, sw_df),
        'System Reliability & Failover Readiness': build_section_10_reliability(hw_df, sw_df),
        'Scalability & Elasticity Opportunities': build_section_11_scalability(hw_df, sw_df),
        'Legacy Systems and Technical Debt': build_section_12_legacy_technical_debt(hw_df, sw_df),
        'Obsolete and High-Risk Platforms': build_section_13_obsolete_risk(hw_df, sw_df),
        'Cloud Migration Potential (Workload Mapping)': build_section_14_cloud_migration(hw_df, sw_df),
        'Strategic Alignment of IT Assets': build_section_15_strategic_alignment(hw_df, sw_df),
        'Business Impact Analysis of Current Gaps': build_section_16_business_impact(hw_df, sw_df),
        'Financial Implications – Cost of Obsolescence': build_section_17_financial_implications(hw_df, sw_df),
        'Environmental Impact and Sustainability': build_section_18_environmental_sustainability(hw_df, sw_df),
        'Recommendations for Remediation & Upgrade': build_recommendations(hw_df, sw_df),
        'Proposed Next Steps and Roadmap': build_section_20_next_steps(hw_df, sw_df)
    }
    narratives = {f"content_{i+1}": ai_narrative(name, summary)
                  for i,(name,summary) in enumerate(sections.items())}

    # Build payload for both docx and pptx
    payload = {
        'session_id': session_id,
        'email': email,
        'goal': goal,
        **uploaded_charts,
        **narratives
    }

    file_links = {}
    # Generate DOCX
    try:
        resp_docx = requests.post(f"{DOCX_SERVICE_URL}/generate_docx", json=payload)
        resp_docx.raise_for_status()
        docx_url = resp_docx.json().get('file_url')
        if docx_url:
            fname = os.path.basename(docx_url)
            local_doc = os.path.join(session_path, fname)
            r = requests.get(docx_url); r.raise_for_status()
            with open(local_doc, 'wb') as fl: fl.write(r.content)
            file_links['file_9_drive_url'] = upload_to_drive(local_doc, fname, folder_id)
    except Exception as e:
        print(f"⚠️ Docx generation failed: {e}", flush=True)

    # Generate PPTX
    try:
        resp_pptx = requests.post(f"{DOCX_SERVICE_URL}/generate_pptx", json=payload)
        resp_pptx.raise_for_status()
        pptx_url = resp_pptx.json().get('file_url')
        if pptx_url:
            fname = os.path.basename(pptx_url)
            local_ppt = os.path.join(session_path, fname)
            r = requests.get(pptx_url); r.raise_for_status()
            with open(local_ppt, 'wb') as fl: fl.write(r.content)
            file_links['file_10_drive_url'] = upload_to_drive(local_ppt, fname, folder_id)
    except Exception as e:
        print(f"⚠️ Pptx generation failed: {e}", flush=True)

    # Notify next module (Market Gap)
    final_payload = {'session_id': session_id, 'gpt_module': 'it_assessment', 'status': 'complete', **file_links}
    webhook = next_action_webhook or MARKET_GAP_WEBHOOK
    try:
        response = requests.post(webhook, json=final_payload)
        response.raise_for_status()
        print(f"[DEBUG] Notified market-gap module at {webhook}", flush=True)
    except Exception as e:
        print(f"⚠️ Failed to notify market-gap webhook ({webhook}): {e}", flush=True)

    return final_payload


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id=data.get('session_id'),
        email=data.get('email'),
        goal=data.get('goal', 'project plan'),
        files=data.get('files', []),
        next_action_webhook=data.get('next_action_webhook', ''),
        folder_id=data.get('folder_id')
    )
