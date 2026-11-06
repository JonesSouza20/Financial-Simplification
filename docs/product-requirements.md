# Requisitos do Produto — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.2 |
| Data | 06/11/2026 |
| Etapa | 2 — Definição (Fase A) |
| Status | Versão 0.1 aprovada em 06/11/2026; versão 0.2 com alterações da Fase B (§14), aprovada em 06/11/2026 |
| Documentos relacionados | `architecture.md`, `decisions.md` |

---

## 1. Visão

Sistema pessoal, de uso individual, para centralizar e controlar toda a vida financeira: dinheiro em contas, cartões, contas a pagar, receitas, dívidas, valores a receber, reservas e metas.

O produto existe para dar **controle, previsibilidade e capacidade de planejamento**. Ele deve responder rapidamente "quanto tenho", "quanto devo", "quanto já está comprometido" e "como estarei nos próximos meses", sempre separando com clareza o que é **real** do que é **projeção**.

Três compromissos orientam todas as decisões:

1. **Confiabilidade dos números.** Todo valor exibido é calculado a partir de um registro central de movimentações (Livro-Razão) e pode ser rastreado até sua origem.
2. **Uso real no dia a dia.** Lançar um gasto pelo celular, na hora, em poucos toques.
3. **Simplicidade de operação.** Roda no computador do usuário, sem custo mensal e sem infraestrutura complexa.

## 2. Contexto de uso

### 2.1 Usuário

- Uma única pessoa, dona dos dados. Não há outros usuários, perfis ou permissões compartilhadas.
- Conhecimento técnico intermediário: segue comandos e ajustes simples. Instalação, atualização, backup e restauração precisam de procedimentos passo a passo.
- Hoje não controla as finanças. Não há dados antigos para migrar.

### 2.2 Situação financeira levantada na descoberta

| Tema | Situação |
|---|---|
| Renda principal | Salário CLT fixo, pago uma vez por mês no 5º dia útil (sábado não conta) |
| Outras entradas | Benefícios (VR/VA) e renda extra eventual (13º, férias, bônus, restituição) |
| Contas e carteiras | 3 a 4, incluindo a carteira de benefícios |
| Cartões de crédito | 4 ou mais, com compras parceladas frequentes (sem juros) |
| Dívidas com juros | 1 empréstimo/financiamento, Tabela Price, taxa e saldo devedor conhecidos |
| Consórcio | Veículo, não contemplado, só sorteio (sem lance) |
| Valores a receber | Empréstimos a terceiros parcelados com datas; compras de terceiros nos cartões do usuário |
| Reserva | Ainda não existe |
| Comportamento | Raramente falta dinheiro, mas às vezes atrasa contas |
| Local | Cidade de São Paulo/SP |

### 2.3 Rotina e ambiente

- Lançamento **na hora do gasto, pelo celular**. Revisões e análises no computador.
- Servidor no PC do usuário (Windows 11 Home), que pode ficar sempre ligado.
- Celular acessa de qualquer lugar por VPN privada (Tailscale), sem expor o PC na internet.
- Alertas de vencimento chegam por bot do Telegram, com nome e valor.
- Início do uso: **01/11/2026**. O usuário lança o que já aconteceu no mês corrente.

### 2.4 Objetivos do usuário, em ordem de prioridade

1. Quitar dívidas antes do prazo.
2. Parar de atrasar contas.
3. Montar uma reserva.
4. Entender os próprios gastos.

A prioridade 1 orienta o MVP. Ela depende, porém, de uma base contábil confiável (seção 8): sem saldos e compromissos corretos, qualquer simulação de quitação partiria de números falsos.

## 3. Perguntas que o sistema responde

| Pergunta | Onde é respondida | Indicador / fórmula (ver glossário) | Entrega |
|---|---|---|---|
| Quanto dinheiro tenho atualmente? | Dashboard | Saldo bancário | MVP-1 |
| Quanto posso gastar sem comprometer contas? | Dashboard | Saldo disponível | MVP-2 |
| Quanto tenho guardado? | Dashboard, Contas | Soma das contas de classe reserva | MVP-1 |
| Quanto devo? | Dashboard, Dívidas | Saldo devedor das dívidas + saldo devedor dos cartões | MVP-1 (provisório), MVP-5 (completo) |
| Quanto tenho de contas pendentes? | Dashboard, Pagamentos | Soma do valor em aberto das obrigações pendentes e vencidas | MVP-2 |
| Qual é meu próximo pagamento? | Dashboard | Próxima obrigação em aberto por data | MVP-2 |
| Quanto preciso pagar nos próximos 7, 15 e 30 dias? | Dashboard, Projeções | Saídas previstas e pendentes, faturas e parcelas de dívida com vencimento até hoje + 7, 15 ou 30 dias (projeção, RN-150) | MVP-6 |
| Quanto vai sobrar depois de pagar as contas? | Dashboard | Saldo disponível e saldo projetado | MVP-2 / MVP-6 |
| Quanto já gastei neste mês? | Dashboard, Relatórios | Despesas por competência no mês (visões por compra e por parcela) | MVP-1 (por compra), MVP-3 (por parcela) |
| Quanto consegui economizar? | Dashboard, Relatórios | Receitas − despesas do mês, e variação das reservas | MVP-6 |
| Quando vou quitar determinada dívida? | Dívidas | Previsão de quitação pela tabela de amortização | MVP-5 |
| Como posso antecipar a quitação? | Dívidas | Simulação de pagamento extra e quitação antecipada | MVP-5 |
| Quanto preciso guardar por mês para uma meta? | Metas | Valor faltante ÷ meses restantes | Pós-MVP |
| Como estarei em 3, 6 e 12 meses? | Projeções | Saldo projetado por mês, com cenários | Pós-MVP |
| Quanto da minha renda futura já está comprometida? | Dashboard, Cartões | Comprometimento de renda (12 meses) | MVP-6 |
| Quanto me devem e quem está atrasado? | Valores a receber | Saldo a receber por pessoa e parcelas atrasadas | MVP-4 (registro básico no MVP-1) |

