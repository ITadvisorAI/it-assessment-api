import os  
import re
import pandas as pd
import requests
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

from docx import Document
from pptx import Presentation
from pptx.util import Inches

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR    = "temp_sessions"

# ──────────────────────────────────────────────
# Cache templates at import time (only once)
print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF        = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF        = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
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

def _to_direct_drive_url(url: str) -> str:
    """Convert a Drive view URL to direct-download URL."""
    m = re.search(r"/d/([A-Za-z0-9_-]+)", url)
    if m:
        fid = m.group(1)
        return f"https://drive.google.com/uc?export=download&id={fid}"
    return url

def generate_assessment(
    session_id,
    email,
    goal,
    files,
    next_action_webhook="",
    folder_id=None
):
    print("[DEBUG] Entered generate_assessment()", flush=True)
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    # ─── Download & classify input files ───
    hw_file_path = sw_file_path = None
    for file in files:
        url = file["file_url"]
        name = file["file_name"]
        local = os.path.join(session_path, name)
        print(f"[DEBUG] Downloading file {name} from {url}", flush=True)
        if url.startswith("http"):
            resp = requests.get(url); resp.raise_for_status()
            with open(local, "wb") as f:
                f.write(resp.content)
        else:
            with open(url, "rb") as src, open(local, "wb") as dst:
                dst.write(src.read())
        print(f"[DEBUG] Saved to {local}", flush=True)
        if file["type"] == "asset_inventory":
            if hw_file_path is None:
                hw_file_path = local
            else:
                sw_file_path = local

    print(f"[DEBUG] hw_file_path={hw_file_path}, sw_file_path={sw_file_path}", flush=True)

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

    # ─── Generate and upload charts ───
    print("[DEBUG] Generating charts...", flush=True)
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    print(f"[DEBUG] Charts: {chart_paths}", flush=True)

    for name, local_path in list(chart_paths.items()):
        try:
            dl_url = _to_direct_drive_url(local_path)
            print(f"[DEBUG] Uploading chart {local_path} to Drive", flush=True)
            drive_url = upload_to_drive(local_path, os.path.basename(local_path), session_id)
            chart_paths[name] = drive_url
            print(f"[DEBUG] Chart {name} uploaded: {drive_url}", flush=True)
        except Exception as ex:
            print(f"❌ Failed to upload chart {local_path}: {ex}", flush=True)

    # ─── Save & upload gap-analysis sheets ───
    hw_gap = sw_gap = None
    if hw_df is not None:
        hw_gap = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
        hw_df.to_excel(hw_gap, index=False)
        print(f"[DEBUG] Saved HW gap sheet: {hw_gap}", flush=True)
    if sw_df is not None:
        sw_gap = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")
        sw_df.to_excel(sw_gap, index=False)
        print(f"[DEBUG] Saved SW gap sheet: {sw_gap}", flush=True)

    if not folder_id:
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        print(f"[DEBUG] Fallback folder_id: {folder_id}", flush=True)
    else:
        print(f"[DEBUG] Using provided folder_id: {folder_id}", flush=True)

    links = {}
    for idx, path in enumerate([hw_gap, sw_gap], start=1):
        if path and os.path.exists(path):
            print(f"[DEBUG] Uploading {path} → Drive", flush=True)
            url = upload_to_drive(path, os.path.basename(path), session_id)
            links[f"file_{idx}_drive_url"] = url
            print(f"[DEBUG] Uploaded to: {url}", flush=True)

    # ──────────────────────────────────────────────
    # Call external docx-generator
    score_summary   = build_score_summary(hw_df, sw_df)
    recommendations = build_recommendations(hw_df, sw_df)
    key_findings    = build_key_findings(hw_df, sw_df)

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
    # Download & upload DOCX/PPTX back to Drive
    docx_rel = gen["docx_url"]
    pptx_rel = gen["pptx_url"]
    docx_url = f"{DOCX_SERVICE_URL}{docx_rel}"
    pptx_url = f"{DOCX_SERVICE_URL}{pptx_rel}"

    docx_name  = os.path.basename(docx_rel)
    pptx_name  = os.path.basename(pptx_rel)
    docx_local = os.path.join(session_path, docx_name)
    pptx_local = os.path.join(session_path, pptx_name)

    for dl_url, local in [(docx_url, docx_local), (pptx_url, pptx_local)]:
        print(f"[DEBUG] Downloading {dl_url}", flush=True)
        dl = requests.get(dl_url); dl.raise_for_status()
        with open(local, "wb") as f:
            f.write(dl.content)
        print(f"[DEBUG] Saved to {local}", flush=True)

    links["file_3_drive_url"] = upload_to_drive(docx_local, docx_name, session_id)
    links["file_4_drive_url"] = upload_to_drive(pptx_local, pptx_name, session_id)
    print(f"[DEBUG] Uploaded DOCX+PPTX to Drive: {links['file_3_drive_url']}, {links['file_4_drive_url']}", flush=True)
    # ──────────────────────────────────────────────

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
