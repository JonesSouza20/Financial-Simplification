# Regras de Negócio — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.2 |
| Data | 06/11/2026 |
| Etapa | 4 — Especificação (Fase B) |
| Status | Versão 0.1 aprovada em 06/11/2026 (Fase B); versão 0.2 com os detalhes da Fase 2A (§22), aprovada em 08/11/2026; RN-154 acrescentada em 08/11/2026 |
| Documentos relacionados | `product-requirements.md` (glossário), `architecture.md` (§6), `decisions.md`, `database-design.md`, `reference-scenarios.md` |

Cada regra tem um identificador (RN-xxx). O `testing-plan.md` liga cada regra a pelo menos um teste. Os cenários com números exatos estão em `reference-scenarios.md` (S00 a S14).

---

## 1. Convenções

| ID | Regra |
|---|---|
| RN-001 | Valores monetários são inteiros em centavos. Nenhum cálculo financeiro usa ponto flutuante. |
| RN-002 | Sinal das pernas: **débito positivo, crédito negativo**. A soma das pernas de uma transação é sempre zero. |
| RN-003 | Saldo de conta de ativo = soma das pernas confirmadas (positivo = dinheiro ou direito). Saldo de conta de passivo = −(soma das pernas confirmadas) (positivo = valor devido). |
| RN-004 | Arredondamento `ROUND_HALF_UP` para centavos, aplicado só em: valor de cada parcela, juros de cada período, valor de cada perna. Cálculos intermediários em decimal com 28 dígitos. |
| RN-005 | Rateio de parcelas: valor-base = total ÷ n, truncado em centavos; a primeira parcela recebe a diferença. Ex.: 100,00 em 3x = 33,34 + 33,33 + 33,33 (S01). Configurável por cartão para "última parcela". |
| RN-006 | Datas financeiras (operação, competência, vencimento) são datas sem hora, no fuso America/Sao_Paulo. Carimbos de criação, atualização e auditoria são data e hora em UTC. |
| RN-007 | Toda transação tem **data da operação** (quando aconteceu ou acontecerá) e **data de competência** (a que mês pertence). Padrão: competência = data da operação. |

## 2. Plano de contas contábeis

O usuário nunca vê contas contábeis. Elas são criadas automaticamente quando ele cadastra contas, cartões, pessoas, dívidas e categorias.

| Tipo | Contas | Criadas quando |
|---|---|---|
| Ativo | Uma por conta financeira (classe livre, reserva ou benefício) | Cadastro da conta financeira |
| Ativo | Uma "A receber" por pessoa | Cadastro da pessoa |
| Passivo | Uma por cartão de crédito | Cadastro do cartão |
| Passivo | Uma por dívida | Cadastro da dívida |
| Receita | Uma por categoria de receita | Cadastro da categoria |
| Despesa | Uma por categoria de despesa | Cadastro da categoria |
| Patrimônio | **Abertura** (saldos e itens de abertura) e **Ajustes de conciliação** | Instalação |

Categorias de sistema (RF-CAT-03), não editáveis nem arquiváveis:

| Categoria | Tipo | Uso |
|---|---|---|
| Encargos de cartão | Despesa | Juros do rotativo, IOF, multa e anuidade cobrados pelo emissor |
| Juros de dívidas | Despesa | Parte de juros das parcelas de dívida |
| Encargos de dívidas | Despesa | Seguros, tarifas e multas de dívida |
| Juros e multas por atraso | Despesa | Acréscimos pagos em contas atrasadas |
| Perdas com valores a receber | Despesa | Baixa de valor a receber |
| Consórcio | Despesa | Parcela do consórcio não contemplado (ADR-008) |
| Rendimentos | Receita | Rendimento de reservas lançado pelo usuário |

## 3. Estados e transições

### 3.1 Estados da transação

| ID | Regra |
|---|---|
| RN-010 | Estados: **previsto**, **pendente**, **confirmado**, **cancelado**, **estornado**. |
| RN-011 | Só pernas de transações **confirmadas** e **estornadas** entram nos saldos reais. O estorno anula o efeito da transação estornada. |
| RN-012 | Transações previstas e pendentes guardam as pernas pretendidas, mas nunca afetam saldo real. Elas alimentam o saldo comprometido, o saldo projetado e o comprometimento de renda. |
| RN-013 | Transação confirmada é imutável: valores, contas, datas e tipo não mudam. Descrição e observação também não; uma nota de correção pode ser **acrescentada**, com registro na auditoria. |
| RN-014 | Nenhuma transação é excluída fisicamente (ADR-003). |

### 3.2 Transições permitidas

| De | Para | Condição | Efeito |
|---|---|---|---|
| (novo) | previsto | Valor estimado ou futuro sem obrigação concreta | Nenhum efeito real |
| (novo) | pendente | Obrigação ou direito concreto, não liquidado | Nenhum efeito real; entra no comprometido se vencer até H |
| (novo) | confirmado | Operação que já aconteceu | Pernas passam a valer nos saldos |
| previsto | pendente | Valor real informado, ou recorrência fixa que entra em H (RN-052) | Passa a contar no comprometido |
| previsto ou pendente | cancelado | Usuário cancela, com motivo obrigatório | Sai do comprometido e do projetado |
| confirmado | estornado | Existe um estorno vinculado e confirmado | Efeito anulado |

