import os
import json
import pandas as pd
import requests
import openai
import traceback
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

# ─────────────────────────────────────────────────────────────────
# Load your Excel _templates_ for gap analysis:
TEMPLATES_DIR      = os.path.join(os.path.dirname(__file__), "templates")
HW_BASE_DF         = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF         = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF  = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
# ─────────────────────────────────────────────────────────────────

# Service endpoints
DOCX_SERVICE_URL    = os.getenv("DOCX_SERVICE_URL", "https://docx-generator-api.onrender.com")
MARKET_GAP_WEBHOOK  = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis.onrender.com/start_market_gap")


# ────────────── Section builder functions ────────────────────────
def build_score_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}

def build_section_2_overview(hw_df, sw_df):
    total_devices       = len(hw_df)
    total_applications  = len(sw_df)
    healthy_devices     = int((hw_df.get("Tier Total Score", pd.Series()).astype(int) >= 75).sum())
    compliant_licenses  = int((sw_df.get("License Status", pd.Series()) != "Expired").sum())
    return {
        "total_devices": total_devices,
        "total_applications": total_applications,
        "healthy_devices": healthy_devices,
        "compliant_licenses": compliant_licenses
    }

def build_section_3_inventory_hardware(hw_df, sw_df):
    return {"hardware_items": hw_df.to_dict(orient="records")}

def build_section_4_inventory_software(hw_df, sw_df):
    counts = sw_df.get("Category", pd.Series()).value_counts().to_dict()
    top5   = sw_df.get("App Name", pd.Series()).value_counts().head(5).to_dict()
    return {"total_apps": len(sw_df), "by_category": counts, "top_5_apps": top5}

def build_section_5_classification_distribution(hw_df, sw_df):
    dist = hw_df.get("Category", pd.Series()).value_counts().to_dict()
    return {"classification_distribution": dist}

def build_section_6_lifecycle_status(hw_df, sw_df):
    return {"lifecycle_status": []}

def build_section_7_software_compliance(hw_df, sw_df):
    if "License Status" in sw_df.columns:
        compliant = int((sw_df["License Status"] != "Expired").sum())
        expired   = int((sw_df["License Status"] == "Expired").sum())
    else:
        compliant, expired = 0, 0
    return {"compliant_count": compliant, "expired_count": expired}

def build_section_8_security_posture(hw_df, sw_df):
    return {"vulnerabilities": []}

def build_section_9_performance(hw_df, sw_df):
    return {"performance_metrics": []}

def build_section_10_reliability(hw_df, sw_df):
    return {"reliability_metrics": []}

def build_section_11_scalability(hw_df, sw_df):
    return {"scalability_opportunities": []}

def build_section_12_legacy_technical_debt(hw_df, sw_df):
    return {"legacy_issues": []}

def build_section_13_obsolete_risk(hw_df, sw_df):
    risks = []
    if "Tier Total Score" in hw_df.columns:
        high_risk_hw = hw_df[hw_df["Tier Total Score"] < 30]
        risks.append({"hardware": high_risk_hw.to_dict(orient="records")})
    if "Tier Total Score" in sw_df.columns:
        high_risk_sw = sw_df[sw_df["Tier Total Score"] < 30]
        risks.append({"software": high_risk_sw.to_dict(orient="records")})
    return {"risks": risks}

def build_section_14_cloud_migration(hw_df, sw_df):
    return {"cloud_migration": []}

def build_section_15_strategic_alignment(hw_df, sw_df):
    return {"alignment": []}

def build_section_16_business_impact(hw_df, sw_df):
    return {"business_impact": []}

def build_section_17_financial_implications(hw_df, sw_df):
    return {"financial_implications": []}

def build_section_18_environmental_sustainability(hw_df, sw_df):
    return {"environmental_sustainability": []}

def build_recommendations(hw_df, sw_df):
    hw_recs = suggest_hw_replacements(hw_df).head(3).to_dict(orient="records") if not hw_df.empty else []
    sw_recs = suggest_sw_replacements(sw_df).head(3).to_dict(orient="records") if not sw_df.empty else []
    return {"hardware_replacements": hw_recs, "software_replacements": sw_recs}

