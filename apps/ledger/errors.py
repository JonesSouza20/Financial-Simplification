"""Erros do Ledger, com mensagens em pt-BR prontas para a interface."""


class LedgerError(Exception):
    """Operação recusada pelas regras do Ledger."""


class InvalidTransactionError(LedgerError):
    """Dados da transação inválidos (pernas, datas, valores, contas)."""


class InvalidStateError(LedgerError):
    """A transação não está num estado que permite a operação."""


class AlreadyReversedError(InvalidStateError):
    """A transação já foi estornada (I-03)."""


class ReversalLimitError(LedgerError):
    """Estornos parciais ultrapassariam o valor original (RN-121)."""


class IdempotencyConflictError(LedgerError):
    """A chave de idempotência já foi usada por outra operação."""


class ConcurrentEditError(LedgerError):
    """O item foi alterado em outro aparelho (RN-172)."""
