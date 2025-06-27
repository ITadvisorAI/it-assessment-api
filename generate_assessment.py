import os
import re
import json
import pandas as pd
import requests
import openai
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

# ──────────────────────────────────────────────
# Load your Excel templates (to preserve chart sheets, formulas, tiers)
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
HW_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx")
SW_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx")
CLASSIFICATION_PATH = os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx")

print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF = pd.read_excel(HW_TEMPLATE_PATH)
SW_BASE_DF = pd.read_excel(SW_TEMPLATE_PATH)
CLASSIFICATION_DF = pd.read_excel(CLASSIFICATION_PATH)
print("[DEBUG] Templates loaded successfully", flush=True)
# ──────────────────────────────────────────────

# Service endpoints
DOCX_SERVICE_URL = os.getenv("DOCX_SERVICE_URL", "https://docx-generator-api.onrender.com")
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis.onrender.com/start_market_gap")

def merge_with_template(df_template: pd.DataFrame, df_inv: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure every column in the incoming inventory exists in the template,
    then append the inventory rows onto the template (preserving any
    pre-built formulas or blank rows for charts).
    """
    for c in df_inv.columns:
        if c not in df_template.columns:
            df_template[c] = None
    df_inv = df_inv.reindex(columns=df_template.columns, fill_value=None)
    return pd.concat([df_template, df_inv], ignore_index=True)

def apply_classification(df: pd.DataFrame) -> pd.DataFrame:
    """
    Join the Tier Total Score to its Category via the loaded classification tiers.
    """
    if not df.empty and "Tier Total Score" in df.columns:
        return df.merge(CLASSIFICATION_DF, how="left", left_on="Tier Total Score", right_on="Score")
    return df

# — Section builder functions (unchanged) —
def build_score_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}

def build_section_2_overview(hw_df, sw_df):
    total_devices = len(hw_df)
    total_applications = len(sw_df)
    healthy_devices = int((hw_df.get("Tier Total Score", pd.Series()).astype(int) >= 75).sum())
    compliant_licenses = int((sw_df.get("License Status", pd.Series()) != "Expired").sum())
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
    top5 = sw_df.get("App Name", pd.Series()).value_counts().head(5).to_dict()
    return {
        "total_apps": len(sw_df),
        "by_category": counts,
        "top_5_apps": top5
   }

def build_section_5_classification_distribution(hw_df, sw_df):
    dist = hw_df.get("Category", pd.Series()).value_counts().to_dict()
    return {"classification_distribution": dist}

def build_section_6_lifecycle_status(hw_df, sw_df):
    return {"lifecycle_status": []}

def build_section_7_software_compliance(hw_df, sw_df):
    if "License Status" in sw_df.columns:
        compliant = int((sw_df["License Status"] != "Expired").sum())
        expired = int((sw_df["License Status"] == "Expired").sum())
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

def ai_narrative(section_name: str, summary: dict) -> str:
    # … (unchanged) …
    print(f"[DEBUG] ai_narrative called for section {section_name}", flush=True)
    # … rest of your existing ai_narrative …

def generate_assessment(session_id: str,
                        email: str,
                        goal: str,
                        files: list,
                        next_action_webhook: str,
                        folder_id: str) -> dict:
    print(f"[DEBUG] Starting generate_assessment for session {session_id}", flush=True)
    try:
        # Prepare session folder
        session_path = f"./{session_id}"
        os.makedirs(session_path, exist_ok=True)
        print(f"[DEBUG] Session path created: {session_path}", flush=True)

        # 1) Download & categorize files
        hw_df, sw_df = pd.DataFrame(), pd.DataFrame()
        for f in files:
            name, url = f['file_name'], f['file_url']
            local_path = os.path.join(session_path, name)
            resp = requests.get(url); resp.raise_for_status()
            with open(local_path, 'wb') as fp: fp.write(resp.content)
            df_temp = pd.read_excel(local_path)
            cols = {c.lower() for c in df_temp.columns}
            ft = f.get('type','').lower()
            if ft == 'asset_inventory' and {'device id','device name'} <= cols:
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
            elif ft == 'asset_inventory' and {'app id','app name'} <= cols:
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True)
            elif ft in ('hardware_inventory','asset_hardware'):
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
            else:
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True)

        # 2) Enrich & classify hardware via templates
        if not hw_df.empty:
            hw_df = merge_with_template(HW_BASE_DF.copy(), hw_df)
            hw_df = suggest_hw_replacements(hw_df)
            hw_df = apply_classification(hw_df)

        # 3) Enrich & classify software via templates
        if not sw_df.empty:
            sw_df = merge_with_template(SW_BASE_DF.copy(), sw_df)
            sw_df = suggest_sw_replacements(sw_df)
            sw_df = apply_classification(sw_df)

        # 4) Generate charts and upload them
        print("[DEBUG] Generating visual charts", flush=True)
        chart_paths = generate_visual_charts(hw_df, sw_df, session_path)
        for name, local in list(chart_paths.items()):
            try:
                url = upload_to_drive(local, os.path.basename(local), folder_id)
                chart_paths[name] = url
            except Exception as ex:
                print(f"[ERROR] Failed to upload chart {name}: {ex}", flush=True)

        # 5) Build AI narratives
        section_funcs = [
            build_score_summary, build_section_2_overview, build_section_3_inventory_hardware,
            build_section_4_inventory_software, build_section_5_classification_distribution,
            build_section_6_lifecycle_status, build_section_7_software_compliance,
            build_section_8_security_posture, build_section_9_performance,
            build_section_10_reliability, build_section_11_scalability,
            build_section_12_legacy_technical_debt, build_section_13_obsolete_risk,
            build_section_14_cloud_migration, build_section_15_strategic_alignment,
            build_section_16_business_impact, build_section_17_financial_implications,
            build_section_18_environmental_sustainability, build_recommendations,
            build_section_20_next_steps
        ]
        narratives = {}
        for i, fn in enumerate(section_funcs, start=1):
            narratives[f"content_{i}"] = ai_narrative(fn.__name__, fn(hw_df, sw_df))

        # 6) Write out gap-analysis Excel sheets (with your data + templates)
        hw_xl = os.path.join(session_path, "HWGapAnalysis.xlsx")
        sw_xl = os.path.join(session_path, "SWGapAnalysis.xlsx")
        hw_df.to_excel(hw_xl, index=False)
        sw_df.to_excel(sw_xl, index=False)

        # 7) Upload those Excels
        hw_url = upload_to_drive(hw_xl, os.path.basename(hw_xl), folder_id)
        sw_url = upload_to_drive(sw_xl, os.path.basename(sw_xl), folder_id)

        # 8) Send to DOCX/PPTX generator
        payload = {
            "session_id": session_id,
            "email": email,
            "goal": goal,
            "hw_gap_url": hw_url,
            "sw_gap_url": sw_url,
            **chart_paths,
            **narratives
        }
        print(f"[DEBUG] Posting to DOCX service: {DOCX_SERVICE_URL}/generate_assessment", flush=True)
        resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
        resp.raise_for_status()
        gen = resp.json()

        # 9) Download & upload DOCX/PPTX back to Drive
        links = {}
        for key in ("docx_url", "pptx_url"):
            url = gen.get(key)
            if url:
                fn = os.path.basename(url)
                local = os.path.join(session_path, fn)
                r2 = requests.get(url); r2.raise_for_status()
                with open(local, "wb") as fp: fp.write(r2.content)
                drive_key = "file_3_drive_url" if key=="docx_url" else "file_4_drive_url"
                links[drive_key] = upload_to_drive(local, fn, folder_id)

        # 10) Notify Market-Gap
        result = {
            "session_id": session_id,
            "gpt_module": "it_assessment",
            "status": "complete",
            "files": [
                {"file_name": os.path.basename(hw_xl), "drive_url": hw_url},
                {"file_name": os.path.basename(sw_xl), "drive_url": sw_url}
            ],
            **chart_paths,
            **links
        }
        try:
            post_url = next_action_webhook or MARKET_GAP_WEBHOOK
            print(f"[DEBUG] Notifying market-gap at {post_url}", flush=True)
            r3 = requests.post(post_url, json=result, timeout=60)
            r3.raise_for_status()
        except Exception as e:
            print(f"[ERROR] Market-gap notify failed: {e}", flush=True)

        return result

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": str(e)}

def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id=data.get("session_id",""),
        email=data.get("email",""),
        goal=data.get("goal",""),
        files=data.get("files",[]),
        next_action_webhook=data.get("next_action_webhook",""),
        folder_id=data.get("folder_id","")
    )
