import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
# from report_docx import generate_docx_report     # no longer used
from drive_utils import upload_to_drive
# from report_pptx import generate_pptx_report     # no longer used

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ──────────────────────────────────────────────
# Cache templates at import time (only once)
print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates cached successfully", flush=True)
# ──────────────────────────────────────────────

# New: where to send doc/PPT generation requests
DOCX_SERVICE_URL = os.getenv(
    "DOCX_SERVICE_URL",
    "https://docx-generator-api.onrender.com"
)

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

    # … (download & classify input files, merge/classify, charting) …

    print("[DEBUG] Generating charts...", flush=True)
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    print(f"[DEBUG] Charts: {chart_paths}", flush=True)

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

    # ──────────────────────────────────────────────
    # NEW: offload DOCX/PPTX creation to the external service
    payload = {
        "session_id": session_id,
        # pass any URLs or data your generator needs:
        "hw_gap_url": links.get("file_1_drive_url"),
        "sw_gap_url": links.get("file_2_drive_url"),
        "chart_paths": chart_paths
    }
    print(f"[DEBUG] Calling Report-Generator at {DOCX_SERVICE_URL}/generate_assessment", flush=True)
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    gen = resp.json()
    print(f"[DEBUG] Report-Generator response: {gen}", flush=True)

    # incorporate back the served URLs
    links["file_3_drive_url"] = gen["docx_url"]
    links["file_4_drive_url"] = gen["pptx_url"]
    # ──────────────────────────────────────────────

    # Build payload for downstream modules
    result = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
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
