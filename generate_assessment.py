import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from report_docx import generate_docx_report
from drive_utils import upload_to_drive
from report_pptx import generate_pptx_report

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ──────────────────────────────────────────────
# Cache templates at import time (only once)
print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates cached successfully", flush=True)
# ──────────────────────────────────────────────

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

    # Download & classify input files
    hw_file_path = sw_file_path = None
    for file in files:
        url = file["file_url"]
        name = file["file_name"]
        local = os.path.join(session_path, name)
        print(f"[DEBUG] Downloading {name}", flush=True)
        if url.startswith("http"):
            resp = requests.get(url); resp.raise_for_status()
            with open(local, "wb") as f: f.write(resp.content)
        else:
            with open(url, "rb") as src, open(local, "wb") as dst:
                dst.write(src.read())
        print(f"[DEBUG] Saved to {local}", flush=True)
        if file["type"].lower() == "asset_inventory":
            # simple heuristic: first = HW, second = SW
            if not hw_file_path:
                hw_file_path = local
            else:
                sw_file_path = local

    print(f"[DEBUG] hw_file_path={hw_file_path}, sw_file_path={sw_file_path}", flush=True)

    # Helpers: merge & classify
    def merge_with_template(tdf, inv_df):
        for c in inv_df.columns:
            if c not in tdf.columns:
                tdf[c] = None
        inv_df = inv_df.reindex(columns=tdf.columns, fill_value=None)
        return pd.concat([tdf, inv_df], ignore_index=True)

    def apply_classification(df):
        if df is not None and "Tier Total Score" in df.columns:
            return df.merge(CLASSIFICATION_DF, how="left",
                            left_on="Tier Total Score", right_on="Score")
        return df

    # Merge & classify
    print("[DEBUG] Merging and classifying data...", flush=True)
    hw_df = sw_df = None
    if hw_file_path:
        inv = pd.read_excel(hw_file_path)
        hw_df = merge_with_template(HW_BASE_DF.copy(), inv)
        hw_df = suggest_hw_replacements(hw_df)
        hw_df = apply_classification(hw_df)
    if sw_file_path:
        inv = pd.read_excel(sw_file_path)
        sw_df = merge_with_template(SW_BASE_DF.copy(), inv)
        sw_df = suggest_sw_replacements(sw_df)
        sw_df = apply_classification(sw_df)
    print("[DEBUG] Merge/classify done", flush=True)

    # Charting
    print("[DEBUG] Generating charts...", flush=True)
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    print(f"[DEBUG] Charts: {chart_paths}", flush=True)

    # Reports
    print("[DEBUG] Generating DOCX report...", flush=True)
    docx_path = generate_docx_report(session_id, hw_df, sw_df, chart_paths)
    print(f"[DEBUG] DOCX at {docx_path}", flush=True)

    print("[DEBUG] Generating PPTX report...", flush=True)
    pptx_path = generate_pptx_report(session_id, hw_df, sw_df, chart_paths)
    print(f"[DEBUG] PPTX at {pptx_path}", flush=True)

    # Save gap sheets
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

    # Upload outputs
    links = {}
    for idx, path in enumerate([hw_gap, sw_gap, docx_path, pptx_path], start=1):
        if path and os.path.exists(path):
            print(f"[DEBUG] Uploading {path} → Drive", flush=True)
            url = upload_to_drive(path, os.path.basename(path), folder_id)
            links[f"file_{idx}_drive_url"] = url
            print(f"[DEBUG] Uploaded to: {url}", flush=True)

    # Build payload
    payload = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
        **links
    }

    # Downstream notification
    if next_action_webhook:
        print(f"[DEBUG] Notifying next module at {next_action_webhook}", flush=True)
        resp = requests.post(next_action_webhook, json=payload)
        print(f"[DEBUG] Downstream status: {resp.status_code}", flush=True)
    else:
        print("⚠️ No next_action_webhook; skipping downstream.", flush=True)

    return payload

def process_assessment(data):
    session_id = data.get("session_id")
    email = data.get("email")
    goal = data.get("goal", "project plan")
    files = data.get("files", [])
    next_action_webhook = data.get("next_action_webhook", "")
    folder_id = data.get("folder_id")

    print("[DEBUG] Entered process_assessment()", flush=True)
    return generate_assessment(session_id, email, goal, files, next_action_webhook, folder_id)
