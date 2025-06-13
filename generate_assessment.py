import os
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from report_docx import generate_docx_report
from drive_utils import upload_to_drive
from report_pptx import generate_pptx_report

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

def generate_assessment(
    session_id,
    email,
    goal,
    files,
    next_action_webhook="",
    folder_id=None  # <— Accept folder_id
):
    session_path = os.path.join("temp_sessions", session_id)
    os.makedirs(session_path, exist_ok=True)

    # Load templates
    hw_base_df = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
    sw_base_df = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
    classification_df = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))

    hw_file_path = sw_file_path = None

    # Download user files
    for file in files:
        url = file["file_url"]
        name = file["file_name"]
        local = os.path.join(session_path, name)
        resp = requests.get(url) if url.startswith("http") else open(url, "rb")
        with open(local, "wb") as f:
            f.write(resp.content if hasattr(resp, "content") else resp.read())
        if "asset_inventory" in file["type"]:
            hw_file_path = local if "hardware" in name.lower() else hw_file_path
            sw_file_path = local if "application" in name.lower() else sw_file_path

    # Merge and classify
    def merge_with_template(tdf, inv_df):
        for c in inv_df.columns:
            if c not in tdf.columns:
                tdf[c] = None
        inv_df = inv_df.reindex(columns=tdf.columns, fill_value=None)
        return pd.concat([tdf, inv_df], ignore_index=True)

    def apply_classification(df):
        if df is not None and "Tier Total Score" in df.columns:
            return df.merge(classification_df, how="left", left_on="Tier Total Score", right_on="Score")
        return df

    hw_df = sw_df = None
    if hw_file_path:
        inv = pd.read_excel(hw_file_path)
        hw_df = apply_classification(suggest_hw_replacements(merge_with_template(hw_base_df, inv)))
    if sw_file_path:
        inv = pd.read_excel(sw_file_path)
        sw_df = apply_classification(suggest_sw_replacements(merge_with_template(sw_base_df, inv)))

    # Generate visuals and reports
    charts = generate_visual_charts(hw_df, sw_df, session_id)
    docx_path = generate_docx_report(session_id, hw_df, sw_df, charts)
    pptx_path = generate_pptx_report(session_id, hw_df, sw_df, charts)

    # Save gap analysis sheets
    if hw_df is not None:
        hw_df.to_excel(os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx"), index=False)
    if sw_df is not None:
        sw_df.to_excel(os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx"), index=False)

    # Determine drive folder
    if not folder_id:
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    # Upload to Drive
    links = {}
    for idx, path in enumerate([
        f"HWGapAnalysis_{session_id}.xlsx",
        f"SWGapAnalysis_{session_id}.xlsx",
        os.path.basename(docx_path),
        os.path.basename(pptx_path)
    ], start=1):
        full = os.path.join(session_path, path)
        if os.path.exists(full):
            links[f"file_{idx}_drive_url"] = upload_to_drive(full, path, folder_id)

    # Build payload for downstream
    payload = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
        **links
    }

    # Notify next module if webhook provided
    if next_action_webhook:
        try:
            r = requests.post(next_action_webhook, json=payload)
            print(f"📤 Sent results downstream: {r.status_code}")
        except Exception as e:
            print(f"❌ Downstream notify failed: {e}", flush=True)
    else:
        print("⚠️ No next_action_webhook; skipping downstream call.", flush=True)

    return payload

def process_assessment(data):
    session_id = data.get("session_id")
    email = data.get("email")
    goal = data.get("goal", "project plan")
    files = data.get("files", [])
    next_action_webhook = data.get("next_action_webhook", "")
    folder_id = data.get("folder_id")  # <— Extract folder_id

    print("[DEBUG] Entered process_assessment()", flush=True)
    return generate_assessment(session_id, email, goal, files, next_action_webhook, folder_id)
