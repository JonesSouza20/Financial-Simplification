# Cenários Financeiros de Referência

| Campo | Valor |
|---|---|
| Versão | 0.1 |
| Data | 06/11/2026 |
| Etapa | 4 — Especificação (Fase B) |
| Status | Aprovado pelo usuário em 06/11/2026 (Fase B) |
| Documentos relacionados | `business-rules.md`, `testing-plan.md`, `database-design.md` |

Especificação executável. Cada cenário vira um teste automatizado (`testing-plan.md`, §5) e é critério das portas de validação. Todos os valores estão em reais, exatos ao centavo. Os cálculos foram conferidos com aritmética decimal exata (`ROUND_HALF_UP`, 28 dígitos).

Notação das pernas: `+` débito, `−` crédito (RN-002). Cada transação soma zero.

---

## Cadastro comum

Usado pelos cenários, salvo indicação em contrário.

**Contas financeiras**

| Conta | Classe |
|---|---|
| Corrente | livre |
| Digital | livre |
| Espécie | livre |
| Reserva | reserva |
| VR/VA | benefício |

**Cartões**

| Cartão | Limite total | Fechamento | Vencimento | Ciclo (RN-070, RN-071) |
|---|---|---|---|---|
| Cartão A | 5.000,00 | dia 25 | dia 5 | Fatura com vencimento 05/12/2026 cobre compras de 25/10 a 24/11 e fecha em 25/11 |
| Cartão B | 3.000,00 | dia 1 | dia 10 | Fatura com vencimento 10/12/2026 cobre compras de 01/11 a 30/11 e fecha em 01/12 |

**Pessoas:** Ana, Bruno.

**Salário:** 5.000,00 líquidos no 5º dia útil (RN-091): 09/11/2026 e 07/12/2026.

**Calendário relevante:**

| Data | Situação |
|---|---|
| 02/11/2026 (seg) | Finados |
| 15/11/2026 (dom) | Proclamação da República, domingo |
| 20/11/2026 (sex) | Consciência Negra, feriado nacional |
| 05/12/2026 | Sábado |
| 10/01/2027 | Domingo |

---

## S00 — Abertura por itens em 01/11/2026

**Regras:** RN-089, T23 a T26, ADR-031.

**Entrada**
- Saldos das contas: Corrente 2.500,00; Digital 800,00; Espécie 150,00; Reserva 0,00; VR/VA 420,00.
- Cartão A, itens de abertura:

| Item | Descrição | Valor | Alocação |
|---|---|---|---|
| A1 | Fatura fechada com vencimento 05/11/2026 | 1.230,00 | Fatura 05/11 (já faturado) |
| A2 | Compras na fatura aberta, próprias | 340,00 | Fatura 05/12 |
| A3 | TV comprada em 15/06/2026, 2.400,00 em 10x de 240,00; 5 parcelas já faturadas | 1.200,00 (parcelas 6 a 10) | Faturas 05/12, 05/01, 05/02, 05/03, 05/04 |

- Empréstimo: saldo devedor 10.000,00; 2% ao mês; 12 parcelas restantes; vencimento dia 15; próxima em 15/11/2026.
- Consórcio: 40 parcelas restantes de 650,00, vencimento dia 20, a partir de 20/11/2026.
- Recorrências:

| Conta | Valor | Vencimento | Tipo |
|---|---|---|---|
| Aluguel | 1.500,00 | dia 10 | fixo |
| Internet | 120,00 | dia 15 | fixo |
| Luz | 180,00 (estimado) | dia 22 | variável |

**Pernas esperadas**

| Transação | Pernas |
|---|---|
| Abertura Corrente | Corrente +2.500,00 / Patrimônio:Abertura −2.500,00 |
| Abertura Digital | Digital +800,00 / Patrimônio:Abertura −800,00 |
| Abertura Espécie | Espécie +150,00 / Patrimônio:Abertura −150,00 |
| Abertura VR/VA | VR/VA +420,00 / Patrimônio:Abertura −420,00 |
| Item A1 | Patrimônio:Abertura +1.230,00 / Cartão A −1.230,00 |
| Item A2 | Patrimônio:Abertura +340,00 / Cartão A −340,00 |
| Item A3 | Patrimônio:Abertura +1.200,00 / Cartão A −1.200,00 |
| Abertura do empréstimo | Patrimônio:Abertura +10.000,00 / Empréstimo −10.000,00 |

