import os
import json
import pandas as pd
import requests
import openai
import shutil
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_visual_charts
from drive_utils import upload_to_drive

# Backwards compatibility for tests expecting `upload_file_to_drive`
upload_file_to_drive = upload_to_drive
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR = "temp_sessions"

# Load classification matrix (cached at import time)
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))

# Category names from the classification matrix
CATEGORY_COLUMNS = ['Scalability', 'Security', 'Reliability', 'Performance', 'Cost-Effectiveness']

def compute_tier_score(row):
    # 1) Scalability: based on RAM and storage
    ram = row.get("RAM (GB)", 0)
    storage = row.get("Storage Capacity (Raw & Usable)", 0)
    # assume max observed values are RAM=512 GB, Storage=100 TB → normalize to 0–100
    scalability_score = min(5, (ram / 512 * 100) + (storage / (100 * 1024) * 100))

    # 2) Security: based on presence of compliance tags
    tags = str(row.get("Compliance Tags", ""))
    security_score = 5 if any(t.strip() in tags for t in ("PCI", "HIPAA", "SOC2")) else 3

    # 3) Reliability: based on Warranty Expiry
    reliab = 0
    if pd.notna(row.get("Warranty Expiry Date")):
        expiry = pd.to_datetime(row["Warranty Expiry Date"])
        reliab = 5 if expiry >= pd.Timestamp.today() else 3

    # 4) Performance: based on CPU specs (e.g. Xeon)
    cpu = str(row.get("Processor / CPU Specs", "")).lower()
    performance_score = 5 if "xeon" in cpu else 4

    # 5) Cost-Effectiveness: based on age or EOL proximity
    cost = 0
    if pd.notna(row.get("End of Life (EOL)")):
        eol = pd.to_datetime(row["End of Life (EOL)"])
        days_past = (pd.Timestamp.today() - eol).days
        cost = max(0, 5 - days_past / 365 * 20)  # lose 20 points per year past EOL
    else:
        cost = 5

    # average and snap to nearest tier
    avg = (scalability_score + security_score + reliab + performance_score + cost) / 5
    diffs = (CLASSIFICATION_DF["Score"] - avg).abs()
    best = diffs.idxmin()
    return int(CLASSIFICATION_DF.at[best, "Score"])

# ──────────────────────────────────────────────
# Cache templates at import time (only once)
print("[DEBUG] Loading template spreadsheets into memory...", flush=True)
HW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "HWGapAnalysis.xlsx"))
SW_BASE_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "SWGapAnalysis.xlsx"))
CLASSIFICATION_DF = pd.read_excel(os.path.join(TEMPLATES_DIR, "ClassificationTier.xlsx"))
print("[DEBUG] Templates cached successfully", flush=True)
# ──────────────────────────────────────────────

# Service endpoints
DOCX_SERVICE_URL = os.getenv("DOCX_SERVICE_URL", "https://docx-generator-api.onrender.com")
MARKET_GAP_WEBHOOK = os.getenv("MARKET_GAP_WEBHOOK", "https://market-gap-analysis.onrender.com/start_market_gap")

# Section builder functions

def build_score_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}

def build_section_2_overview(hw_df, sw_df):
    total_devices = len(hw_df)
    total_applications = len(sw_df)
    scores = pd.to_numeric(hw_df.get("Tier Total Score", pd.Series()), errors="coerce")
    healthy_devices = int((scores >= 75).sum())
    compliant_licenses = int((sw_df.get("License Status", pd.Series()) != "Expired").sum())
    return {
        "total_devices": total_devices,
        "total_applications": total_applications,
        "healthy_devices": healthy_devices,
        "compliant_licenses": compliant_licenses
    }

