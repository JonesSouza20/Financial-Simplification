"""Navegação principal (ui-ux-specification.md §8)."""

NAV = [
    ("ui:home", "Início", "home"),
    ("payables:central", "Pagamentos", "clock"),
    ("entries:list", "Movimentações", "list"),
]
NAV_HOLDINGS = [
    ("cards:list", "Cartões", "card"),
    ("debts:list", "Dívidas", "debt"),
    ("receivables:list", "A receber", "users"),
    ("accounts:list", "Contas", "wallet"),
]
SETTINGS_NAV = [
    ("payables:money_settings", "Dinheiro", "wallet"),
    ("payables:holidays", "Feriados", "clock"),
    ("categories:list", "Categorias", "tag"),
    ("security:settings", "Segurança", "shield"),
    ("backup:index", "Backup", "shield"),
    ("backup:health", "Saúde", "check"),
    ("ui:appearance", "Aparência", "sun"),
]


def ui(request):
    match = getattr(request, "resolver_match", None)
    current = f"{match.namespace}:{match.url_name}" if match and match.namespace else ""
    in_settings = current == "ui:settings" or any(n == current for n, _, _ in SETTINGS_NAV)
    section = "" if in_settings else current.split(":")[0]
    tab = {"ui": "home", "payables": "payables", "entries": "entries"}.get(section, "more")
    if current in ("ui:more", "ui:appearance", "ui:origin"):
        tab = "more"
    return {
        "tab": tab,
        "nav": [
            (n, label, icon, n.split(":")[0] == section and current != "ui:more")
            for n, label, icon in NAV
        ],
        "nav_holdings": [
            (n, label, icon, n.split(":")[0] == section) for n, label, icon in NAV_HOLDINGS
        ],
        "settings_nav": [(n, label, icon, n == current) for n, label, icon in SETTINGS_NAV],
        "settings_active": in_settings,
    }