Um compromisso previsto ou pendente **nunca** passa a confirmado. Ele é liquidado por transações confirmadas novas (RN-040), mesmo quando o pagamento é total e no valor exato. O botão "Pagar" faz isso em um passo. Assim existe um único caminho para dinheiro real entrar no Ledger, e o plano original fica preservado para comparação (planejado × realizado).

Transições proibidas, com bloqueio no serviço e no banco:
- previsto ou pendente → confirmado (usar liquidação);
- confirmado → previsto, pendente ou cancelado;
- cancelado → qualquer estado;
- estornado → qualquer estado;
- estornar uma transação que não está confirmada;
- estornar duas vezes a mesma transação.

### 3.3 Liquidação de compromissos

| ID | Regra |
|---|---|
| RN-040 | Um compromisso previsto ou pendente (conta a pagar, receita prevista, parcela de dívida, parcela de consórcio) é **liquidado** por uma ou mais transações confirmadas novas, ligadas a ele por vínculo "liquida" com o valor liquidado. O compromisso em si não muda de valor. |
| RN-041 | Valor em aberto do compromisso = valor planejado − soma das liquidações confirmadas e não estornadas. |
| RN-042 | O compromisso fica **liquidado** quando o valor em aberto chega a zero, ou quando o usuário declara "pago com valor diferente" (ex.: conta veio menor). Nesse caso a diferença é encerrada, com motivo, e não gera perna. |
| RN-043 | Liquidação acima do valor em aberto exige confirmação explícita e a classificação do excedente (juros e multa, ou valor real maior). Sem isso, o serviço recusa (proteção contra pagamento duplicado). |
| RN-044 | Estornar uma liquidação reabre o valor em aberto do compromisso. |

### 3.4 Status exibido de contas a pagar

| Status | Regra de cálculo |
|---|---|
| Previsto | Compromisso previsto |
| Pendente | Compromisso pendente, valor em aberto > 0, vencimento efetivo ≥ hoje |
| Agendado | Pendente com marca "agendado" e data de débito |
| Atrasado | Pendente com valor em aberto > 0 e vencimento efetivo < hoje |
| Pago parcialmente | Valor em aberto > 0 e ao menos uma liquidação |
| Pago | Liquidado (RN-042) |
| Cancelado | Compromisso cancelado |

Atrasado e pago parcialmente são **calculados**, nunca gravados. Assim não podem ficar desatualizados.

## 4. Efeito de cada tipo de operação

Legenda das colunas:
- **Pernas:** débito (+) e crédito (−).
- **Bancário:** efeito no saldo bancário (contas livres e reserva).
- **Disp.:** efeito no saldo disponível.
- **Resultado:** gera receita ou despesa por competência.
- **Limite:** efeito no limite disponível do cartão.

| # | Operação | Pernas | Bancário | Disp. | Resultado | Limite |
|---|---|---|---|---|---|---|
| T01 | Receita recebida em conta livre | Conta +v / Receita:cat −v | +v | +v | Receita v | — |
| T02 | Despesa paga com conta livre | Despesa:cat +v / Conta −v | −v | −v | Despesa v | — |
| T03 | Despesa paga com benefício | Despesa:cat +v / Benefício −v | — | — | Despesa v | — |
| T04 | Crédito de benefício (VR/VA) | Benefício +v / Receita:Benefícios −v | — | — | Receita v | — |
| T05 | Transferência entre contas livres | Destino +v / Origem −v | 0 | 0 | Nenhum | — |
| T06 | Aporte em reserva (livre → reserva) | Reserva +v / Livre −v | 0 | −v | Nenhum | — |
| T07 | Retirada de reserva (reserva → livre) | Livre +v / Reserva −v | 0 | +v | Nenhum | — |
| T08 | Compra própria no cartão | Despesa:cat +v / Cartão −v | — | −(parte devida até H) | Despesa v (competência da compra) | −v |
| T09 | Compra de terceiro no cartão | A receber:pessoa +v / Cartão −v | — | −(parte devida até H) | Nenhum | −v |
| T10 | Compra mista no cartão | Despesa:cat +p / A receber:pessoa +t / Cartão −(p+t) | — | −(parte devida até H) | Despesa p | −(p+t) |
| T11 | Pagamento de fatura | Cartão +v / Conta −v | −v | 0 (troca saldo por compromisso já contado) | Nenhum | +v |
| T12 | Encargo do cartão informado pelo emissor | Despesa:Encargos de cartão +v / Cartão −v | — | −v se devido até H | Despesa v | −v |
| T13 | Estorno comercial de compra no cartão | Pernas da compra invertidas, com vínculo "estorna" | — | +(parte que estava devida até H) | Despesa −v (data do estorno) | +v |
| T14 | Empréstimo a terceiro | A receber:pessoa +v / Conta −v | −v | −v | Nenhum | — |
| T15 | Recebimento de terceiro | Conta +v / A receber:pessoa −v | +v | +v | Nenhum | — |
| T16 | Baixa de valor a receber | Despesa:Perdas +v / A receber:pessoa −v | — | — | Despesa v | — |
| T17 | Parcela de dívida | Dívida +principal / Despesa:Juros +j / Despesa:Encargos +e / Conta −(principal+j+e) | −total | 0 (já estava no comprometido) | Despesa j+e | — |
| T18 | Amortização extraordinária | Dívida +v / Conta −v | −v | −v | Nenhum | — |
| T19 | Parcela de consórcio | Despesa:Consórcio +v / Conta −v | −v | 0 (já estava no comprometido) | Despesa v | — |
| T20 | Reembolso de despesa | Conta +v / Despesa:cat −v, vínculo com a despesa original | +v | +v | Despesa −v | — |
| T21 | Juros e multa por atraso | Despesa:Juros e multas +v / Conta −v (junto da liquidação) | −v | −v | Despesa v | — |
| T22 | Rendimento de reserva | Reserva +v / Receita:Rendimentos −v | +v | — | Receita v | — |
| T23 | Saldo de abertura de conta | Conta +v / Patrimônio:Abertura −v | +v | +v | Nenhum | — |
| T24 | Item de abertura de cartão, próprio | Patrimônio:Abertura +v / Cartão −v | — | −(parte devida até H) | Nenhum | −v |
| T25 | Item de abertura de cartão, de terceiro | A receber:pessoa +v / Cartão −v | — | −(parte devida até H) | Nenhum | −v |
| T26 | Abertura de dívida | Patrimônio:Abertura +v / Dívida −v | — | — | Nenhum | — |
| T27 | Ajuste de conciliação de saldo | Conta ±d / Patrimônio:Ajustes ∓d | ±d | ±d | Nenhum (aparece como "diferenças de conciliação") | — |
| T28 | Estorno técnico (parte do "Corrigir") | Pernas da original invertidas, com vínculo "estorna" | Anula a original | Anula a original | Anula a original na **competência original** | Anula a original |

