# [no change to imports or constants]

def process_assessment(session_id, files, email):
    try:
        print(f"🚀 Processing assessment for session: {session_id}")
        session_path = os.path.join(BASE_DIR, session_id)
        os.makedirs(session_path, exist_ok=True)

        hw_file = next((f["path"] for f in files if "hardware" in f["type"]), None)
        sw_file = next((f["path"] for f in files if "software" in f["type"]), None)

        hw_df = pd.read_excel(hw_file, header=0) if hw_file else pd.DataFrame()
        sw_df = pd.read_excel(sw_file, header=0) if sw_file else pd.DataFrame()

        print("📥 HW Columns:", hw_df.columns.tolist())
        print("📥 SW Columns:", sw_df.columns.tolist())

        REQUIRED_COLUMNS_HW = parse_readme_columns("README_HWGapAnalysis.docx")
        REQUIRED_COLUMNS_SW = parse_readme_columns("README_SWGapAnalysis.docx")

        valid_hw, missing_hw = validate_columns(hw_df, REQUIRED_COLUMNS_HW, label="HW") if not hw_df.empty else (True, [])
        valid_sw, missing_sw = validate_columns(sw_df, REQUIRED_COLUMNS_SW, label="SW") if not sw_df.empty else (True, [])

        if not valid_hw or not valid_sw:
            return {
                "status": "error",
                "message": "Missing columns in uploaded files.",
                "missing_hw": missing_hw,
                "missing_sw": missing_sw
            }

        hw_defaults = {"Tier": "Unknown", "Total Score": 0, "Calculation": 0}
        sw_defaults = {"Tier Classification referencing tier metrix in ClassificationTier.xlsx": "Unknown", "Total Score": 0}

        hw_df = autofill_missing_columns(hw_df, hw_defaults)
        sw_df = autofill_missing_columns(sw_df, sw_defaults)

        tier_df = pd.read_excel(tier_matrix_path)
        hw_df = classify_devices(hw_df, tier_df, is_hw=True)
        sw_df = classify_devices(sw_df, tier_df, is_hw=False)

        hw_gap_path = os.path.join(session_path, f"HWGapAnalysis_{session_id}.xlsx")
        sw_gap_path = os.path.join(session_path, f"SWGapAnalysis_{session_id}.xlsx")

        if not hw_df.empty:
            hw_df.to_excel(hw_gap_path, index=False)
        else:
            print("⚠️ HW DataFrame is empty, skipping Excel output")

        if not sw_df.empty:
            sw_df.to_excel(sw_gap_path, index=False)
        else:
            print("⚠️ SW DataFrame is empty, skipping Excel output")

        hw_charts = generate_hw_charts(hw_gap_path, session_id) if not hw_df.empty else []
        sw_charts = generate_sw_charts(sw_gap_path, session_id) if not sw_df.empty else []
        print("📊 Charts generated:", hw_charts + sw_charts)

        if 'Tier' in hw_df.columns and hw_df['Tier'].notnull().any():
            hw_tier_summary = hw_df['Tier'].value_counts().to_dict()
            total_hw = sum(hw_tier_summary.values())
            summary = ", ".join([f"{k}: {int(v/total_hw*100)}%" for k, v in hw_tier_summary.items()]) if total_hw > 0 else "No hardware data available"
        else:
            summary = "Tier column missing or empty in HW data."

        recommendations = "Upgrade all devices marked as Tier 4 or 'Unknown'. Consider phasing out legacy systems."
        findings = f"{len(hw_df)} hardware entries and {len(sw_df)} software entries processed and classified."

        api_result = call_generate_api(session_id, summary, recommendations, findings)

        docx_path = generate_docx_report(session_id)
        pptx_path = generate_pptx_report(session_id)

        upload_to_drive(hw_gap_path, session_id)
        upload_to_drive(sw_gap_path, session_id)
        upload_to_drive(docx_path, session_id)
        upload_to_drive(pptx_path, session_id)

        print("✅ Assessment completed for session:", session_id)
        return {
            "status": "complete",
            "docx": docx_path,
            "pptx": pptx_path,
            "api_response": api_result
        }
    except Exception as e:
        print(f"🔥 Unhandled error in process_assessment: {e}")
        traceback.print_exc()
        return {}