## 4. Glossário

Termos usados de forma idêntica em todos os documentos.

### 4.1 Estrutura contábil

- **Livro-Razão (Ledger):** registro central e único de todas as movimentações financeiras. Nenhum módulo mantém saldo próprio.
- **Transação:** uma operação financeira (ex.: uma compra, uma transferência). Tem duas ou mais **pernas** cuja soma é zero.
- **Perna:** lançamento de um valor em uma conta contábil. Débito e crédito são pernas de sinais opostos.
- **Conta contábil:** "gaveta" interna do Ledger. Tipos:
  - **ativo:** contas bancárias, espécie, carteira de benefícios, reservas, valores a receber;
  - **passivo:** cartões de crédito, dívidas;
  - **receita:** uma por categoria de receita;
  - **despesa:** uma por categoria de despesa;
  - **patrimônio:** saldo de abertura e ajustes de conciliação.

  O usuário não lida com contas contábeis diretamente; ele vê contas, cartões, categorias e pessoas.
- **Conta financeira:** conta do usuário que guarda dinheiro (conta corrente, conta digital, espécie, reserva, carteira de benefícios). Cada uma é uma conta contábil de ativo.
- **Classe da conta financeira:**
  - **livre:** dinheiro de uso geral (corrente, digital, espécie);
  - **reserva:** dinheiro separado para reserva ou metas;
  - **benefício:** VR/VA, de uso restrito.
- **Saldo de abertura:** valor de cada conta financeira em 01/11/2026, registrado contra a conta de patrimônio.
- **Itens de abertura:** obrigações e direitos que já existiam em 01/11/2026, registrados item a item, e não como um valor único, para preservar seus cronogramas:
  - cartões: fatura fechada a vencer, compras da fatura aberta e parcelas restantes de compras antigas, cada uma com data original, total, número de parcelas, parcelas já faturadas e indicação de própria ou de terceiro;
  - dívida: saldo devedor, taxa e parcelas restantes;
  - consórcio: parcelas restantes;
  - empréstimos a terceiros: parcelas restantes.

  Itens próprios são lançados contra a conta de patrimônio (não viram despesa de novembro); itens de terceiro, contra o valor a receber da pessoa.

### 4.2 Estados

- **Estado da movimentação** (no Ledger):
  - **previsto:** planejado, ainda sem obrigação concreta (ex.: salário do próximo mês);
  - **pendente:** obrigação ou direito concreto, ainda não liquidado (ex.: conta de luz recebida);
  - **confirmado:** aconteceu de fato; produz efeito nos saldos e é imutável;
  - **cancelado:** previsto ou pendente que não vai mais acontecer;
  - **estornado:** confirmado que foi anulado por um estorno vinculado.
- **Status de uma conta a pagar** (como aparece para o usuário), derivado do estado:

| Status exibido | Origem |
|---|---|
| Previsto | Movimentação prevista |
| Pendente | Movimentação pendente, vencimento hoje ou no futuro |
| Agendado | Pendente marcada como agendada no banco, com data de débito |
| Atrasado | Pendente com vencimento já passado (calculado, não gravado) |
| Pago parcialmente | Pendente com liquidações confirmadas menores que o valor total |
| Pago | Valor total liquidado por movimentações confirmadas |
| Cancelado | Movimentação cancelada |

### 4.3 Saldos

As definições abaixo são **disjuntas**: cada item entra em um único grupo, conforme seu estado e origem. Fórmulas detalhadas e exemplos numéricos ficam em `business-rules.md` (Fase B).

- **Saldo bancário:** soma das pernas **confirmadas** das contas de classe livre e reserva. É o dinheiro que existe de fato nas instituições. Não inclui nada previsto.
- **Saldo de benefícios:** soma das pernas confirmadas das contas de classe benefício. Exibido separado; não entra em nenhum outro saldo.
- **Saldo comprometido (horizonte H):** obrigações já assumidas, com vencimento até H, a pagar com contas livres:
  - faturas fechadas ainda não pagas;
  - fatura aberta (compras já feitas);
  - contas pendentes e atrasadas;
  - compromissos fixos: parcelas de dívida e de consórcio, e recorrências de valor fixo ou contratual (aluguel, internet, assinaturas, mensalidades).

  Regra de enquadramento (decidida pelo usuário, P-07): dentro de H, recorrências de valor fixo ou contratual viram **pendente** automaticamente e entram no comprometido. Contas de valor variável estimado (luz, água, mercado) ficam **previstas** e entram só no saldo projetado, até o usuário informar o valor real.

  Uma compra no cartão entra **só** pela fatura, nunca também como conta pendente. Receitas previstas e valores a receber **não** reduzem o comprometido.
- **Saldo comprometido total:** obrigações já assumidas sem limite de data: todas as faturas e parcelas futuras de cartão, parcelas de dívida e de consórcio, contas parceladas e pendentes avulsos. Recorrências sem data final (aluguel, assinaturas) não entram. Só informativo; não entra no disponível (RN-144).
- **Saldo disponível:** saldo bancário das contas **livres** − saldo comprometido (H). Exclui reservas e benefícios. Não soma receitas previstas.
- **Saldo projetado (data D):** saldo bancário das contas livres + receitas previstas e pendentes até D + valores a receber previstos até D − contas previstas e pendentes até D − faturas e parcelas até D − aportes planejados até D + retiradas planejadas da reserva até D. Itens atrasados contam como de hoje; parcelas a receber atrasadas ficam de fora até serem reagendadas (fórmula completa: RN-146). Sempre rotulado como **projeção**.
- **Horizonte H:** data-limite usada no saldo comprometido e no disponível. Padrão: **até a data do próximo salário ainda não recebido** (exclusive); H só avança quando o salário é confirmado (A-02). Alternativa configurável: fim do mês. Decidido pelo usuário (P-01).
- **Saldo mínimo de segurança:** valor definido pelo usuário. Quando o disponível ou o projetado fica abaixo dele, o sistema alerta.

