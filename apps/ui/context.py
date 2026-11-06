"""Navegação principal (ui-ux-specification.md §8)."""

NAV = [
    ("ui:home", "Início", "home"),
    ("entries:list", "Movimentações", "list"),
    ("accounts:list", "Contas", "wallet"),
    ("categories:list", "Categorias", "tag"),
]
SETTINGS_NAV = [
    ("security:settings", "Segurança", "shield"),
    ("ui:appearance", "Aparência", "sun"),
]


def ui(request):
    match = getattr(request, "resolver_match", None)
    current = f"{match.namespace}:{match.url_name}" if match and match.namespace else ""
    section = current.split(":")[0]
    return {
        "nav": [(n, label, icon, n.split(":")[0] == section) for n, label, icon in NAV],
        "settings_nav": [(n, label, icon, n == current) for n, label, icon in SETTINGS_NAV],
    }
