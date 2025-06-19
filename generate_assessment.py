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

# Service endpoints
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
    return {"total_devices": total_devices, "total_applications": total_apps,
            "healthy_devices": healthy_devices, "compliant_licenses": compliant_licenses}


def build_section_3_inventory_hardware(hw_df, sw_df):
    return {"hardware_items": hw_df.to_dict(orient="records")}


def build_section_4_inventory_software(hw_df, sw_df):
    return {"software_items": sw_df.to_dict(orient="records")}


def build_section_5_classification_distribution(hw_df, sw_df):
    dist = hw_df.get("Category", pd.Series()).value_counts().to_dict() if "Category" in hw_df.columns else {}
    return {"classification_distribution": dist}


def build_section_6_lifecycle_status(hw_df, sw_df):
    return {"lifecycle_status": []}


def build_section_7_software_compliance(hw_df, sw_df):
    compliant = sw_df[sw_df.get("License Status") != "Expired"].shape[0] if "License Status" in sw_df.columns else 0
    expired = sw_df[sw_df.get("License Status") == "Expired"].shape[0] if "License Status" in sw_df.columns else 0
    return {"compliant_count": compliant, "expired_count": expired}


def build_section_8_security_posture(hw_df, sw_df):
    return {"vulnerabilities": []}


def build_section_9_performance(hw_df, sw_df):
    return {"performance_metrics": []}


def build_section_10_reliability(hw_df, sw_df):
    return {"reliability_metrics": []}


def build_section_11_scalability(hw_df, sw_df):
    return {"scalability_opportunities": []}


def build_section_12_legacy_technical_debt(hw_df, sw_df):
    return {"legacy_issues": []}


def build_section_13_obsolete_risk(hw_df, sw_df):
    risks = []
    if not hw_df.empty:
        high_risk_hw = hw_df[hw_df.get("Tier Total Score", 0) < 30]
        risks.append({"hardware": high_risk_hw.to_dict(orient="records")})
    if not sw_df.empty:
        high_risk_sw = sw_df[sw_df.get("Tier Total Score", 0) < 30]
        risks.append({"software": high_risk_sw.to_dict(orient="records")})
    return {"risks": risks}


def build_section_14_cloud_migration(hw_df, sw_df):
    return {"cloud_migration": []}


def build_section_15_strategic_alignment(hw_df, sw_df):
    return {"alignment": []}


def build_section_16_business_impact(hw_df, sw_df):
    return {"business_impact": []}


def build_section_17_financial_implications(hw_df, sw_df):
    return {"financial_implications": []}


def build_section_18_environmental_sustainability(hw_df, sw_df):
    return {"environmental_sustainability": []}


def build_recommendations(hw_df, sw_df):
    hw_recs = suggest_hw_replacements(hw_df).head(3).to_dict(orient="records") if not hw_df.empty else []
    sw_recs = suggest_sw_replacements(sw_df).head(3).to_dict(orient="records") if not sw_df.empty else []
    return {"hardware_replacements": hw_recs, "software_replacements": sw_recs}


def build_section_20_next_steps(hw_df, sw_df):
    return build_section_8_action_items(hw_df, sw_df)


def ai_narrative(section_name: str, summary: dict) -> str:
    """
    Generate a narrative in chunks to avoid rate-limit errors.
    """
    items = list(summary.items())
    narratives = []
    for idx in range(0, len(items), 50):
        chunk = dict(items[idx:idx + 50])
        label = f" (chunk {idx//50+1})" if len(items) > 50 else ""
        user_content = f"Section: {section_name}{label}\nData: {json.dumps(chunk)}"
        messages = [
            {"role": "system", "content": (
                "You are a senior IT transformation advisor. "
                "Given the data summary, write a concise, professional narrative for the report section."
            )},
            {"role": "user", "content": user_content}
        ]
        try:
            resp = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3
            )
        except (openai.RateLimitError, openai.NotFoundError):
                        # Fallback to gpt-3.5-turbo if primary fails
            resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3
            )
        narratives.append(resp.choices[0].message.content.strip())
    return "\n\n".join(narratives)