### 4.4 Cartões

- **Compra no cartão:** gera despesa (ou valor a receber, se for de terceiro) e aumenta o passivo do cartão pelo valor total, na data da compra. Não tira dinheiro de conta bancária.
- **Parcela:** fração de uma compra parcelada alocada a uma fatura. Parcelas e faturas são **alocações** sobre o passivo do cartão; não criam novas pernas no Ledger.
- **Fatura:** agrupamento de parcelas e lançamentos de um ciclo. Estados: aberta, fechada, paga parcialmente, paga, vencida.
- **Liquidação de fatura:** pagamento do cartão a partir de uma conta financeira. Reduz o passivo; não é despesa nova.
- **Limite disponível:** limite total − saldo devedor do cartão (inclui parcelas futuras) + créditos.
- **Comprometimento de renda:** para cada um dos próximos 12 meses, quanto da renda prevista já está tomado por obrigações assumidas.

### 4.5 Relatórios

- **Competência:** mês ao qual o gasto pertence. Para compras no cartão, é o mês da compra.
- **Caixa:** mês em que o dinheiro saiu ou entrou na conta financeira.
- **Visão por compra:** compra parcelada aparece pelo valor total no mês da compra.
- **Visão por parcela:** cada parcela aparece no mês de sua fatura (vencimento original). Compra à vista no cartão conta como uma parcela, no mês da sua fatura (RN-162).

### 4.6 Valores a receber

- **Valor a receber:** direito de receber dinheiro de uma pessoa (empréstimo feito a ela ou compra dela no cartão do usuário). É um ativo, nunca receita.
- **Recebimento:** liquidação total ou parcial de um valor a receber. Não gera receita.
- **Baixa:** reconhecimento de que um valor não será recebido. Vira despesa de perda, com motivo.

### 4.7 Correções e controle

- **Estorno:** transação que anula outra transação confirmada, vinculada a ela. Dois tipos:
  - **estorno técnico:** corrige lançamento errado e anula na competência original;
  - **estorno comercial:** devolução ou cancelamento pelo lojista; vale na data do estorno (RN-082, RN-083).
- **Corrigir:** ação da interface que faz, em uma única operação, o estorno da transação errada e o lançamento da transação correta.
- **Ajuste de conciliação:** transação que registra a diferença entre o saldo calculado e o saldo informado pela instituição, sem apagar o histórico.
- **Chave de idempotência:** identificador único de cada envio de formulário. Impede que um duplo toque ou reenvio registre a mesma operação duas vezes.
- **Porta de validação:** conjunto de critérios que uma entrega do MVP precisa cumprir antes de a próxima começar.
- **Dia útil:** segunda a sexta, exceto feriados nacionais, estaduais e da cidade de São Paulo cadastrados no calendário do sistema, e exceto segunda e terça de Carnaval (P-02).

## 5. Princípios do produto

1. **Real e projetado nunca se misturam.** Todo número projetado tem rótulo e estilo visual próprios.
2. **Todo número tem origem.** Qualquer indicador permite abrir a lista de movimentações que o compõem.
3. **Nada é apagado.** Previstos e pendentes são cancelados; confirmados são estornados. O histórico é sempre preservado.
4. **Nenhuma dupla contagem.** Transferências, aportes em reserva, pagamentos de fatura e recebimentos de terceiros são neutros para receitas e despesas.
5. **Cálculos exatos.** Dinheiro nunca é calculado com ponto flutuante.
6. **Estimativas não são garantias.** Simulações de dívida e projeções sempre informam que são estimativas e quais premissas usaram.
7. **Lançar é rápido.** O lançamento mais comum (gasto no cartão ou débito) cabe em uma tela do celular.
8. **Interface limpa.** Mostrar primeiro o que exige atenção; detalhes sob demanda.

## 6. Requisitos funcionais

Cada requisito tem um identificador, usado depois na especificação, no roadmap e nos testes. A coluna "Entrega" indica em qual fase ele é construído (seção 8).

### 6.1 Livro-Razão (LED)

| ID | Requisito | Entrega |
|---|---|---|
| RF-LED-01 | Registrar toda operação financeira como transação de partidas dobradas, com pernas que somam zero. | MVP-1 |
| RF-LED-02 | Cada transação guarda: id único, tipo, valor, data da operação, data de competência, contas envolvidas, categoria, descrição, entidade relacionada, estado, datas de criação e atualização, referência à transação original (estornos e ajustes). | MVP-1 |
| RF-LED-03 | Suportar os tipos: receita recebida, despesa paga, despesa pendente, transferência entre contas próprias, compra no cartão, liquidação de fatura, pagamento de dívida (principal, juros e encargos separados), amortização extraordinária, valor a receber, recebimento de terceiro, estorno, reembolso, aporte e retirada de reserva, movimentação de meta, ajuste de conciliação, saldo de abertura. | MVP-1 (tipos básicos); demais tipos na entrega do módulo correspondente |
| RF-LED-04 | Estados previsto, pendente, confirmado, cancelado, estornado, com transições validadas. Previsto e pendente nunca afetam saldos reais. | MVP-1 |
| RF-LED-05 | Transação confirmada é imutável. Correção só por estorno vinculado + nova transação; a ação "Corrigir" faz as duas coisas numa única operação. | MVP-1 |
| RF-LED-06 | Previstos e pendentes não são excluídos; são cancelados, com motivo. | MVP-1 |
| RF-LED-07 | Operações com várias pernas ou várias transações são atômicas. | MVP-1 |
| RF-LED-08 | Bloquear pagamento duplicado (chave de idempotência), estorno repetido, estorno sem original e transação com pernas que não somam zero. | MVP-1 |
| RF-LED-09 | Controle de versão otimista para edições concorrentes (PC e celular). | MVP-1 |
| RF-LED-10 | Trilha de auditoria para transações e para alterações em contas, cartões, faturas, dívidas, metas, pessoas e configurações. | MVP-1 |
| RF-LED-11 | Verificação de invariantes sob demanda e em todo backup: soma das pernas = 0 em cada transação; saldo de cada conta = saldo de abertura + pernas confirmadas. | MVP-1 |
| RF-LED-12 | Qualquer indicador permite ver as movimentações que o compõem (drill-down). | MVP-1 (saldos), MVP-6 (todos os indicadores) |