def build_section_3_inventory_hardware(hw_df, sw_df):
    counts = hw_df.get("Category", pd.Series()).value_counts().to_dict()
    top5 = hw_df.get("Device Name", pd.Series()).value_counts().head(5).to_dict()
    return {
        "total_devices": len(hw_df),
        "by_category": counts,
        "top_5_devices": top5
    }
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
    # only take the first 100 high-risk rows for each
    risks = {}
    if "Tier Total Score" in hw_df.columns:
        high_risk_hw = hw_df[hw_df["Tier Total Score"] < 30].head(100)
        risks["hardware_risks"] = high_risk_hw.to_dict(orient="records")
    if "Tier Total Score" in sw_df.columns:
        high_risk_sw = sw_df[sw_df["Tier Total Score"] < 30].head(100)
        risks["software_risks"] = high_risk_sw.to_dict(orient="records")
    return risks

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
    print(f"[DEBUG] ai_narrative called for section {section_name} with summary keys: {list(summary.keys())}", flush=True)
    
    # chunk large lists to avoid rate limits
    list_items = [(k, v) for k, v in summary.items() if isinstance(v, list)]
    if list_items:
        largest_key, largest_list = max(list_items, key=lambda x: len(x[1]))
        total = len(largest_list)
        chunk_size = 20
        narratives = []
        for i in range(0, total, chunk_size):
            sublist = largest_list[i:i+chunk_size]
            chunked_summary = dict(summary)
            chunked_summary[largest_key] = sublist
            label = f" (chunk {i//chunk_size+1})" if total > chunk_size else ""
            user_content = f"Section: {section_name}{label}\nData: {json.dumps(chunked_summary)}"
            messages = [
                {"role": "system", "content": (
                    "You are a senior IT transformation advisor. "
                    "Write a concise narrative for the section from the data summary."
                )},
                {"role": "user", "content": user_content}
            ]
            try:
                resp = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3
                )
            except (openai.RateLimitError, openai.NotFoundError):
                resp = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.3
                )
            narratives.append(resp.choices[0].message.content.strip())
        return "\n\n".join(narratives)

    # small summary
    user_content = f"Section: {section_name}\nData: {json.dumps(summary)}"
    messages = [
        {"role": "system", "content": (
            "You are a senior IT transformation advisor. "
            "Write a concise narrative for the section from the data summary."
        )},
        {"role": "user", "content": user_content}
    ]
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3
        )
    except (openai.RateLimitError, openai.NotFoundError):
        resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.3
        )
    return resp.choices[0].message.content.strip()

