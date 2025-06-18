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

# Initialize OpenAI API key for AI-driven narratives
# Note: 'oepn' alias used to avoid conflicts
oepn = openai
oepn.api_key = os.getenv("OPENAI_API_KEY")

# Template and output directories
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR = "temp_sessions"

# ──────────────────────────────────────────────
# Cache templates at import time (only once)
print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates cached successfully", flush=True)
# ──────────────────────────────────────────────

DOCX_SERVICE_URL = os.getenv(
    "DOCX_SERVICE_URL",
    "https://docx-generator-api.onrender.com"
)
MARKET_GAP_WEBHOOK = "https://market-gap-analysis.onrender.com/start_market_gap"


def ai_narrative(section_name: str, summary: dict) -> str:
    """
    Use OpenAI to transform a summary dict into a polished narrative for a report section.
    """
    system_msg = {
        "role": "system",
        "content": (
            "You are a senior IT transformation advisor. "
            "Given the data summary, write a concise, professional narrative for the specified report section."
        )
    }
    user_msg = {
        "role": "user",
        "content": (
            f"Section: {section_name}\n"
            f"Data Summary (JSON):\n{json.dumps(summary, indent=2)}"
        )
    }
    resp = oepn.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, user_msg],
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()

# Existing build_section_* helpers assumed here


