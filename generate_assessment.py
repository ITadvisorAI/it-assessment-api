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
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis-api.onrender.com/start_gap_analysis")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp")

# Initialize OpenAI client
client = openai.OpenAI()

# ─── Section builder helper functions ───────────────────────────────────────────

def build_score_summary(hw_df, sw_df):
    return {
        "text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."
    }

# ... other builder functions unchanged ...

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
    for f in files:
        # download and read df_temp...
        # infer and append to hw_df or sw_df
        pass

    # Enrich dataframes using pd.concat instead of deprecated append
    if not hw_df.empty:
        merged_hw = pd.concat([HW_BASE_DF, hw_df], ignore_index=True)
        hw_df = suggest_hw_replacements(merged_hw)
        hw_df = hw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')
    if not sw_df.empty:
        merged_sw = pd.concat([SW_BASE_DF, sw_df], ignore_index=True)
        sw_df = suggest_sw_replacements(merged_sw)
        sw_df = sw_df.merge(CLASSIFICATION_DF, how='left', left_on='Tier Total Score', right_on='Score')

    # Generate & upload charts, build payload, call DOCX service, etc.
    # ... rest of code unchanged ...
    return {}


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id=data.get('session_id'),
        email=data.get('email'),
        goal=data.get('goal','project plan'),
        files=data.get('files', []),
        next_action_webhook=data.get('next_action_webhook',''),
        folder_id=data.get('folder_id')
    )
