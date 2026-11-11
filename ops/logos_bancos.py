"""Baixa e limpa os logotipos dos bancos usados no cartão desenhado (ADR-043).

Os logotipos são marcas registradas dos bancos e não fazem parte deste repositório.
Rodar uma vez, na pasta do projeto:

    uv run python ops/logos_bancos.py

Origem: https://github.com/Tgentil/Bancos-em-SVG. Cada arquivo é limpo antes de gravar:
só formas e estilos, sem script, sem referência externa e sem imagem embutida.
Sem os arquivos, o cartão aparece só com a cor, sem logotipo.
"""

from __future__ import annotations

import pathlib
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://raw.githubusercontent.com/Tgentil/Bancos-em-SVG/main/"
FILES = {
    "nubank": "Nu Pagamentos S.A/nubank-branco.svg",
    "itau": "Itaú Unibanco S.A/itau.svg",
    "bradesco": "Bradesco S.A/bradesco.svg",
    "santander": "Banco Santander Brasil S.A/banco-santander-logo.svg",
    "bb": "Banco do Brasil S.A/banco-do-brasil-sem-fundo.svg",
    "caixa": "Caixa Econômica Federal/caixa-economica-federal-1.svg",
    "inter": "Banco Inter S.A/inter.svg",
    "c6": "Banco C6 S.A/c6 bank- branco.svg",
    "btg": "Banco BTG Pacutal/btg-pactual.svg",
    "mercadopago": "Mercado Pago/mercado-pago.svg",
    "picpay": "PicPay/Logo-PicPay.svg",
    "neon": "Neon/header-logo-neon.svg",
    "pagbank": "PagSeguro Internet S.A/logo-pagbank.svg",
    "sicredi": "Sicredi/logo-svg2.svg",
    "sicoob": "Sicoob/sicoob-vector-logo.svg",
    "pan": "Banco Pan/bancoPan.svg",
    "xp": "XP Investimentos/xp-investimentos-logo.svg",
}
MAX_BYTES = 200_000
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ALLOWED = {
    "svg",
    "g",
    "path",
    "rect",
    "circle",
    "ellipse",
    "polygon",
    "polyline",
    "line",
    "defs",
    "clipPath",
    "linearGradient",
    "radialGradient",
    "stop",
    "style",
    "title",
}
DEST = pathlib.Path(__file__).resolve().parents[1] / "static" / "img" / "bancos"


def _local(name: str) -> str:
    return name.split("}", 1)[1] if "}" in name else name


def _namespace(name: str) -> str:
    return name.split("}")[0][1:] if "}" in name else ""


def _clean(element) -> None:
    for child in list(element):
        if _namespace(child.tag) not in ("", SVG) or _local(child.tag) not in ALLOWED:
            element.remove(child)
            continue
        _clean(child)
    for attr in list(element.attrib):
        name, value = _local(attr), element.attrib[attr]
        namespace = _namespace(attr)
        handler = name.lower().startswith("on")
        foreign = bool(namespace) and namespace != XLINK
        external_link = name == "href" and not value.startswith("#")
        external_url = "url(" in value and not re.fullmatch(r"url\(#[\w.-]+\)", value.strip())
        if handler or foreign or external_link or external_url:
            del element.attrib[attr]
    unsafe = r"@import|url\((?!#)|expression|javascript"
    if _local(element.tag) == "style" and element.text and re.search(unsafe, element.text, re.I):
        element.text = ""


def sanitize(data: bytes) -> str:
    if b"<!ENTITY" in data or b"<!DOCTYPE" in data:
        raise ValueError("SVG com DOCTYPE ou ENTITY recusado")
    ET.register_namespace("", SVG)
    root = ET.fromstring(data)  # noqa: S314 - sem DOCTYPE/ENTITY, conferido acima
    if _local(root.tag) != "svg":
        raise ValueError("não é SVG")
    _clean(root)
    text = ET.tostring(root, encoding="unicode")
    if re.search(r"script|foreignObject|javascript:|<image", text, re.I):
        raise ValueError("conteúdo proibido depois da limpeza")
    return text


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    failures = 0
    for slug, path in FILES.items():
        url = BASE + urllib.parse.quote(path)
        try:
            with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - URL fixa
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("arquivo grande demais")
            (DEST / f"{slug}.svg").write_text(sanitize(data), encoding="utf-8")
            print(f"ok    {slug}")
        except (OSError, ValueError, ET.ParseError) as exc:
            failures += 1
            print(f"falha {slug}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