Observações:
- Em T11, o saldo disponível não muda no momento do pagamento: o saldo bancário cai v, mas o comprometido também cai v, porque a fatura já estava contada. Se a fatura vencia depois de H, o disponível cai, porque o dinheiro sai antes do que o horizonte previa.
- Em T17 e T19 vale a mesma lógica: a parcela já estava no comprometido como compromisso pendente.
- "Parte devida até H", em T08 a T10 e T24/T25: soma das parcelas daquela compra que caem em faturas com vencimento original anterior a H (RN-070).

## 5. Receitas

| ID | Regra |
|---|---|
| RN-020 | Receita prevista (ex.: salário do próximo mês) é transação **prevista**; não entra em saldo real, disponível nem comprometido. Entra só no projetado, na data prevista. |
| RN-021 | Receita confirmada liquida a prevista correspondente (RN-040). Se o valor recebido for diferente, a liquidação registra o valor real e a prevista é encerrada (RN-042). |
| RN-022 | Salário: recorrência mensal na data do 5º dia útil (RN-090), valor fixo informado. O valor líquido do holerite é o lançado. Descontos não são detalhados no MVP. |
| RN-023 | Receita prevista atrasada (data passou e não houve recebimento) aparece em atenção no dashboard e continua no projetado com a data de hoje, até ser confirmada ou cancelada. |
| RN-024 | Recebimentos de terceiros (T15), transferências (T05 a T07), reembolsos (T20) e estornos **nunca** são receita. |
| RN-025 | Crédito de VR/VA é receita de benefício (T04) e fica na carteira de benefícios (ADR-030). Relatórios de receita mostram benefícios em grupo próprio, separado da renda em dinheiro. |

## 6. Despesas e contas a pagar

| ID | Regra |
|---|---|
| RN-030 | Despesa paga na hora (débito, Pix, espécie) é transação confirmada direta (T02), sem compromisso. |
| RN-031 | Conta a pagar é um compromisso com: valor planejado, vencimento, categoria, conta financeira prevista, forma de pagamento, tipo de valor (fixo ou variável). |
| RN-032 | Competência da despesa de conta a pagar = mês de referência informado (ex.: luz de outubro paga em novembro); padrão = mês do vencimento. |
| RN-033 | Pagamento parcial: cada pagamento é uma liquidação (RN-040). A conta continua pendente pelo valor em aberto. |
| RN-034 | Juros e multa por atraso são registrados em perna separada, na categoria de sistema, na mesma transação da liquidação (T21). Nunca aumentam a despesa da categoria original. |
| RN-035 | Agendado: pendente com data de débito. No dia, o sistema pergunta se o débito ocorreu. Nunca confirma sozinho, porque o banco pode recusar o agendamento. |
| RN-036 | Cancelar conta exige motivo. Conta com liquidações não pode ser cancelada; ela é encerrada (RN-042). |
| RN-037 | Parcelamento fora do cartão (ex.: boleto em 5x): gera N compromissos ligados a um mesmo grupo, rateados pela RN-005, cada um com vencimento. A competência de cada parcela é o mês do vencimento. |

