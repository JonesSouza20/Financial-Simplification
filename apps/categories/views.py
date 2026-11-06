"""Categorias: lista padrão editável (F-013 §13; RF-CAT-01 a 03)."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.ledger.errors import LedgerError
from apps.ui.forms import StyledForm

from . import services
from .models import Category, CategoryKind


class CategoryForm(StyledForm):
    name = forms.CharField(label="Nome", max_length=60)
    kind = forms.ChoiceField(label="Tipo", choices=CategoryKind.choices)
    parent = forms.ModelChoiceField(
        label="Dentro de",
        required=False,
        empty_label="(categoria principal)",
        queryset=Category.objects.none(),
    )
    accepts_benefit = forms.BooleanField(label="Aceita pagamento com VR/VA", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = Category.objects.filter(
            parent__isnull=True, is_system=False, archived_at__isnull=True
        )


@require_http_methods(["GET", "POST"])
def list_view(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.create(**form.cleaned_data)
            messages.success(request, "Categoria criada.")
            return redirect("categories:list")
        except LedgerError as exc:
            form.add_error(None, str(exc))
    roots = (
        Category.objects.filter(parent__isnull=True, archived_at__isnull=True)
        .prefetch_related("children")
        .order_by("kind", "is_system", "sort_order", "name")
    )
    return render(request, "categories/list.html", {"roots": roots, "form": form})


@require_POST
def rename(request, pk):
    category = get_object_or_404(Category, pk=pk)
    try:
        services.rename(category, request.POST.get("name", ""))
        messages.success(request, "Categoria renomeada.")
    except LedgerError as exc:
        messages.error(request, str(exc))
    return redirect("categories:list")


@require_POST
def archive(request, pk):
    category = get_object_or_404(Category, pk=pk)
    try:
        services.archive(category)
        messages.success(request, f"Categoria “{category.name}” arquivada. O histórico continua.")
    except LedgerError as exc:
        messages.error(request, str(exc))
    return redirect("categories:list")