O consórcio e as recorrências não geram pernas; geram compromissos previstos.

**Resultados esperados em 01/11/2026**

| Indicador | Valor | Verificável a partir de |
|---|---|---|
| Saldo bancário (livre + reserva) | 3.450,00 | MVP-1 |
| Saldo de benefícios | 420,00 | MVP-1 |
| Passivo do Cartão A | 2.770,00 | MVP-1 |
| Limite disponível do Cartão A | 2.230,00 | MVP-1 |
| Saldo de Patrimônio:Abertura | +8.900,00 (patrimônio líquido de abertura negativo: −8.900,00) | MVP-1 |
| Despesas de novembro | 0,00 (itens de abertura não são despesa, RN-164) | MVP-1 |
| Horizonte H | 09/11/2026 (salário previsto mais antigo não recebido) | MVP-2 |
| Saldo comprometido (H) | 1.230,00 (fatura 05/11; aluguel vence em 10/11, fora de H). No MVP-2, a parte do cartão vem da estimativa RN-075 e dá o mesmo valor | MVP-2 |
| Saldo disponível | 3.450,00 − 1.230,00 = 2.220,00 | MVP-2 |
| Fatura 05/11 | 1.230,00 | MVP-3 |
| Fatura 05/12 (até aqui) | 580,00 (340,00 + 240,00) | MVP-3 |
| Faturas 05/01, 05/02, 05/03 e 05/04 | 240,00 cada | MVP-3 |
| Conferência I-07 | 1.230,00 + 580,00 + 4 × 240,00 = 2.770,00 | MVP-3 |

---|---|
| Saldo bancário (livre + reserva) | 3.450,00 |
| Saldo de benefícios | 420,00 |
| Passivo do Cartão A | 2.770,00 |
| Limite disponível do Cartão A | 2.230,00 |
| Fatura 05/11 | 1.230,00 |
| Fatura 05/12 (até aqui) | 580,00 (340,00 + 240,00) |
| Faturas 05/01, 05/02, 05/03 e 05/04 | 240,00 cada |
| Conferência I-07 | 1.230,00 + 580,00 + 4 × 240,00 = 2.770,00 |
| Horizonte H | 09/11/2026 |
| Saldo comprometido (H) | 1.230,00 (fatura 05/11; aluguel vence em 10/11, fora de H) |
| Saldo disponível | 3.450,00 − 1.230,00 = 2.220,00 |
| Saldo de Patrimônio:Abertura | +8.900,00 (patrimônio líquido de abertura negativo: −8.900,00) |
| Despesas de novembro | 0,00 (itens de abertura não são despesa, RN-164) |

---

## S01 — Rateio de compra parcelada

**Regras:** RN-005, RN-073, I-06.

| Compra | Parcelas esperadas | Soma |
|---|---|---|
| 100,00 em 3x | 33,34 / 33,33 / 33,33 | 100,00 |
| 1.000,00 em 7x | 142,90 / 142,85 × 6 | 1.000,00 |
| 600,00 em 6x | 100,00 × 6 | 600,00 |

Com a opção "resto na última parcela": 100,00 em 3x = 33,33 / 33,33 / 33,34.

---

## S02 — Compra antes e no dia do fechamento

**Regras:** RN-070, RN-071, RN-073. Cartão A.

| Compra | Data | Parcelas e faturas |
|---|---|---|
| 300,00 em 3x | 24/11/2026 | 100,00 em cada fatura: 05/12/2026, 05/01/2027, 05/02/2027 |
| 300,00 em 3x | 25/11/2026 (dia do fechamento) | 100,00 em cada fatura: 05/01/2027, 05/02/2027, 05/03/2027 |

Nas duas compras, as pernas são as mesmas, na data da compra: Despesa:cat +300,00 / Cartão A −300,00. O limite cai 300,00 na hora.

Vencimento efetivo da fatura 05/12/2026 (sábado) = 07/12/2026 (RN-072). Para o horizonte H, vale 05/12.

---

## S03 — Compras de terceiro: à vista, parcelada e mista

**Regras:** T09, T10, RN-100, RN-101, RN-102. Cartão A, pessoa Ana.

