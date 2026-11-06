"""Rotas. Toda rota exige login, exceto as marcadas com `login_not_required` (security-plan §8)."""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.ui.urls")),
    path("acesso/", include("apps.security.urls")),
    path("contas/", include("apps.accounts.urls")),
    path("categorias/", include("apps.categories.urls")),
    path("movimentacoes/", include("apps.entries.urls")),
    path("cartoes/", include("apps.cards.urls")),
    path("a-receber/", include("apps.receivables.urls")),
    path("dividas/", include("apps.debts.urls")),
    path("abertura/", include("apps.opening.urls")),
]
