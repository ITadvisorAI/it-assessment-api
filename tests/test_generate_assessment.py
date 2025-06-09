import os
import sys
from io import BytesIO
import pandas as pd
import pytest

sys.path.insert(0, os.getcwd())

import generate_assessment


class DummyResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200
    def raise_for_status(self):
        pass


def setup_common_monkeypatch(monkeypatch, tmp_path):
    # Patch heavy report/chart generation functions
    monkeypatch.setattr(generate_assessment, "generate_visual_charts", lambda *a, **k: {})
    monkeypatch.setattr(generate_assessment, "generate_docx_report", lambda *a, **k: "docx")
    monkeypatch.setattr(generate_assessment, "generate_pptx_report", lambda *a, **k: "pptx")

    monkeypatch.setattr(
        generate_assessment,
        "upload_file_to_drive",
        lambda path, name=None, folder_id=None: f"https://drive/{os.path.basename(path)}",
    )
    
    class PostResp:
        status_code = 200
    monkeypatch.setattr(generate_assessment.requests, "post", lambda *a, **k: PostResp())


def test_local_file_copy(tmp_path, monkeypatch):
    setup_common_monkeypatch(monkeypatch, tmp_path)

    df = pd.DataFrame({"a": [1, 2]})
    local_src = tmp_path / "hw.xlsx"
    df.to_excel(local_src, index=False)

    files = [{
        "type": "hardware",
        "file_url": str(local_src),
        "file_name": "hw.xlsx",
    }]

    session_id = "local"
    generate_assessment.generate_assessment(session_id, "", "", files, "http://example.com")

    session_file = os.path.join("temp_sessions", session_id, "hw.xlsx")
    assert os.path.exists(session_file)
    df_read = pd.read_excel(session_file)
    assert df_read.equals(df)


def test_remote_file_download(tmp_path, monkeypatch):
    setup_common_monkeypatch(monkeypatch, tmp_path)

    df = pd.DataFrame({"b": [3, 4]})
    bio = BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)

    monkeypatch.setattr(
        generate_assessment.requests,
        "get",
        lambda url: DummyResponse(bio.getvalue()),
    )

    files = [{
        "type": "hardware",
        "file_url": "http://example.com/hw.xlsx",
        "file_name": "hw.xlsx",
    }]

    session_id = "remote"
    generate_assessment.generate_assessment(session_id, "", "", files, "http://example.com")

    session_file = os.path.join("temp_sessions", session_id, "hw.xlsx")
    assert os.path.exists(session_file)
    df_read = pd.read_excel(session_file)
    assert df_read.equals(df)


def test_drive_upload_and_post(tmp_path, monkeypatch):
    setup_common_monkeypatch(monkeypatch, tmp_path)

    uploaded = []
    def fake_upload(path, name=None, folder_id=None):
        uploaded.append(os.path.basename(path))
        return f"https://drive/{os.path.basename(path)}"
    monkeypatch.setattr(generate_assessment, "upload_file_to_drive", fake_upload)

    posted = {}
    def fake_post(url, json):
        posted.update(json)
        class R:
            status_code = 200
        return R()
    monkeypatch.setattr(generate_assessment.requests, "post", fake_post)

    df = pd.DataFrame({"a": [1]})
    src = tmp_path / "hw.xlsx"
    df.to_excel(src, index=False)

    files = [{"type": "hardware", "file_url": str(src), "file_name": "hw.xlsx"}]
    session_id = "drive"
    result = generate_assessment.generate_assessment(session_id, "", "", files, "http://example.com")

    assert len(uploaded) == 3
    assert posted["file_1_drive_url"].startswith("https://drive/")
    assert result["file_1_drive_url"] == posted["file_1_drive_url"]