def build_section_20_next_steps(hw_df, sw_df):
    return build_recommendations(hw_df, sw_df)
# ─────────────────────────────────────────────────────────────────


def ai_narrative(section_name: str, summary: dict) -> str:
    print(f"[DEBUG] ai_narrative called for section {section_name}", flush=True)
    # … identical body to your current version …
    # it sends summary to OpenAI and returns the narrative string.
    ...


# ────────────── Template‐merge utilities ────────────────────────
def merge_with_template(df_template: pd.DataFrame, df_inv: pd.DataFrame) -> pd.DataFrame:
    # Ensure inventory df has exactly the same columns as the template
    for c in df_inv.columns:
        if c not in df_template.columns:
            df_template[c] = None
    df_inv = df_inv.reindex(columns=df_template.columns, fill_value=None)
    return pd.concat([df_template, df_inv], ignore_index=True)

def apply_classification(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and "Tier Total Score" in df.columns:
        return df.merge(CLASSIFICATION_DF, how="left",
                        left_on="Tier Total Score", right_on="Score")
    return df
# ─────────────────────────────────────────────────────────────────


def generate_assessment(session_id: str,
                        email: str,
                        goal: str,
                        files: list,
                        next_action_webhook: str,
                        folder_id: str) -> dict:
    print(f"[DEBUG] Starting generate_assessment for session {session_id}", flush=True)
    try:
        # Initialize and session folder
        hw_df, sw_df = pd.DataFrame(), pd.DataFrame()
        session_path = f"./{session_id}"
        os.makedirs(session_path, exist_ok=True)
        print(f"[DEBUG] Session path: {session_path}", flush=True)

        # ─ 1) Download & categorize all uploads ─────────
        for f in files:
            name, url = f["file_name"], f["file_url"]
            local_inv = os.path.join(session_path, name)
            r = requests.get(url); r.raise_for_status()
            open(local_inv, "wb").write(r.content)
            df_temp = pd.read_excel(local_inv)
            cols = {c.lower() for c in df_temp.columns}
            ft   = f.get("type", "").lower()
            if ft == "asset_inventory" and {"device id","device name"} <= cols:
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
            elif ft == "asset_inventory" and {"app id","app name"} <= cols:
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True)
            elif ft in ("hardware_inventory","asset_hardware"):
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
            else:
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True)

        # ─ 2) Enrich & classify hardware via template merge ───
        if not hw_df.empty:
            hw_df = merge_with_template(HW_BASE_DF.copy(), hw_df)
            hw_df = suggest_hw_replacements(hw_df)
            hw_df = apply_classification(hw_df)

        # ─ 3) Enrich & classify software via template merge ───
        if not sw_df.empty:
            sw_df = merge_with_template(SW_BASE_DF.copy(), sw_df)
            sw_df = suggest_sw_replacements(sw_df)
            sw_df = apply_classification(sw_df)

        # ─ 4) Generate & upload charts ────────────────────
        print(f"[DEBUG] Generating visual charts", flush=True)
        charts = generate_visual_charts(hw_df, sw_df, session_path)
        print(f"[DEBUG] Charts: {charts}", flush=True)

        # ─ 5) Build each narrative section by name ────────
        section_1_summary            = build_score_summary(hw_df, sw_df)
        section_2_overview           = build_section_2_overview(hw_df, sw_df)
        section_3_inventory_hw       = build_section_3_inventory_hardware(hw_df, sw_df)
        section_4_inventory_sw       = build_section_4_inventory_software(hw_df, sw_df)
        section_5_class_dist         = build_section_5_classification_distribution(hw_df, sw_df)
        section_6_lifecycle          = build_section_6_lifecycle_status(hw_df, sw_df)
        section_7_software_compliance= build_section_7_software_compliance(hw_df, sw_df)
        section_8_security           = build_section_8_security_posture(hw_df, sw_df)
        section_9_performance        = build_section_9_performance(hw_df, sw_df)
        section_10_reliability       = build_section_10_reliability(hw_df, sw_df)
        section_11_scalability       = build_section_11_scalability(hw_df, sw_df)
        section_12_legacy_debt       = build_section_12_legacy_technical_debt(hw_df, sw_df)
        section_13_obsolete_risk     = build_section_13_obsolete_risk(hw_df, sw_df)
        section_14_cloud_migration   = build_section_14_cloud_migration(hw_df, sw_df)
        section_15_alignment         = build_section_15_strategic_alignment(hw_df, sw_df)
        section_16_impact            = build_section_16_business_impact(hw_df, sw_df)
        section_17_financial         = build_section_17_financial_implications(hw_df, sw_df)
        section_18_sustainability    = build_section_18_environmental_sustainability(hw_df, sw_df)
        section_19_recs              = build_recommendations(hw_df, sw_df)
        section_20_next_steps        = build_section_20_next_steps(hw_df, sw_df)

        # Now call AI for each section
        narrative_1  = ai_narrative("Section 1 Summary", section_1_summary)
        narrative_2  = ai_narrative("Section 2 Overview", section_2_overview)
        narrative_3  = ai_narrative("Section 3 Hardware Inventory", section_3_inventory_hw)
        narrative_4  = ai_narrative("Section 4 Software Inventory", section_4_inventory_sw)
        narrative_5  = ai_narrative("Section 5 Classification Distribution", section_5_class_dist)
        narrative_6  = ai_narrative("Section 6 Lifecycle Status", section_6_lifecycle)
        narrative_7  = ai_narrative("Section 7 Software Compliance", section_7_software_compliance)
        narrative_8  = ai_narrative("Section 8 Security Posture", section_8_security)
        narrative_9  = ai_narrative("Section 9 Performance Metrics", section_9_performance)
        narrative_10 = ai_narrative("Section 10 Reliability", section_10_reliability)
        narrative_11 = ai_narrative("Section 11 Scalability", section_11_scalability)
        narrative_12 = ai_narrative("Section 12 Legacy Technical Debt", section_12_legacy_debt)
        narrative_13 = ai_narrative("Section 13 Obsolete Risk", section_13_obsolete_risk)
        narrative_14 = ai_narrative("Section 14 Cloud Migration", section_14_cloud_migration)
        narrative_15 = ai_narrative("Section 15 Strategic Alignment", section_15_alignment)
        narrative_16 = ai_narrative("Section 16 Business Impact", section_16_impact)
        narrative_17 = ai_narrative("Section 17 Financial Implications", section_17_financial)
        narrative_18 = ai_narrative("Section 18 Environmental Sustainability", section_18_sustainability)
        narrative_19 = ai_narrative("Section 19 Recommendations", section_19_recs)
        narrative_20 = ai_narrative("Section 20 Next Steps", section_20_next_steps)

        # ─ 6) Write the gap‐analysis Excel workbooks ─────────
        hw_xl = os.path.join(session_path, "HWGapAnalysis_Output.xlsx")
        sw_xl = os.path.join(session_path, "SWGapAnalysis_Output.xlsx")
        hw_df.to_excel(hw_xl, index=False)
        sw_df.to_excel(sw_xl, index=False)

        # ─ 7) Upload those workbooks ────────────────────────
        hw_url = upload_to_drive(hw_xl, os.path.basename(hw_xl), folder_id)
        sw_url = upload_to_drive(sw_xl, os.path.basename(sw_xl), folder_id)

        files_for_gap = [
            {"file_name": os.path.basename(hw_xl), "drive_url": hw_url},
            {"file_name": os.path.basename(sw_xl), "drive_url": sw_url}
        ]

        # ─ 8) Build payload for your DOCX/PPTX generator ────
        doc_generator_payload = {
            print(f"[DEBUG] Calling Report-Generator at {DOCX_SERVICE_URL}/generate_assessment", flush=True)
        payload = {
            "session_id": session_id,
            "email":      email,
            "goal":       goal,

            # your two gap-analysis Excel URLs:
            "hw_gap_url": links.get("file_1_drive_url"),
            "sw_gap_url": links.get("file_2_drive_url"),

            # local chart paths for the generator to embed:
            "chart_paths": charts,

            # the 20 narrative sections, exactly as your template expects:
            "content_1":  score_summary,
            "content_2":  section_2_overview,
            "content_3":  section_3_inventory_hardware,
            "content_4":  section_4_inventory_software,
            "content_5":  section_5_classification_distribution,
            "content_6":  section_6_lifecycle_status,
            "content_7":  section_7_software_compliance,
            "content_8":  section_8_security_posture,
            "content_9":  section_9_performance,
            "content_10": section_10_reliability,
            "content_11": section_11_scalability,
            "content_12": section_12_legacy_technical_debt,
            "content_13": section_13_obsolete_risk,
            "content_14": section_14_cloud_migration,
            "content_15": section_15_strategic_alignment,
            "content_16": section_16_business_impact,
            "content_17": section_17_financial_implications,
            "content_18": section_18_environmental_sustainability,
            "content_19": recommendations,
            "content_20": section_20_next_steps,

            # any appendices your template uses:
            "appendix_classification_matrix": classification_matrix_md,
            "appendix_data_sources":          data_sources_text,

            # explicit slide‐by‐slide duplication (if your PPTX template
            # uses slide placeholders instead of content_#):
            "slide_executive_summary":       score_summary,
            "slide_it_landscape_overview":   section_2_overview,
            "slide_hardware_analysis":       section_3_inventory_hardware,
            "slide_software_analysis":       section_4_inventory_software,
            "slide_tier_classification_summary": section_5_classification_distribution,
            "slide_hardware_lifecycle_chart":    section_6_lifecycle_status,
            # …and so on for each slide placeholder…
        }
        resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
        resp.raise_for_status()
        gen = resp.json()
        print(f"[DEBUG] Report-Generator response: {gen}", flush=True)

        # extract the relative URLs and turn into full links
        docx_rel = gen.get("docx_url")
        pptx_rel = gen.get("pptx_url")
        docx_url = f"{DOCX_SERVICE_URL.rstrip('/')}{docx_rel}"
        pptx_url = f"{DOCX_SERVICE_URL.rstrip('/')}{pptx_rel}"

        # 9) Call the DOCX/PPTX generator service
        resp = requests.post(
            f"{DOCX_SERVICE_URL}/generate_assessment",
            json=doc_generator_payload
        )
        resp.raise_for_status()
        gen = resp.json()
        docx_url = gen.get("docx_url")
        pptx_url = gen.get("pptx_url")

        # ─ 10) Upload DOCX & PPTX ─────────────────────────
        file_links = {}
        if docx_url:
            ld = os.path.join(session_path, os.path.basename(docx_url))
            r  = requests.get(docx_url); r.raise_for_status()
            open(ld, "wb").write(r.content)
            file_links["file_9_drive_url"] = upload_to_drive(ld, os.path.basename(ld), folder_id)
        if pptx_url:
            lp = os.path.join(session_path, os.path.basename(pptx_url))
            r  = requests.get(pptx_url); r.raise_for_status()
            open(lp, "wb").write(r.content)
            file_links["file_10_drive_url"] = upload_to_drive(lp, os.path.basename(lp), folder_id)

        # ─ 11) Notify Market‐Gap analysis ───────────────────
        market_payload = {
            "session_id": session_id,
            "folder_id":  folder_id,
            "gpt_module": "it_assessment",
            "status":     "complete",
            "files":      files_for_gap,
            "charts":     charts,
            **file_links
        }
        requests.post(next_action_webhook or MARKET_GAP_WEBHOOK, json=market_payload, timeout=60)
        print("[DEBUG] Notified market-gap", flush=True)
        return market_payload

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id           = data.get("session_id", ""),
        email                = data.get("email", ""),
        goal                 = data.get("goal", ""),
        files                = data.get("files", []),
        next_action_webhook  = data.get("next_action_webhook", ""),
        folder_id            = data.get("folder_id", "")
    )
