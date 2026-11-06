"""Ponto de entrada do serviço (ops/serve.py)."""

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def serve(monkeypatch):
    for key in ("FINANCAS_PORT", "FINANCAS_TAILNET_HOST", "FINANCAS_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    spec = importlib.util.spec_from_file_location("serve", ROOT / "ops" / "serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = dict(os.environ)
    yield module
    os.environ.clear()  # configure() grava direto no ambiente; devolve como estava
    os.environ.update(saved)


def test_argumentos_viram_ambiente(serve, tmp_path, monkeypatch):
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.test")
    serve.configure(
        ["--port", "8123", "--tailnet-host", "pc.exemplo.ts.net", "--data-dir", str(tmp_path)]
    )
    assert os.environ["FINANCAS_PORT"] == "8123"
    assert os.environ["FINANCAS_TAILNET_HOST"] == "pc.exemplo.ts.net"
    assert os.environ["FINANCAS_DATA_DIR"] == str(tmp_path)


def test_porta_invalida(serve):
    with pytest.raises(ValueError):
        serve.configure(["--port", "abc"])


def test_padroes(serve):
    serve.configure([])
    assert os.environ["FINANCAS_PORT"] == "8000"
    assert "FINANCAS_DATA_DIR" not in os.environ
