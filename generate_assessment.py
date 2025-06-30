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


def build_section_2_overview(hw_df, sw_df):
    return (
        f"The organization’s IT landscape includes {len(hw_df)} hardware assets "
        f"and {len(sw_df)} software assets across multiple environments."
    )


def build_section_3_hardware_breakdown(hw_df, sw_df):
    if "Device Type" in hw_df.columns:
        counts = hw_df["Device Type"].value_counts().to_dict()
        return f"Hardware inventory breakdown by type: {counts}."
    return f"Hardware asset count: {len(hw_df)}."


def build_section_4_software_breakdown(hw_df, sw_df):
    if "Application" in sw_df.columns:
        counts = sw_df["Application"].value_counts().to_dict()
        return f"Software inventory breakdown by application: {counts}."
    return f"Software asset count: {len(sw_df)}."


def build_section_5_tier_distribution(hw_df, sw_df):
    if "Tier" in hw_df.columns:
        dist = hw_df["Tier"].value_counts().to_dict()
        return f"Tier distribution for hardware: {dist}."
    return "Tier distribution data unavailable."


def build_section_6_hardware_lifecycle(hw_df, sw_df):
    if "Lifecycle Status" in hw_df.columns:
        stats = hw_df["Lifecycle Status"].value_counts().to_dict()
        return f"Hardware lifecycle statuses: {stats}."
    return "Lifecycle status data unavailable."


def build_section_7_software_licensing(hw_df, sw_df):
    if "License Status" in sw_df.columns:
        lic = sw_df["License Status"].value_counts().to_dict()
        return f"Software licensing status: {lic}."
    return "Licensing data unavailable."


def build_section_8_security_posture(hw_df, sw_df):
    return "Security posture analysis pending integration."


def build_section_9_performance_metrics(hw_df, sw_df):
    return "Performance metrics analysis pending integration."


def build_section_10_reliability(hw_df, sw_df):
    return "Reliability metrics analysis pending integration."


def build_section_11_scalability(hw_df, sw_df):
    return "Scalability assessment pending integration."


def build_section_12_legacy_debt(hw_df, sw_df):
    return "Legacy systems and technical debt analysis pending integration."


def build_section_13_obsolete_platforms(hw_df, sw_df):
    return "Obsolete platform identification pending integration."


def build_section_14_cloud_migration(hw_df, sw_df):
    return "Cloud migration potential analysis pending integration."


def build_section_15_strategic_alignment(hw_df, sw_df):
    return "Strategic alignment analysis pending integration."


def build_section_17_financial_implications(hw_df, sw_df):
    return "Financial implications analysis pending integration."


def build_section_18_sustainability(hw_df, sw_df):
    return "Environmental impact and sustainability analysis pending integration."


def build_section_20_next_steps(hw_df, sw_df):
    return "Recommended next steps and roadmap pending integration."


