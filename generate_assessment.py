import os
import re
import io
import json
import logging
import requests
import pandas as pd
import openai
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

# If you need to use python-docx or python-pptx directly, import here; otherwise, we use the docx-generator service
# from docx import Document
# from pptx import Presentation
# from pptx.util import Inches

# Configure logging
tlogging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(levelname)s:%(message)s')

# Constants and template loading
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR = "temp_sessions"

# Base templates for Excel merging
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
logging.debug("Templates loaded successfully")

# External services
DOCX_SERVICE_URL = os.getenv(
    "DOCX_SERVICE_URL",
    "https://docx-generator-api.onrender.com"
)
MARKET_GAP_WEBHOOK = os.getenv(
    "MARKET_GAP_WEBHOOK",
    "https://market-gap-analysis.onrender.com/start_market_gap"
)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Utility functions

def _download_file(url: str, dest: str):
    """Download a file from a URL to a local destination."""
    logging.debug(f"Downloading {url} to {dest}")
    resp = requests.get(url)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def merge_with_template(template_df: pd.DataFrame, inv_df: pd.DataFrame) -> pd.DataFrame:
    """Merge inventory data into the template on shared columns."""
    return pd.concat([template_df, inv_df], ignore_index=True)


def apply_classification(df: pd.DataFrame) -> pd.DataFrame:
    """Apply classification tier lookup to DataFrame."""
    if not df.empty and "Tier Total Score" in df.columns:
        merged = df.merge(
            CLASSIFICATION_DF,
            how="left",
            left_on="Tier Total Score",
            right_on="Score"
        )
        logging.debug(f"Applied classification; rows: {len(merged)}")
        return merged
    logging.debug("Skipping classification; empty or missing 'Tier Total Score'")
    return df


def ai_narrative(section_name: str, data) -> str:
    """Generate a narrative for a section via OpenAI."""
    prompt_payload = json.dumps({"section": section_name, "data": data}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": (
            "You are a senior IT transformation advisor. Provide a concise narrative." )},
        {"role": "user", "content": f"Section: {section_name}\nData: {prompt_payload}"}
    ]
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3
        )
    except Exception as e:
        logging.warning(f"gpt-4o-mini failed: {e}, falling back to gpt-3.5-turbo")
        resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.3
        )
    content = resp.choices[0].message.content.strip()
    logging.debug(f"Narrative for {section_name}: {content[:50]}...")
    return content

# Section builders

def build_score_summary(hw_df, sw_df):
    """Produce a high-level summary of inventory counts."""
    return {
        "sections": "Score Summary",
        "count": {"hardware": len(hw_df), "software": len(sw_df)}
    }

def build_hardware_details(hw_df, sw_df):
    """Detail hardware classification distribution."""
    dist = hw_df['Classification'].value_counts().to_dict() if 'Classification' in hw_df.columns else {}
    return {"ClassificationDistribution": dist}

def build_software_details(hw_df, sw_df):
    """Detail software status distribution."""
    dist = sw_df['Status'].value_counts().to_dict() if 'Status' in sw_df.columns else {}
    return {"StatusDistribution": dist}

def build_recommendations(hw_df, sw_df):
    """List high-level recommendations based on data presence."""
    recs = []
    if hw_df.empty:
        recs.append("No hardware inventory found; please upload assets.")
    else:
        recs.append("Review and upgrade assets in lowest tiers.")
    if sw_df.empty:
        recs.append("No software inventory found; please upload application data.")
    else:
        recs.append("Ensure critical applications are patched and up-to-date.")
    return {"recommendations": recs}

# Main functions