| Data | Compra | Pernas | A receber gerado |
|---|---|---|---|
| 12/11 | Ana, à vista, 80,00 | A receber:Ana +80,00 / Cartão A −80,00 | 80,00, vence 05/12 |
| 13/11 | Ana, 120,00 em 3x | A receber:Ana +120,00 / Cartão A −120,00 | 40,00 vence 05/12; 40,00 vence 05/01; 40,00 vence 05/02 |
| 14/11 | Jantar 250,00: 100,00 próprio, 150,00 da Ana | Despesa:Restaurantes +100,00 / A receber:Ana +150,00 / Cartão A −250,00 | 150,00, vence 05/12 |

**Resultados esperados após 14/11**

| Indicador | Valor |
|---|---|
| A receber da Ana | 350,00 |
| Despesas de novembro geradas por estas compras | 100,00 (só a parte própria do jantar) |
| Aumento do passivo do Cartão A | 450,00 |
| Fatura 05/12, parte destas compras | 80,00 + 40,00 + 250,00 = 370,00 |
| Receitas | 0,00 |

---

## S04 — Recebimentos parciais e totais

**Regras:** T15, RN-103, RN-104, RN-105. Continua o S03.

| Data | Recebimento | Alocação (vencimento mais antigo, depois ordem de criação) | Em aberto da Ana |
|---|---|---|---|
| 20/11 | 30,00 na Digital | 30,00 na parcela de 80,00 (fica 50,00) | 320,00 |
| 01/12 | 200,00 na Digital | 50,00 (quita os 80,00); 40,00 (quita 1ª de 3); 110,00 na de 150,00 (fica 40,00) | 120,00 |
| 06/12 | — | Parcela de 150,00 com 40,00 em aberto e vencimento 05/12: **atrasada** | 120,00 |
| 10/12 | 120,00 na Digital | 40,00 (quita a de 150,00); 40,00 (vence 05/01); 40,00 (vence 05/02) | 0,00 |

Pernas de cada recebimento: Digital +v / A receber:Ana −v.

**Resultados esperados**
- Receitas geradas: 0,00 (RN-104).
- Digital aumenta 350,00 no total.
- Em 06/12, o projetado **não** inclui os 40,00 atrasados (RN-105) até o usuário reagendar.

---

## S05 — Empréstimo a terceiro e baixa

**Regras:** T14, T15, T16, RN-106. Pessoa Bruno.

| Data | Evento | Pernas |
|---|---|---|
| 12/11/2026 | Empréstimo de 500,00 pela Digital, 5x de 100,00, vencimentos 10/12, 10/01, 10/02, 10/03, 10/04 | A receber:Bruno +500,00 / Digital −500,00 |
| 10/12/2026 | Recebe 100,00 | Digital +100,00 / A receber:Bruno −100,00 |
| 11/01/2027 | Recebe 100,00 | Digital +100,00 / A receber:Bruno −100,00 |
| 15/04/2027 | Baixa de 300,00 por inadimplência, motivo obrigatório | Despesa:Perdas com valores a receber +300,00 / A receber:Bruno −300,00 |

**Resultados esperados**

| Indicador | Valor |
|---|---|
| Despesa em novembro/2026 | 0,00 (empréstimo não é despesa) |
| Despesa em abril/2027 | 300,00 (perda) |
| Receitas | 0,00 |
| A receber do Bruno após a baixa | 0,00 |
| Parcelas | 10/12 e 10/01 "recebidas"; 10/02, 10/03 e 10/04 "baixadas" |
| Efeito líquido na Digital | −300,00 |

---

## S06 — Pagamento parcial de fatura, saldo transportado e encargos

**Regras:** T11, T12, RN-076, RN-079. Cartão B, só esta fatura em aberto.

| Data | Evento | Pernas | Passivo do Cartão B | Limite disponível |
|---|---|---|---|---|
| até 30/11 | Compras somam 1.000,00 (fatura 10/12) | — | 1.000,00 | 2.000,00 |
| 10/12 | Paga 600,00 da Corrente | Cartão B +600,00 / Corrente −600,00 | 400,00 | 2.600,00 |
| 11/12 | Vencimento efetivo passou com 400,00 em aberto: fatura **paga parcialmente → vencida**; 400,00 transportados para a fatura 10/01/2027 como saldo anterior; alerta forte | — | 400,00 | 2.600,00 |
| dezembro | Novas compras próprias de 200,00 (ciclo 01/12 a 31/12) | Despesa:cat +200,00 / Cartão B −200,00 | 600,00 | 2.400,00 |
| 02/01/2027 | Usuário informa encargos da fatura do emissor: juros 56,00 e IOF 3,52 | Despesa:Encargos de cartão +59,52 / Cartão B −59,52 | 659,52 | 2.340,48 |

