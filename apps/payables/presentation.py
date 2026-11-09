"""Como saldos e compromissos viram linhas, barras e faixas (F-034, F-035; design-study.md).

Nada aqui calcula saldo: tudo vem de `balances.position` e de `payables.services`.
"""

from __future__ import annotations

import calendar as month_calendar
import datetime
from dataclasses import dataclass

from django.db.models import Sum
from django.urls import reverse

from apps.balances import services as balances
from apps.calendar_br import services as calendar
from apps.calendar_br.services import CalendarMissingError
from apps.cards import services as cards
from apps.categories.models import Category
from apps.debts import services as debts
from apps.ledger.models import EFFECTIVE_STATUSES, LedgerPosting, TransactionStatus
from apps.money import Money
from apps.ui import models as prefs

from . import horizon as horizons
from . import services
from .models import Commitment, CommitmentKind, DayRule, Direction, Frequency, RecurrenceRule

GROUP_TILES = {"Moradia": "tile-c1", "Contas da casa": "tile-c2", "Alimentação": "tile-c3"}
ICONS = {
    "Luz": "bolt",
    "Água": "drop",
    "Gás": "flame",
    "Internet": "wifi",
    "Celular": "phone",
    "Moradia": "home",
    "Aluguel": "home",
    "Alimentação": "meal",
    "Mercado": "market",
    "Transporte": "bus",
}
LATER_DAYS = 60
LABEL_WIDTH_PERCENT = 20  # largura aproximada de uma etiqueta na linha do tempo
LABEL_HEIGHT = 44
MONTHS = 24  # o calendário navega até dois anos para cada lado


@dataclass(frozen=True)
class Row:
    name: str
    when: str
    amount: Money
    icon: str = "other"
    tile: str = ""
    approx: bool = False  # valor estimado: mostra ≈
    tag: str = ""
    overdue: bool = False
    status: str = ""
    action_url: str = ""
    action_label: str = ""
    paid_percent: int | None = None
    due_date: datetime.date | None = None
    incoming: bool = False


def relative(due: datetime.date, today: datetime.date) -> str:
    days = (due - today).days
    if days < 0:
        return "Venceu ontem" if days == -1 else f"Venceu há {-days} dias"
    if days == 0:
        return "Hoje"
    if days == 1:
        return "Amanhã"
    return f"Em {days} dias"


def num(amount: Money) -> str:
    return amount.format_brl().replace("R$ ", "")


def _mark(commitment: Commitment) -> tuple[str, str]:
    """Ícone e cor da conta, pela categoria."""
    if commitment.kind == CommitmentKind.CONSORTIUM:
        return "car", ""
    if commitment.direction == Direction.IN:
        return "income", ""
    category = services.category_of(commitment)
    group = category.parent.name if category.parent_id else category.name
    return ICONS.get(category.name) or ICONS.get(group) or "other", GROUP_TILES.get(group, "")


def _when(commitment: Commitment, today: datetime.date) -> str:
    if services.status(commitment, today) == services.SCHEDULED:
        return f"Agendado para {commitment.scheduled_debit_date:%d/%m}"
    if commitment.direction == Direction.IN and commitment.due_date >= today:
        return relative(commitment.due_date, today)
    when = relative(commitment.due_date, today)
    if commitment.effective_due_date != commitment.due_date:
        when += f", pode pagar até {commitment.effective_due_date:%d/%m}"
    return when