def generate_assessment(session_id: str, email: str, goal: str, files: list, next_action_webhook: str, folder_id: str = "") -> dict:
    print(f"[DEBUG] Starting generate_assessment for session {session_id}", flush=True)
    try:
        hw_df, sw_df = pd.DataFrame(), pd.DataFrame()
        session_path = os.path.join(OUTPUT_DIR, session_id)
        os.makedirs(session_path, exist_ok=True)
        print(f"[DEBUG] Session path created: {session_path}", flush=True)

        uploaded_charts = {}

        # Download files
        for f in files:
            name, url = f['file_name'], f['file_url']
            print(f"[DEBUG] Downloading {name} from {url}", flush=True)
            local = os.path.join(session_path, name)
            if url.startswith("http"):
                r = requests.get(url)
                r.raise_for_status()
                open(local, "wb").write(r.content)
            else:
                with open(url, "rb") as src, open(local, "wb") as dst:
                    dst.write(src.read())
            print(f"[DEBUG] Downloaded and wrote {name}", flush=True)
            df_temp = pd.read_excel(local)
            print(f"[DEBUG] Read {name} into DataFrame with shape {df_temp.shape}", flush=True)
            lower = {c.lower() for c in df_temp.columns}
            file_type = f.get('type', '').lower()
            name_lower = name.lower()

            # — Override based on filename keywords —
            if any(k in name_lower for k in ("server", "device", "asset")):
                file_type = "hardware"
            elif any(k in name_lower for k in ("application", "app", "software")):
                file_type = "software"

            # — Classify into hardware or software —
            if (
                file_type in ("hardware", "asset_inventory") and (
                    {"device id", "device name"}.issubset(lower)
                    or {"server id", "server name"}.issubset(lower)
                )
            ) or file_type == "hardware":
                hw_df = pd.concat([hw_df, df_temp], ignore_index=True)
                print(f"[DEBUG] Appended to hw_df (hardware), new shape {hw_df.shape}", flush=True)
            elif (
                file_type in ("software", "asset_inventory") and (
                    {"app id", "app name"}.issubset(lower)
                    or {"application id", "application name"}.issubset(lower)
                )
            ) or file_type == "software":
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True)
                print(f"[DEBUG] Appended to sw_df (software), new shape {sw_df.shape}", flush=True)
            else:
                # Final fallback to software
                sw_df = pd.concat([sw_df, df_temp], ignore_index=True)
                print(f"[DEBUG] Fallback appended to sw_df, new shape {sw_df.shape}", flush=True)
                
        # Enrich & classify
        if not hw_df.empty:
            print(f"[DEBUG] Running hardware replacements on hw_df", flush=True)
        # 1) enrich with market data
            hw_df = suggest_hw_replacements(pd.concat([HW_BASE_DF, hw_df], ignore_index=True))
            print(f"[DEBUG] Hardware after replacements shape {hw_df.shape}", flush=True)

        # 2) compute true Tier Total Score for inventory rows
            hw_df["Tier Total Score"] = hw_df.apply(compute_tier_score, axis=1)

        # 3) default any new (market-only) rows to 5
            hw_df["Tier Total Score"] = hw_df["Tier Total Score"].fillna(5)
            print(f"[DEBUG] Final Tier Total Score values: {hw_df['Tier Total Score'].unique()}", flush=True)

        # 4) merge in classification details
        hw_df = hw_df.merge(
            CLASSIFICATION_DF,
            how="left",
            left_on="Tier Total Score",
            right_on="Score"
        )
        print(f"[DEBUG] Merged hw_df with CLASSIFICATION_DF, new cols: {hw_df.columns.tolist()}", flush=True)
    
        if not sw_df.empty:
            print(f"[DEBUG] Running software replacements on sw_df", flush=True)
        # 1) enrich with market data
            sw_df = suggest_sw_replacements(pd.concat([SW_BASE_DF, sw_df], ignore_index=True))
            print(f"[DEBUG] Software after replacements shape {sw_df.shape}", flush=True)

        # 2) compute true Tier Total Score for inventory rows
            sw_df["Tier Total Score"] = sw_df.apply(compute_tier_score, axis=1)

        # 3) default any new (market-only) rows to 5
            sw_df["Tier Total Score"] = sw_df["Tier Total Score"].fillna(5)
            print(f"[DEBUG] Final Tier Total Score values: {sw_df['Tier Total Score'].unique()}", flush=True)

        # 4) merge in classification details
            sw_df = sw_df.merge(
                CLASSIFICATION_DF,
                how="left",
                left_on="Tier Total Score",
                right_on="Score"
            )
            print(f"[DEBUG] Merged sw_df with CLASSIFICATION_DF, new cols: {sw_df.columns.tolist()}", flush=True)

        # Generate visual charts
        print(f"[DEBUG] Pre-chart hw_df shape: {hw_df.shape}", flush=True)
        print(f"[DEBUG] Pre-chart sw_df shape: {sw_df.shape}", flush=True)
        if "Tier Total Score" in hw_df.columns:
            print(f"[DEBUG] hw_df Tier scores: {hw_df['Tier Total Score'].unique()}", flush=True)
        if "Tier Total Score" in sw_df.columns:
            print(f"[DEBUG] sw_df Tier scores: {sw_df['Tier Total Score'].unique()}", flush=True)
        if "Category" in hw_df.columns:
            print(f"[DEBUG] hw_df Categories: {hw_df['Category'].value_counts().to_dict()}", flush=True)
        if "Category" in sw_df.columns:
            print(f"[DEBUG] sw_df Categories: {sw_df['Category'].value_counts().to_dict()}", flush=True)
        # … debug prints …
        print(f"[DEBUG] Generating visual charts", flush=True)
        # ensure the pie-chart code sees "Tier" and "Status"
        hw_df = hw_df.rename(columns={"Tier Total Score": "Tier"})
        sw_df = sw_df.rename(columns={"Tier Total Score": "Tier"})
        if "Availability" in hw_df.columns:
            hw_df["Status"] = hw_df["Availability"]
        if "Availability" in sw_df.columns:
            sw_df["Status"] = sw_df["Availability"]
        uploaded_charts = generate_visual_charts(hw_df, sw_df, session_path)
        print(f"[DEBUG] Uploaded charts: {uploaded_charts}", flush=True)

        # 5) Build narratives
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
        for i, func in enumerate(section_funcs):
            narratives[f"content_{i+1}"] = ai_narrative(func.__name__, func(hw_df, sw_df))

        # 6) Write gap-analysis Excels
        hw_xl = os.path.join(session_path, "HWGapAnalysis.xlsx")
        sw_xl = os.path.join(session_path, "SWGapAnalysis.xlsx")
        hw_df.to_excel(hw_xl, index=False)
        sw_df.to_excel(sw_xl, index=False)

        file_urls = {
            "file_1_url": f"/files/{session_id}/{os.path.basename(hw_xl)}",
            "file_2_url": f"/files/{session_id}/{os.path.basename(sw_xl)}",
        }

        # 7) Upload gap-analysis Excels
        hw_url = upload_file_to_drive(hw_xl, os.path.basename(hw_xl), folder_id)
        sw_url = upload_file_to_drive(sw_xl, os.path.basename(sw_xl), folder_id)

        # 8) Prepare files list for Market-Gap
        files_for_gap = [
            {"file_name": os.path.basename(hw_xl), "drive_url": hw_url},
            {"file_name": os.path.basename(sw_xl), "drive_url": sw_url}
        ]

        # Assemble payload
        payload = {"session_id": session_id, "email": email, "goal": goal, **uploaded_charts, **narratives}
        print(f"[DEBUG] Payload assembled with keys: {list(payload.keys())}", flush=True)
        # Send to DOCX/PPTX generator (single endpoint) or fall back to local generation
        docx_url = pptx_url = None
        try:
            resp = requests.post(f"{DOCX_SERVICE_URL}/generate_assessment", json=payload)
            if hasattr(resp, "raise_for_status"):
                resp.raise_for_status()
            resp_data = resp.json() if hasattr(resp, "json") else {}
            docx_url = resp_data.get('docx_url')
            pptx_url = resp_data.get('pptx_url')
            if not docx_url:
                raise ValueError("docx missing")
        except Exception:
            docx_url = generate_docx_report(session_id, hw_df, sw_df, uploaded_charts)
            pptx_url = generate_pptx_report(session_id, hw_df, sw_df, uploaded_charts)
        # Upload to Drive
        file_links = {}
        if docx_url:
            print(f"[DEBUG] Downloading and uploading DOCX to Drive", flush=True)
            fname = os.path.basename(docx_url)
            local_doc = os.path.join(session_path, fname)
            if docx_url.startswith('http'):
                r = requests.get(docx_url); r.raise_for_status(); open(local_doc, 'wb').write(r.content)
            else:
                if os.path.abspath(docx_url) != os.path.abspath(local_doc) and os.path.exists(docx_url):
                    shutil.copy(docx_url, local_doc)
                else:
                    open(local_doc, 'wb').close()
            file_links['file_1_drive_url'] = upload_file_to_drive(local_doc, fname, folder_id)
            print(f"[DEBUG] DOCX uploaded, Drive URL: {file_links['file_1_drive_url']}", flush=True)
            file_urls["file_3_url"] = f"/files/{session_id}/{fname}"
        if pptx_url:
            fname = os.path.basename(pptx_url)
            local_ppt = os.path.join(session_path, fname)
            if pptx_url.startswith('http'):
                r = requests.get(pptx_url); r.raise_for_status(); open(local_ppt, 'wb').write(r.content)
            else:
                if os.path.abspath(pptx_url) != os.path.abspath(local_ppt) and os.path.exists(pptx_url):
                    shutil.copy(pptx_url, local_ppt)
                else:
                    open(local_ppt, 'wb').close()
            file_urls["file_4_url"] = f"/files/{session_id}/{fname}"

        # 11) Notify Market-Gap
        try:
            market_payload = {
                "session_id": session_id,
                "folder_id": folder_id,
                "gpt_module": "it_assessment",
                "status": "complete",
                "files": files_for_gap,
                "charts": uploaded_charts,
                **file_links,
                **file_urls,
            }
            print(f"[DEBUG] Notifying market-gap with payload: {market_payload}", flush=True)
            resp = requests.post(
                next_action_webhook or MARKET_GAP_WEBHOOK,
                json=market_payload,
            )
            if hasattr(resp, "raise_for_status"):
                resp.raise_for_status()
            print("[DEBUG] Market-gap notified successfully", flush=True)
            return market_payload

        except Exception as e:
            import traceback; traceback.print_exc()
            return {"error": str(e)}

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": str(e)}

def process_assessment(data: dict) -> dict:
    return generate_assessment(
        session_id=data.get("session_id", ""),
        email=data.get("email", ""),
        goal=data.get("goal", ""),
        files=data.get("files", []),
        next_action_webhook=data.get("next_action_webhook", ""),
        folder_id=data.get("folder_id", "")
    )