**Resultados esperados**

| Indicador | Valor |
|---|---|
| Fatura 10/01/2027 | 400,00 + 59,52 + 200,00 = 659,52 |
| Vencimento efetivo da fatura 10/01/2027 (domingo) | 11/01/2027 |
| Despesa de encargos | 59,52, na categoria de sistema, competência janeiro/2027 |
| Os 400,00 transportados | Não geram nova despesa (já eram despesa na competência das compras) |

---

## S07 — Pagamento acima da fatura

**Regras:** RN-080, RN-086. Cartão B.

| Data | Evento | Passivo | Limite disponível |
|---|---|---|---|
| até 30/11 | Fatura 10/12 = 300,00 | 300,00 | 2.700,00 |
| 08/12 | Paga 350,00, com confirmação de pagamento acima (RN-043) | −50,00 (crédito a favor) | 3.050,00 |
| dezembro | Compras de 200,00 | 150,00 | 2.850,00 |

**Resultados esperados**
- Fatura 10/01/2027 = 200,00 − 50,00 (crédito) = 150,00.
- Nenhuma receita nem despesa gerada pelo excesso.

---

## S08 — Transferências e reserva

**Regras:** T05, T06, T07, RN-060, RN-061. Início: Corrente 2.000,00; Digital 500,00; Reserva 0,00; nenhum compromisso.

| Operação | Pernas | Corrente | Digital | Reserva | Bancário | Livre (disponível) |
|---|---|---|---|---|---|---|
| Início | — | 2.000,00 | 500,00 | 0,00 | 2.500,00 | 2.500,00 |
| Transferência Corrente → Digital 400,00 | Digital +400,00 / Corrente −400,00 | 1.600,00 | 900,00 | 0,00 | 2.500,00 | 2.500,00 |
| Aporte Corrente → Reserva 1.000,00 | Reserva +1.000,00 / Corrente −1.000,00 | 600,00 | 900,00 | 1.000,00 | 2.500,00 | 1.500,00 |
| Retirada Reserva → Digital 300,00 | Digital +300,00 / Reserva −300,00 | 600,00 | 1.200,00 | 700,00 | 2.500,00 | 1.800,00 |

**Resultados esperados**
- Receitas e despesas: 0,00 em todas as visões.
- Total guardado: 700,00.
- Cada transferência grava as duas pernas na mesma transação. Teste de falha: interromper a gravação entre as pernas não deixa nenhuma perna gravada (RN-173).

---

## S09 — Tabela Price e amortização extraordinária

**Regras:** RN-110 a RN-115, T17, T18. Empréstimo do S00: S = 10.000,00; i = 2% ao mês; n = 12.

PMT = 10.000,00 × 0,02 ÷ (1 − 1,02^−12) = **945,60**.

**Tabela original**

| Parcela | Pagamento | Juros | Principal | Saldo devedor |
|---|---|---|---|---|
| 1 | 945,60 | 200,00 | 745,60 | 9.254,40 |
| 2 | 945,60 | 185,09 | 760,51 | 8.493,89 |
| 3 | 945,60 | 169,88 | 775,72 | 7.718,17 |
| 4 | 945,60 | 154,36 | 791,24 | 6.926,93 |
| 5 | 945,60 | 138,54 | 807,06 | 6.119,87 |
| 6 | 945,60 | 122,40 | 823,20 | 5.296,67 |
| 7 | 945,60 | 105,93 | 839,67 | 4.457,00 |
| 8 | 945,60 | 89,14 | 856,46 | 3.600,54 |
| 9 | 945,60 | 72,01 | 873,59 | 2.726,95 |
| 10 | 945,60 | 54,54 | 891,06 | 1.835,89 |
| 11 | 945,60 | 36,72 | 908,88 | 927,01 |
| 12 | **945,55** | 18,54 | 927,01 | 0,00 |
| **Total** | 11.347,15 | **1.347,15** | 10.000,00 | |

A última parcela absorve o resíduo (RN-111).

Pernas da parcela 1 (paga em 16/11/2026, vencimento efetivo de 15/11, domingo): Empréstimo +745,60 / Despesa:Juros de dívidas +200,00 / Corrente −945,60.

**Amortização extraordinária de 2.000,00 logo após a parcela 1, reduzindo prazo (padrão)**