## 7. Recorrências

| ID | Regra |
|---|---|
| RN-050 | Recorrência tem: periodicidade (semanal, mensal, anual, a cada N meses), dia de referência ou regra de dia útil, valor, tipo (fixo ou variável), data de início e fim opcional. |
| RN-051 | O sistema materializa as ocorrências como compromissos **previstos** numa janela móvel de 13 meses. A janela é renovada diariamente pela tarefa agendada. |
| RN-052 | Ocorrência de recorrência **fixa ou contratual** que entra no horizonte H vira **pendente** automaticamente (P-07). Ocorrência **variável** continua prevista até o usuário informar o valor real, quando vira pendente. |
| RN-053 | Alterar a recorrência (valor, dia, fim) cancela e regenera só as ocorrências futuras sem liquidação. Ocorrências passadas, pendentes com liquidação e confirmadas não mudam. |
| RN-054 | Encerrar a recorrência cancela as ocorrências futuras sem liquidação, com motivo "recorrência encerrada". |
| RN-055 | Ocorrência criada para dia inexistente (ex.: dia 31 em abril) vai para o último dia do mês. |

## 8. Transferências, reservas e metas

| ID | Regra |
|---|---|
| RN-060 | Transferência entre contas próprias é uma transação com duas pernas (T05 a T07). Não existe transferência "pela metade": origem e destino são gravados juntos, atomicamente. |
| RN-061 | Transferência entre classes muda o disponível: livre → reserva reduz o disponível (T06); reserva → livre aumenta (T07). O saldo bancário não muda. |
| RN-062 | Aporte em meta (pós-MVP) = transferência para conta de reserva marcada com a meta. Nunca é despesa. O valor acumulado da meta = soma das transferências marcadas − retiradas marcadas. |
| RN-063 | Aporte planejado é transação prevista de transferência; entra no projetado (reduz o livre projetado), não no comprometido. |
| RN-064 | Dinheiro "reservado" = saldo das contas de classe reserva. Dinheiro "comprometido" = saldo comprometido (H). Os dois nunca se somam no disponível. |

## 9. Cartões de crédito

### 9.1 Ciclo e alocação

| ID | Regra |
|---|---|
| RN-070 | Cada fatura é identificada pelo **vencimento original**. Ela cobre as compras com data a partir do fechamento anterior (inclusive) até o dia anterior ao seu fechamento. Compra **no dia do fechamento** vai para a fatura seguinte. Regra configurável por cartão. |
| RN-071 | Data de fechamento e de vencimento de cada ciclo: dia de fechamento e dia de vencimento do cartão. Se o dia de vencimento for menor ou igual ao de fechamento, o vencimento cai no mês seguinte ao fechamento. |
| RN-072 | Vencimento efetivo = vencimento original, ou o próximo dia útil bancário se ele cair em dia não útil (pagamento sem encargos até o efetivo). O horizonte H e os relatórios usam o **vencimento original**; alertas e atraso usam o **efetivo**. |
| RN-073 | Compra parcelada em n vezes: parcela k (1..n) vai para a fatura do ciclo da compra + (k − 1). Valores pela RN-005. |
| RN-074 | Parcelas e faturas são **alocações** do passivo do cartão; não criam pernas (ADR-004). Soma das parcelas de uma compra = total da compra (invariante I-06). |
| RN-075 | Antes do MVP-3 não existem faturas gravadas. A "parte devida até H" é calculada pelas mesmas RN-070 a RN-073, aplicadas aos dados da compra. A tela indica que é estimativa. |

### 9.2 Faturas

| ID | Regra |
|---|---|
| RN-076 | Estados da fatura: **aberta** (antes do fechamento), **fechada** (após o fechamento; congelada para compras: novas compras vão para a fatura seguinte, e só aceita encargos informados pelo emissor e lançamentos de conciliação, RN-079, RN-081), **paga parcialmente**, **paga**, **vencida** (vencimento efetivo passou com valor em aberto). Os estados são calculados. |
| RN-077 | Valor da fatura = parcelas alocadas + encargos alocados + saldo transportado da fatura anterior − créditos alocados (estornos, pagamento acima). |
| RN-078 | Pagamento de fatura (T11) é alocado à fatura mais antiga com valor em aberto, salvo escolha do usuário. |
| RN-079 | Pagamento parcial: depois do vencimento efetivo, o valor em aberto é **transportado** para a fatura seguinte como "saldo anterior". Encargos (juros do rotativo, IOF, multa) só são lançados quando o usuário os informa a partir da fatura do emissor (T12). O sistema não calcula juros do rotativo por conta própria. A fatura com saldo transportado gera alerta forte. |
| RN-080 | Pagamento acima do valor em aberto gera **crédito** alocado à próxima fatura. O passivo do cartão pode ficar negativo (crédito a favor do usuário). |
| RN-081 | Conciliação de fatura: o usuário informa o total da fatura fechada do emissor. Diferença → o sistema lista causas prováveis (compra não lançada, encargo, estorno do emissor) e o usuário lança o que falta. Nenhum ajuste automático contra patrimônio em cartão: a diferença precisa ser explicada por movimentações. |

