from django.dispatch import Signal

# Enviado quando a tabela de feriados muda: vencimentos em aberto são recalculados.
holidays_changed = Signal()
