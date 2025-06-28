import os
import json
import traceback
import pandas as pd
import requests
from openai import OpenAI
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

# ────────────────────────────────────────────────────────────────────────────────
# Configuration & Constants
# ────────────────────────────────────────────────────────────────────────────────
TEMPLATES_DIR      = os.path.join(os.path.dirname(__file__), "templates")
HW_TEMPLATE_PATH   = os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx")
SW_TEMPLATE_PATH   = os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx")
CLASSIFICATION_PATH= os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx")

DOCX_SERVICE_URL   = os.getenv("DOCX_SERVICE_URL",   "https://docx-generator-api.onrender.com")
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis.onrender.com/start_market_gap")

OPENAI_MODEL       = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

# Instantiate new OpenAI client
client = OpenAI()

print("[DEBUG] Loading Excel templates...", flush=True)
HW_TEMPLATE_DF    = pd.read_excel(HW_TEMPLATE_PATH)
SW_TEMPLATE_DF    = pd.read_excel(SW_TEMPLATE_PATH)
CLASSIFICATION_DF = pd.read_excel(CLASSIFICATION_PATH)
print("[DEBUG] Templates loaded:", 
      f"HW={HW_TEMPLATE_DF.shape}", f"SW={SW_TEMPLATE_DF.shape}", f"CL={CLASSIFICATION_DF.shape}", flush=True)


# ────────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ────────────────────────────────────────────────────────────────────────────────
def merge_with_template(template_df: pd.DataFrame, inv_df: pd.DataFrame) -> pd.DataFrame:
    for col in inv_df.columns:
        if col not in template_df.columns:
            template_df[col] = pd.NA
    inv_df = inv_df.reindex(columns=template_df.columns, fill_value=pd.NA)
    merged = pd.concat([template_df, inv_df], ignore_index=True)
    print(f"[DEBUG] merge_with_template: merged shape {merged.shape}", flush=True)
    return merged

def apply_classification(df: pd.DataFrame) -> pd.DataFrame:
    if "Tier Total Score" in df.columns:
        merged = df.merge(CLASSIFICATION_DF, how="left",
                          left_on="Tier Total Score", right_on="Score")
        print(f"[DEBUG] apply_classification: result shape {merged.shape}", flush=True)
        return merged
    return df

def detect_inventory_type(df: pd.DataFrame, filename: str) -> str:
    cols = [c.lower() for c in df.columns]
    name = filename.lower()
    if any("device" in c for c in cols) or "server" in name:
        return "hw"
    if any("app" in c for c in cols) or "software" in name:
        return "sw"
    return ""

def ai_narrative(section_name: str, data_summary: dict) -> str:
    """
    Generate a narrative via the new OpenAI v1 API.
    """
    prompt = (
        f"You are an IT infrastructure analyst. "
        f"Write a concise narrative for the section '{section_name}' "
        f"based on this data:\n{json.dumps(data_summary, indent=2)}"
    )
    print(f"[DEBUG] ai_narrative → prompting for {section_name}", flush=True)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=OPENAI_TEMPERATURE,
        messages=[
            {"role": "system", "content": "You draft professional IT infrastructure analysis narratives."},
            {"role": "user",   "content": prompt}
        ]
    )
    text = resp.choices[0].message.content.strip()
    print(f"[DEBUG] ai_narrative → received {len(text.split())} words", flush=True)
    return text


# ────────────────────────────────────────────────────────────────────────────────
# Section Builders
# ────────────────────────────────────────────────────────────────────────────────
def build_score_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}

def build_section_2_overview(hw_df, sw_df):
    healthy = int((hw_df.get("Tier Total Score", 0) >= 75).sum())
    if "License Status" in sw_df.columns:
        expired   = int((sw_df["License Status"] == "Expired").sum())
        compliant = int(len(sw_df) - expired)
    else:
        expired, compliant = 0, 0
    return {
        "total_devices": len(hw_df),
        "total_applications": len(sw_df),
        "healthy_devices":     healthy,
        "compliant_licenses":  compliant  
    }

def build_section_3_inventory_hardware(hw_df, sw_df):
    return {"hardware_items": hw_df.to_dict(orient="records")}

def build_section_4_inventory_software(hw_df, sw_df):
    by_cat = sw_df.get("Category", pd.Series()).value_counts().to_dict()
    top5  = sw_df.get("App Name", pd.Series()).value_counts().head(5).to_dict()
    return {"by_category": by_cat, "top_5_apps": top5}

def build_section_5_classification_distribution(hw_df, sw_df):
    dist = hw_df.get("Category", pd.Series()).value_counts().to_dict()
    return {"classification_distribution": dist}

def build_section_6_lifecycle_status(hw_df, sw_df):
    return {"lifecycle_status": []}

def build_section_7_software_compliance(hw_df, sw_df):
    if "License Status" in sw_df.columns:
        expired = int((sw_df["License Status"] == "Expired").sum())
        valid   = int(len(sw_df) - expired)
    else:
        expired, valid = 0, 0
    return {"valid_licenses": valid, "expired_licenses": expired}

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
    if not hw_df.empty:
        low = hw_df[hw_df["Tier Total Score"] < 30]
        risks.append({"hardware": low.to_dict(orient="records")})
    if not sw_df.empty:
        low = sw_df[sw_df["Tier Total Score"] < 30]
        risks.append({"software": low.to_dict(orient="records")})
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
    hw_recs = suggest_hw_replacements(hw_df).head(5).to_dict(orient="records") if not hw_df.empty else []
    sw_recs = suggest_sw_replacements(sw_df).head(5).to_dict(orient="records") if not sw_df.empty else []
    return {"hardware_replacements": hw_recs, "software_replacements": sw_recs}