def _to_direct_drive_url(url: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def generate_assessment(
    session_id,
    email,
    goal,
    files,
    next_action_webhook="",
    folder_id= "folder_id"
):
    print("[DEBUG] Entered generate_assessment()", flush=True)
    session_path = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    hw_df, sw_df = pd.DataFrame(), pd.DataFrame()
    hw_file_path = sw_file_path = None
    for file in files:
        url, name = file.get("file_url"), file.get("file_name")
        local = os.path.join(session_path, name)
        print(f"[DEBUG] Downloading file {name} from {url}", flush=True)
        if url.startswith("http"):
            resp = requests.get(_to_direct_drive_url(url))
            resp.raise_for_status()
            with open(local, "wb") as f:
                f.write(resp.content)
        else:
            with open(url, "rb") as src, open(local, "wb") as dst:
                dst.write(src.read())
        print(f"[DEBUG] Saved to {local}", flush=True)
        # First asset_inventory -> hardware, second -> software
        if file.get("type") == "asset_inventory":
            if hw_file_path is None:
                hw_file_path = local
            else:
                sw_file_path = local
        # Also accept explicit gap_working for software
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

    # Charts
    chart_paths = generate_visual_charts(hw_df, sw_df, session_id)
    for name, local_path in chart_paths.items():
        try:
            chart_paths[name] = upload_to_drive(
            chart_local,
            os.path.basename(chart_local),
            folder_id
        )
        except Exception as ex:
            print(f"❌ Failed upload chart {name}: {ex}", flush=True)

    # Save & upload GAP sheets
    links = {}
    for idx, df in enumerate((hw_df, sw_df), start=1):
        if not df.empty:
            file_label = ['HW', 'SW'][idx - 1]
            path = upload_to_drive(p, os.path.basename(p), folder_id)
            df.to_excel(path, index=False)
            links[f"file_{idx}_drive_url"] = upload_to_drive(path, os.path.basename(path), session_id)

    # Build narratives
    score_summary = build_score_summary(hw_df, sw_df)
    recommendations = build_recommendations(hw_df, sw_df)
    key_findings = build_key_findings(hw_df, sw_df)

    # Section content
    section_2_overview = build_section_2_overview(hw_df, sw_df)
    section_3_hardware_breakdown = build_section_3_hardware_breakdown(hw_df, sw_df)
    section_4_software_breakdown = build_section_4_software_breakdown(hw_df, sw_df)
    section_5_tier_distribution = build_section_5_tier_distribution(hw_df, sw_df)
    section_6_hardware_lifecycle = build_section_6_hardware_lifecycle(hw_df, sw_df)
    section_7_software_licensing = build_section_7_software_licensing(hw_df, sw_df)
    section_8_security_posture = build_section_8_security_posture(hw_df, sw_df)
    section_9_performance_metrics = build_section_9_performance_metrics(hw_df, sw_df)
    section_10_reliability = build_section_10_reliability(hw_df, sw_df)
    section_11_scalability = build_section_11_scalability(hw_df, sw_df)
    section_12_legacy_debt = build_section_12_legacy_debt(hw_df, sw_df)
    section_13_obsolete_platforms = build_section_13_obsolete_platforms(hw_df, sw_df)
    section_14_cloud_migration = build_section_14_cloud_migration(hw_df, sw_df)
    section_15_strategic_alignment = build_section_15_strategic_alignment(hw_df, sw_df)
    section_17_financial_implications = build_section_17_financial_implications(hw_df, sw_df)
    section_18_sustainability = build_section_18_sustainability(hw_df, sw_df)
    section_20_next_steps = build_section_20_next_steps(hw_df, sw_df)

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
        "content_5": section_5_tier_distribution,
        "content_6": section_6_hardware_lifecycle,
        "content_7": section_7_software_licensing,
        "content_8": section_8_security_posture,
        "content_9": section_9_performance_metrics,
        "content_10": section_10_reliability,
        "content_11": section_11_scalability,
        "content_12": section_12_legacy_debt,
        "content_13": section_13_obsolete_platforms,
        "content_14": section_14_cloud_migration,
        "content_15": section_15_strategic_alignment,
        "content_16": key_findings,
        "content_17": section_17_financial_implications,
        "content_18": section_18_sustainability,
        "content_19": recommendations,
        "content_20": section_20_next_steps,
        "appendix_classification_matrix": classification_matrix_md,
        "appendix_data_sources": data_sources_text,
        "slide_executive_summary": score_summary,
        "slide_it_landscape_overview": section_2_overview,
        "slide_hardware_analysis": section_3_hardware_breakdown,
        "slide_software_analysis": section_4_software_breakdown,
        "slide_tier_classification_summary": section_5_tier_distribution,
        "slide_hardware_lifecycle_chart": section_6_hardware_lifecycle,
        "slide_software_licensing_review": section_7_software_licensing,
        "slide_security_vulnerability_heatmap": section_8_security_posture,
        "slide_performance_&_uptime_trends": section_9_performance_metrics,
        "slide_system_reliability_overview": section_10_reliability,
        "slide_scalability_insights": section_11_scalability,
        "slide_legacy_system_exposure": section_12_legacy_debt,
        "slide_obsolete_platform_matrix": section_13_obsolete_platforms,
        "slide_cloud_migration_targets": section_14_cloud_migration,
        "slide_strategic_it_alignment": section_15_strategic_alignment,
        "slide_business_impact_of_gaps": key_findings,
        "slide_cost_of_obsolescence": section_17_financial_implications,
        "slide_sustainability_&_green_it": section_18_sustainability,
        "slide_remediation_recommendations": recommendations,
        "slide_roadmap_&_next_steps": section_20_next_steps,
    }

    print(f"[DEBUG] Calling Report-Generator at {DOCX_SERVICE_URL}/generate_assessment", flush=True)
    resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
    resp.raise_for_status()
    gen = resp.json()
    print(f"[DEBUG] Report-Generator response: {gen}", flush=True)

    # Download & upload DOCX/PPTX back to Drive
    docx_rel, pptx_rel = gen.get("docx_url"), gen.get("pptx_url")
    docx_url = f"{DOCX_SERVICE_URL.rstrip('/')}{docx_rel}"
    pptx_url = f"{DOCX_SERVICE_URL.rstrip('/')}{pptx_rel}"
    docx_name, pptx_name = os.path.basename(docx_rel), os.path.basename(pptx_rel)
    docx_local = upload_to_drive(local_doc, os.path.basename(local_doc), folder_id)
    pptx_local = upload_to_drive(local_ppt, os.path.basename(local_ppt), folder_id)
    for dl_url, local in [(docx_url, docx_local), (pptx_url, pptx_local)]:
        resp_dl = requests.get(dl_url)
        resp_dl.raise_for_status()
        with open(local, "wb") as f:
            f.write(resp_dl.content)
    links["file_3_drive_url"] = upload_to_drive(local_doc, os.path.basename(local_doc), folder_id)
    links["file_4_drive_url"] = upload_to_drive(local_ppt, os.path.basename(local_ppt), folder_id)
    result = {
        "session_id": session_id,
        "gpt_module": "it_assessment",
        "status": "complete",
        **links
    }

    try:
        r = requests.post(MARKET_GAP_WEBHOOK, json=result)
        print(f"[DEBUG] Market-GAP notify status: {r.status_code}", flush=True)
    except Exception as e:
        print(f"❌ Market-GAP notify failed: {e}", flush=True)

    return result


def process_assessment(data):
    session_id = data.get("session_id")
    email = data.get("email")
    goal = data.get("goal", "project plan")
    files = data.get("files", [])
    next_action_webhook = data.get("next_action_webhook", "")
    folder_id = data.get("folder_id")

    print("[DEBUG] Entered process_assessment()", flush=True)
    return generate_assessment(
        session_id, email, goal, files, next_action_webhook, folder_id
    )
