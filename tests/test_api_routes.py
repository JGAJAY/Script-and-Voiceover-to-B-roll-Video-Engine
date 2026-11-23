import pytest
from fastapi.testclient import TestClient

def test_health_and_ready_endpoints(client: TestClient):
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # Ready check
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
    assert "dependencies" in res_ready.json()

def test_create_broll_job_accepted(client: TestClient):
    payload = {
        "script": "Testing the IncuBrix B-roll video generation API endpoints.",
        "voice": "en-IN-female",
        "aspect_ratios": ["16:9"],
        "style": "clean modern",
        "avoid": ["people's faces"]
    }
    res = client.post("/api/v1/broll/jobs", json=payload)
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "queued"

def test_idempotency_key_header_safe_retry(client: TestClient):
    payload = {
        "script": "Testing idempotency key header behavior for duplicate submissions.",
        "voice": "en-IN-female",
        "aspect_ratios": ["16:9"]
    }
    idempotency_key = "test_key_unique_12345"
    headers = {"Idempotency-Key": idempotency_key}

    # First request
    res1 = client.post("/api/v1/broll/jobs", json=payload, headers=headers)
    assert res1.status_code == 202
    job_id_1 = res1.json()["job_id"]

    # Second request with identical Idempotency-Key
    res2 = client.post("/api/v1/broll/jobs", json=payload, headers=headers)
    assert res2.status_code == 202
    job_id_2 = res2.json()["job_id"]

    # Must return exact same job and not create duplicate
    assert job_id_1 == job_id_2
    assert "Idempotency-Key" in res2.json()["message"]

def test_error_json_structure_and_codes(client: TestClient):
    # Empty request payload (missing all inputs)
    res = client.post("/api/v1/broll/jobs", json={"script": "", "audio_url": None, "scenes": None})
    assert res.status_code == 422 or res.status_code == 400

    # Non-existent job
    res_not_found = client.get("/api/v1/jobs/non_existent_job_99999")
    assert res_not_found.status_code == 404
    body = res_not_found.json()
    assert "error" in body
    assert body["error"]["code"] == "JOB_NOT_FOUND"
    assert "message" in body["error"]
    assert "retryable" in body["error"]