def generate_assessment(
    session_id,
    email,
    goal,
    files,
    next_action_webhook="",
    folder_id=None
):
    print("[DEBUG] Entered generate_assessment()", flush=True)
    # Determine target Drive folder: required folder_id or fallback to session_id
    upload_folder = folder_id if folder_id else session_id

    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    # Download and prepare dataframes
    hw_df, sw_df = pd.DataFrame(), pd.DataFrame()
    hw_file_path = sw_file_path = None
    for file in files:
        url, name = file.get("file_url"), file.get("file_name")
        local = os.path.join(session_path, name)
        print(f"[DEBUG] Downloading file {name} from {url}", flush=True)
        if url.startswith("http"):
            resp = requests.get(url)
            resp.raise_for_status()
            with open(local, "wb") as f:
                f.write(resp.content)
        else:
            with open(url, "rb") as src, open(local, "wb") as dst:
                dst.write(src.read())
        print(f"[DEBUG] Saved to {local}", flush=True)
        if file.get("type") == "asset_inventory":
            if hw_file_path is None:
                hw_file_path = local
            else:
                sw_file_path = local
        elif file.get("type") == "gap_working" and sw_file_path is None:
            sw_file_path = local

    # Merge & classify
    def merge_with_template(df_template, df_inv):
        for c in df_inv.columns:
            if c not in df_template.columns:
                df_template[c] = None
        df_inv = df_inv.reindex(columns=df_template.columns, fill_value=None)
        return pd.concat([df_template, df_inv], ignore_index=True)

    def apply_classification(df):
        if not df.empty and "Tier Total Score" in df.columns:
            return df.merge(CLASSIFICATION_DF, how="left", left_on="Tier Total Score", right_on="Score")
        return df

    if hw_file_path:
        hw_df = merge_with_template(HW_BASE_DF.copy(), pd.read_excel(hw_file_path))
        hw_df = suggest_hw_replacements(hw_df)
        hw_df = apply_classification(hw_df)
    if sw_file_path:
        sw_df = merge_with_template(SW_BASE_DF.copy(), pd.read_excel(sw_file_path))
        sw_df = suggest_sw_replacements(sw_df)
        sw_df = apply_classification(sw_df)

    # Charts upload
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    for name, local_path in chart_paths.items():
        try:
            # Upload charts to the folder specified by folder_id
            url = upload_to_drive(local_path, os.path.basename(local_path), upload_folder)
            chart_paths[name] = url
        except Exception as ex:
            print(f"❌ Failed upload chart {name}: {ex}", flush=True)

    # Save & upload GAP sheets
    links = {}
    for idx, df in enumerate((hw_df, sw_df), start=1):
        if not df.empty:
            file_label = ['HW', 'SW'][idx - 1]
            path = os.path.join(session_path, f"{file_label}GapAnalysis_{session_id}.xlsx")
            df.to_excel(path, index=False)
            # Use folder_id for output file uploads
            links[f"file_{idx}_drive_url"] = upload_to_drive(path, os.path.basename(path), upload_folder)

    # Build core narratives and recommendations
    score_summary    = build_score_summary(hw_df, sw_df)
    recommendations  = build_recommendations(hw_df, sw_df)
    key_findings     = build_key_findings(hw_df, sw_df)

    # AI-enhanced section narratives
    section_2_overview             = ai_narrative("IT Landscape Overview", {"raw_summary": build_section_2_overview(hw_df, sw_df)})
    section_3_hardware_breakdown   = ai_narrative("Hardware Breakdown by Device Type", {"raw_summary": build_section_3_hardware_breakdown(hw_df, sw_df)})
    section_4_software_breakdown   = ai_narrative("Software Breakdown by Application", {"raw_summary": build_section_4_software_breakdown(hw_df, sw_df)})
    # ... other sections retained unchanged ...
    section_20_next_steps          = ai_narrative("Recommended Next Steps & Roadmap", {"raw_summary": build_section_20_next_steps(hw_df, sw_df)})

    # Appendices
    try:
        classification_matrix_md = CLASSIFICATION_DF.to_markdown(index=False)
    except Exception:
        classification_matrix_md = CLASSIFICATION_DF.to_csv(index=False)
    data_sources_text = "Data sources: asset inventory files, GAP templates, classification tiers."

    # Build full payload
    payload = {
        "session_id": session_id,
        "email": email,
        "goal": goal,
        "hw_gap_url": links.get("file_1_drive_url"),
        "sw_gap_url": links.get("file_2_drive_url"),
        "chart_paths": chart_paths,
        "content_1": score_summary,
        "content_2": section_2_overview,
        "content_3": section_3_hardware_breakdown,
        "content_4": section_4_software_breakdown,
        # ... all content_x and slide_x keys unchanged ...
        "content_20": section_20_next_steps,
        "appendix_classification_matrix": classification_matrix_md,
        "appendix_data_sources": data_sources_text,
    }

    print(f"[DEBUG] Calling Report-Generator at {DOCX_SERVICE_URL}/generate_assessment", flush=True)
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    gen = resp.json()

    # Download & upload generated files
    docx_rel, pptx_rel = gen.get("docx_url"), gen.get("pptx_url")
    docx_local = os.path.join(session_path, os.path.basename(docx_rel))
    pptx_local = os.path.join(session_path, os.path.basename(pptx_rel))
    for dl_url, local in [(docx_rel, docx_local), (pptx_rel, pptx_local)]:
        resp_dl = requests.get(dl_url)
        resp_dl.raise_for_status()
        with open(local, "wb") as f:
            f.write(resp_dl.content)
    # Upload outputs using the provided folder_id
    links["file_3_drive_url"] = upload_to_drive(docx_local, os.path.basename(docx_rel), upload_folder)
    links["file_4_drive_url"] = upload_to_drive(pptx_local, os.path.basename(pptx_rel), upload_folder)

    result = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
        **links
    }

    try:
        requests.post(MARKET_GAP_WEBHOOK, json=result)
    except Exception as e:
        print(f"❌ Market-GAP notify failed: {e}", flush=True)

    return result


def process_assessment(data):
    session_id          = data.get("session_id")
    email               = data.get("email")
    goal                = data.get("goal", "project plan")
    files               = data.get("files", [])
    next_action_webhook = data.get("next_action_webhook", "")
    folder_id           = data.get("folder_id")

    print("[DEBUG] Entered process_assessment()", flush=True)
    return generate_assessment(
        session_id, email, goal, files, next_action_webhook, folder_id
    )