### 6.2 Contas financeiras (CON)

| ID | Requisito | Entrega |
|---|---|---|
| RF-CON-01 | Cadastrar contas: corrente, digital, espécie, reserva, carteira de benefícios, outras. Cada conta tem classe livre, reserva ou benefício. | MVP-1 |
| RF-CON-02 | Saldo de abertura em 01/11/2026 (ou na data de criação da conta). Cartões, dívida, consórcio e empréstimos a terceiros abrem por itens (glossário 4.1). | MVP-1 |
| RF-CON-03 | Saldo atual calculado pelo Ledger; histórico de entradas, saídas e transferências por conta. | MVP-1 |
| RF-CON-04 | Transferência entre contas próprias: saída na origem, entrada no destino, sem receita nem despesa. | MVP-1 |
| RF-CON-05 | Conciliação: informar o saldo do banco; o sistema mostra a diferença e registra ajuste de conciliação, sem apagar histórico. | MVP-1 |
| RF-CON-06 | Arquivar conta sem movimentações futuras (nunca excluir). | MVP-1 |

### 6.3 Categorias (CAT)

| ID | Requisito | Entrega |
|---|---|---|
| RF-CAT-01 | Lista padrão de categorias e subcategorias de despesa e receita, editável. | MVP-1 |
| RF-CAT-02 | Renomear, reorganizar e arquivar categorias, preservando o histórico. | MVP-1 |
| RF-CAT-03 | Categorias de sistema não editáveis para encargos de cartão, juros de dívida, perdas com valores a receber e ajustes. | MVP-1 |

### 6.4 Lançamentos de receitas e despesas (LAN)

| ID | Requisito | Entrega |
|---|---|---|
| RF-LAN-01 | Lançamento rápido no celular: valor, forma (conta ou cartão), categoria, data (padrão hoje), descrição opcional. | MVP-1 |
| RF-LAN-02 | Receitas: salário, renda extra, benefícios, freelance, reembolsos, outras, com origem, data prevista, data de recebimento e estado. | MVP-1 (confirmadas), MVP-2 (previstas e recorrentes) |
| RF-LAN-03 | Crédito de benefício entra na carteira de benefícios; gastos com benefício saem dela. | MVP-1 |
| RF-LAN-04 | Data de competência diferente da data da operação (ex.: conta de outubro paga em novembro). | MVP-1 |
| RF-LAN-05 | Reembolso vinculado à despesa original reduz a despesa líquida da categoria. | MVP-2 |
| RF-LAN-06 | Filtros por período, categoria, conta, cartão, estado e texto. | MVP-1 |

### 6.5 Contas a pagar, receitas previstas e controle de pagamentos (PAG)

| ID | Requisito | Entrega |
|---|---|---|
| RF-PAG-01 | Cadastrar conta a pagar com nome, descrição, categoria, valor, vencimento, periodicidade, forma de pagamento e conta financeira prevista. | MVP-2 |
| RF-PAG-02 | Recorrências (mensal, anual, semanal, personalizada) gerando previstos numa janela móvel. Alterar a regra atualiza só os previstos futuros. | MVP-2 |
| RF-PAG-03 | Despesas parceladas fora do cartão (ex.: boleto em 5x). | MVP-2 |
| RF-PAG-04 | Pagamento total ou parcial, com data, valor pago, conta de origem e observações. O valor em aberto = valor da conta − liquidações confirmadas. | MVP-2 |
| RF-PAG-05 | Juros e multa por atraso registrados separadamente, em categoria própria. | MVP-2 |
| RF-PAG-06 | Marcar como agendada, com data de débito. No dia, o sistema pede confirmação. | MVP-2 |
| RF-PAG-07 | Área central de pagamentos: realizados, pendentes, futuros, atrasados e agendados, com filtros por período, categoria e status. | MVP-2 |
| RF-PAG-08 | Calendário de vencimentos (mês e lista). | MVP-2 |
| RF-PAG-09 | Receitas previstas e recorrentes (ex.: salário no 5º dia útil), diferenciadas das recebidas. | MVP-2 |
| RF-PAG-10 | Identificar despesas recorrentes e sugerir transformá-las em recorrência. | Pós-MVP |

### 6.6 Cartões de crédito (CAR)

| ID | Requisito | Entrega |
|---|---|---|
| RF-CAR-01 | Cadastrar cartão: nome, emissor/bandeira, limite total, dia de fechamento, dia de vencimento, conta de pagamento padrão. | MVP-1 |
| RF-CAR-02 | Registro provisório: compra à vista ou parcelada gera despesa (ou valor a receber) e passivo no cartão pelo valor total; número e valor das parcelas ficam gravados na compra. | MVP-1 |
| RF-CAR-02a | Abertura de cartão por itens: fatura fechada a vencer, compras da fatura aberta e parcelas restantes de compras antigas, com data original, total, parcelas e parcelas já faturadas; próprios contra patrimônio, de terceiro contra valor a receber. O passivo de abertura é a soma dos itens. | MVP-1 |
| RF-CAR-03 | Pagamento ao cartão (liquidação do passivo) a partir de conta financeira. | MVP-1 |
| RF-CAR-04 | Geração de parcelas e faturas a partir das compras e dos itens de abertura, inclusive os registrados no MVP-1, sem reescrever lançamentos. Data da compra define a fatura (antes ou depois do fechamento). | MVP-3 |
| RF-CAR-05 | Faturas abertas, fechadas, pagas parcialmente, pagas e vencidas; histórico de faturas. | MVP-3 |
| RF-CAR-06 | Pagamento parcial de fatura: saldo restante transportado para a fatura seguinte; juros e encargos registrados quando cobrados; alerta forte. | MVP-3 |
| RF-CAR-07 | Pagamento acima da fatura gera crédito para a próxima. | MVP-3 |
| RF-CAR-08 | Estorno total ou parcial de compra, inclusive parcelada (parcelas futuras canceladas; parcelas já faturadas viram crédito). | MVP-3 |
| RF-CAR-09 | Encargos e tarifas (anuidade, IOF, juros) em categorias próprias. | MVP-3 |
| RF-CAR-10 | Conciliação da fatura com o valor informado pelo emissor. | MVP-3 |
| RF-CAR-11 | Limite disponível calculado e conciliação com o limite informado pelo emissor, com causas prováveis da diferença. Ajuste de limite não gera movimentação no Ledger. | MVP-3 |
| RF-CAR-12 | Compra de terceiro: passivo no cartão + valor a receber da pessoa; nunca despesa própria. Compra mista (parte própria, parte de terceiro). | MVP-1 (registro básico), MVP-4 (parcelas a receber) |
| RF-CAR-13 | Previsão de comprometimento dos próximos meses por cartão e consolidada. | MVP-6 |