Pernas: Empréstimo +2.000,00 / Corrente −2.000,00. Saldo devedor: 7.254,40.

| Parcela | Pagamento | Juros | Principal | Saldo devedor |
|---|---|---|---|---|
| 2 | 945,60 | 145,09 | 800,51 | 6.453,89 |
| 3 | 945,60 | 129,08 | 816,52 | 5.637,37 |
| 4 | 945,60 | 112,75 | 832,85 | 4.804,52 |
| 5 | 945,60 | 96,09 | 849,51 | 3.955,01 |
| 6 | 945,60 | 79,10 | 866,50 | 3.088,51 |
| 7 | 945,60 | 61,77 | 883,83 | 2.204,68 |
| 8 | 945,60 | 44,09 | 901,51 | 1.303,17 |
| 9 | 945,60 | 26,06 | 919,54 | 383,63 |
| 10 | **391,30** | 7,67 | 383,63 | 0,00 |

**Resultados esperados**

| Indicador | Valor |
|---|---|
| Juros totais com a amortização (parcelas 1 a 10) | 901,70 |
| **Juros economizados** (RN-114) | 1.347,15 − 901,70 = **445,45** |
| Parcelas | 10 em vez de 12; quitação estimada 2 meses antes |
| Total pago | 9 × 945,60 + 391,30 + 2.000,00 = 10.901,70 (= 10.000,00 + 901,70) |
| Alternativa "reduzir parcela" (mesmo prazo, 11 parcelas restantes) | Nova PMT = 741,24; juros totais = 1.099,24; economia = 247,91 |
| Aviso de estimativa (RN-115) | Exibido |

---

## S10 — Estornos no cartão

**Regras:** RN-082 a RN-084, T13. Cartão A.

**Parte A — estorno comercial de compra parcelada com parcela já faturada**

| Data | Evento | Pernas | Efeito nas faturas |
|---|---|---|---|
| 10/11/2026 | Compra 600,00 em 6x (Eletrônicos) | Despesa:Eletrônicos +600,00 / Cartão A −600,00 | 100,00 nas faturas 05/12, 05/01, 05/02, 05/03, 05/04, 05/05 |
| 25/11/2026 | Fatura 05/12 fecha (parcela 1 faturada) | — | — |
| 07/12/2026 | Fatura 05/12 paga integralmente | Cartão A +v / Corrente −v | — |
| 10/12/2026 | Lojista cancela a compra (estorno comercial total) | Cartão A +600,00 / Despesa:Eletrônicos −600,00, vínculo "estorna" com a compra | Parcelas 2 a 6 (500,00) canceladas; crédito de 100,00 (parcela 1 já faturada) na fatura 05/01 |

Resultados esperados:

| Indicador | Valor |
|---|---|
| Efeito líquido da compra no passivo após o estorno | −100,00 (crédito a favor) |
| Fatura 05/01, parte desta compra | 0,00 de parcela + (−100,00) de crédito = −100,00 |
| Limite | Libera 600,00 no estorno |
| Visão por compra | Novembro +600,00; dezembro −600,00 |
| Visão por parcela (mês da fatura) | Dezembro +100,00 (parcela 1, fatura 05/12); janeiro −100,00 (crédito na fatura 05/01) |
| Soma em qualquer visão | 0,00 |

**Parte B — estorno parcial à vista no mesmo ciclo**

| Data | Evento | Pernas |
|---|---|---|
| 15/11 | Compra à vista 200,00 (Vestuário) | Despesa:Vestuário +200,00 / Cartão A −200,00 |
| 18/11 | Estorno parcial de 50,00 (troca) | Cartão A +50,00 / Despesa:Vestuário −50,00, vínculo "estorna parcialmente" |

Resultados:
- a partir do MVP-1: despesa de novembro em Vestuário = 150,00 (visão por compra); passivo do cartão +150,00 líquido;
- a partir do MVP-3: fatura 05/12 recebe 200,00 e −50,00 (líquido 150,00); visão por parcela: dezembro 150,00.

---

## S11 — Correção de lançamento confirmado

**Regras:** RN-082, RN-120, RN-122, ADR-003.

