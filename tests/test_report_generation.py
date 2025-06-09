import os
import sys
import pandas as pd
import zipfile
import matplotlib

sys.path.insert(0, os.getcwd())

from visualization import generate_charts
from report_docx import generate_docx_report
from report_pptx import generate_pptx_report


def test_reports_include_charts(tmp_path, monkeypatch):
    matplotlib.use("Agg")
    # work in tmp directory to avoid polluting repo
    monkeypatch.chdir(tmp_path)

    session_id = "test_session"
    hw_df = pd.DataFrame({"Tier": ["1"], "Status": ["Active"]})
    sw_df = pd.DataFrame({"Tier": ["1"], "Status": ["Active"]})

    session_folder = os.path.join("temp_sessions", session_id)
    charts = generate_charts(hw_df, sw_df, session_folder)

    docx_path = generate_docx_report(session_id, hw_df, sw_df, charts)
    pptx_path = generate_pptx_report(session_id, hw_df, sw_df, charts)

    with zipfile.ZipFile(docx_path) as zf:
        assert any(name.startswith("word/media/") for name in zf.namelist())

    with zipfile.ZipFile(pptx_path) as zf:
        assert any(name.startswith("ppt/media/") for name in zf.namelist())
