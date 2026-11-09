"""Central de pagamentos, calendário, recorrências e ajustes do dinheiro (F-030 a F-036)."""

import datetime
import hashlib

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.balances import services as balances
from apps.calendar_br import services as calendar
from apps.calendar_br.models import Holiday
from apps.categories.services import by_key
from apps.entries.services import UNDO_WINDOW
from apps.ledger import services as ledger
from apps.ledger.errors import LedgerError
from apps.money import Money
from apps.ui import models as prefs

from . import horizon as horizons
from . import presentation, recurrence, services
from .forms import (
    ActualForm,
    BillForm,
    HolidayForm,
    IncomeForm,
    MoneySettingsForm,
    PayForm,
    ReasonForm,
    RuleEditForm,
    RuleForm,
    ScheduleForm,
)
from .models import (
    Commitment,
    DayRule,
    Direction,
    ExcessKind,
    Frequency,
    RecurrenceRule,
    Settlement,
)


def _commitment(pk):
    return get_object_or_404(Commitment.objects.select_related("transaction"), pk=pk)


def _version(request):
    try:
        return int(request.POST.get("version", ""))
    except ValueError:
        return None


def _effect(before: balances.Position) -> str:
    """Toda ação diz, em uma frase, o que mudou no que dá para gastar (design-study.md §11)."""
    difference = (balances.position().can_spend - before.can_spend).cents
    if difference == 0:
        return "O que você pode gastar não mudou."
    word = "a mais" if difference > 0 else "a menos"
    return f"Você pode gastar {Money(abs(difference))} {word}."


def _form_page(request, form, title, **extra):
    return render(request, "payables/form.html", {"form": form, "title": title, **extra})


@require_GET
def central(request):
    return render(request, "payables/central.html", presentation.central(ledger.today()))


def _before_note(commitment: Commitment, position: balances.Position) -> str:
    """O efeito previsto de confirmar, pela conta prevista."""
    if commitment.expected_account is None or commitment.expected_account.asset_class != "free":
        return ""
    if commitment.direction == Direction.IN:
        return "Esse valor passa a contar no que você pode gastar."
    if commitment.due_date < position.horizon:
        return "O que você pode gastar não muda: esse valor já estava separado."
    return "Esse valor ainda não estava separado: sai do que você pode gastar."


@require_http_methods(["GET", "POST"])
def pay(request, pk):
    """Pagar (F-031): abre com o valor cheio; parcial, juros e encerrar ficam em outro valor."""
    commitment = _commitment(pk)
    remaining = services.open_amount(commitment)
    if not remaining.is_positive:
        messages.info(request, "Este compromisso não tem valor em aberto.")
        return redirect("payables:central")
    incoming = commitment.direction == Direction.IN
    initial = {
        "amount": presentation.num(remaining),
        "account": commitment.expected_account,
    }
    form = PayForm(request.POST or None, initial=initial, remaining=remaining, incoming=incoming)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        amount = data["amount"]
        excess = data.get("excess_kind") or None
        if incoming and amount.cents > remaining.cents:
            excess = ExcessKind.HIGHER_ACTUAL
        before = balances.position()
        try:
            settlement = services.pay(
                commitment,
                amount=amount,
                account=data["account"],
                on=data["on"],
                late_fee=data.get("late_fee"),
                excess_kind=excess,
                close_reason=data.get("close_reason") or None,
                idempotency_key=data.get("idempotency_key") or None,
            )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            request.session["undo_txn"] = settlement.transaction_id
            request.session["pay_effect"] = _effect(before)
            return redirect("payables:done", pk=commitment.pk)
    row = presentation.commitment_row(commitment, ledger.today())
    return render(
        request,
        "payables/pay.html",
        {
            "c": commitment,
            "row": row,
            "form": form,
            "remaining": remaining,
            "incoming": incoming,
            "has_payment": bool(services.settled_cents(commitment)),
            "can_schedule": commitment.transaction.status == "pending" and not incoming,
            "note": _before_note(commitment, balances.position()),
            "show_alternatives": request.method == "POST" and not form.full,
        },
    )