### 9.3 Estornos no cartão

| ID | Regra |
|---|---|
| RN-082 | **Estorno técnico** (lançamento errado, via "Corrigir"): anula a compra na **competência original**, como se não tivesse existido. Alocações são removidas por completo. |
| RN-083 | **Estorno comercial** (devolução ou cancelamento pelo lojista): transação nova, com data e competência do estorno, vinculada à compra (T13). Total ou parcial. |
| RN-084 | Estorno comercial de compra parcelada: parcelas ainda não faturadas são canceladas a partir da última; o valor das parcelas já faturadas e não compensadas vira crédito na fatura aberta. Ex.: S10. |
| RN-085 | Estorno de compra de terceiro reduz o valor a receber da pessoa na mesma proporção. Se a pessoa já pagou, o excedente vira valor a devolver (a receber negativo), mostrado em destaque. |

### 9.4 Limite

| ID | Regra |
|---|---|
| RN-086 | Limite disponível calculado = limite total − saldo do passivo do cartão. O passivo inclui parcelas futuras (a compra parcelada consome o limite total na compra). Crédito a favor aumenta o disponível. |
| RN-087 | Conciliação de limite: o usuário informa o limite disponível do app do emissor. Diferenças e causas prováveis: pagamento ainda em compensação (D+1/D+2), compra ou encargo não lançado, mudança do limite total, emissor que não consome o limite pelo total do parcelado. |
| RN-088 | Mudança do limite total é evento do cartão, com data, sem perna no Ledger. Diferença sem causa financeira é registrada como evento de conciliação de limite. |

### 9.5 Abertura e registro provisório

| ID | Regra |
|---|---|
| RN-089 | Abertura do cartão em 01/11/2026 por itens (T24, T25): fatura fechada a vencer (um item, já faturado), compras da fatura aberta, parcelas restantes de compras antigas (data original, total, n, parcelas já faturadas). Passivo de abertura = soma dos itens. Ex.: S00. |

## 10. Valores a receber

| ID | Regra |
|---|---|
| RN-100 | Valor a receber nasce de: empréstimo a terceiro (T14), compra de terceiro no cartão (T09, T10) ou item de abertura (T25). |
| RN-101 | Cronograma: compra de terceiro à vista vence no vencimento original da fatura em que a compra cai; parcelada gera uma parcela a receber por parcela do cartão, com o mesmo vencimento. Empréstimo a terceiro: parcelas e datas informadas, rateio RN-005. O usuário pode alterar as datas a receber. |
| RN-102 | Parcelas a receber são **alocações** do ativo "A receber" (não criam pernas). Soma das parcelas = valor a receber de origem. |
| RN-103 | Recebimento (T15) é alocado à parcela em aberto de vencimento mais antigo da pessoa, salvo escolha do usuário. Recebimento parcial deixa a parcela "recebida parcialmente". |
| RN-104 | Recebimento **nunca** é receita; valor a receber **nunca** entra em saldo real, disponível ou comprometido. No projetado, entra como "a receber previsto" na data de vencimento. |
| RN-105 | Parcela a receber com vencimento passado e valor em aberto é "atrasada" (calculado). Parcelas atrasadas **não** entram no projetado futuro, até o usuário reagendar. |
| RN-106 | Baixa (T16): total ou parcial, com motivo (perdão ou inadimplência). Parcelas baixadas ficam "baixadas". A baixa pode ser estornada se a pessoa pagar depois. |
| RN-107 | Recebimento acima do devido exige confirmação; o excedente vira "a devolver" para a pessoa. |

## 11. Dívidas e consórcio

### 11.1 Empréstimo Price

| ID | Regra |
|---|---|
| RN-110 | Parcela (PMT) = S × i ÷ (1 − (1 + i)^−n), arredondada para centavos. S = saldo devedor, i = taxa mensal, n = parcelas restantes. Se o contrato informa outro valor de parcela, vale o do contrato e a diferença aparece como aviso. |
| RN-111 | Juros do período = saldo devedor × i, arredondado. Principal = PMT − juros. Última parcela = saldo devedor restante + juros (absorve resíduos). Ex.: S09. |
| RN-112 | Pagamento de parcela (T17) separa principal, juros e encargos. O valor de juros vem da tabela; se o extrato do banco mostrar valor diferente, vale o extrato e a tabela é recalculada a partir do novo saldo. |
| RN-113 | Amortização extraordinária (T18) reduz o saldo devedor. Padrão **reduzir prazo** (ADR-027): mantém a PMT e recalcula o número de parcelas; a última absorve o resíduo. Opção reduzir parcela: mantém o prazo e recalcula a PMT. |
| RN-114 | Juros economizados = juros totais restantes da tabela atual − juros totais restantes da tabela após a amortização, calculados com as mesmas premissas. |
| RN-115 | Toda simulação mostra o aviso: "Estimativa com taxa constante e juros mensais, sem tarifas, seguros ou cálculo proporcional por dias. O valor real depende das regras do contrato e do banco." |
| RN-116 | Parcelas futuras da dívida são compromissos previstos (com pernas pretendidas de principal e juros), materializados até o fim do contrato. Viram pendentes ao entrar em H (contratuais, RN-052). |
| RN-117 | Antes do MVP-5 (registro provisório), o usuário lança a parcela informando principal e juros do extrato; o saldo devedor é o do Ledger. |

