import os
import sys
import pandas as pd

sys.path.insert(0, os.getcwd())

from app import app
import generate_assessment


def setup_api_monkeypatch(monkeypatch):
    def write_placeholder(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"x")
        return path

    monkeypatch.setattr(generate_assessment, "generate_visual_charts", lambda *a, **k: {})
    monkeypatch.setattr(
        generate_assessment,
        "generate_docx_report",
        lambda session_id, *a, **k: write_placeholder(os.path.join("temp_sessions", session_id, "IT_Current_Status_Assessment_Report.docx")),
    )
    monkeypatch.setattr(
        generate_assessment,
        "generate_pptx_report",
        lambda session_id, *a, **k: write_placeholder(os.path.join("temp_sessions", session_id, "IT_Current_Status_Executive_Report.pptx")),
    )

    class DummyResp:
        status_code = 200
    monkeypatch.setattr(generate_assessment.requests, "post", lambda *a, **k: DummyResp())


def test_start_assessment_downloadable_urls(tmp_path, monkeypatch):
    setup_api_monkeypatch(monkeypatch)

    hw_df = pd.DataFrame({"a": [1]})
    sw_df = pd.DataFrame({"b": [2]})
    hw_path = tmp_path / "hw.xlsx"
    sw_path = tmp_path / "sw.xlsx"
    hw_df.to_excel(hw_path, index=False)
    sw_df.to_excel(sw_path, index=False)

    files = [
        {"type": "hardware", "file_url": str(hw_path), "file_name": "hw.xlsx"},
        {"type": "software", "file_url": str(sw_path), "file_name": "sw.xlsx"},
    ]

    client = app.test_client()
    resp = client.post(
        "/start_assessment",
        json={
            "session_id": "sess",
            "email": "user@example.com",
            "goal": "goal",
            "files": files,
            "next_action_webhook": "http://example.com",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    urls = [data["result"][f"file_{i}_url"] for i in range(1, 5)]
    for url in urls:
        r = client.get(url)
        assert r.status_code == 200