@require_GET
def done(request, pk):
    """Confirmação com "Desfazer" pelos 2 minutos seguintes (design-study.md §11)."""
    commitment = _commitment(pk)
    txn_id = request.session.get("undo_txn")
    settlement = (
        Settlement.objects.select_related("transaction")
        .filter(commitment=commitment, transaction_id=txn_id)
        .first()
    )
    if settlement is None:
        return redirect("payables:central")
    moved = next(
        (
            p
            for p in settlement.transaction.postings.select_related("account")
            if p.account.owner_type == "financial_account"
        ),
        None,
    )
    still_open = services.is_open(commitment)
    incoming = commitment.direction == Direction.IN
    return render(
        request,
        "payables/done.html",
        {
            "c": commitment,
            "amount": Money(abs(moved.amount_cents)) if moved else Money(settlement.amount_cents),
            "account": moved.account.name if moved else "",
            "still_open": still_open,
            "remaining": services.open_amount(commitment),
            "incoming": incoming,
            "effect": request.session.get("pay_effect", ""),
            "can_undo": timezone.now() - settlement.transaction.created_at <= UNDO_WINDOW,
        },
    )


@require_http_methods(["GET", "POST"])
def actual(request, pk):
    """Valor real de uma conta variável (RN-052)."""
    commitment = _commitment(pk)
    form = ActualForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        before = balances.position()
        try:
            services.set_actual_amount(
                commitment, amount=form.cleaned_data["amount"], expected_version=_version(request)
            )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Valor informado. {_effect(before)}")
            return redirect("payables:central")
    return _form_page(
        request,
        form,
        f"Valor real de {commitment.transaction.description}",
        version=commitment.version,
        submit="Salvar",
        back="payables:central",
    )


@require_http_methods(["GET", "POST"])
def schedule(request, pk):
    commitment = _commitment(pk)
    form = ScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.schedule(
                commitment,
                debit_date=form.cleaned_data["debit_date"],
                expected_version=_version(request),
            )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Agendado. No dia, o sistema pergunta se o débito aconteceu.")
            return redirect("payables:central")
    return _form_page(
        request,
        form,
        f"Agendar {commitment.transaction.description}",
        intro="Agendar não paga: a conta continua em aberto até você confirmar o débito.",
        version=commitment.version,
        submit="Agendar",
        back="payables:central",
    )


@require_POST
def unschedule(request, pk):
    try:
        services.unschedule(_commitment(pk), expected_version=_version(request))
        messages.success(request, "Agendamento removido. A conta voltou a pendente.")
    except LedgerError as exc:
        messages.error(request, str(exc))
    return redirect("payables:central")