### 11.2 Consórcio não contemplado

| ID | Regra |
|---|---|
| RN-118 | Parcela de consórcio é despesa da categoria Consórcio (T19), recorrência contratual com número de parcelas restantes. Reajuste é informado pelo usuário e vale para as parcelas futuras (RN-053). Sem passivo e sem juros (ADR-008). |

## 12. Estornos, cancelamentos e correções

| ID | Regra |
|---|---|
| RN-120 | Estorno inverte todas as pernas da original, com vínculo "estorna". Só transações confirmadas podem ser estornadas, e só uma vez (unicidade no banco). |
| RN-121 | Estorno parcial existe só para compras no cartão (estorno comercial parcial) e reembolsos. Nos demais casos, estorna-se o total e lança-se o correto. A soma dos estornos parciais e reembolsos de uma transação nunca passa do valor original; um estorno total feito depois de parciais estorna só o restante; tentativa que ultrapasse o total é recusada. |
| RN-122 | "Corrigir" = estorno técnico (competência original) + nova transação, numa operação atômica, com vínculo "corrige". Se a original liquidava um compromisso, a liquidação passa para a nova. |
| RN-123 | Estornar transação que liquidou compromisso reabre o valor em aberto (RN-044). Estornar pagamento de fatura reabre a fatura. |
| RN-124 | Transações estornadas e seus estornos ficam ocultos nas listas e relatórios por padrão; o filtro "mostrar estornos" exibe os pares. Totais sempre consideram os dois (somam zero). |
| RN-125 | Cancelamento (previsto ou pendente) exige motivo e nunca gera pernas. |

## 13. Conciliação de saldo

| ID | Regra |
|---|---|
| RN-130 | O usuário informa o saldo de uma conta numa data. O sistema compara com o saldo calculado na mesma data (até o fim do dia). |
| RN-131 | Com diferença, o sistema primeiro sugere conferir lançamentos esquecidos. Só depois oferece o ajuste (T27), com descrição obrigatória. |
| RN-132 | Ajustes ficam na conta Patrimônio:Ajustes de conciliação. Não são receita nem despesa, mas aparecem em linha própria nos relatórios ("diferenças de conciliação"). |
| RN-133 | Cada conciliação aceita grava um marco. Lançar ou estornar transação com data anterior a um marco exige confirmação, porque desfaz a conciliação daquela data. O marco passa a "a reconciliar". |

## 14. Saldos — fórmulas

Notação:
- `hoje` = data atual;
- `H` = horizonte (RN-140);
- `D` = data da projeção;
- "aberto" = valor em aberto (RN-041).

| ID | Indicador | Fórmula |
|---|---|---|
| RN-140 | Horizonte H | Data do salário previsto **mais antigo ainda não recebido** (liquidado). H só avança para o salário seguinte quando o usuário confirma o recebimento (decisão do usuário). Se o salário atrasar (data passou sem confirmação), H = amanhã até a confirmação, e o dashboard mostra "salário atrasado". Exclusive: compromissos com vencimento original **< H** entram. Configurável para "fim do mês" (H = primeiro dia do mês seguinte). Sem salário previsto, usa fim do mês. |
| RN-141 | Saldo bancário | Σ pernas confirmadas ou estornadas das contas de classe **livre** e **reserva**, até hoje. |
| RN-142 | Saldo de benefícios | Σ pernas confirmadas ou estornadas das contas de classe **benefício**. |
| RN-143 | Saldo comprometido (H) | Σ aberto das faturas com vencimento original < H **+** Σ aberto dos compromissos pendentes de saída (contas, parcelas de dívida, consórcio) com vencimento original < H, inclusive atrasados. Não inclui: previstos, receitas, valores a receber, aportes planejados, compras de terceiro já cobertas pelas faturas (já estão dentro da fatura). |
| RN-144 | Saldo comprometido total | Σ aberto de todas as faturas e parcelas de cartão futuras **+** Σ aberto de todos os compromissos com prazo final (parcelas de dívida, consórcio, contas parceladas) **+** pendentes avulsos. Recorrências sem data final (aluguel, assinaturas) não entram; aparecem no comprometimento de renda mês a mês. |
| RN-145 | Saldo disponível | Saldo das contas **livres** − saldo comprometido (H). |
| RN-146 | Saldo projetado (D) | Saldo das contas livres hoje **+** Σ receitas previstas e pendentes ainda não recebidas com data em [hoje, D] (receita atrasada conta como de hoje, RN-023) **+** Σ parcelas a receber em aberto com vencimento em [hoje, D] **−** Σ compromissos de saída previstos e pendentes com vencimento ≤ D, inclusive atrasados **−** Σ aberto das faturas e parcelas com vencimento original ≤ D **−** Σ aportes planejados (livre → reserva) com data ≤ D **+** Σ retiradas planejadas (reserva → livre) com data ≤ D. |
| RN-147 | Total guardado | Σ saldo das contas de classe reserva. |
| RN-148 | Total de dívidas | Σ saldo das contas de passivo de dívida **+** Σ saldo devedor dos cartões. |
| RN-149 | Comprometimento de renda (mês M) | Σ parcelas próprias de cartão das faturas com vencimento em M **+** compromissos de saída previstos e pendentes em M (inclusive recorrências) **+** aportes planejados em M. Comparado com a renda prevista em M. Mostra valor, % e sobra. Parcelas de terceiros aparecem em linha separada ("no seu cartão, a receber"). |