| Data | Evento | Transação | Pernas | Estado final |
|---|---|---|---|---|
| 03/11 | Mercado 85,00 na Corrente (valor errado) | T1 | Despesa:Mercado +85,00 / Corrente −85,00 | estornado |
| 04/11 | "Corrigir" para 58,00 | T2 = estorno técnico de T1, data da operação 04/11, competência 03/11 | Despesa:Mercado −85,00 / Corrente +85,00 | confirmado |
| 04/11 | (mesma operação atômica) | T3 = nova, data 03/11, vínculo "corrige" T1 | Despesa:Mercado +58,00 / Corrente −58,00 | confirmado |

**Resultados esperados**
- Efeito líquido na Corrente: −58,00. Despesa de novembro em Mercado: 58,00.
- A lista padrão mostra só T3; o filtro "mostrar estornos" mostra T1 e T2.
- Auditoria: três registros ligados (estorno, criação, vínculo).
- Tentar estornar T1 de novo: recusado (I-03). Tentar alterar valor de T3: recusado (RN-013).
- Falha simulada após gravar T2 e antes de T3: nada é gravado (atomicidade).

---

## S12 — Idempotência e pagamento duplicado

**Regras:** RN-043, RN-170.

**Parte A — duplo envio (a partir do MVP-1)**

| Passo | Ação | Resultado esperado |
|---|---|---|
| 1 | Formulário "pagar Cartão A" aberto com chave K1; envia 1.230,00 | Uma transação T11 criada |
| 2 | Duplo toque: segundo envio com a mesma chave K1 | Nenhuma transação nova; a resposta devolve a transação do passo 1 |
| Final | Corrente diminuiu 1.230,00 **uma** vez | — |

**Parte B — pagamento de algo já quitado (a partir do MVP-2)**

| Passo | Ação | Resultado esperado |
|---|---|---|
| 1 | Aluguel de novembro (1.500,00) liquidado em 10/11 | Valor em aberto 0,00; status "Pago" |
| 2 | Novo formulário (chave K2) tenta pagar 1.500,00 no mesmo aluguel | Recusado: "Esta conta já está paga"; opções explícitas: juros e multa, valor real maior, cancelar (RN-043) |
| Final | Existe uma única liquidação do aluguel | — |

**Parte C — fatura já paga (a partir do MVP-3)**

| Passo | Ação | Resultado esperado |
|---|---|---|
| 1 | Fatura 05/11 do Cartão A paga integralmente | Fatura "paga" |
| 2 | Novo formulário tenta pagar 1.230,00 indicando a fatura 05/11 | Aviso: "Fatura já paga"; opção explícita de registrar como pagamento acima (crédito, RN-080) ou alocar à fatura aberta |

---|---|---|
| 1 | Formulário "pagar fatura 05/11" aberto com chave K1; envia 1.230,00 | Uma transação criada; fatura paga |
| 2 | Duplo toque: segundo envio com a mesma chave K1 | Nenhuma transação nova; resposta devolve a transação do passo 1 |
| 3 | Novo formulário (chave K2) tenta pagar 1.230,00 na mesma fatura, já quitada | Recusado: "Fatura já paga"; opção explícita de registrar como pagamento acima (crédito) |
| Final | Corrente diminuiu 1.230,00 **uma** vez; existe uma única liquidação da fatura | — |

---

## S13 — Conciliação de saldo e de limite

**Regras:** RN-130 a RN-133, RN-087, RN-088.

**Saldo**

| Passo | Valor |
|---|---|
| Saldo calculado da Corrente em 20/11 | 1.234,56 |
| Saldo informado pelo banco | 1.229,56 |
| Diferença | −5,00 |
| Usuário não encontra lançamento faltante e aceita o ajuste | Corrente −5,00 / Patrimônio:Ajustes de conciliação +5,00 |
| Saldo após ajuste | 1.229,56 |
| Receitas e despesas | Inalteradas; relatório mostra "diferenças de conciliação: −5,00" |
| Lançamento posterior com data 18/11 | Pede confirmação; marco de 20/11 passa a "a reconciliar" |

**Limite (Cartão B, passivo 1.000,00, limite total 3.000,00)**

| Passo | Calculado | Informado pelo app | Diferença | Tratamento |
|---|---|---|---|---|
| 10/12, após pagar 600,00 às 20h | 2.600,00 | 2.000,00 | 600,00 | Causa provável: "pagamento em compensação". Evento de conciliação registrado; **nenhuma perna** |
| 11/12 | 2.600,00 | 2.600,00 | 0,00 | Conciliado |
| 15/12, emissor aumenta o limite total para 3.500,00 | Atualizado pelo usuário para 3.100,00 | 3.100,00 | 0,00 | Evento "mudança de limite total", sem perna (RN-088) |