def commitment_row(commitment: Commitment, today: datetime.date) -> Row:
    icon, tile = _mark(commitment)
    status = services.status(commitment, today)
    forecast = commitment.transaction.status == TransactionStatus.FORECAST
    variable = commitment.value_type == "variable"
    settled = services.settled_cents(commitment)
    incoming = commitment.direction == Direction.IN
    if forecast and variable and not incoming:
        url, label = reverse("payables:actual", args=[commitment.pk]), "Informar"
    else:
        label = "Recebi" if incoming else "Pagar"
        url = reverse("payables:pay", args=[commitment.pk])
    words = {services.OVERDUE: "Atrasado", services.PARTIAL: "Pago em parte"}
    return Row(
        name=commitment.transaction.description,
        when=_when(commitment, today),
        amount=services.open_amount(commitment),
        icon=icon,
        tile=tile,
        approx=forecast and variable,
        tag="estimativa" if forecast and variable else "",
        overdue=status == services.OVERDUE,
        status=words.get(status, ""),
        action_url=url,
        action_label=label,
        paid_percent=(
            (settled * 100 + commitment.planned_amount_cents // 2)
            // commitment.planned_amount_cents
            if settled and commitment.planned_amount_cents
            else None
        ),
        due_date=commitment.due_date,
        incoming=incoming,
    )


def invoice_row(card, invoice, today: datetime.date) -> Row:
    return Row(
        name=f"Fatura {card.name}",
        when=relative(invoice.due_date, today),
        amount=invoice.amount,
        icon="card",
        tag="estimativa",
        overdue=invoice.overdue,
        status="Atrasado" if invoice.overdue else "",
        action_url=reverse("cards:detail", args=[card.pk]),
        action_label="Pagar",
        due_date=invoice.due_date,
    )


def _planned(direction: str, **filters) -> list[Commitment]:
    candidates = Commitment.objects.filter(
        direction=direction,
        transaction__status__in=services.PLANNED,
        closed_at__isnull=True,
        **filters,
    ).select_related("transaction", "recurrence")
    return [c for c in candidates if services.is_open(c)]


def _invoice_rows(today: datetime.date, until: datetime.date, since=None) -> list[Row]:
    rows = []
    for card in cards.active_cards():
        for invoice in cards.estimate(card, today):
            if not invoice.amount.is_positive or invoice.due_date >= until:
                continue
            if since is None or invoice.due_date >= since:
                rows.append(invoice_row(card, invoice, today))
    return rows


def horizon_words(p: balances.Position, salary: Commitment | None) -> str:
    """Como a tela chama o fim do período do "Pode gastar"."""
    if p.salary_late:
        return "amanhã"
    if salary is not None and salary.due_date == p.horizon:
        return "o salário"
    return "o fim do mês"


def central(today: datetime.date) -> dict:
    """Agrupa por quando agir: atrasados, esta semana, até o horizonte, depois dele."""
    p = balances.position(today)
    until = today + datetime.timedelta(days=LATER_DAYS)
    rows = [commitment_row(c, today) for c in _planned(Direction.OUT, due_date__lt=until)]
    rows += _invoice_rows(today, until)
    rows.sort(key=lambda r: r.due_date)
    week_end = today + datetime.timedelta(days=7)
    overdue, week, until_salary, later = [], [], [], []
    for row in rows:
        if row.overdue:
            overdue.append(row)
        elif row.due_date >= p.horizon:
            later.append(row)
        elif row.due_date < week_end:
            week.append(row)
        else:
            until_salary.append(row)
    salary = horizons.oldest_open_salary()
    incomes = [
        commitment_row(c, today)
        for c in _planned(Direction.IN, due_date__lt=until)
        if salary is None or c.pk != salary.pk
    ]
    to_pay = [*overdue, *week, *until_salary]
    words = horizon_words(p, salary)
    return {
        "position": p,
        "words": words,
        "after_words": "de amanhã" if p.salary_late else f"d{words}",
        "overdue": overdue,
        "week": week,
        "until_salary": until_salary,
        "later": later,
        "later_total": Money.sum([r.amount for r in later]),
        "later_icons": later[:4],
        "salary": commitment_row(salary, today) if salary else None,
        "incomes": incomes,
        "to_pay": Money.sum([r.amount for r in to_pay]),
        "to_pay_approx": any(r.approx for r in to_pay),
        "days": day_strip(rows, salary, today),
        "last_day": today + datetime.timedelta(days=30),
        "empty": not rows,
    }


def _is_closed(day: datetime.date) -> bool:
    try:
        return not calendar.is_business_day(day)
    except CalendarMissingError:
        return day.weekday() >= 5


def day_strip(rows: list[Row], salary, today: datetime.date, days: int = 31) -> list[str]:
    """Classe de cada um dos próximos dias na faixa da central."""
    estimated = {r.due_date for r in rows if r.approx}
    bills = {r.due_date for r in rows} - estimated
    out = []
    for offset in range(days):
        day = today + datetime.timedelta(days=offset)
        if salary is not None and day == salary.due_date:
            css = "pay"
        elif day in bills:
            css = "bill"
        elif day in estimated:
            css = "est"
        elif _is_closed(day):
            css = "wknd"
        else:
            css = ""
        out.append(f"{css} now".strip() if offset == 0 else css)
    return out


# Início --------------------------------------------------------------------------------


def _share(part: int, total: int) -> int:
    """Percentual arredondado, só com inteiros."""
    return (part * 100 + total // 2) // total


def _short(amount: Money, estimated: bool) -> str:
    return f"≈{num(amount).removesuffix(',00')}" if estimated else num(amount)


def _money_lines(p: balances.Position) -> list:
    """Linhas fixas e estimadas da barra: no máximo quatro, para continuar legível."""
    lines = [*p.invoices, *p.pending]
    if len(lines) <= 4:
        return lines
    lines.sort(key=lambda line: -line.amount.cents)
    rest = Money.sum([line.amount for line in lines[3:]])
    return [
        *lines[:3],
        balances.Line(label=f"Outras {len(lines) - 3} contas", amount=rest, due_date=p.today),
    ]


def money_bar(p: balances.Position) -> list[dict]:
    """Segmentos da barra do dinheiro. Cor nunca sozinha: o texto descreve a barra inteira."""
    parts = [("seg-comp", line.label, line.amount, False) for line in _money_lines(p)]
    parts += [("seg-est", line.label, line.amount, True) for line in p.estimates]
    if p.state == balances.UNCOVERED:
        parts.append(("seg-crit", "Faltam", p.shortfall, False))
    else:
        kept = p.minimum if p.state != balances.BELOW_MINIMUM else p.minimum - p.shortfall
        if kept.is_positive:
            parts.append(("seg-min", "Mínimo", kept, False))
        if p.can_spend.is_positive:
            parts.append(("seg-free", "Livre para gastar", p.can_spend, False))
    total = sum(amount.cents for _, _, amount, _ in parts)
    if not total:
        return []
    return [
        {
            "css": css,
            "name": name,
            "value": _short(amount, estimated),
            "percent": max(_share(amount.cents, total), 1),
            "text": amount.cents * 20 >= total,
        }
        for css, name, amount, estimated in parts
    ]


def legend(p: balances.Position) -> list[dict]:
    """Legenda da barra no celular, onde não cabe texto dentro dela."""
    items = []
    if p.committed.is_positive:
        items.append({"css": "seg-comp", "name": "Já tem dono", "value": num(p.committed)})
    if p.estimated_total.is_positive:
        items.append(
            {"css": "seg-est", "name": "Estimativas", "value": _short(p.estimated_total, True)}
        )
    if p.state == balances.UNCOVERED:
        items.append({"css": "seg-crit", "name": "Faltam", "value": num(p.shortfall)})
        return items
    kept = p.minimum if p.state != balances.BELOW_MINIMUM else p.minimum - p.shortfall
    if kept.is_positive:
        items.append({"css": "seg-min", "name": "Mínimo", "value": num(kept)})
    if p.can_spend.is_positive:
        items.append({"css": "seg-free", "name": "Livre", "value": num(p.can_spend)})
    return items


def _line_url(line) -> str:
    if line.commitment is not None:
        return reverse("payables:pay", args=[line.commitment.pk])
    if line.card is not None:
        return reverse("cards:detail", args=[line.card.pk])
    return ""


def calculation(p: balances.Position) -> list[dict]:
    """Passo a passo do "Como calculamos" (F-071: cada termo leva à origem)."""
    row = lambda label, amount, **extra: {"label": label, "amount": amount, **extra}  # noqa: E731
    rows = [row("Contas livres", p.free, url=reverse("ui:origin", args=["livre"]))]
    for line in [*p.invoices, *p.pending]:
        rows.append(row(line.label, -line.amount, estimated=line.estimated, url=_line_url(line)))
    rows.append(row("Disponível", p.available, total=True))
    for line in p.estimates:
        rows.append(row(line.label, -line.amount, estimated=True, url=_line_url(line)))
    if p.minimum.is_positive:
        rows.append(row("Mínimo de segurança", -p.minimum))
    rows.append(row("Pode gastar", p.can_spend, strong=True))
    return rows


def _snap(value: int) -> int:
    """As alturas viram classes de CSS de 4 em 4 px (a CSP não permite estilo inline)."""
    return (value + 2) // 4 * 4


def timeline(p: balances.Position, salary: Commitment | None, words: str) -> dict:
    """Linha do tempo até o horizonte: barras pelo valor, etiquetas sem se sobrepor."""
    lines = sorted(
        (line for line in [*p.pending, *p.invoices, *p.estimates] if line.due_date >= p.today),
        key=lambda line: line.due_date,
    )[:6]
    span = max((p.horizon - p.today).days, 1)
    largest = max((line.amount.cents for line in lines), default=1)
    placed: list[tuple[int, int, int]] = []
    points = []
    for line in lines:
        percent = min((line.due_date - p.today).days * 100 // span, 100)
        height = _snap(max(line.amount.cents * 56 // largest, 8))
        right = percent > 55
        start, end = (
            (percent - LABEL_WIDTH_PERCENT, percent)
            if right
            else (percent, percent + LABEL_WIDTH_PERCENT)
        )
        top = height + 8
        clashes = [
            other_top
            for other_start, other_end, other_top in placed
            if start < other_end and other_start < end
        ]
        while any(abs(top - other) < LABEL_HEIGHT for other in clashes):
            top = max(other for other in clashes if abs(top - other) < LABEL_HEIGHT) + LABEL_HEIGHT
        top = _snap(top)
        placed.append((start, end, top))
        points.append(
            {
                "name": line.label,
                "amount": _short(line.amount, line.estimated)
                if line.commitment
                else num(line.amount),
                "tag": line.estimated and line.commitment is not None,
                "left": percent,
                "height": height,
                "right": right,
                "top": top,
                "days": relative(line.due_date, p.today).lower(),
            }
        )
    bottom = max((top for _, _, top in placed), default=0) + LABEL_HEIGHT
    summary = "; ".join(f"{pt['name']} {pt['amount']}, {pt['days']}" for pt in points)
    return {
        "points": points,
        "height": _snap(94 + bottom + 8),
        "salary": commitment_row(salary, p.today) if salary and words == "o salário" else None,
        "summary": summary,
    }


def next_rows(today: datetime.date, p: balances.Position, count: int = 3) -> list[Row]:
    """Lista que substitui a linha do tempo no celular."""
    rows = [commitment_row(c, today) for c in _planned(Direction.OUT, due_date__lt=p.horizon)]
    rows += _invoice_rows(today, p.horizon)
    rows.sort(key=lambda r: r.due_date)
    return rows[:count]


def categories_summary(today: datetime.date) -> dict:
    """Para onde foi o dinheiro no mês: três maiores grupos e Outros (RN-161)."""
    rows = (
        LedgerPosting.objects.filter(
            account__kind="expense",
            transaction__status__in=EFFECTIVE_STATUSES,
            transaction__competence_date__gte=today.replace(day=1),
            transaction__competence_date__lte=today,
        )
        .values("account_id")
        .annotate(total=Sum("amount_cents"))
    )
    names = {
        c.ledger_account_id: (c.parent.name if c.parent_id else c.name)
        for c in Category.objects.select_related("parent")
    }
    by_group: dict[str, int] = {}
    for row in rows:
        group = names.get(row["account_id"], "Outros")
        by_group[group] = by_group.get(group, 0) + row["total"]
    positive = sorted(
        ((name, cents) for name, cents in by_group.items() if cents > 0),
        key=lambda item: -item[1],
    )
    total = sum(cents for _, cents in positive)
    if not total:
        return {"total": Money(0), "items": [], "month": today}
    items = [
        {"name": name, "percent": _share(cents, total), "css": f"fill-c{index + 1}"}
        for index, (name, cents) in enumerate(positive[:3])
    ]
    if positive[3:]:
        items.append(
            {
                "name": "Outros",
                "percent": max(100 - sum(i["percent"] for i in items), 0),
                "css": "fill-c4",
            }
        )
    return {"total": Money(total), "items": items, "month": today}


def _tenths_text(tenths: int) -> str:
    """Percentual em décimos, sem ponto flutuante: 75 vira "7,5%"; 80 vira "8%"."""
    whole, decimal = divmod(tenths, 10)
    return f"{whole},{decimal}%" if decimal else f"{whole}%"


def debts_summary() -> dict:
    """Total devido e barras: quitação do empréstimo e uso do limite do cartão."""
    rows = []
    total = Money(0)
    for debt in debts.active():
        if debt.kind != "loan":
            continue
        balance = debts.balance(debt)
        total = total + balance
        original = debt.original_amount_cents or 0
        paid = (
            (max(original - balance.cents, 0) * 1000 + original // 2) // original
            if original
            else None
        )
        rows.append(
            {
                "name": debt.description,
                "balance": balance,
                "url": reverse("debts:detail", args=[debt.pk]),
                "note": f"{_tenths_text(paid)} quitado" if paid is not None else "",
                "percent": (paid + 5) // 10 if paid is not None else None,
                "done": True,
            }
        )
    for card in cards.active_cards():
        balance = cards.liability(card)
        if not balance.is_positive:
            continue
        total = total + balance
        limit = card.credit_limit_cents
        used = min((balance.cents * 1000 + limit // 2) // limit, 1000)
        rows.append(
            {
                "name": card.name,
                "balance": balance,
                "url": reverse("cards:detail", args=[card.pk]),
                "note": f"{_tenths_text(used)} do limite",
                "percent": (used + 5) // 10,
                "done": False,
            }
        )
    return {"total": total, "rows": rows}


def attention(today: datetime.date, overdue: int = 0) -> list[dict]:
    """Bloco de atenção do Início, do mais grave ao menos (F-032, F-070; RN-023, RN-094)."""
    items = []
    if overdue:
        text = "1 conta atrasada." if overdue == 1 else f"{overdue} contas atrasadas."
        items.append({"text": text, "url": reverse("payables:central"), "action": "Ver"})
    for c in Commitment.objects.filter(
        transaction__status=TransactionStatus.PENDING,
        closed_at__isnull=True,
        scheduled_debit_date__lte=today,
    ).select_related("transaction"):
        if services.is_open(c):
            items.append(
                {
                    "text": f"Débito agendado de {c.transaction.description}: aconteceu?",
                    "url": reverse("payables:pay", args=[c.pk]),
                    "action": "Sim",
                    "no_url": reverse("payables:unschedule", args=[c.pk]),
                }
            )
    salary = horizons.oldest_open_salary()
    for c in services.late_incomes(today):
        if salary is None or c.pk != salary.pk:
            items.append(
                {
                    "text": f"{c.transaction.description} ainda não entrou.",
                    "url": reverse("payables:pay", args=[c.pk]),
                    "action": "Recebi",
                }
            )
    if calendar.needs_yearly_review(today):
        items.append(
            {
                "text": "Dezembro: revise os feriados do próximo ano.",
                "url": reverse("payables:holidays"),
                "action": "Revisar",
            }
        )
    return items


def home(today: datetime.date) -> dict:
    p = balances.position(today)
    salary = horizons.oldest_open_salary()
    words = horizon_words(p, salary)
    overdue = sum(1 for r in central(today)["overdue"])
    return {
        "p": p,
        "words": words,
        "salary": commitment_row(salary, today) if salary else None,
        "no_salary": salary is None,
        "month_mode": prefs.get("horizon_mode", horizons.NEXT_SALARY) == horizons.MONTH_END,
        "left_after_bills": p.minimum - p.shortfall,
        "bar": money_bar(p),
        "bar_text": ", ".join(f"{s['name']} {s['value']}" for s in money_bar(p)),
        "legend": legend(p),
        "calculation": calculation(p),
        "timeline": timeline(p, salary, words),
        "next_rows": next_rows(today, p),
        "debts": debts_summary(),
        "categories": categories_summary(today),
        "attention": attention(today, overdue),
    }


# Calendário ----------------------------------------------------------------------------


def parse_month(text: str | None, today: datetime.date) -> datetime.date:
    """AAAA-MM válido e dentro da janela; qualquer outra coisa volta para o mês atual."""
    current = today.replace(day=1)
    try:
        year, month = (int(part) for part in (text or "").split("-"))
        first = datetime.date(year, month, 1)
    except ValueError:
        return current
    low, high = calendar.add_months(current, -MONTHS), calendar.add_months(current, MONTHS)
    return first if low <= first <= high else current


def _month_rows(first: datetime.date, today: datetime.date) -> dict[datetime.date, list[Row]]:
    next_month = calendar.add_months(first, 1, day=1)
    span = {"due_date__gte": first, "due_date__lt": next_month}
    rows = [commitment_row(c, today) for c in _planned(Direction.OUT, **span)]
    rows += [commitment_row(c, today) for c in _planned(Direction.IN, **span)]
    rows += _invoice_rows(today, next_month, since=first)
    by_day: dict[datetime.date, list[Row]] = {}
    for row in rows:
        by_day.setdefault(row.due_date, []).append(row)
    return by_day


def month(first: datetime.date, selected_day: int | None, today: datetime.date) -> dict:
    """Grade do mês, começando na segunda, com a lista do dia escolhido (F-035)."""
    by_day = _month_rows(first, today)
    last = month_calendar.monthrange(first.year, first.month)[1]
    default = today.day if (today.year, today.month) == (first.year, first.month) else 1
    chosen = selected_day if selected_day and 1 <= selected_day <= last else default
    cells: list[dict] = [{"blank": True}] * first.weekday()
    for number in range(1, last + 1):
        day = first.replace(day=number)
        rows = by_day.get(day, [])
        marks = ["g" if r.incoming else ("e" if r.approx else "c") for r in rows][:3]
        cells.append(
            {
                "number": number,
                "marks": marks,
                "closed": _is_closed(day),
                "selected": number == chosen,
                "today": day == today,
                "count": len(rows),
            }
        )
    cells += [{"blank": True}] * ((7 - len(cells) % 7) % 7)
    day = first.replace(day=chosen)
    rows = by_day.get(day, [])
    return {
        "first": first,
        "day": day,
        "cells": cells,
        "rows": rows,
        "to_pay": Money.sum([r.amount for r in rows if not r.incoming]),
        "to_receive": Money.sum([r.amount for r in rows if r.incoming]),
        "previous": calendar.add_months(first, -1),
        "next": calendar.add_months(first, 1),
        "weekdays": ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"],
    }


# Recorrências --------------------------------------------------------------------------


def describe_rule(rule: RecurrenceRule) -> str:
    """Regra em uma frase: "Todo 5º dia útil", "Todo dia 10"."""
    if rule.frequency == Frequency.WEEKLY:
        when = "Toda semana" if rule.interval == 1 else f"A cada {rule.interval} semanas"
    else:
        if rule.day_rule == DayRule.NTH_BUSINESS_DAY:
            when = f"Todo {rule.day_value}º dia útil"
        elif rule.day_rule == DayRule.LAST_DAY:
            when = "Todo último dia"
        else:
            when = f"Todo dia {rule.day_value}"
        if rule.frequency == Frequency.YEARLY:
            when += ", uma vez por ano"
        elif rule.frequency == Frequency.EVERY_N_MONTHS and rule.interval > 1:
            when += f", a cada {rule.interval} meses"
    if rule.remaining_count:
        when += f" · {rule.remaining_count} ocorrências"
    return when


def rule_row(rule: RecurrenceRule) -> dict:
    icon, tile = "other", ""
    if rule.kind == CommitmentKind.CONSORTIUM:
        icon = "car"
    elif rule.kind == CommitmentKind.INCOME:
        icon = "income"
    elif rule.category is not None:
        group = rule.category.parent.name if rule.category.parent_id else rule.category.name
        icon = ICONS.get(rule.category.name) or ICONS.get(group) or "other"
        tile = GROUP_TILES.get(group, "")
    return {
        "rule": rule,
        "icon": icon,
        "tile": tile,
        "when": describe_rule(rule),
        "amount": Money(rule.amount_cents),
        "incoming": rule.kind == CommitmentKind.INCOME,
        "variable": rule.value_type == "variable",
    }
