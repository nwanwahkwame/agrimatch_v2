"""HTTP-layer tests for public reference endpoints.

Verifies error handling (503 on DB failure) and normal response shapes.
No DB connection required -- all repo calls are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.reference import router, _cache
from utils.cache import TtlCache


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure TTL cache is empty before every test."""
    _cache._store.clear()
    yield
    _cache._store.clear()


app = FastAPI()

# Provide stub app.state for model-status endpoint dependencies.
app.state.xgb_predictor  = MagicMock(models={})
app.state.lstm_predictor  = MagicMock(models={})
app.state.delay_clf       = MagicMock(model=None)

app.include_router(router)

# Inject stub dependencies so the model-status endpoint works without real models.
from api import dependencies as _deps
app.dependency_overrides[_deps.get_xgb]       = lambda: app.state.xgb_predictor
app.dependency_overrides[_deps.get_lstm]      = lambda: app.state.lstm_predictor
app.dependency_overrides[_deps.get_delay_clf] = lambda: app.state.delay_clf


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# ── /api/crops ────────────────────────────────────────────────────────────────

def _mock_crop():
    r = MagicMock()
    r.id                  = 1
    r.internal_name       = "Maize"
    r.is_byproduct_source = False
    return r


@patch("api.routers.reference.get_session")
@patch("api.routers.reference.ReferenceRepo.get_crops", return_value=[_mock_crop()])
def test_crops_returns_list(mock_repo, mock_gs, client):
    from contextlib import contextmanager

    @contextmanager
    def _fake():
        yield MagicMock()

    mock_gs.side_effect = _fake
    resp = client.get("/api/crops")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Maize"


@patch("api.routers.reference.get_session")
def test_crops_returns_503_on_db_failure(mock_gs, client):
    mock_gs.side_effect = RuntimeError("DB down")
    resp = client.get("/api/crops")
    assert resp.status_code == 503


# ── /api/stats ────────────────────────────────────────────────────────────────

@patch("api.routers.reference.get_session")
def test_stats_returns_503_on_db_failure(mock_gs, client):
    mock_gs.side_effect = RuntimeError("DB down")
    resp = client.get("/api/stats")
    assert resp.status_code == 503


# ── /api/regions ──────────────────────────────────────────────────────────────

@patch("api.routers.reference.get_session")
def test_regions_returns_503_on_db_failure(mock_gs, client):
    mock_gs.side_effect = RuntimeError("DB down")
    resp = client.get("/api/regions")
    assert resp.status_code == 503


# ── /api/model-accuracy ───────────────────────────────────────────────────────

@patch("api.routers.reference.get_session")
def test_model_accuracy_returns_503_on_db_failure(mock_gs, client):
    mock_gs.side_effect = RuntimeError("DB down")
    resp = client.get("/api/model-accuracy")
    assert resp.status_code == 503


# ── /api/models/status ────────────────────────────────────────────────────────

def test_models_status_returns_200(client):
    resp = client.get("/api/models/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "xgboost_models" in data
    assert "lstm_models"    in data
    assert "api_version"    in data