---

## S14 — Mês combinado e disjunção dos saldos

**Regras:** RN-140 a RN-149, RN-160 a RN-167, I-08. Parte do S00. Fotografia em **20/11/2026**, fim do dia.

**Eventos de 01/11 a 20/11**

| Data | Evento | Pernas |
|---|---|---|
| 03/11 | Mercado 230,00 no débito | Despesa:Mercado +230,00 / Corrente −230,00 |
| 05/11 | Paga fatura 05/11 do Cartão A | Cartão A +1.230,00 / Corrente −1.230,00 |
| 09/11 | Salário (liquida a receita prevista) | Corrente +5.000,00 / Receita:Salário −5.000,00 |
| 10/11 | Aluguel (liquida o pendente) | Despesa:Moradia +1.500,00 / Corrente −1.500,00 |
| 10/11 | Compra própria 600,00 em 6x no Cartão A | Despesa:Eletrônicos +600,00 / Cartão A −600,00 |
| 12/11 | Aporte na reserva | Reserva +1.000,00 / Corrente −1.000,00 |
| 14/11 | Jantar 250,00 (100,00 próprio, 150,00 da Ana) no Cartão A | Despesa:Restaurantes +100,00 / A receber:Ana +150,00 / Cartão A −250,00 |
| 16/11 | Parcela 1 do empréstimo (venc. 15/11, domingo) | Empréstimo +745,60 / Despesa:Juros de dívidas +200,00 / Corrente −945,60 |
| 16/11 | Internet (venc. 15/11, domingo) | Despesa:Internet +120,00 / Corrente −120,00 |
| 16/11 | Ana paga 50,00 | Digital +50,00 / A receber:Ana −50,00 |
| 18/11 | Transporte 35,00 no débito | Despesa:Transporte +35,00 / Digital −35,00 |
| 18/11 | Mercado 45,00 com VR | Despesa:Mercado +45,00 / VR/VA −45,00 |

**Compromissos em 20/11**

| Compromisso | Estado | Vencimento | Valor em aberto |
|---|---|---|---|
| Consórcio novembro | pendente (fixo dentro de H) | 20/11 (feriado; efetivo 23/11; **não** atrasado) | 650,00 |
| Luz novembro | previsto (variável) | 22/11 | 180,00 (estimado) |
| Aluguel dezembro | previsto | 10/12 | 1.500,00 |
| Internet dezembro | previsto | 15/12 | 120,00 |
| Empréstimo, parcela 2 | previsto | 15/12 | 945,60 |
| Consórcio dezembro | previsto | 20/12 | 650,00 |
| Salário dezembro | receita prevista | 07/12 | 5.000,00 |

**Fatura 05/12 do Cartão A em 20/11 (aberta)**

| Item | Valor |
|---|---|
| A2 — compras da fatura aberta na abertura | 340,00 |
| A3 — TV, parcela 6 | 240,00 |
| Compra 600,00, parcela 1 | 100,00 |
| Jantar (inclui 150,00 da Ana) | 250,00 |
| **Total** | **930,00** |

Parcelas futuras não faturadas: TV 7 a 10 = 960,00; compra 600,00, parcelas 2 a 6 = 500,00; total 1.460,00.

**Saldos de contas em 20/11**

| Conta | Cálculo | Saldo |
|---|---|---|
| Corrente | 2.500,00 − 230,00 − 1.230,00 + 5.000,00 − 1.500,00 − 1.000,00 − 945,60 − 120,00 | 2.474,40 |
| Digital | 800,00 + 50,00 − 35,00 | 815,00 |
| Espécie | 150,00 | 150,00 |
| Reserva | 1.000,00 | 1.000,00 |
| VR/VA | 420,00 − 45,00 | 375,00 |
| A receber: Ana | 150,00 − 50,00 | 100,00 (vence 05/12) |
| Passivo do Cartão A | 2.770,00 − 1.230,00 + 600,00 + 250,00 | 2.390,00 (= 930,00 + 1.460,00) |
| Empréstimo | 10.000,00 − 745,60 | 9.254,40 |

**Resultados esperados**