### 6.7 Valores a receber (REC)

| ID | Requisito | Entrega |
|---|---|---|
| RF-REC-01 | Cadastrar pessoa (devedor). | MVP-1 |
| RF-REC-02 | Empréstimo a terceiro: saída de conta financeira → valor a receber; não é despesa. | MVP-1 (sem parcelas), MVP-4 (parcelado) |
| RF-REC-03 | Parcelas com vencimento; vínculo automático com compras de terceiro no cartão. | MVP-4 |
| RF-REC-04 | Recebimento total ou parcial: valor a receber → conta financeira; não gera receita. | MVP-1 (simples), MVP-4 (por parcela) |
| RF-REC-05 | Saldo pendente por pessoa e por parcela; lista de atrasados. | MVP-4 |
| RF-REC-06 | Baixa por perdão ou inadimplência, como despesa de perda, com motivo. | MVP-4 |
| RF-REC-07 | Valores a receber aparecem nas projeções como "a receber previsto", separados da renda. | MVP-6 |
| RF-REC-08 | Juros sobre empréstimo a terceiro; lembretes de cobrança. | Pós-MVP |

### 6.8 Dívidas (DIV)

| ID | Requisito | Entrega |
|---|---|---|
| RF-DIV-00 | Registro provisório: dívida como passivo com saldo de abertura; pagamento de parcela lançado com principal e juros informados pelo usuário (do extrato). | MVP-1 |
| RF-DIV-01 | Cadastrar dívida: credor, descrição, valor original, saldo devedor atual, taxa de juros, sistema de amortização (Price no MVP), número de parcelas, parcelas pagas e restantes, valor da parcela, próximo vencimento. | MVP-5 |
| RF-DIV-02 | Pagamento de parcela separando principal, juros e encargos. | MVP-5 |
| RF-DIV-03 | Tabela de amortização e acompanhamento do saldo devedor; data estimada de quitação. | MVP-5 |
| RF-DIV-04 | Pagamento extraordinário; padrão reduzir prazo, opção reduzir parcela. | MVP-5 |
| RF-DIV-05 | Simulação de antecipação de parcelas e de quitação antecipada, com juros economizados, marcada como estimativa. | MVP-5 |
| RF-DIV-06 | Consórcio não contemplado como compromisso mensal fixo, sem juros; parcelas e reajustes informados pelo usuário. | MVP-5 |
| RF-DIV-07 | Histórico de pagamentos por dívida. | MVP-5 |
| RF-DIV-08 | Estratégias avalanche e bola de neve, com comparação de resultados. | Pós-MVP |
| RF-DIV-09 | Sistema SAC e outras modalidades. | Pós-MVP |

### 6.9 Dashboard (DSH)

| ID | Requisito | Entrega |
|---|---|---|
| RF-DSH-01 | Saldo bancário, saldo de benefícios e total guardado. | MVP-1 |
| RF-DSH-02 | Saldo disponível, contas pendentes, próximo pagamento, próximos vencimentos, atrasados. | MVP-2 |
| RF-DSH-03 | Receitas, despesas e pagamentos realizados no mês; saldo projetado até o fim do mês. | MVP-6 |
| RF-DSH-04 | Total de dívidas; comprometimento de renda dos próximos 12 meses. | MVP-6 |
| RF-DSH-05 | Destaque de situações de atenção: vencimento próximo, atraso, saldo projetado abaixo do mínimo, fatura paga parcialmente, conciliação pendente, backup com falha. | MVP-2 (vencimentos), MVP-6 (completo) |
| RF-DSH-06 | Gráficos: receitas × despesas, evolução do patrimônio, das dívidas e das economias, gastos por categoria, comparação entre meses. | MVP-6 (receitas × despesas, categorias), pós-MVP (evoluções e comparações) |
| RF-DSH-07 | Progresso das metas. | Pós-MVP |

### 6.10 Alertas (ALE)

| ID | Requisito | Entrega |
|---|---|---|
| RF-ALE-01 | Alertas no dashboard. | MVP-2 |
| RF-ALE-02 | Bot do Telegram com nome e valor: vencimentos próximos, atrasos, saldo abaixo do mínimo, fatura fechada, bloqueio de login, falha de backup. | MVP-2 (vencimentos e segurança), demais com os módulos |
| RF-ALE-03 | Antecedência dos avisos configurável (ex.: 3 dias e no dia). | MVP-2 |

### 6.11 Projeções e cenários (PRJ)

| ID | Requisito | Entrega |
|---|---|---|
| RF-PRJ-01 | Projeção de 7, 15 e 30 dias: saldo inicial, receitas previstas, despesas previstas, pagamentos de dívidas, aportes planejados, saldo final projetado. | MVP-6 |
| RF-PRJ-02 | Projeção de 3, 6 e 12 meses. | Pós-MVP |
| RF-PRJ-03 | Cenários: aumento de despesas, renda extra, antecipação de dívida, aumento de aportes. Cenários não alteram dados reais. | Pós-MVP |

