import os  
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ──────────────────────────────────────────────
# Cache templates at import time (only once)
print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF          = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF          = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF   = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates cached successfully", flush=True)
# ──────────────────────────────────────────────

DOCX_SERVICE_URL = os.getenv(
    "DOCX_SERVICE_URL",
    "https://docx-generator-api.onrender.com"
)

def build_score_summary(hw_df, sw_df):
    hw_count = len(hw_df) if hw_df is not None else 0
    sw_count = len(sw_df) if sw_df is not None else 0
    return (
        f"Your hardware inventory contains {hw_count} items, "
        f"and your software inventory contains {sw_count} items."
    )

def build_recommendations(hw_df, sw_df):
    recs = []
    if hw_df is None or hw_df.empty:
        recs.append("No hardware data provided.")
    else:
        recs.append("Review hardware tiers for under-resourced assets.")
    if sw_df is None or sw_df.empty:
        recs.append("No software data provided.")
    else:
        recs.append("Ensure all applications are classified by criticality.")
    return " ".join(recs)

def build_key_findings(hw_df, sw_df):
    findings = []
    if hw_df is not None and "Tier Total Score" in hw_df.columns:
        max_score = hw_df["Tier Total Score"].max()
        findings.append(f"Maximum hardware tier score: {max_score}.")
    if sw_df is not None and "Tier Total Score" in sw_df.columns:
        avg_score = sw_df["Tier Total Score"].mean()
        findings.append(f"Average software tier score: {avg_score:.1f}.")
    return " ".join(findings)

def generate_assessment(
    session_id,
    email,
    goal,
    files,
    next_action_webhook="",
    folder_id=None
):
    print("[DEBUG] Entered generate_assessment()", flush=True)
    session_path = os.path.join("temp_sessions", session_id)
    os.makedirs(session_path, exist_ok=True)

    # … your existing download, merge/classify, charting, and gap-sheet code …

    # Charting
    print("[DEBUG] Generating charts...", flush=True)
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    # … upload charts to Drive …

    # … save & upload HWGapAnalysis and SWGapAnalysis sheets …

    # Build narrative
    score_summary   = build_score_summary(hw_df, sw_df)
    recommendations = build_recommendations(hw_df, sw_df)
    key_findings    = build_key_findings(hw_df, sw_df)

    # ──────────────────────────────────────────────
    # Call external docx-generator
    payload = {
        "session_id":      session_id,
        "hw_gap_url":      links.get("file_1_drive_url"),
        "sw_gap_url":      links.get("file_2_drive_url"),
        "chart_paths":     chart_paths,
        "score_summary":   score_summary,
        "recommendations": recommendations,
        "key_findings":    key_findings
    }
    print(f"[DEBUG] Calling Report-Generator at {DOCX_SERVICE_URL}/generate_assessment", flush=True)
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    gen = resp.json()
    print(f"[DEBUG] Report-Generator response: {gen}", flush=True)

    # ──────────────────────────────────────────────
    # NEW: download the generated docx + pptx
    docx_rel = gen["docx_url"]   # e.g. "/files/{session_id}/...report.docx"
    pptx_rel = gen["pptx_url"]
    docx_url = f"{DOCX_SERVICE_URL}{docx_rel}"
    pptx_url = f"{DOCX_SERVICE_URL}{pptx_rel}"

    # local paths
    docx_name = os.path.basename(docx_rel)
    pptx_name = os.path.basename(pptx_rel)
    docx_local = os.path.join(session_path, docx_name)
    pptx_local = os.path.join(session_path, pptx_name)

    # download DOCX
    dl = requests.get(docx_url)
    dl.raise_for_status()
    with open(docx_local, "wb") as f:
        f.write(dl.content)
    print(f"[DEBUG] Downloaded DOCX to {docx_local}", flush=True)

    # download PPTX
    dl = requests.get(pptx_url)
    dl.raise_for_status()
    with open(pptx_local, "wb") as f:
        f.write(dl.content)
    print(f"[DEBUG] Downloaded PPTX to {pptx_local}", flush=True)

    # upload both to Drive
    links["file_3_drive_url"] = upload_to_drive(docx_local, docx_name, folder_id)
    links["file_4_drive_url"] = upload_to_drive(pptx_local, pptx_name, folder_id)
    print(f"[DEBUG] Uploaded DOCX+PPTX to Drive: {links['file_3_drive_url']}, {links['file_4_drive_url']}", flush=True)
    # ──────────────────────────────────────────────

    # Build final payload
    result = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status":     "complete",
        **links
    }

    if next_action_webhook:
        try:
            r = requests.post(next_action_webhook, json=result)
            print(f"[DEBUG] Downstream notify status: {r.status_code}", flush=True)
        except Exception as e:
            print(f"❌ Downstream notify failed: {e}", flush=True)
    else:
        print("⚠️ No next_action_webhook; skipping downstream.", flush=True)

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
