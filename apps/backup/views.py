"""Backup, restauração e saúde (F-100; security-plan.md §7)."""

import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.ledger.errors import LedgerError
from apps.ui.forms import StyledForm

from . import core, health, secrets
from .models import BackupRecord, RestoreTest


class PassphraseForm(StyledForm):
    password = forms.CharField(label="Sua senha de login", widget=forms.PasswordInput)
    passphrase = forms.CharField(
        label="Nova senha de backup (16+ caracteres)", widget=forms.PasswordInput
    )
    confirm = forms.CharField(label="Repita a senha de backup", widget=forms.PasswordInput)
    saved = forms.BooleanField(label="Guardei esta senha fora do sistema (papel ou cofre)")

    def clean(self):
        d = super().clean()
        if d.get("passphrase") != d.get("confirm"):
            raise forms.ValidationError("As senhas de backup não são iguais.")
        return d


class CloudForm(StyledForm):
    path = forms.CharField(
        label="Pasta sincronizada da nuvem",
        max_length=300,
        help_text=r"Ex.: %USERPROFILE%\Google Drive\Backups Finanças",
    )


class RestoreForm(StyledForm):
    name = forms.CharField(widget=forms.HiddenInput)
    password = forms.CharField(label="Sua senha de login", widget=forms.PasswordInput)
    passphrase = forms.CharField(label="Senha de backup", widget=forms.PasswordInput)
    confirm = forms.BooleanField(
        label="Entendo que os dados atuais serão substituídos (um backup deles é feito antes)",
        required=False,
    )


@require_http_methods(["GET"])
def index(request):
    return render(
        request,
        "backup/index.html",
        {
            "has_passphrase": secrets.has(secrets.BACKUP_PASSPHRASE),
            "cloud": core.cloud_dir(),
            "records": BackupRecord.objects.all()[:20],
            "tests": RestoreTest.objects.all()[:10],
            "available": core.available()[:30],
            "passphrase_form": PassphraseForm(),
            "cloud_form": CloudForm(initial={"path": core.cloud_dir() or ""}),
            "restore_form": RestoreForm(),
        },
    )


@require_POST
def set_passphrase(request):
    form = PassphraseForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "Confira os campos: " + " ".join(e for errs in form.errors.values() for e in errs),
        )
    elif not request.user.check_password(form.cleaned_data["password"]):
        messages.error(request, "Senha de login incorreta. Nada foi alterado.")
    else:
        try:
            secrets.validate_passphrase(form.cleaned_data["passphrase"])
            secrets.put(secrets.BACKUP_PASSPHRASE, form.cleaned_data["passphrase"])
            from apps.ledger import audit

            audit.record_event("backup_passphrase_set", "backup", 0)
            messages.success(
                request,
                "Senha de backup definida. Os próximos backups usam ela; "
                "backups antigos continuam com a senha antiga.",
            )
        except LedgerError as exc:
            messages.error(request, str(exc))
    return redirect("backup:index")


@require_POST
def set_cloud(request):
    form = CloudForm(request.POST)
    if form.is_valid():
        try:
            path = core.set_cloud_dir(form.cleaned_data["path"])
            messages.success(request, f"Pasta da nuvem: {path}")
        except LedgerError as exc:
            messages.error(request, str(exc))
    return redirect("backup:index")


@require_POST
def backup_now(request):
    try:
        record = core.create_backup("manual")
        msg = f"Backup {record.file_name} gravado e verificado."
        if record.message:
            msg += f" {record.message}"
        messages.success(request, msg)
    except LedgerError as exc:
        messages.error(request, f"Backup falhou: {exc}")
    return redirect("backup:index")


@require_POST
def test_restore(request):
    """Modo teste: restaura num arquivo temporário e verifica, sem tocar nos dados."""
    try:
        entry = core.find(request.POST.get("name", ""))
        passphrase = request.POST.get("passphrase") or None
        test = core.test_restore(
            entry, passphrase=passphrase, kind="manual" if passphrase else "auto"
        )
        counts = test.details_json["counts"]
        messages.success(
            request,
            f"Restauração em teste OK: {counts['ledger_transaction']} "
            f"transações, {counts['financial_account']} contas.",
        )
    except LedgerError as exc:
        messages.error(request, f"Teste de restauração falhou: {exc}")
    return redirect("backup:index")


PREVIEW_KEY = "backup_restore_preview"


@require_POST
def restore(request):
    """Dois passos (security-plan.md §7.2): 1) restaura em arquivo temporário e mostra o
    resumo; 2) com a confirmação, substitui os dados. As duas etapas pedem as senhas."""
    form = RestoreForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe a senha de login e a senha de backup.")
        return redirect("backup:index")
    if not request.user.check_password(form.cleaned_data["password"]):
        messages.error(request, "Senha de login incorreta. Nada foi alterado.")
        return redirect("backup:index")
    name = form.cleaned_data["name"]
    passphrase = form.cleaned_data["passphrase"]
    if not form.cleaned_data["confirm"]:
        try:
            test = core.test_restore(core.find(name), passphrase=passphrase, kind="manual")
        except LedgerError as exc:
            messages.error(request, f"Nada foi substituído: {exc}")
            return redirect("backup:index")
        request.session[PREVIEW_KEY] = name
        details = test.details_json
        created = datetime.datetime.fromisoformat(details["created_at"])
        last = details["summary"]["last"]
        return render(
            request,
            "backup/restore_confirm.html",
            {
                "name": name,
                "details": details,
                "created": created.strftime("%d/%m/%Y %H:%M"),
                "last_date": datetime.date.fromisoformat(last["date"]).strftime("%d/%m/%Y")
                if last
                else None,
                "form": RestoreForm(initial={"name": name}),
            },
        )
    if request.session.get(PREVIEW_KEY) != name:
        messages.error(request, "Veja o resumo do backup antes de confirmar a restauração.")
        return redirect("backup:index")
    try:
        entry = core.find(name)
        core.restore_live(entry, passphrase=passphrase)
    except LedgerError as exc:
        messages.error(request, f"Nada foi substituído: {exc}")
        return redirect("backup:index")
    logout(request)  # sessões e aparelhos vêm do backup; entre de novo
    messages.success(request, f"Dados restaurados de {entry.name}. Entre com a senha.")
    return redirect("security:login")


@require_http_methods(["GET"])
def health_view(request):
    data = health.report()
    data["level"] = health.level(data["issues"])
    return render(request, "backup/health.html", data)
