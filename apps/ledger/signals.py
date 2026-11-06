"""Sinais do Ledger para módulos que mantêm alocações sobre ativos e passivos (ADR-034)."""

from django.dispatch import Signal

# Enviado dentro da transação de banco, depois de gravar um estorno total ou parcial.
# Argumentos: original (LedgerTransaction), reversal (LedgerTransaction).
transaction_reversed = Signal()

# Enviado dentro da transação de banco, logo depois de finalizar qualquer transação nova
# (registro, estorno ou correção). Argumento: transaction (LedgerTransaction).
transaction_created = Signal()
