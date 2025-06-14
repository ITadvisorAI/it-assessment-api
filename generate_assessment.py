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
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates cached successfully", flush=True)
# ──────────────────────────────────────────────

# Where to send doc/PPT generation requests
DOCX_SERVICE_URL = os.getenv(
    "DOCX_SERVICE_URL",
    "https://docx-generator-api.onrender.com"
)

def build_score_summary(hw_df, sw_df):
    # Simple example summary—customize as needed
    hw_count = len(hw_df) if hw_df is not None else 0
    sw_count = len(sw_df) if sw_df is not None else 0
    return (
        f"Your hardware inventory contains {hw_count} items, "
        f"and your software inventory contains {sw_count} items."
    )

def build_recommendations(hw_df, sw_df):
    # Placeholder recommendations logic
    recs = []
    if hw_df is not None and hw_df.empty:
        recs.append("No hardware data provided.")
    else:
        recs.append("Review hardware tiers for under-resourced assets.")
    if sw_df is not None and sw_df.empty:
        recs.append("No software data provided.")
    else:
        recs.append("Ensure all applications are classified by criticality.")
    return " ".join(recs)

def build_key_findings(hw_df, sw_df):
    # Placeholder key findings logic
    findings = []
    if hw_df is not None:
        max_score = hw_df["Tier Total Score"].max() if "Tier Total Score" in hw_df.columns else None
        findings.append(f"Maximum hardware tier score: {max_score}.")
    if sw_df is not None:
        avg_score = sw_df["Tier Total Score"].mean() if "Tier Total Score" in sw_df.columns else None
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

    # … (download & classify input files, merge/classify, assume hw_df & sw_df defined) …

    # Charting
    print("[DEBUG] Generating charts...", flush=True)
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    print(f"[DEBUG] Charts: {chart_paths}", flush=True)

    # Upload each chart image to Drive and replace its local path with the Drive URL
    for chart_name, local_path in list(chart_paths.items()):
        try:
            print(f"[DEBUG] Uploading chart {local_path} to Drive", flush=True)
            drive_url = upload_to_drive(local_path, os.path.basename(local_path), folder_id)
            chart_paths[chart_name] = drive_url
            print(f"[DEBUG] Chart {chart_name} uploaded: {drive_url}", flush=True)
        except Exception as ex:
            print(f"❌ Failed to upload chart {local_path}: {ex}", flush=True)
            # leave local path if upload fails

    # Save gap-analysis sheets
    hw_gap = sw_gap = None
    if hw_df is not None:
        hw_gap = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
        hw_df.to_excel(hw_gap, index=False)
        print(f"[DEBUG] Saved HW gap sheet: {hw_gap}", flush=True)
    if sw_df is not None:
        sw_gap = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")
        sw_df.to_excel(sw_gap, index=False)
        print(f"[DEBUG] Saved SW gap sheet: {sw_gap}", flush=True)

    # Determine Drive folder
    if not folder_id:
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        print(f"[DEBUG] Fallback folder_id: {folder_id}", flush=True)
    else:
        print(f"[DEBUG] Using provided folder_id: {folder_id}", flush=True)

    # Upload intermediate artifacts to Drive
    links = {}
    for idx, path in enumerate([hw_gap, sw_gap], start=1):
        if path and os.path.exists(path):
            print(f"[DEBUG] Uploading {path} → Drive", flush=True)
            url = upload_to_drive(path, os.path.basename(path), folder_id)
            links[f"file_{idx}_drive_url"] = url
            print(f"[DEBUG] Uploaded to: {url}", flush=True)

    # Build narrative content for the report
    score_summary   = build_score_summary(hw_df, sw_df)
    recommendations = build_recommendations(hw_df, sw_df)
    key_findings    = build_key_findings(hw_df, sw_df)

    # Offload DOCX/PPTX creation to the external service
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

    # incorporate back the served URLs
    links["file_3_drive_url"] = gen["docx_url"]
    links["file_4_drive_url"] = gen["pptx_url"]

    # Build payload for downstream modules
    result = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status":     "complete",
        **links
    }

    # Notify next module if requested
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