| Indicador | Regra | Cálculo | Valor |
|---|---|---|---|
| Horizonte H | RN-140 | Próximo salário após 20/11 | 07/12/2026 |
| Saldo bancário | RN-141 | 2.474,40 + 815,00 + 150,00 + 1.000,00 | **4.439,40** |
| Saldo das contas livres | — | 2.474,40 + 815,00 + 150,00 | 3.439,40 |
| Saldo de benefícios | RN-142 | — | **375,00** |
| Total guardado | RN-147 | — | **1.000,00** |
| Saldo comprometido (H) | RN-143 | Fatura 05/12 930,00 (vencimento original 05/12 < 07/12) + consórcio 650,00. Luz fica de fora (prevista); aluguel, internet, empréstimo e consórcio de dezembro vencem depois de H | **1.580,00** |
| Saldo disponível | RN-145 | 3.439,40 − 1.580,00 | **1.859,40** |
| Saldo comprometido total | RN-144 | 930,00 + 1.460,00 + consórcio 40 × 650,00 + empréstimo parcelas 2 a 12 (10 × 945,60 + 945,55) | **38.791,55** |
| Saldo projetado em 06/12 | RN-146 | 3.439,40 + a receber Ana 100,00 − (consórcio 650,00 + luz 180,00) − fatura 930,00 | **1.779,40** |
| Saldo projetado em 07/12 | RN-146 | 1.779,40 + salário 5.000,00 | **6.779,40** |
| Limite disponível do Cartão A | RN-086 | 5.000,00 − 2.390,00 | **2.610,00** |
| Total de dívidas | RN-148 | 9.254,40 + 2.390,00 | **11.644,40** |
| Receitas de novembro | RN-160 | Salário | **5.000,00** |
| Despesas de novembro, visão por compra | RN-161 | 230,00 + 1.500,00 + 600,00 + 100,00 + 200,00 + 120,00 + 35,00 + 45,00 | **2.830,00** |
| Despesas de novembro, visão por parcela | RN-162 | Despesas fora do cartão (230,00 + 1.500,00 + 200,00 + 120,00 + 35,00 + 45,00 = 2.130,00) + parte própria da fatura com vencimento em novembro (item A1, 1.230,00, "compra anterior ao início"). As compras de novembro no cartão caem na fatura 05/12 e contam em dezembro | **3.360,00** |
| Despesas de dezembro, visão por parcela (até 20/11) | RN-162 | Parte própria da fatura 05/12: 340,00 + 240,00 + 100,00 + 100,00 | **780,00** (+ despesas de dezembro fora do cartão) |
| Pagamentos realizados no mês | RN-166 | 1.230,00 + 1.500,00 + 945,60 + 120,00 | **3.795,60** |
| Comprometimento de renda, dezembro/2026 | RN-149 | Parcelas próprias da fatura 05/12 (930,00 − 150,00 da Ana = 780,00) + aluguel 1.500,00 + internet 120,00 + empréstimo 945,60 + consórcio 650,00 + luz estimada 180,00 = 4.175,60; renda prevista 5.000,00 | **4.175,60 (83,5%)**; sobra prevista 824,40; linha separada "no seu cartão, a receber": 150,00 |

**O que não pode aparecer como receita ou despesa** (RN-164): pagamento da fatura (1.230,00), aporte (1.000,00), principal do empréstimo (745,60), parte da Ana no jantar (150,00), recebimento da Ana (50,00), itens de abertura.

**Equação patrimonial (I-08)**

| Lado | Cálculo | Valor |
|---|---|---|
| Ativos | 3.439,40 + 1.000,00 + 375,00 + 100,00 | 4.914,40 |
| Passivos | 2.390,00 + 9.254,40 | 11.644,40 |
| Ativos − passivos | | −6.730,00 |
| Patrimônio de abertura + receitas − despesas | −8.900,00 + 5.000,00 − 2.830,00 | −6.730,00 ✔ |

**Provas de disjunção** (cada uma vira asserção de teste):
1. A parte da Ana (150,00) está na fatura (comprometido) e no a receber (projetado), mas nunca nas despesas.
2. O consórcio de novembro aparece uma única vez no comprometido e uma no projetado de 06/12.
3. A luz (prevista) está no projetado e **não** no comprometido.
4. A reserva (1.000,00) está no bancário e **não** nas contas livres, no disponível nem no projetado.
5. O VR/VA (375,00) não está em nenhum dos quatro saldos.
6. A compra de 600,00 entra no comprometido só pela parcela 1, dentro da fatura 05/12, e nunca como compromisso avulso.
