from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from certificate_generator.app import create_app


def client(tmp_path):
    return TestClient(create_app(tmp_path))


def payload(recipients=None):
    return {"course": "Python Workshop", "issue_date": "2026-10-07",
            "recipients": recipients or [{"name": "Asha Rao", "email": "asha@example.org",
                                         "recipient_id": "P-001"}]}


def test_create_job_progress_and_download(tmp_path):
    api = client(tmp_path)
    created = api.post("/jobs", json=payload())
    assert created.status_code == 202
    assert created.json()["status"] == "queued"
    job = api.get(created.json()["status_url"]).json()
    assert job["status"] == "completed"
    assert job["total"] == 1
    assert job["counts"] == {"queued": 0, "completed": 1, "failed": 0}
    downloaded = api.get(job["recipients"][0]["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    text = PdfReader(BytesIO(downloaded.content)).pages[0].extract_text()
    assert "Asha Rao" in text
    assert "Python Workshop" in text
    assert "P-001" in text


def test_top_level_validation(tmp_path):
    api = client(tmp_path)
    assert api.post("/jobs", json=payload([]) | {"recipients": []}).status_code == 422
    assert api.post("/jobs", json=payload() | {"issue_date": "bad"}).status_code == 422
    assert api.post("/jobs", json=payload() | {"recipients": [{}] * 1001}).status_code == 422


def test_invalid_recipient_does_not_block_valid_one(tmp_path):
    api = client(tmp_path)
    recipients = [{"name": "Valid Person", "email": "valid@example.org"},
                  {"name": "", "email": "wrong"}, "not an object"]
    created = api.post("/jobs", json=payload(recipients))
    job = api.get(created.json()["status_url"]).json()
    assert job["status"] == "completed_with_errors"
    assert job["counts"] == {"queued": 0, "completed": 1, "failed": 2}
    assert job["recipients"][1]["error"]
    assert job["recipients"][2]["position"] == 2
    assert api.get(job["recipients"][1]["download_url"] if job["recipients"][1]["download_url"]
                   else f"/jobs/{job['job_id']}/certificates/{job['recipients'][1]['id']}").status_code == 409


def test_generation_failure_is_isolated(tmp_path, monkeypatch):
    from certificate_generator import app as app_module

    original = app_module.generate_pdf

    def flaky(path, **kwargs):
        if kwargs["name"] == "Fail Person":
            raise RuntimeError("simulated renderer failure")
        return original(path, **kwargs)

    monkeypatch.setattr(app_module, "generate_pdf", flaky)
    api = client(tmp_path)
    recipients = [{"name": "Fail Person", "email": "fail@example.org"},
                  {"name": "Good Person", "email": "good@example.org"}]
    created = api.post("/jobs", json=payload(recipients))
    job = api.get(created.json()["status_url"]).json()
    assert job["status"] == "completed_with_errors"
    assert job["counts"] == {"queued": 0, "completed": 1, "failed": 1}
    assert "simulated renderer failure" in job["recipients"][0]["error"]
    assert api.get(job["recipients"][1]["download_url"]).status_code == 200


def test_unknown_resources(tmp_path):
    api = client(tmp_path)
    assert api.get("/jobs/missing").status_code == 404
    assert api.get("/jobs/missing/certificates/missing").status_code == 404


def test_frontend_cors_preflight(tmp_path):
    api = client(tmp_path)
    response = api.options("/jobs", headers={
        "Origin": "http://127.0.0.1:5173",
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