### 6.12 Metas (MET)

| ID | Requisito | Entrega |
|---|---|---|
| RF-MET-01 | Metas com nome, descrição, valor desejado, valor acumulado, data de início, prazo, prioridade, contribuição mensal planejada, progresso. | Pós-MVP |
| RF-MET-02 | Cálculo de quanto falta, quanto guardar por mês e por semana, previsão de conclusão, diferença entre planejado e realizado. | Pós-MVP |
| RF-MET-03 | Aportes variáveis e extraordinários, como transferências para conta de reserva (neutros para receita e despesa). | Pós-MVP |
| RF-MET-04 | Reserva de emergência com alvo em meses de despesa ou valor fixo (tamanho definido depois pelo usuário). | Pós-MVP |

### 6.13 Orçamento (ORC)

| ID | Requisito | Entrega |
|---|---|---|
| RF-ORC-01 | Limite mensal por categoria, com alerta ao atingir percentuais configuráveis. | Pós-MVP |

### 6.14 Relatórios e exportação (REL)

| ID | Requisito | Entrega |
|---|---|---|
| RF-REL-01 | Relatório mensal e anual; despesas por categoria; receitas por origem; comparação entre meses. | Pós-MVP |
| RF-REL-02 | Evolução patrimonial, histórico de dívidas, evolução das metas. | Pós-MVP |
| RF-REL-03 | Visões por competência e por caixa; para parcelados, por compra e por parcela. | MVP-3 (alternador nas listas), pós-MVP (relatórios) |
| RF-REL-04 | Exportação CSV e Excel. | Pós-MVP |
| RF-REL-05 | Relatório mensal em PDF. | Pós-MVP |

### 6.15 Importação (IMP)

| ID | Requisito | Entrega |
|---|---|---|
| RF-IMP-01 | Importar extratos OFX e CSV, com detecção de possíveis duplicados e revisão antes de confirmar. | Pós-MVP |
| RF-IMP-02 | O modelo de dados já reserva campos para id externo e hash de deduplicação desde o MVP-1. | MVP-1 |

### 6.16 Segurança e acesso (SEG)

| ID | Requisito | Entrega |
|---|---|---|
| RF-SEG-01 | Login com senha forte, armazenada só como hash com algoritmo próprio para senhas. | MVP-1 |
| RF-SEG-02 | PIN como conveniência em aparelho confiável: desbloqueia uma sessão de aparelho já autenticada; nunca substitui a senha. | MVP-1 |
| RF-SEG-03 | Senha exigida no primeiro acesso de cada aparelho, periodicamente, após falhas de PIN e em operações sensíveis. | MVP-1 |
| RF-SEG-04 | Proteção contra tentativas repetidas (atraso progressivo e bloqueio temporário), com registro e alerta (no sistema desde o MVP-1; no Telegram a partir do MVP-2). | MVP-1 |
| RF-SEG-05 | Expiração de sessão por inatividade e absoluta; lista de aparelhos confiáveis com revogação. | MVP-1 |
| RF-SEG-06 | Acesso remoto só via Tailscale, com HTTPS. | MVP-1 |
| RF-SEG-07 | Credenciais do Telegram fora do banco e do código, protegidas pelo sistema operacional. | MVP-2 |

### 6.17 Backup e recuperação (BKP)

| ID | Requisito | Entrega |
|---|---|---|
| RF-BKP-01 | Backup diário automático, e também antes de atualizações e migrações. | MVP-1 |
| RF-BKP-02 | Cópia consistente do banco em uso, criptografada, em pasta local e em pasta sincronizada de nuvem. | MVP-1 |
| RF-BKP-03 | Histórico de versões com retenção (proposta: 7 diários, 4 semanais, 12 mensais). | MVP-1 |
| RF-BKP-04 | Verificação de integridade em todo backup (checksum, integridade do banco, invariantes do Ledger), com alerta em falha (no sistema desde o MVP-1; no Telegram a partir do MVP-2). | MVP-1 |
| RF-BKP-05 | Restauração guiada: escolher versão, restaurar em local temporário, validar, substituir; backup do estado atual antes. | MVP-1 |
| RF-BKP-06 | Teste mensal automático de restauração e checklist de teste manual trimestral. | MVP-1 |

### 6.18 Configurações (CFG)

| ID | Requisito | Entrega |
|---|---|---|
| RF-CFG-01 | Saldo mínimo de segurança. | MVP-2 |
| RF-CFG-02 | Horizonte H (próximo salário ou fim do mês). | MVP-2 |
| RF-CFG-03 | Calendário de feriados (nacionais e da cidade de São Paulo pré-carregados, editável) e regra de dia útil. | MVP-2 |
| RF-CFG-04 | Tema claro, escuro ou automático. | MVP-1 |

## 7. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | **Precisão:** valores monetários guardados como inteiros em centavos; cálculos intermediários em decimal exato; regra de arredondamento única e documentada. |
| RNF-02 | **Integridade:** banco com transações ACID e restrições de integridade; invariantes do Ledger verificáveis a qualquer momento. |
| RNF-03 | **Localização:** pt-BR, Real (R$ 1.234,56), datas dd/mm/aaaa, fuso America/Sao_Paulo, semana começando no domingo nos calendários. |
| RNF-04 | **Desempenho:** telas principais abrem em até 1 segundo no celular via Tailscale, com até 10 anos de dados de uso pessoal. |
| RNF-05 | **Disponibilidade:** o sistema inicia sozinho com o Windows e se recupera de reinícios; tarefas agendadas perdidas durante o desligamento rodam quando o sistema volta. |
| RNF-06 | **Responsividade:** uso completo no celular, tablet e computador; lançamento rápido otimizado para celular. |
| RNF-07 | **Acessibilidade:** contraste adequado nos dois temas; não depender só de cor para indicar estado; navegação por teclado no computador. |
| RNF-08 | **Privacidade:** nenhum dado financeiro sai do PC, exceto backups criptografados para a nuvem escolhida e alertas do Telegram (nome e valor, por decisão do usuário). Sem telemetria, sem CDN externa. |
| RNF-09 | **Manutenção:** instalação, atualização, backup e restauração por scripts e guias passo a passo; dependências com versões fixadas. |
| RNF-10 | **Custo:** zero de custo mensal (softwares livres, Tailscale e Telegram gratuitos para uso pessoal). |
| RNF-11 | **Testabilidade:** regras de cálculo isoladas da interface; todo cenário de referência vira teste automatizado. |
| RNF-12 | **Rastreabilidade:** todo indicador tem fórmula documentada a partir do Ledger e permite drill-down. |