def generate_assessment(
    session_id: str,
    email: str,
    goal: str,
    files: list,
    next_action_webhook: str = "",
    folder_id: str = None,
) -> dict:
    """Core workflow for IT asset gap analysis."""
    # Setup
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)
    logging.info(f"Session directory: {session_path}")

    # Use provided Drive folder ID
    session_folder = folder_id

    # Download & map files
    hw_path = sw_path = None
    for f in files:
        url = f['file_url']; name = f['file_name']; ftype = f.get('type','').lower()
        local_file = os.path.join(session_path, name)
        _download_file(url, local_file)
        try:
            temp_df = pd.read_excel(local_file)
            cols = {c.strip().lower() for c in temp_df.columns}
        except Exception:
            cols = set()
        # Determine hardware vs software
        if ftype == 'asset_inventory':
            if hw_path is None and ({'device id','device name'} & cols or {'server id','server name'} & cols):
                hw_path = local_file
            elif sw_path is None and {'app id','app name'} & cols:
                sw_path = local_file
            elif hw_path and not sw_path:
                sw_path = local_file
        elif ftype == 'gap_working' and not sw_path:
            sw_path = local_file
    # Load DataFrames
    hw_df = pd.read_excel(hw_path) if hw_path else pd.DataFrame()
    sw_df = pd.read_excel(sw_path) if sw_path else pd.DataFrame()
    logging.info(f"Loaded hw_df: {len(hw_df)} rows, sw_df: {len(sw_df)} rows")

    # Merge template, suggest, classify
    if not hw_df.empty:
        hw_df = merge_with_template(HW_BASE_DF.copy(), hw_df)
        hw_df = suggest_hw_replacements(hw_df)
        hw_df = apply_classification(hw_df)
    if not sw_df.empty:
        sw_df = merge_with_template(SW_BASE_DF.copy(), sw_df)
        sw_df = suggest_sw_replacements(sw_df)
        sw_df = apply_classification(sw_df)

    # Generate and upload Excels
    links = {}
    hw_excel = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
    sw_excel = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")
    try:
        hw_df.to_excel(hw_excel, index=False)
        links['file_1_drive_url'] = upload_to_drive(hw_excel, os.path.basename(hw_excel), session_folder)
    except Exception as e:
        logging.error(f"HW Excel error: {e}")
    try:
        sw_df.to_excel(sw_excel, index=False)
        links['file_2_drive_url'] = upload_to_drive(sw_excel, os.path.basename(sw_excel), session_folder)
    except Exception as e:
        logging.error(f"SW Excel error: {e}")

    # Generate and upload charts
    try:
        chart_urls = generate_visual_charts(hw_df, sw_df, session_folder)
        links.update(chart_urls)
    except Exception as e:
        logging.error(f"Chart error: {e}")

    # Build narratives
    builders = [build_score_summary, build_hardware_details, build_software_details, build_recommendations]
    narratives = {}
    for i, fn in enumerate(builders, start=1):
        key = f"content_{i}"
        data = fn(hw_df, sw_df)
        try:
            narratives[key] = ai_narrative(fn.__name__, data)
        except Exception as e:
            logging.error(f"Narrative {fn.__name__} error: {e}")

    # Assemble payload
    payload = {"session_id": session_id, "email": email, "goal": goal, **links, **narraries}
    # Call docx service
    try:
        resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
        resp.raise_for_status()
        gen = resp.json()
    except Exception as e:
        logging.error(f"DOCX service error: {e}")
        return {"error": str(e)}

    # Download and upload DOCX/PPTX
    for idx, key in enumerate(['docx_url','pptx_url'], start=3):
        rel = gen.get(key)
        if rel:
            url = f"{DOCX_SERVICE_URL.rstrip('/')}" + rel
            local = os.path.join(session_path, os.path.basename(rel))
            r = requests.get(url)
            r.raise_for_status()
            with open(local, 'wb') as f:
                f.write(r.content)
            links[f'file_{idx}_drive_url'] = upload_to_drive(local, os.path.basename(local), session_folder)

    # Notify Market Gap
    try:
        notify = {"session_id": session_id, "gpt_module": "it_assessment", "status": "complete", **links}
        requests.post(MARKET_GAP_WEBHOOK, json=notify)
    except Exception as e:
        logging.error(f"Market notify error: {e}")

    # Next-action webhook
    if next_action_webhook:
        try:
            requests.post(next_action_webhook, json={"session_id": session_id, **links})
        except Exception as e:
            logging.error(f"Next webhook error: {e}")

    logging.info(f"Assessment complete for {session_id}")
    return {"session_id": session_id, **links, **narraries}


def process_assessment(data: dict) -> dict:
    logging.debug(f"process_assessment: {data.get('session_id')}")
    return generate_assessment(
        session_id=data.get('session_id'),
        email=data.get('email'),
        goal=data.get('goal',''),
        files=data.get('files',[]),
        next_action_webhook=data.get('next_action_webhook',''),
        folder_id=data.get('folder_id')
    )
