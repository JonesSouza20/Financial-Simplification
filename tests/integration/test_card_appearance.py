"""Banco e cor do cartão desenhado (ADR-043). Só aparência: nenhum valor muda."""

import pathlib
import re

import pytest
from django.conf import settings

from apps.cards import brands
from apps.cards import services as cards
from apps.cards.models import Card
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.models import AuditLog
from apps.money import Money

STATIC = pathlib.Path(settings.BASE_DIR) / "static" / "img"


def test_cadastro_com_banco_e_cor(fin, web, monkeypatch):
    monkeypatch.setattr(brands, "has_logo", lambda slug: True)
    response = web.post(
        "/cartoes/novo/",
        {
            "name": "Roxinho",
            "credit_limit": "3.000,00",
            "closing_day": 3,
            "due_day": 10,
            "bank": "nubank",
            "color": "",
        },
    )
    card = Card.objects.get(name="Roxinho")
    assert response.status_code == 302
    assert (card.bank, card.color) == ("nubank", "")
    html = web.get(f"/cartoes/{card.pk}/").content.decode()
    assert "face-b-nubank" in html and "img/bancos/nubank" in html


def test_aparencia_troca_sem_mexer_em_valor(web, card_a, monkeypatch):
    monkeypatch.setattr(brands, "has_logo", lambda slug: True)
    before = cards.liability(card_a)
    web.post(f"/cartoes/{card_a.pk}/aparencia/", {"bank": "itau", "color": "vinho"})
    card_a.refresh_from_db()
    assert (card_a.bank, card_a.color) == ("itau", "vinho")
    assert cards.liability(card_a) == before
    assert AuditLog.objects.filter(action="appearance", entity_id=card_a.pk).exists()
    html = web.get("/cartoes/").content.decode()
    assert "face-c-vinho" in html and "logo-badge" in html


def test_banco_ou_cor_desconhecidos_recusados(card_a):
    with pytest.raises(InvalidTransactionError):
        cards.set_appearance(card_a, bank="banco-x", color="")
    with pytest.raises(InvalidTransactionError):
        cards.set_appearance(card_a, bank="", color="rosa")


def test_tela_recusa_opcao_fora_da_lista(web, card_a):
    response = web.post(f"/cartoes/{card_a.pk}/aparencia/", {"bank": "banco-x", "color": ""})
    assert response.status_code == 200
    card_a.refresh_from_db()
    assert card_a.bank == ""


@pytest.mark.parametrize(
    ("bank", "color", "css", "badge", "dark"),
    [
        ("", "", "face-c-grafite", False, False),
        ("nubank", "", "face-b-nubank", False, False),
        ("itau", "", "face-b-itau", True, False),
        ("bb", "", "face-b-bb", True, True),
        ("bradesco", "verde", "face-c-verde", True, False),
    ],
)
def test_face(bank, color, css, badge, dark, monkeypatch):
    monkeypatch.setattr(brands, "has_logo", lambda slug: True)
    face = brands.face(Card(name="X", bank=bank, color=color, credit_limit_cents=Money(1).cents))
    assert (face["css"], face["badge"], face["dark_text"]) == (css, badge, dark)


def test_todo_banco_tem_cor_no_css_e_logotipo_limpo_se_baixado():
    css = (pathlib.Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(
        encoding="utf-8"
    )
    for slug in brands.BANKS:
        assert f"face-b-{slug}" in css
        path = STATIC / "bancos" / f"{slug}.svg"
        if path.exists():  # os logotipos ficam fora do repositório (ops/logos_bancos.py)
            logo = path.read_text(encoding="utf-8")
            assert not re.search(
                r"<script|foreignObject|javascript:|<image|href=\"http", logo, re.I
            )
    for slug in brands.COLORS:
        assert f"face-c-{slug}" in css


def test_icones_3d_existem():
    from apps.payables.presentation import GROUP_3D, ICONS_3D

    for name in {*ICONS_3D.values(), *GROUP_3D.values(), "carteira", "calendario", "banco"}:
        assert (STATIC / "3d" / f"{name}.svg").exists(), name


def test_abertura_guarda_banco_e_cor(db, cats):
    from apps.opening import services as opening
    from tests.scenarios.test_s00_abertura import S00_DRAFT

    draft = {
        **S00_DRAFT,
        "cards": [{**c, "bank": "nubank", "color": "roxo"} for c in S00_DRAFT["cards"]],
    }
    opening.commit(draft)
    assert set(Card.objects.values_list("bank", "color")) == {("nubank", "roxo")}


def test_rascunho_antigo_sem_banco_continua_valendo(db, cats):
    from apps.opening import services as opening
    from tests.scenarios.test_s00_abertura import S00_DRAFT

    opening.commit(S00_DRAFT)
    assert set(Card.objects.values_list("bank", "color")) == {("", "")}


def test_sem_arquivo_de_logotipo_o_cartao_fica_so_com_a_cor(monkeypatch):
    brands.has_logo.cache_clear()
    monkeypatch.setattr(brands, "has_logo", lambda slug: False)
    face = brands.face(Card(name="X", bank="itau", color="", credit_limit_cents=100))
    assert (face["logo"], face["badge"], face["css"]) == ("", False, "face-b-itau")


def test_limpeza_tira_script_e_referencia_externa():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "logos_bancos", pathlib.Path(settings.BASE_DIR) / "ops" / "logos_bancos.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dirty = (
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="x()"><script>alert(1)</script>'
        b'<path d="M0 0h1" fill="url(http://mal.example/a)"/><image href="http://x"/></svg>'
    )
    clean = module.sanitize(dirty)
    assert "script" not in clean and "onload" not in clean and "http://mal" not in clean
    assert "<path" in clean
    with pytest.raises(ValueError):
        module.sanitize(
            b'<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"/>'
        )