## 8. Escopo por entrega

Cada entrega termina numa **porta de validação**: testes automatizados e cenários de referência passando, e uso real por um período curto comparando com extratos e faturas. A próxima entrega só começa depois da aprovação do usuário.

| Entrega | Conteúdo | Porta de validação |
|---|---|---|
| **MVP-1 — Núcleo do Ledger** | Ledger completo (estados, estorno, Corrigir, auditoria, idempotência, invariantes); contas financeiras e carteira de benefícios; categorias; receitas e despesas confirmadas; transferências; conciliação de saldo; cartões com registro provisório e pagamento; dívida como passivo com pagamentos lançados manualmente; compra de terceiro e empréstimo simples como valor a receber; login e segurança; Tailscale com HTTPS; backup completo; tema. | Saldos calculados batem com os bancos após algumas semanas de uso; invariantes sempre válidas; restauração de backup testada. |
| **MVP-2 — Contas a pagar e receitas previstas** | Previstos e pendentes; recorrências; parcelados fora do cartão; pagamento parcial; juros e multa; agendados; área de pagamentos; calendário de vencimentos; calendário de dias úteis; salário no 5º dia útil; saldo disponível; alertas no dashboard e Telegram; saldo mínimo. | Nenhum previsto afeta saldo real; datas e recorrências corretas em meses simulados; saldo disponível conferido manualmente (com a parte do cartão estimada pelas parcelas, ver `architecture.md` 6.8); alertas chegam no Telegram. |
| **MVP-3 — Cartões de crédito** | Parcelas e faturas geradas a partir das compras; estados da fatura; pagamento total, parcial e acima; estornos; encargos; conciliação de fatura e de limite; visão por compra e por parcela. | Faturas calculadas batem com as faturas reais de todos os cartões; compras e itens de abertura do MVP-1 migrados sem reescrita. |
| **MVP-4 — Valores a receber** | Empréstimos parcelados; parcelas a receber ligadas a compras de terceiro; recebimentos parciais; saldo por pessoa; atrasados; baixa. | Nenhuma compra de terceiro aparece como gasto próprio; recebimentos não geram receita. |
| **MVP-5 — Dívidas** | Empréstimo Price com principal, juros e encargos; tabela de amortização; pagamento extra; simulações de antecipação e quitação; consórcio como compromisso. | Tabela de amortização bate com o extrato do banco. |
| **MVP-6 — Dashboard e comprometimento** | Indicadores completos com drill-down; atenção; comprometimento de renda de 12 meses; projeção de 7/15/30 dias; gráficos essenciais. | Todo indicador explicável pelas movimentações; projeção de 30 dias conferida manualmente. |
| **Pós-MVP** | Projeções de 3/6/12 meses e cenários; metas e reserva de emergência; avalanche e bola de neve; orçamento por categoria; relatórios completos, CSV, Excel e PDF mensal; importação OFX/CSV; identificação de recorrências; SAC; juros em empréstimos a terceiros; gráficos de evolução. | Definida no roadmap (Fase B). |

**Por que cartões vêm antes de dívidas**, apesar da prioridade "quitar dívidas": com 4 ou mais cartões em uso diário, as compras precisam ser lançadas desde o primeiro dia. Sem faturas e valores a receber corretos, o saldo e os compromissos ficam errados, e a simulação de "quanto posso antecipar" sairia de números falsos. O MVP-4 e o MVP-5 podem trocar de ordem se o usuário preferir.

## 9. Fora do escopo

- Conexão automática com bancos (Open Finance). Pode ser avaliada no futuro, com autorização explícita.
- Múltiplos usuários, compartilhamento de dados ou perfis familiares.
- Controle de carteira de investimentos (ações, fundos, Tesouro). Reservas simples com rendimento lançado manualmente estão no escopo.
- Lance de consórcio (o usuário só conta com sorteio).
- Declaração de imposto de renda.
- Aplicativo nativo de loja (o celular usa o sistema pelo navegador, instalável como aplicativo web).
- Funcionamento offline no celular.

## 10. Premissas

- O PC fica ligado; com ele desligado, o sistema e os alertas ficam indisponíveis.
- Tailscale está instalado no PC e no celular, na mesma conta do usuário.
- O usuário tem conta no Telegram e cria um bot seguindo o guia do sistema.
- Uma pasta de nuvem sincronizada (Google Drive para desktop ou OneDrive) está disponível no PC.
- Os saldos, faturas e dívidas de abertura em 01/11/2026 são informados pelo usuário a partir dos apps dos bancos.

