"""Lista padrão de categorias (functional-specification.md §14) e de sistema (business-rules.md §2).

Formato: (nome, [subcategorias], aceita_benefício, chave_de_sistema).
"""

EXPENSES = [
    ("Moradia", ["Aluguel", "Condomínio", "Manutenção"], False, None),
    ("Contas da casa", ["Luz", "Água", "Gás", "Internet", "Celular"], False, None),
    ("Alimentação", ["Mercado", "Restaurantes", "Delivery"], False, None),
    (
        "Transporte",
        [
            "Combustível",
            "Aplicativo",
            "Transporte público",
            "Estacionamento",
            "Manutenção do veículo",
        ],
        False,
        None,
    ),
    ("Saúde", ["Plano de saúde", "Farmácia", "Consultas"], False, None),
    ("Educação", [], False, None),
    ("Lazer", [], False, None),
    ("Compras", ["Eletrônicos", "Vestuário", "Casa"], False, None),
    ("Assinaturas", [], False, None),
    ("Cuidados pessoais", [], False, None),
    ("Presentes e doações", [], False, None),
    ("Impostos e taxas", [], False, None),
    ("Pets", [], False, None),
    ("Outros", [], False, None),
]

# Subcategorias que aceitam pagamento com VR/VA (RN-186).
BENEFIT_SUBCATEGORIES = {"Mercado", "Restaurantes", "Delivery"}

SYSTEM_EXPENSES = [
    ("Encargos de cartão", "card_charges"),
    ("Juros de dívidas", "debt_interest"),
    ("Encargos de dívidas", "debt_charges"),
    ("Juros e multas por atraso", "late_fees"),
    ("Perdas com valores a receber", "receivable_losses"),
    ("Consórcio", "consortium"),
]

INCOMES = [
    ("Salário", "salary"),
    ("Renda extra", None),
    ("13º e férias", None),
    ("Freelance", None),
    ("Reembolsos", None),
    ("Restituição de imposto", None),
    ("Benefícios", "benefit_income"),
    ("Rendimentos", "reserve_yield"),
    ("Outras receitas", None),
]

# Receitas com chave são de sistema (não arquiváveis): usadas por T04 e T22.
SYSTEM_INCOME_KEYS = {"benefit_income", "reserve_yield"}
