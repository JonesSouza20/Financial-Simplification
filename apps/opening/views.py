"""Assistente de abertura (F-002): contas → cartões → dívidas → a receber → revisão."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.ledger.errors import LedgerError

from . import services
from .forms import (
    AccountDraftForm,
    CardDraftForm,
    DebtDraftForm,
    ItemDraftForm,
    ReceivableDraftForm,
)

STEPS = [
    ("contas", "Contas"),
    ("cartoes", "Cartões"),
    ("dividas", "Dívidas e consórcio"),
    ("receber", "A receber"),
    ("revisao", "Revisão"),
]
FORMS = {
    "accounts": AccountDraftForm,
    "cards": CardDraftForm,
    "items": ItemDraftForm,
    "debts": DebtDraftForm,
    "receivables": ReceivableDraftForm,
}
STEP_SECTIONS = {
    "contas": ["accounts"],
    "cartoes": ["cards", "items"],
    "dividas": ["debts"],
    "receber": ["receivables"],
    "revisao": [],
}


def _form(section, draft, data=None):
    kwargs = {"cards": draft["cards"]} if section == "items" else {}
    return FORMS[section](data, prefix=section, **kwargs)


@require_http_methods(["GET", "POST"])
def step(request, step):
    if step not in STEP_SECTIONS:
        raise Http404
    if services.done():
        messages.success(
            request, "A abertura já foi feita. Novos itens entram pelas telas normais."
        )
        return redirect("ui:home")
    draft = services.load(request.session)
    forms = {s: _form(s, draft) for s in STEP_SECTIONS[step]}
    if request.method == "POST":
        action = request.POST.get("action", "")
        section = action.split(":")[1] if ":" in action else ""
        if action.startswith("add:") and section in forms:
            form = _form(section, draft, request.POST)
            if form.is_valid():
                draft[section].append(form.item())
                services.save(request.session, draft)
                return redirect("opening:step", step=step)
            forms[section] = form
        elif action.startswith("remove:") and section in STEP_SECTIONS[step]:
            index = int(request.POST.get("index", -1))
            if 0 <= index < len(draft[section]):
                if section == "cards":
                    draft["items"] = [
                        {**i, "card": i["card"] - (i["card"] > index)}
                        for i in draft["items"]
                        if i["card"] != index
                    ]
                draft[section].pop(index)
                services.save(request.session, draft)
            return redirect("opening:step", step=step)
        elif action == "commit" and step == "revisao":
            try:
                services.commit(draft)
                request.session.pop(services.SESSION_KEY, None)
                messages.success(request, "Abertura gravada. Confira cada conta com o banco.")
                return redirect("ui:home")
            except LedgerError as exc:
                messages.error(request, f"Nada foi gravado: {exc}")
    index = [s for s, _ in STEPS].index(step)
    return render(
        request,
        "opening/step.html",
        {
            "step": step,
            "steps": STEPS,
            "index": index,
            "next": STEPS[index + 1][0] if index + 1 < len(STEPS) else None,
            "prev": STEPS[index - 1][0] if index > 0 else None,
            "draft": draft,
            "forms": forms,
            "summary": services.summary(draft),
            "items_view": [(i, services.item_amount(i)) for i in draft["items"]],
        },
    )