## 11. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| PC desligado ou com defeito | Sistema e alertas fora do ar | Início automático; backup na nuvem; guia de recuperação em outra máquina |
| Lançamentos esquecidos | Saldos divergem do banco | Conciliação periódica com lembrete; ajuste de conciliação rastreável |
| Regras de faturas diferentes entre emissores | Faturas calculadas divergem | Conciliação de fatura e de limite; regras configuráveis por cartão |
| Senha de backup perdida | Backups ilegíveis | Guia para guardar a senha fora do sistema; teste periódico de restauração |
| Celular perdido desbloqueado | Acesso indevido | PIN, expiração de sessão, revogação remota de aparelho |
| Escopo crescer durante o desenvolvimento | Atrasos e erros de cálculo | Entregas pequenas com portas de validação |
| Dados no disco do PC sem criptografia | Exposição em caso de roubo do PC | Criptografia do dispositivo do Windows, conferida na instalação (P-06); se o hardware não suportar, risco aceito e reavaliado no pós-MVP |
| Conta Microsoft com Windows Hello sem senha local | Serviço do Windows não consegue rodar com a conta do usuário (cofre de credenciais e pasta da nuvem ficam inacessíveis) | Verificação na instalação; plano B: tarefa agendada "ao fazer logon" |
| Pasta da nuvem só sincroniza com o usuário logado | Backup da nuvem atrasa enquanto ninguém faz logon | Manter sessão do Windows aberta (tela bloqueada); tela de saúde mostra a data da última cópia sincronizada |
| Itens de abertura incompletos | Faturas e comprometimento divergem nos primeiros meses | Guia de abertura com o que copiar de cada app de banco; conciliação de fatura no MVP-3 |

## 12. Decisões da Fase A

| # | Ponto | Resultado | Status |
|---|---|---|---|
| P-01 | Horizonte H do saldo comprometido e disponível | Até a próxima data prevista de salário, configurável para fim do mês | Decidido pelo usuário |
| P-02 | Carnaval no cálculo de dias úteis | Segunda e terça de Carnaval **não** são dias úteis, nem para o salário nem para vencimentos | Decidido pelo usuário |
| P-03 | Feriado estadual de 9 de julho (vale na capital) | Incluir no calendário | Aceito com a aprovação da Fase A |
| P-04 | Centavos restantes em compra parcelada | Diferença fica na primeira parcela; configurável por cartão se algum emissor fizer diferente | Aceito com a aprovação da Fase A |
| P-05 | Parcela do consórcio não contemplado | Lançar como despesa da categoria "Consórcio" (compromisso fixo), sem passivo; reavaliar se houver contemplação | Aceito com a aprovação da Fase A |
| P-06 | Criptografia do banco de dados no disco | Criptografia do dispositivo do Windows, conferida na instalação; sem suporte do hardware, risco aceito e SQLCipher reavaliado no pós-MVP | Decidido pelo usuário |
| P-07 | Quais contas recorrentes entram no saldo comprometido | Recorrências de valor fixo ou contratual viram pendentes dentro de H e entram no comprometido; contas variáveis estimadas ficam previstas e entram só no projetado | Decidido pelo usuário |

## 13. Rastreabilidade com o pedido original

| Seção do pedido | Requisitos |
|---|---|
| 3.1 Dashboard | RF-DSH-01 a 07, RF-ALE-01 |
| 3.2 Contas e despesas | RF-PAG-01 a 08, RF-PAG-10, RF-LAN-01, RF-LAN-06, RF-LED-05, RF-LED-06 |
| 3.3 Receitas | RF-LAN-02, RF-LAN-03, RF-PAG-09 |
| 3.4 Dívidas | RF-DIV-01 a 09 |
| 3.5 Controle de pagamentos | RF-PAG-04, RF-PAG-07, RF-LED-10 |
| 3.6 Contas bancárias e saldos | RF-CON-01 a 06, glossário 4.3 |
| 3.7 Metas | RF-MET-01 a 04 |
| 3.8 Planejamento e projeções | RF-PRJ-01 a 03, glossário 4.3 |
| 3.9 Cartões | RF-CAR-01 a 13 |
| 3.10 Relatórios | RF-REL-01 a 05 |
| 6 Segurança | RF-SEG-01 a 07, RF-BKP-01 a 06 |
| 7 Regras e integridade | RF-LED-01 a 12, RF-REC-01 a 08 |
| Requisito do Ledger | RF-LED-01 a 12, RF-CON-05, RF-IMP-02 |
| Requisitos adicionados na descoberta | RF-REC (valores a receber), RF-ORC-01 (orçamento), RF-CFG-01 a 03 |

## 14. Alterações após a aprovação da Fase A

Fase A aprovada em 06/11/2026 (versão 0.1). Alterações feitas durante a Fase B (versão 0.2):

| # | Alteração | Motivo | Aprovação |
|---|---|---|---|
| A-01 | Visão por parcela: esclarecido que compra à vista no cartão conta como uma parcela no mês da sua fatura, e que créditos de estorno contam no mês da fatura que os recebe (RN-162). A regra "mês da fatura" da Fase A foi mantida | Detalhamento necessário para os cenários | Confirmada pelo usuário em 06/11/2026 |
| A-02 | Horizonte H: só avança para o salário seguinte quando o recebimento do salário atual é confirmado; salário atrasado faz H = amanhã (RN-140, ADR-036) | Evitar que o disponível despenque no dia do salário antes de o dinheiro entrar | Decisão do usuário em 06/11/2026 |
| A-03 | PIN reabre a sessão também após a expiração absoluta de 12 h, enquanto o aparelho for confiável (30 dias) (ADR-035, que substitui parte da ADR-019) | Uso diário prático no celular | Decisão do usuário em 06/11/2026 |
| A-04 | Previsto e pendente nunca passam a confirmado; são liquidados por transações novas (ADR-032) | Um único caminho para dinheiro real entrar no Ledger; pagamentos parciais sem editar o planejado | Proposta da Fase B |
| A-05 | Estorno dividido em técnico e comercial (glossário 4.7, ADR-033) | Efeito diferente nos relatórios mensais | Proposta da Fase B |
| A-06 | Revisão da Etapa 7: "quanto pagar em 7/15/30 dias" passa a apontar para a projeção (RN-150), e não para o comprometido; definições de comprometido total e projetado alinhadas às fórmulas RN-144 e RN-146; alertas de bloqueio e de backup no sistema desde o MVP-1 e no Telegram a partir do MVP-2 | Consistência entre documentos | Revisão da Etapa 7 |