def build_section_20_next_steps(hw_df, sw_df):
    return build_recommendations(hw_df, sw_df)


# ────────────────────────────────────────────────────────────────────────────────
# Core Assessment Generator
# ────────────────────────────────────────────────────────────────────────────────
def generate_assessment(session_id: str,
                        email: str,
                        goal: str,
                        files: list,
                        next_action_webhook: str,
                        folder_id: str) -> dict:
    print(f"[DEBUG] → Starting assessment for session '{session_id}'", flush=True)
    try:
        # Workspace
        workspace = os.path.join(os.getcwd(), session_id)
        os.makedirs(workspace, exist_ok=True)
        print(f"[DEBUG] Workspace created at {workspace}", flush=True)

        # 1) Download & ingest
        hw_df = pd.DataFrame()
        sw_df = pd.DataFrame()
        for f in files:
            name = f.get("file_name","unknown.xlsx")
            url  = f.get("file_url","")
            local = os.path.join(workspace, name)
            r = requests.get(url); r.raise_for_status()
            with open(local, "wb") as fp: fp.write(r.content)
            temp_df = pd.read_excel(local)
            temp_df.columns = [c.strip() for c in temp_df.columns]
            inv_type = detect_inventory_type(temp_df, name)
            print(f"[DEBUG] File '{name}' detected as '{inv_type}'", flush=True)
            if inv_type == "hw":
                hw_df = pd.concat([hw_df, temp_df], ignore_index=True)
            elif inv_type == "sw":
                sw_df = pd.concat([sw_df, temp_df], ignore_index=True)
            else:
                print(f"[WARN] Skipping unknown inventory '{name}'", flush=True)

        print(f"[DEBUG] After ingestion: hw_df={hw_df.shape}, sw_df={sw_df.shape}", flush=True)

        # 2) Merge & classify
        hw_df = merge_with_template(HW_TEMPLATE_DF.copy(), hw_df)
        sw_df = merge_with_template(SW_TEMPLATE_DF.copy(), sw_df)
        hw_df = suggest_hw_replacements(hw_df)
        sw_df = suggest_sw_replacements(sw_df)
        hw_df = apply_classification(hw_df)
        sw_df = apply_classification(sw_df)

        # 3) Charts
        print("[DEBUG] Generating charts...", flush=True)
        charts = generate_visual_charts(hw_df, sw_df, workspace)
        for key, path in list(charts.items()):
            try:
                url = upload_to_drive(path, os.path.basename(path), folder_id)
                charts[key] = url
                print(f"[DEBUG] Uploaded chart '{key}' → {url}", flush=True)
            except Exception as ex:
                print(f"[ERROR] Chart upload failed for {key}: {ex}", flush=True)

        # 4) Narratives
        section_fns = [
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
        for idx, fn in enumerate(section_fns, start=1):
            name = fn.__name__
            summary = fn(hw_df, sw_df)
            narratives[f"content_{idx}"] = ai_narrative(name, summary)

        # 5) Write Excel
        hw_path = os.path.join(workspace, "HWGapAnalysis.xlsx")
        sw_path = os.path.join(workspace, "SWGapAnalysis.xlsx")
        hw_df.to_excel(hw_path, index=False)
        sw_df.to_excel(sw_path, index=False)
        hw_url = upload_to_drive(hw_path, os.path.basename(hw_path), folder_id)
        sw_url = upload_to_drive(sw_path, os.path.basename(sw_path), folder_id)
        print(f"[DEBUG] Excels uploaded: HW→{hw_url}, SW→{sw_url}", flush=True)

        # 6) Docx generator
        payload = {
            "session_id": session_id,
            "email": email,
            "goal": goal,
            "hw_gap_url": hw_url,
            "sw_gap_url": sw_url,
            **charts,
            **narratives
        }
        endpoint = f"{DOCX_SERVICE_URL.rstrip('/')}/generate_assessment"
        print(f"[DEBUG] Posting to Docx service @ {endpoint}", flush=True)
        resp = requests.post(endpoint, json=payload, timeout=300); resp.raise_for_status()
        docx_resp = resp.json()

        # 7) Download & re-upload docs
        results = {
            "session_id": session_id,
            "gpt_module": "it_assessment",
            "status": "complete",
            "files": [
                {"file_name": os.path.basename(hw_path), "drive_url": hw_url},
                {"file_name": os.path.basename(sw_path), "drive_url": sw_url}
            ],
            **charts
        }
        for field in ("docx_url", "pptx_url"):
            if docx_resp.get(field):
                dl = requests.get(docx_resp[field]); dl.raise_for_status()
                fname = os.path.basename(docx_resp[field])
                local = os.path.join(workspace, fname)
                with open(local, "wb") as fp: fp.write(dl.content)
                key = "file_3_drive_url" if field=="docx_url" else "file_4_drive_url"
                results[key] = upload_to_drive(local, fname, folder_id)
                print(f"[DEBUG] Uploaded {field} → {results[key]}", flush=True)

        # 8) Notify next
        notify_url = next_action_webhook or MARKET_GAP_WEBHOOK
        print(f"[DEBUG] Notifying next at {notify_url}", flush=True)
        nt = requests.post(notify_url, json=results, timeout=60); nt.raise_for_status()

        return results

    except Exception as e:
        print("[ERROR] generate_assessment exception:", str(e), flush=True)
        traceback.print_exc()
        return {"error": str(e)}

def process_assessment(payload: dict) -> dict:
    return generate_assessment(
        session_id=payload.get("session_id",""),
        email=payload.get("email",""),
        goal=payload.get("goal",""),
        files=payload.get("files", []),
        next_action_webhook=payload.get("next_action_webhook",""),
        folder_id=payload.get("folder_id","")
    )