Disjunção (provada no S14):
- uma compra no cartão aparece só via fatura, nunca como compromisso;
- um valor a receber nunca reduz o comprometido;
- uma reserva nunca entra no disponível;
- um previsto nunca entra no comprometido;
- um benefício nunca entra em nenhum desses saldos.

## 15. Projeções e cenários

| ID | Regra |
|---|---|
| RN-150 | Projeção de 7, 15 e 30 dias = RN-146 com D = hoje + 7, 15 ou 30, detalhando: saldo inicial (livre), receitas previstas, a receber, despesas previstas, faturas, pagamentos de dívidas, aportes, saldo final. |
| RN-151 | Projeção diária (série) para gráfico: saldo projetado ao fim de cada dia até D. Dia com saldo projetado abaixo do saldo mínimo de segurança é destacado. |
| RN-152 | Cenários (pós-MVP) são cópias temporárias das premissas (ex.: +10% despesas, renda extra, amortização extra). Nunca gravam transações. Cada cenário mostra a diferença em relação ao projetado base. |
| RN-153 | Toda tela de projeção mostra o rótulo "Projeção" e as premissas usadas. |

## 16. Relatórios

| ID | Regra |
|---|---|
| RN-160 | Despesas e receitas de um período = Σ pernas em contas de resultado de transações confirmadas (e seus estornos), pela **data de competência**. |
| RN-161 | Visão por compra (padrão): compra parcelada conta pelo total na competência da compra. |
| RN-162 | Visão por parcela (decisão do usuário, ADR-005): cada parcela de compra no cartão conta no **mês do vencimento original da fatura** em que cai. Compra à vista no cartão = uma parcela, no mês da sua fatura. Despesas fora do cartão continuam pela competência. Itens de abertura entram pelo mês da fatura em que caem, marcados "compra anterior ao início". Créditos de estorno contam no mês da fatura que os recebe. A visão existe a partir do MVP-3, quando as faturas passam a existir (ADR-005); antes disso, só a visão por compra é exibida. Os totais das duas visões diferem e nunca se somam. |
| RN-163 | Visão de caixa: entradas e saídas das contas livres pela data da operação, incluindo pagamento de fatura, transferências para reserva e amortizações. Usada para "para onde foi o dinheiro". |
| RN-164 | Nunca são receita nem despesa, em nenhuma visão: transferências, aportes e retiradas de reserva, pagamento de fatura, compra de terceiro, empréstimo a terceiro, recebimento de terceiro, amortização de principal, saldos e itens de abertura, ajustes de conciliação. |
| RN-165 | Estorno comercial reduz a despesa na competência do estorno (RN-083). Estorno técnico anula na competência original (RN-082). |
| RN-166 | "Pagamentos realizados no mês" = Σ liquidações confirmadas de compromissos e de faturas, pela data da operação. |
| RN-167 | "Economia do mês" = receitas (exceto benefícios) − despesas pagas com contas livres, por competência. É mostrada junto com a variação do total guardado. |

## 17. Dias úteis e vencimentos

| ID | Regra |
|---|---|
| RN-090 | Dia útil = segunda a sexta, exceto feriados da tabela e segunda e terça de Carnaval (P-02). |
| RN-091 | 5º dia útil do mês M = quinto dia útil contado a partir do dia 1º de M. Ex.: 09/11/2026 (dia 2 é Finados) e 07/12/2026. |
| RN-092 | Feriados carregados: nacionais (1/1, Sexta-feira Santa, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 20/11, 25/12); estadual SP (9/7); municipais da capital (25/1, Corpus Christi); Carnaval calculado pela Páscoa. Tabela editável. |
| RN-093 | Vencimento em dia não útil: o vencimento efetivo é o próximo dia útil (contas e faturas), salvo se o usuário marcar a conta como "antecipa" (ex.: algumas concessionárias). |
| RN-094 | Em dezembro, o sistema lembra o usuário de revisar os feriados do ano seguinte. |

## 18. Idempotência, duplicidade e concorrência

| ID | Regra |
|---|---|
| RN-170 | Toda criação de transação recebe uma chave de idempotência gerada ao abrir o formulário. Mesma chave → mesma transação devolvida, nada novo gravado (S12). |
| RN-171 | Aviso de possível duplicidade (sem bloquear): mesma conta, mesmo valor, mesma data e descrição parecida nas últimas 24 horas. |
| RN-172 | Edição de entidade editável (conta, cartão, compromisso não confirmado, recorrência) exige o número de versão lido. Versão desatualizada → recusa e recarga. |
| RN-173 | Operações compostas são atômicas: transferência, compra mista, Corrigir, pagamento com juros, estorno com realocação, abertura por itens, geração de recorrências. |