def _reason_action(request, pk, action, title, intro, submit):
    commitment = _commitment(pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        before = balances.position()
        try:
            action(
                commitment,
                reason=form.cleaned_data["reason"],
                expected_version=_version(request),
            )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{submit} feito. {_effect(before)}")
            return redirect("payables:central")
    return _form_page(
        request,
        form,
        f"{title} {commitment.transaction.description}",
        intro=intro,
        version=commitment.version,
        submit=submit,
        danger=True,
        back="payables:central",
    )


@require_http_methods(["GET", "POST"])
def cancel(request, pk):
    return _reason_action(
        request,
        pk,
        services.cancel,
        "Cancelar",
        "Fica registrado como cancelado, com o motivo. Nada é apagado.",
        "Cancelamento",
    )


@require_http_methods(["GET", "POST"])
def close(request, pk):
    return _reason_action(
        request,
        pk,
        services.close,
        "Encerrar",
        "Para quando a conta veio menor: o que falta deixa de ser cobrado.",
        "Encerramento",
    )


@require_http_methods(["GET", "POST"])
def new_bill(request):
    form = BillForm(
        request.POST or None,
        initial={"value_type": "fixed", "installments": 1, "due_date": ledger.today()},
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        before = balances.position()
        common = {
            "description": data["description"],
            "category": data["category"],
            "account": data["account"],
            "payment_method": data["payment_method"] or None,
            "anticipates": data["anticipates"],
            "idempotency_key": data["idempotency_key"] or None,
        }
        try:
            if data["installments"] > 1:
                services.create_installments(
                    total=data["amount"],
                    count=data["installments"],
                    first_due=data["due_date"],
                    **common,
                )
            else:
                services.create_bill(
                    amount=data["amount"],
                    due_date=data["due_date"],
                    value_type=data["value_type"],
                    reference_month=data["reference_month"] or None,
                    **common,
                )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Conta salva. {_effect(before)}")
            return redirect("payables:central")
    return _form_page(request, form, "Nova conta", submit="Salvar", back="payables:central")


@require_http_methods(["GET", "POST"])
def new_income(request):
    form = IncomeForm(request.POST or None, initial={"due_date": ledger.today()})
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            services.create_income(
                description=data["description"],
                category=data["category"],
                account=data["account"],
                amount=data["amount"],
                due_date=data["due_date"],
                idempotency_key=data["idempotency_key"] or None,
            )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Receita prevista salva. Só conta depois que entrar.")
            return redirect("payables:central")
    return _form_page(
        request,
        form,
        "Nova receita prevista",
        intro="Receita prevista não entra no que você pode gastar até ser recebida.",
        submit="Salvar",
        back="payables:central",
    )


@require_GET
def calendar_view(request):
    today = ledger.today()
    first = presentation.parse_month(request.GET.get("mes"), today)
    try:
        day = int(request.GET.get("dia", ""))
    except ValueError:
        day = None
    context = presentation.month(first, day, today)
    context["holiday"] = Holiday.objects.filter(date=context["day"]).first()
    return render(request, "payables/calendar.html", context)


# Recorrências --------------------------------------------------------------------------


@require_GET
def recurrences(request):
    rules = list(
        RecurrenceRule.objects.filter(active=True).select_related("category", "category__parent")
    )
    rows = [presentation.rule_row(rule) for rule in rules]
    selected = None
    try:
        wanted = int(request.GET.get("r", ""))
    except ValueError:
        wanted = None
    for row in rows:
        if row["rule"].pk == wanted:
            selected = row
    selected = selected or (rows[0] if rows else None)
    dates = []
    if selected is not None:
        try:
            dates = recurrence.preview(selected["rule"], count=8, today=ledger.today())
        except LedgerError:
            dates = []
    return render(
        request,
        "payables/recurrences.html",
        {"rows": rows, "selected": selected, "dates": dates},
    )


def _draft(data, kind, start_date, base=None) -> RecurrenceRule:
    """Regra ainda não salva, só para calcular a prévia."""
    return RecurrenceRule(
        name=data["name"],
        kind=kind,
        frequency=data["frequency"],
        interval=data["interval"],
        day_rule=data["day_rule"],
        day_value=data["day_value"],
        amount_cents=data["amount"].cents,
        value_type=data.get("value_type") or "fixed",
        category=data.get("category") or (base.category if base else None),
        financial_account=data["account"],
        debt=base.debt if base else None,
        anticipates=data["anticipates"],
        start_date=start_date,
        end_date=data["end_date"],
        remaining_count=data["remaining_count"],
    )


def _signature(post) -> str:
    """Identifica o que foi visto na prévia: salvar outra coisa exige ver as datas de novo."""
    skip = {"csrfmiddlewaretoken", "previewed", "save"}
    text = "&".join(f"{k}={post.get(k)}" for k in sorted(post) if k not in skip)
    return hashlib.sha256(text.encode()).hexdigest()


def _rule_page(request, form, title, **extra):
    return render(request, "payables/recurrence_form.html", {"form": form, "title": title, **extra})


@require_http_methods(["GET", "POST"])
def recurrence_new(request):
    initial = {
        "start_date": ledger.today(),
        "frequency": Frequency.MONTHLY,
        "interval": 1,
        "value_type": "fixed",
    }
    if request.GET.get("tipo") == "salario":
        initial |= {
            "name": "Salário",
            "kind": "income",
            "day_rule": DayRule.NTH_BUSINESS_DAY,
            "day_value": 5,
            "category": by_key("salary"),
        }
    form = RuleForm(request.POST or None, initial=initial)
    dates = []
    signature = ""
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        signature = _signature(request.POST)
        try:
            draft = _draft(data, data["kind"], data["start_date"])
            dates = recurrence.preview(draft, count=12, today=ledger.today())
            if "save" in request.POST and request.POST.get("previewed") == signature:
                recurrence.create_rule(
                    name=data["name"],
                    kind=data["kind"],
                    amount=data["amount"],
                    frequency=data["frequency"],
                    day_rule=data["day_rule"],
                    day_value=data["day_value"],
                    interval=data["interval"],
                    start_date=data["start_date"],
                    account=data["account"],
                    category=data["category"],
                    value_type=data["value_type"],
                    end_date=data["end_date"],
                    remaining_count=data["remaining_count"],
                    anticipates=data["anticipates"],
                )
                messages.success(request, "Recorrência criada.")
                return redirect("payables:recurrences")
        except LedgerError as exc:
            form.add_error(None, str(exc))
            dates = []
    return _rule_page(request, form, "Nova recorrência", dates=dates, signature=signature)


@require_http_methods(["GET", "POST"])
def recurrence_edit(request, pk):
    rule = get_object_or_404(RecurrenceRule, pk=pk, active=True)
    initial = {
        "name": rule.name,
        "kind": rule.kind,
        "amount": presentation.num(Money(rule.amount_cents)),
        "frequency": rule.frequency,
        "interval": rule.interval,
        "day_rule": rule.day_rule,
        "day_value": rule.day_value,
        "category": rule.category,
        "account": rule.financial_account,
        "value_type": rule.value_type,
        "end_date": rule.end_date,
        "remaining_count": rule.remaining_count,
        "anticipates": rule.anticipates,
        "from_date": ledger.today(),
    }
    form = RuleEditForm(request.POST or None, initial=initial, rule=rule)
    dates = []
    signature = ""
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        signature = _signature(request.POST)
        try:
            draft = _draft(data, rule.kind, rule.start_date, base=rule)
            first = max(data["from_date"], ledger.today())
            dates = recurrence.preview(draft, count=12, today=first)
            if "save" in request.POST and request.POST.get("previewed") == signature:
                changes = {
                    "name": data["name"],
                    "amount_cents": data["amount"].cents,
                    "frequency": data["frequency"],
                    "interval": data["interval"],
                    "day_rule": data["day_rule"],
                    "day_value": data["day_value"],
                    "financial_account": data["account"],
                    "anticipates": data["anticipates"],
                    "end_date": data["end_date"],
                    "remaining_count": data["remaining_count"],
                }
                if rule.kind != "consortium":
                    changes |= {"category": data["category"], "value_type": data["value_type"]}
                recurrence.update_rule(
                    rule, from_date=data["from_date"], expected_version=_version(request), **changes
                )
                messages.success(request, "Recorrência alterada daqui para a frente.")
                return redirect("payables:recurrences")
        except LedgerError as exc:
            form.add_error(None, str(exc))
            dates = []
    return _rule_page(
        request,
        form,
        f"Alterar {rule.name}",
        dates=dates,
        signature=signature,
        version=rule.version,
    )


@require_http_methods(["GET", "POST"])
def recurrence_end(request, pk):
    rule = get_object_or_404(RecurrenceRule, pk=pk, active=True)
    if request.method == "POST":
        before = balances.position()
        try:
            recurrence.end_rule(rule, expected_version=_version(request))
        except LedgerError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Recorrência encerrada. {_effect(before)}")
        return redirect("payables:recurrences")
    return render(request, "payables/recurrence_end.html", {"rule": rule})


# Ajustes -------------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def money_settings(request):
    initial = {
        "minimum": presentation.num(balances.get_minimum()),
        "horizon_mode": prefs.get("horizon_mode", horizons.NEXT_SALARY),
    }
    form = MoneySettingsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        before = balances.position()
        try:
            balances.set_minimum(form.cleaned_data["minimum"] or Money(0))
            prefs.put("horizon_mode", form.cleaned_data["horizon_mode"])
            recurrence.promote_due()
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Ajustes salvos. {_effect(before)}")
            return redirect("payables:money_settings")
    return render(request, "payables/money_settings.html", {"form": form})


@require_http_methods(["GET", "POST"])
def holidays(request):
    today = ledger.today()
    try:
        year = int(request.GET.get("ano", today.year))
    except ValueError:
        year = today.year
    form = HolidayForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            calendar.add_holiday(
                data["date"],
                data["name"],
                affects_salary=data["affects_salary"],
                affects_banking=data["affects_banking"],
            )
        except LedgerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Feriado incluído. Os vencimentos em aberto foram revistos.")
            return redirect(f"{request.path}?ano={data['date'].year}")
    return render(
        request,
        "payables/holidays.html",
        {
            "form": form,
            "year": year,
            "previous": year - 1,
            "next": year + 1,
            "items": Holiday.objects.filter(date__year=year),
        },
    )


@require_POST
def holiday_remove(request, day):
    try:
        parsed = datetime.date.fromisoformat(day)
        calendar.remove_holiday(parsed)
        messages.success(request, "Feriado removido. Os vencimentos em aberto foram revistos.")
    except ValueError:
        messages.error(request, "Data inválida.")
    except LedgerError as exc:
        messages.error(request, str(exc))
    return redirect("payables:holidays")