def generate_assessment(session_id: str, email: str, goal: str, files: list, next_action_webhook: str, folder_id: str) -> dict:
    # Prepare dataframes
    hw_df, sw_df = pd.DataFrame(), pd.DataFrame()
    session_path = f"./{session_id}"
    os.makedirs(session_path, exist_ok=True)

    # Download and classify files
    for f in files:
        name, url = f['file_name'], f['file_url']
        local = os.path.join(session_path, name)
        try:
            r = requests.get(url); r.raise_for_status()
            with open(local, 'wb') as fl: fl.write(r.content)
            df_temp = pd.read_excel(local)
        except Exception as e:
            print(f"⚠️ Error reading {name}: {e}", flush=True)
            continue
        cols = set(c.lower() for c in df_temp.columns)
        provided = f.get('type','').lower()
        if provided=='asset_inventory' and {'device id','device name'}<=cols:
            hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
        elif provided=='asset_inventory' and {'app id','app name'}<=cols:
            sw_df = pd.concat([sw_df, df_temp], ignore_index=True)
        elif provided in ('hardware_inventory','asset_hardware') or {'device id','device name'}<=cols:
            hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
        else:
            sw_df = pd.concat([sw_df, df_temp], ignore_index=True)

    # Enrich & classify
    if not hw_df.empty:
        hw_df = suggest_hw_replacements(pd.concat([HW_BASE_DF, hw_df], ignore_index=True))
        hw_df = hw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')
    if not sw_df.empty:
        sw_df = suggest_sw_replacements(pd.concat([SW_BASE_DF, sw_df], ignore_index=True))
        sw_df = sw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Generate charts
    uploaded_charts = generate_visual_charts(hw_df, sw_df, session_path)

    # Build narratives
    section_funcs = [
        build_score_summary, build_section_2_overview, build_section_3_inventory_hardware,
        build_section_4_inventory_software, build_section_5_classification_distribution,
        build_section_6_lifecycle_status, build_section_7_software_compliance,
        build_section_8_security_posture, build_section_9_performance,
        build_section_10_reliability, build_section_11_scalability,
        build_section_12_legacy_technical_debt, build_section_13_obsolete_risk,
        build_section_14_cloud_migration, build_section_15_strategic_alignment,
        build_section_16_business_impact, build_section_17_financial_implications,
        build_section_18_environmental_sustainability, build_recommendations,
        build_section_20_next_steps
    ]
    narratives = {f"content_{i+1}": ai_narrative(func.__name__, func(hw_df, sw_df))
                  for i, func in enumerate(section_funcs)}

    payload = {
        'session_id': session_id,
        'email': email,
        'goal': goal,
        **uploaded_charts,
        **narratives
    }

    # Send to DOCX generator
    try:
        resp_docx = requests.post(f"{DOCX_SERVICE_URL}/generate_docx", json=payload)
        resp_docx.raise_for_status()
        docx_url = resp_docx.json().get('file_url')
    except Exception as e:
        print(f"⚠️ Docx gen failed: {e}", flush=True)
        docx_url = ''

    # Send to PPTX generator
    try:
        resp_pptx = requests.post(f"{DOCX_SERVICE_URL}/generate_pptx", json=payload)
        resp_pptx.raise_for_status()
        pptx_url = resp_pptx.json().get('file_url')
    except Exception as e:
        print(f"⚠️ Pptx gen failed: {e}", flush=True)
        pptx_url = ''

    # Upload to Drive
    file_links = {}
    if docx_url:
        fname = os.path.basename(docx_url)
        local_doc = os.path.join(session_path, fname)
        r = requests.get(docx_url); r.raise_for_status()
        with open(local_doc, 'wb') as fl: fl.write(r.content)
        file_links['file_9_drive_url'] = upload_to_drive(local_doc, fname, folder_id)
    if pptx_url:
        fname = os.path.basename(pptx_url)
        local_ppt = os.path.join(session_path, fname)
        r = requests.get(pptx_url); r.raise_for_status()
        with open(local_ppt, 'wb') as fl: fl.write(r.content)
        file_links['file_10_drive_url'] = upload_to_drive(local_ppt, fname, folder_id)

    # Notify market-gap
    final_payload = {'session_id': session_id, 'gpt_module': 'it_assessment', 'status': 'complete', **file_links}
    try:
        requests.post(next_action_webhook or MARKET_GAP_WEBHOOK, json=final_payload).raise_for_status()
    except Exception as e:
        print(f"⚠️ Market-gap notify failed: {e}", flush=True)

    return final_payload


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id=data.get('session_id'),
        email=data.get('email'),
        goal=data.get('goal', ''),
        files=data.get('files', []),
        next_action_webhook=data.get('next_action_webhook', ''),
        folder_id=data.get('folder_id', '')
    )