## 19. Validações de entrada

| ID | Regra |
|---|---|
| RN-180 | Valor > 0 em todo formulário. O sinal vem do tipo de operação, nunca do usuário. Máximo: R$ 9.999.999,99 por lançamento (proteção contra digitação). |
| RN-181 | Data da operação confirmada não pode ser futura. Previstos e pendentes podem. Datas anteriores a 01/11/2026 só para itens de abertura. |
| RN-182 | Parcelas: 2 a 48 no cartão; 1 a 360 em dívidas. |
| RN-183 | Taxa de juros: 0% a 30% ao mês, com até 6 casas decimais. Fora disso, confirmação explícita. |
| RN-184 | Dia de fechamento e vencimento de cartão: 1 a 31. Fechamento e vencimento não podem ser iguais. |
| RN-185 | Conta, cartão, categoria ou pessoa arquivados não aceitam lançamentos novos. Arquivamento só é permitido sem compromissos futuros em aberto. |
| RN-186 | Despesa com benefício só pode usar categorias marcadas como "aceita benefício" (ex.: mercado, refeição). |

## 20. Auditoria

| ID | Regra |
|---|---|
| RN-190 | Registro de auditoria só aceita inserção. Grava: data e hora, aparelho, ação, entidade, identificador, valores antes e depois (campos alterados), motivo quando houver. |
| RN-191 | Auditados: toda transação e mudança de estado, compromissos, recorrências, contas, cartões (inclusive limite), pessoas, dívidas, categorias, configurações, conciliações, logins, falhas de login, PIN, aparelhos, backups e restaurações. |
| RN-192 | Auditoria não registra senha, PIN, tokens nem segredos. |

## 21. Invariantes

Verificadas por testes, no backup e na tela "Saúde dos dados" (`architecture.md` §6.6).

| ID | Invariante |
|---|---|
| I-01 | Σ pernas de cada transação = 0. |
| I-02 | Transação confirmada tem ≥ 2 pernas e nenhuma perna com valor zero. |
| I-03 | Cada estorno aponta para uma transação confirmada; cada transação tem no máximo um estorno total; o estorno total é o espelho exato do restante da original; Σ estornos parciais + reembolsos ≤ valor original. |
| I-04 | Saldo de cada conta, recalculado do zero, = valor exibido. |
| I-05 | Σ liquidações de um compromisso ≤ valor planejado + excedentes classificados. |
| I-06 | Σ parcelas de cada compra no cartão = total da compra; Σ parcelas a receber = valor a receber de origem. |
| I-07 | Σ alocações de faturas abertas, fechadas e futuras de um cartão = saldo do passivo do cartão. |
| I-08 | Σ saldos de ativo − Σ saldos de passivo = Σ patrimônio (abertura + ajustes) + Σ receitas − Σ despesas (equação patrimonial; S14). |
| I-09 | Nenhuma transação confirmada tem data anterior a 01/11/2026, exceto as de abertura. |
| I-10 | Nenhum compromisso aponta para conta, cartão ou categoria arquivados com vencimento futuro em aberto. |

## 22. Alterações após a aprovação

| Regra | Detalhe definido na Fase 2A | Motivo |
|---|---|---|
| RN-154 (novo, ADR-041) | **Pode gastar** = disponível (RN-145) − saldo mínimo de segurança − Σ aberto dos compromissos de saída **previstos** com vencimento original < H (ex.: conta variável estimada). É o número principal da tela inicial. O disponível e o comprometido (RN-143) não mudam, e o disponível aparece na conta. Sem mínimo configurado, o mínimo vale zero. Se o resultado ficar abaixo do mínimo ou o dinheiro não cobrir as contas, a tela mostra a situação em frase, sem número negativo grande | Decisões do usuário em 08/11/2026 |
| RN-051 | A janela móvel vai de hoje em diante. Recorrência criada com início no passado não gera ocorrência já vencida; o que aconteceu antes é lançado como movimentação | Evita salário "atrasado" e conta vencida que nunca existiram |
| RN-052 | "Vira pendente ao entrar em H" vale só para **saídas**. Receita prevista continua prevista até ser recebida | RN-020 e RN-143: receita não entra no comprometido; o próprio salário define H |
| §3.4 | Conta pendente, atrasada e já paga em parte aparece como **Atrasado** | É o que exige ação; "pago parcialmente" continua valendo para as não vencidas |
| RN-042, RN-044 | Estornar a liquidação de uma conta encerrada desfaz o encerramento | O motivo do encerramento deixou de existir |
| RN-122 | "Corrigir" é recusado em pagamento de conta e em despesa com reembolso. O caminho é estornar e lançar de novo | ADR-039 |
| T20, RN-121 | Reembolso entra na competência da data do reembolso. Só existe para despesa paga (T02, T03). Benefício volta para benefício, e o restante para conta comum | Mesma lógica do estorno comercial (T13); benefício não vira dinheiro |
