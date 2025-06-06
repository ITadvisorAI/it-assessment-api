
import os
import pandas as pd
from market_lookup import suggest_hw_replacements, suggest_sw_replacements
from visualization import generate_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report

def load_inventory_file(file_path):
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path)
    elif file_path.endswith('.xlsx'):
        return pd.read_excel(file_path)
    return pd.DataFrame()

def generate_assessment(session_id, files, goal):
    try:
        session_dir = os.path.join("temp_sessions", session_id)
        os.makedirs(session_dir, exist_ok=True)

        hw_df, sw_df = pd.DataFrame(), pd.DataFrame()

        # Identify files
        for f in files:
            fpath = f.get("local_path")
            ftype = f.get("type", "general")
            if ftype == "asset_inventory":
                df = load_inventory_file(fpath)
                if "software" in fpath.lower():
                    sw_df = df
                else:
                    hw_df = df

        if hw_df.empty and sw_df.empty:
            print("⚠️ No valid HW/SW inventory files found.")
            return None

        # Step 1: Market upgrade logic
        if not hw_df.empty:
            hw_df = suggest_hw_replacements(hw_df)
        if not sw_df.empty:
            sw_df = suggest_sw_replacements(sw_df)

        # Step 2: Visualization
        charts = generate_charts(hw_df, sw_df, session_id)

        # Step 3: DOCX report
        docx_path = generate_docx_report(session_id, hw_df, sw_df, charts)

        # Step 4: PPTX report
        pptx_path = generate_pptx_report(session_id, hw_df, sw_df, charts)

        # Step 5: Save updated GAP sheets
        hw_gap_path = os.path.join(session_dir, "HWGapAnalysis.xlsx")
        sw_gap_path = os.path.join(session_dir, "SWGapAnalysis.xlsx")
        if not hw_df.empty:
            hw_df.to_excel(hw_gap_path, index=False)
        if not sw_df.empty:
            sw_df.to_excel(sw_gap_path, index=False)

        return {
            "status": "completed",
            "docx": docx_path,
            "pptx": pptx_path,
            "hw_gap": hw_gap_path,
            "sw_gap": sw_gap_path,
            "charts": charts
        }

    except Exception as e:
        print("❌ Error in generate_assessment:", str(e))
        return {"status": "failed", "error": str(e)}
