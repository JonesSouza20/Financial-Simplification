"""Proíbe ponto flutuante nos módulos financeiros (RN-001, ADR-002).

O Ruff não tem regra que proíba o uso de `float`. Esta verificação faz isso
analisando a árvore sintática de cada arquivo dos módulos financeiros.

Bloqueia:
- literais de ponto flutuante (ex.: 0.1);
- o nome `float` (chamada, anotação, isinstance);
- importação ou uso do módulo `math`.
"""

import ast
from pathlib import Path

import pytest

APPS_DIR = Path(__file__).resolve().parents[2] / "apps"

# Módulos onde dinheiro é calculado (architecture.md §5).
FINANCIAL_PACKAGES = [
    "money",
    "ledger",
    "cards",
    "receivables",
    "payables",
    "debts",
    "balances",
]


def find_float_usage(source: str, filename: str = "<código>") -> list[str]:
    """Devolve a lista de usos proibidos, no formato 'arquivo:linha: motivo'."""
    problems = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            problems.append(f"{filename}:{line}: literal de ponto flutuante {node.value!r}")
        elif isinstance(node, ast.Name) and node.id == "float":
            problems.append(f"{filename}:{line}: uso de float")
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names = [a.name for a in node.names]
            module = getattr(node, "module", None)
            if "math" in names or module == "math":
                problems.append(f"{filename}:{line}: importação de math")
    return problems


def financial_files() -> list[Path]:
    files = []
    for package in FINANCIAL_PACKAGES:
        root = APPS_DIR / package
        if root.exists():
            files += [p for p in root.rglob("*.py") if "migrations" not in p.parts]
    return files


@pytest.mark.parametrize(
    "code",
    [
        "x = 0.1",
        "y = float('1.5')",
        "def f(v: float): ...",
        "import math",
        "from math import floor",
    ],
)
def test_detector_encontra_usos_proibidos(code):
    assert find_float_usage(code)


@pytest.mark.parametrize(
    "code",
    [
        "from decimal import Decimal\nx = Decimal('0.1')",
        "cents = 10 // 3",
        "total = sum([100, 200])",
    ],
)
def test_detector_aceita_codigo_valido(code):
    assert find_float_usage(code) == []


def test_modulos_financeiros_sem_float():
    problems = []
    for path in financial_files():
        problems += find_float_usage(path.read_text(encoding="utf-8"), str(path))
    assert problems == [], "\n".join(problems)
