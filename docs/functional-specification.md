# Especificação Funcional — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.2 |
| Data | 06/11/2026 |
| Etapa | 4 — Especificação (Fase B) |
| Status | Aprovado pelo usuário em 06/11/2026 (Fase B) |
| Documentos relacionados | `product-requirements.md` (RF), `business-rules.md` (RN), `ui-ux-specification.md` (telas), `reference-scenarios.md` (S) |

Este documento descreve **o que cada tela e cada ação fazem**, para cada módulo: campos, validações, fluxos e mensagens. As regras de cálculo estão em `business-rules.md`; aqui elas são citadas pelo identificador. O visual e o layout estão em `ui-ux-specification.md`.

Formato de cada funcionalidade: **Objetivo**, **Entrada**, **Comportamento**, **Validações e erros**, **Requisitos e regras**, **Entrega**.

---

## 1. Navegação e estrutura

| Área | Conteúdo | Entrega |
|---|---|---|
| Início (dashboard) | Saldos, atenção, próximos vencimentos, gráficos | MVP-1 (básico), MVP-2, MVP-6 |
| Lançar (+) | Lançamento rápido, sempre acessível | MVP-1 |
| Movimentações | Lista e filtros de todas as transações | MVP-1 |
| Pagamentos | Contas a pagar, receitas previstas, calendário | MVP-2 |
| Cartões | Cartões, faturas, compras, limite | MVP-1 (provisório), MVP-3 |
| A receber | Pessoas, valores a receber, recebimentos | MVP-1 (básico), MVP-4 |
| Dívidas | Empréstimo, consórcio, simulações | MVP-1 (provisório), MVP-5 |
| Contas | Contas financeiras, conciliação | MVP-1 |
| Planejamento | Projeções, comprometimento de renda, cenários, metas | MVP-6, pós-MVP |
| Relatórios | Relatórios e exportação | Pós-MVP |
| Configurações | Categorias, recorrências, calendário, alertas, segurança, backup, saúde | MVP-1 em diante |

## 2. Primeiro uso e abertura

### F-001 — Assistente de instalação no sistema

- **Objetivo:** deixar o sistema pronto e seguro antes do primeiro lançamento.
- **Comportamento:** sequência guiada, uma etapa por tela, retomável:
  1. Criar senha (força mínima exibida).
  2. Criar senha de backup, com aviso: "Guarde esta senha fora do sistema. Sem ela, os backups não podem ser abertos."
  3. Escolher a pasta da nuvem para backups.
  4. Conferir criptografia do disco (resultado informativo).
  5. Configurar o Telegram (opcional; pode ser feito depois).
  6. Escolher o tema.
- **Requisitos:** RF-SEG-01, RF-BKP-02, ADR-022. **Entrega:** MVP-1.

### F-002 — Assistente de abertura (saldos de 01/11/2026)

- **Objetivo:** registrar a situação inicial com os cronogramas preservados (ADR-031).
- **Etapas:**
  1. **Contas financeiras:** nome, tipo, classe, saldo em 01/11/2026.
  2. **Cartões:** cadastro (F-040), depois os itens de abertura, um por linha:
     - fatura fechada a vencer (valor, vencimento);
     - compras da fatura aberta (valor total, próprias ou de pessoa);
     - parcelas restantes de compras antigas (descrição, data original, total, número de parcelas, parcelas já faturadas, valor da parcela, própria ou de pessoa).

     O sistema mostra a soma e pede para comparar com "total da fatura atual + lançamentos futuros" do app do banco.
  3. **Dívida:** credor, saldo devedor, taxa mensal, parcelas restantes, valor da parcela do contrato, vencimento.
  4. **Consórcio:** valor da parcela, dia do vencimento, parcelas restantes.
  5. **Valores a receber existentes:** pessoa, valor, parcelas restantes e datas.
  6. **Recorrências principais:** salário (5º dia útil), aluguel, contas de consumo, assinaturas, com tipo fixo ou variável.
  7. **Revisão:** resumo com saldo bancário, passivos, a receber e comprometido; confirmação única grava tudo atomicamente.
- **Validações:**
  - itens com data anterior a 01/11/2026 são permitidos só aqui (RN-181);
  - parcelas já faturadas < número de parcelas;
  - soma do item de parcelas = (n − já faturadas) × valor da parcela, com tolerância de centavos do rateio.
- **Requisitos:** RF-CON-02, RF-CAR-02a, RF-DIV-00, RN-089. **Cenário:** S00. **Entrega:** MVP-1.

## 3. Lançamentos

### F-010 — Lançamento rápido (celular)

- **Objetivo:** registrar um gasto ou recebimento em poucos segundos (RF-LAN-01).
- **Entrada:**

| Campo | Regra |
|---|---|
| Valor | Teclado numérico; digitação em centavos (digitar `4590` mostra R$ 45,90) |
| Tipo | Gasto (padrão), Recebimento, Transferência |
| Forma | Lista com contas e cartões; a última usada vem selecionada |
| Categoria | As 6 mais usadas como atalhos + busca |
| Data | Hoje, com atalhos "ontem" e calendário |
| Parcelas | Visível quando a forma é cartão; padrão 1 |
| Descrição | Opcional |
| "Dividir com alguém" | Opcional, só em cartão; ver F-012 |

- **Comportamento:**
  - Botão "Salvar" grava a transação confirmada (T02, T03 ou T08) com chave de idempotência (RN-170).
  - Após salvar: confirmação visual com valor e forma, botão "Desfazer" por 10 segundos (faz estorno técnico, RN-122) e campos limpos para o próximo lançamento.
  - Aviso de possível duplicidade (RN-171), sem bloquear.
- **Validações:**
  - valor > 0 e ≤ 9.999.999,99 (RN-180);
  - data não futura (RN-181);
  - categoria compatível com benefício (RN-186);
  - conta ou cartão não arquivado (RN-185).
- **Entrega:** MVP-1.

### F-011 — Lançamento completo

- **Objetivo:** todas as opções de lançamento (computador ou celular).
- **Campos adicionais:**
  - data de competência diferente da data da operação (RF-LAN-04);
  - observação;
  - vínculo com compromisso pendente: a tela sugere pendentes com valor e data próximos.
- **Tipos disponíveis:** receita, despesa, transferência, aporte e retirada de reserva, compra no cartão, pagamento de fatura, empréstimo a terceiro, recebimento de terceiro, pagamento de parcela de dívida, amortização extra, reembolso, rendimento.
- **Entrega:** MVP-1 (tipos básicos); demais tipos com seus módulos.

### F-012 — Compra no cartão com partes de terceiros

- **Entrada:** valor total, parcelas, uma ou mais linhas "pessoa + valor". A parte própria é calculada (total − partes) e pode ser zero (compra inteira de terceiro).
- **Comportamento:** gera T08, T09 ou T10 numa única transação, mais um valor a receber por pessoa.
  - MVP-1: vencimento do a receber = vencimento estimado da fatura (RN-075).
  - MVP-4: parcelas alinhadas às faturas (RN-101).
- **Cenário:** S03. **Entrega:** MVP-1.

### F-013 — Lista de movimentações

- **Colunas:** data, descrição, categoria, conta ou cartão, valor (cor e sinal pelo efeito), estado.
- **Filtros:**
  - período, categoria, conta, cartão, pessoa, estado, texto;
  - "mostrar estornos e cancelados" (RN-124);
  - competência ou caixa;
  - visão por compra ou por parcela (RN-161, RN-162); a visão por parcela aparece a partir do MVP-3.
- **Ações por linha:**
  - ver detalhe (pernas em linguagem comum, vínculos, auditoria);
  - Corrigir;
  - Estornar;
  - acrescentar nota.
- **Totais:** do filtro aplicado, com a visão indicada.
- **Entrega:** MVP-1.

### F-014 — Corrigir e estornar

- **Corrigir:** abre o formulário preenchido com a transação original; ao salvar, executa estorno técnico + nova transação (RN-122). Se a original liquidava um compromisso, a nova passa a liquidar.
- **Estornar:**
  - pede motivo;
  - em compra de cartão, pergunta se é "lançamento errado" (técnico, RN-082) ou "devolução ou cancelamento pelo lojista" (comercial, RN-083), com opção de valor parcial;
  - mostra o efeito antes de confirmar (ex.: "A fatura de 05/01 receberá crédito de R$ 100,00").
- **Bloqueios:** transação já estornada (I-03); conciliação posterior pede confirmação (RN-133).
- **Cenários:** S10, S11. **Entrega:** MVP-1.

## 4. Contas financeiras e conciliação

### F-020 — Contas

- **Cadastro:** nome, tipo, classe (livre, reserva, benefício), instituição, saldo de abertura e data.
- **Detalhe:** saldo atual, entradas e saídas do mês, transferências, histórico, última conciliação.
- **Arquivar:** só sem compromissos futuros em aberto (RN-185).
- **Requisitos:** RF-CON-01 a 06. **Entrega:** MVP-1.

### F-021 — Transferência

- Origem, destino, valor, data, descrição.
- Origem e destino diferentes.
- Aviso quando a transferência muda o disponível (livre ↔ reserva, RN-061).
- **Cenário:** S08. **Entrega:** MVP-1.

### F-022 — Conciliação de saldo

- **Fluxo:**
  1. Usuário informa saldo e data.
  2. Sistema mostra calculado, diferença e lançamentos recentes daquela conta.
  3. Sem diferença → marco gravado.
  4. Com diferença → sugere procurar lançamentos faltantes; depois oferece ajuste com descrição obrigatória (RN-131).
- **Lembrete:** conciliação semanal sugerida, configurável; o dashboard mostra contas sem conciliação há mais de 14 dias.
- **Cenário:** S13. **Entrega:** MVP-1.

## 5. Pagamentos (contas a pagar e receitas previstas)

### F-030 — Cadastro de conta a pagar

- **Campos:**
  - nome, categoria, valor, vencimento;
  - tipo de valor (fixo ou variável);
  - competência (padrão: mês do vencimento);
  - conta prevista, forma de pagamento;
  - recorrência (F-033) ou parcelamento (N vezes);
  - "antecipa se cair em dia não útil" (RN-093).
- **Requisitos:** RF-PAG-01 a 03. **Entrega:** MVP-2.

### F-031 — Pagar

- **Botão "Pagar"** na lista e no detalhe. Preenche valor em aberto, hoje e conta prevista.
- O usuário pode:
  - alterar o valor (pagamento parcial, RN-033);
  - informar juros e multa separadamente (RN-034);
  - encerrar com valor diferente (RN-042).
- **Bloqueio:** pagamento acima do aberto sem classificação (RN-043).
- **Resultado:** liquidação; o status exibido muda para "Pago parcialmente" ou "Pago".
- **Entrega:** MVP-2.

### F-032 — Agendar

- Marca data de débito (RN-035).
- No dia, aparece em atenção: "Débito agendado de R$ X: aconteceu?" com "Sim" (cria liquidação) e "Não" (volta a pendente).
- **Entrega:** MVP-2.

### F-033 — Recorrências

- **Campos:** periodicidade, regra de dia (dia fixo, N-ésimo dia útil, último dia), valor, tipo, início, fim ou número de ocorrências.
- **Pré-visualização:** as próximas 12 datas antes de salvar (mostra o efeito de feriados e fins de semana).
- **Alterar:** pergunta "a partir de qual ocorrência"; regenera só as futuras sem liquidação (RN-053).
- **Encerrar:** cancela as futuras sem liquidação (RN-054).
- **Valor variável:** a ocorrência mostra "valor estimado" e pede o valor real quando a conta chega (RN-052).
- **Entrega:** MVP-2.

### F-034 — Central de pagamentos

- **Abas:**
  - Atrasados;
  - Próximos (até H);
  - Futuros;
  - Agendados;
  - Pagos (período);
  - Receitas previstas.
- **Filtros:** período, categoria, status, conta.
- **Por linha:** nome, vencimento (original e efetivo, se diferentes), valor planejado, valor em aberto, status, ações (Pagar, Agendar, Informar valor real, Cancelar).
- **Totais:** em aberto, pago no período.
- **Requisito:** RF-PAG-07. **Entrega:** MVP-2.

### F-035 — Calendário de vencimentos

- **Visão de mês:** cada dia mostra a soma a pagar e a receber; feriados marcados; o dia do salário destacado.
- **Toque no dia:** abre a lista daquele dia.
- **Visão de lista:** para o celular.
- **Requisito:** RF-PAG-08. **Entrega:** MVP-2.

### F-036 — Receitas previstas

- Salário como recorrência de 5º dia útil.
- **Botão "Recebi":** cria a liquidação com valor editável (RN-021).
- Receita atrasada aparece em atenção (RN-023).
- **Entrega:** MVP-2.

## 6. Cartões

### F-040 — Cadastro de cartão

- **Campos:**
  - nome, emissor, bandeira;
  - limite total, dia de fechamento, dia de vencimento;
  - conta de pagamento padrão;
  - regras avançadas (compra no dia do fechamento, resto de centavos, consumo de limite do parcelado).
- **Pré-visualização:** as próximas 3 faturas com período e vencimento.
- **Entrega:** MVP-1.

### F-041 — Visão do cartão (MVP-1, provisória)

- **Indicadores:** passivo total, limite disponível calculado, "estimativa de valor devido até H" com rótulo de estimativa (RN-075).
- **Lista:** compras com parcelas, itens de abertura, pagamentos.
- **Ação:** pagar cartão (T11).
- **Entrega:** MVP-1.

### F-042 — Faturas (MVP-3)

- **Linha do tempo de faturas:** anteriores, atual, próximas. Cada uma mostra estado, período, fechamento, vencimento (original e efetivo), valor e valor em aberto.
- **Detalhe da fatura:**
  - parcelas (compra, k/n);
  - encargos;
  - créditos;
  - saldo anterior;
  - pagamentos;
  - partes de terceiros marcadas.
- **Ações:**
  - pagar fatura (padrão: valor em aberto; pagamento parcial e acima com confirmação, RN-079, RN-080);
  - informar encargos (T12);
  - conciliar fatura com o valor do emissor (RN-081).
- **Migração:** ao ativar o MVP-3, o sistema gera as faturas a partir das compras e itens de abertura e mostra um relatório de conferência por fatura.
- **Cenários:** S02, S06, S07. **Entrega:** MVP-3.

### F-043 — Limite e conciliação de limite

- **Exibe:** limite total, usado, disponível calculado.
- **"Conferir limite":**
  1. Usuário informa o disponível do app.
  2. Sistema mostra a diferença e as causas prováveis, em ordem: pagamento recente em compensação, compra ou encargo não lançado, mudança de limite total, regra do emissor (RN-087).
  3. Registra evento.
- **"Mudar limite total":** evento com data (RN-088).
- **Cenário:** S13. **Entrega:** MVP-3 (conferência); MVP-1 (exibição do calculado).

### F-044 — Estorno no cartão

Conforme F-014, com a pré-visualização do efeito nas faturas (RN-084).
- **Cenário:** S10. **Entrega:** MVP-1 (técnico e comercial à vista); MVP-3 (parcelado com crédito em fatura).

## 7. Valores a receber

### F-050 — Pessoas

- Cadastro simples: nome e observação.
- **Detalhe:** total a receber, atrasado, histórico, compras no cartão, empréstimos.
- **Entrega:** MVP-1.

### F-051 — Empréstimo a terceiro

- **Campos:** pessoa, valor, conta de saída, data, número de parcelas e datas (MVP-4; no MVP-1, uma data prevista).
- **Comportamento:** gera T14 e o cronograma (RN-101).
- **Cenário:** S05. **Entrega:** MVP-1 (simples), MVP-4.

### F-052 — Receber

- **Botão "Recebi"** na pessoa ou na parcela: valor, data, conta de entrada.
- Alocação automática pela parcela mais antiga, com opção de escolher (RN-103).
- Excedente pede confirmação (RN-107).
- **Cenário:** S04. **Entrega:** MVP-1 (simples), MVP-4.

### F-053 — Baixa

- Total ou parcial, motivo obrigatório (perdão ou inadimplência), aviso: "Este valor será registrado como perda (despesa)."
- Estornável (RN-106).
- **Entrega:** MVP-4.

## 8. Dívidas

### F-060 — Empréstimo (MVP-1, provisório)

- Cadastro com saldo devedor de abertura.
- **"Pagar parcela":** campos principal, juros, encargos e conta (valores do extrato) (RN-117).
- **Entrega:** MVP-1.

### F-061 — Empréstimo com tabela (MVP-5)

- **Cadastro completo:** taxa, sistema Price, parcelas restantes, parcela do contrato, vencimento.
- **Tabela de amortização:** parcela, data, pagamento, juros, principal, saldo; a linha atual destacada.
- Divergência entre a PMT calculada e a do contrato → aviso (RN-110).
- **"Pagar parcela":** preenche os valores da tabela; se o usuário altera os juros (extrato diferente), recalcula (RN-112).
- **Indicadores:** saldo devedor, parcelas pagas e restantes, data estimada de quitação, juros restantes.
- **Cenário:** S09. **Entrega:** MVP-5.

### F-062 — Simulador de antecipação

- **Entradas:** valor extra e data; modo (reduzir prazo, padrão; reduzir parcela); ou "quitar tudo".
- **Saída lado a lado:**

| | Atual | Reduzir prazo | Reduzir parcela |
|---|---|---|---|
| Parcelas restantes | | | |
| Valor da parcela | | | |
| Quitação estimada | | | |
| Juros restantes | | | |
| Juros economizados | — | | |

- Aviso de estimativa (RN-115).
- **"Registrar amortização":** cria T18 e a nova versão da tabela.
- Mostra o impacto no saldo disponível e no projetado antes de confirmar.
- **Entrega:** MVP-5.

### F-063 — Consórcio

- **Cadastro:** parcela, dia, parcelas restantes.
- **Reajuste:** novo valor a partir de uma data.
- **Pagar:** liquida a parcela (T19).
- Sem simulação de juros (ADR-008).
- **Entrega:** MVP-5 (MVP-2 já permite tratá-lo como recorrência fixa).

## 9. Dashboard

### F-070 — Painel principal

| Bloco | Conteúdo | Regras | Entrega |
|---|---|---|---|
| Saldos | Bancário, disponível (destaque), total guardado, benefícios; toque abre a composição | RN-141 a RN-147 | MVP-1 (bancário, guardado, benefícios), MVP-2 (disponível) |
| Atenção | Lista ordenada por gravidade: atrasados, fatura vencida ou paga parcialmente, saldo projetado abaixo do mínimo, débito agendado de hoje, receita atrasada, a receber atrasado, conciliação antiga, backup com falha | RF-DSH-05 | MVP-2, MVP-6 |
| Próximos vencimentos | Até H, com total e "próximo pagamento" | RN-143 | MVP-2 |
| Mês | Receitas, despesas, pagamentos realizados, saldo projetado até o fim do mês | RN-160, RN-166 | MVP-6 |
| Dívidas | Total de dívidas e quitação estimada | RN-148 | MVP-6 |
| Comprometimento | Barra dos próximos 3 meses (atalho para 12) | RN-149 | MVP-6 |
| Gráficos | Receitas × despesas (6 meses), gastos por categoria (mês) | RF-DSH-06 | MVP-6 |

Todo número abre a lista de movimentações que o compõem (RF-LED-12). Para o comprometido, a lista é por fatura e compromisso.

### F-071 — "De onde vem este número"

- Para qualquer indicador:
  - mostra a fórmula em linguagem comum (ex.: "Disponível = contas livres R$ 3.439,40 − comprometido até 07/12 R$ 1.580,00");
  - cada termo é clicável até chegar às transações.
- **Entrega:** MVP-1 (saldos), MVP-6 (todos).

## 10. Alertas

### F-080 — Alertas

| Alerta | Gatilho | Canal | Exemplo de texto |
|---|---|---|---|
| Vencimento próximo | X dias antes (padrão 3) e no dia, 08:00 | Dashboard e Telegram | "Aluguel R$ 1.500,00 vence em 10/12 (quinta)." |
| Atraso | Dia seguinte ao vencimento efetivo | Dashboard e Telegram | "Atrasado: Internet R$ 120,00, venceu em 16/11." |
| Fatura | Fechamento e 3 dias antes do vencimento | Dashboard e Telegram | "Fatura Cartão A fechou: R$ 930,00, vence em 05/12 (pague até 07/12)." |
| Saldo abaixo do mínimo | Projetado de 30 dias cai abaixo do mínimo | Dashboard e Telegram | "Projeção: saldo abaixo de R$ 300,00 em 05/12." |
| Segurança | Bloqueio de login, novo aparelho confiável | Telegram | "Login bloqueado após 5 tentativas às 23:14." |
| Backup | Falha ou ausência de backup > 36 h; teste de restauração com falha | Dashboard e Telegram | "Backup de hoje falhou: verificação de integridade." |

- **Deduplicação:** o mesmo alerta não é enviado duas vezes no mesmo dia (`notification.dedup_key`).
- **Silêncio noturno:** configurável (padrão 22h–07h), exceto segurança.
- **Requisitos:** RF-ALE-01 a 03, ADR-029. **Entrega:** MVP-2 (vencimentos, atraso, segurança, backup), MVP-3 (fatura), MVP-6 (saldo).

## 11. Planejamento

### F-090 — Projeção de curto prazo (7, 15, 30 dias)

- **Seletor:** 7, 15, 30.
- **Tabela:** saldo inicial, receitas previstas, a receber, despesas previstas, faturas, dívidas, aportes, saldo final (RN-150).
- **Gráfico diário:** linha tracejada com faixa do saldo mínimo (RN-151).
- Rótulo "Projeção" sempre visível (RN-153).
- **Entrega:** MVP-6.

### F-091 — Comprometimento de renda (12 meses)

- **Barras por mês:** cartões próprios, compromissos fixos, variáveis estimados, aportes, sobra. Linha separada para terceiros (RN-149).
- **Toque no mês:** detalhe por item.
- **Cenário:** S14. **Entrega:** MVP-6.

### F-092 — Projeções de 3, 6 e 12 meses e cenários (pós-MVP)

- Saldo projetado ao fim de cada mês.
- **Cenários:** % de aumento de despesas, renda extra (valor e mês), amortização extra, aumento de aportes.
- Comparação base × cenário. Nada é gravado no Ledger (RN-152).

### F-093 — Metas (pós-MVP)

- **Cadastro** conforme RF-MET-01.
- **Cálculos:** falta, por mês, por semana, previsão de conclusão, planejado × realizado (RF-MET-02).
- **Aporte:** transferência marcada para a conta de reserva (RN-062).
- **Reserva de emergência:** alvo em meses de despesa média fixa ou valor fixo.

## 12. Relatórios e exportação (pós-MVP)

| Relatório | Conteúdo |
|---|---|
| Mensal | Receitas por origem, despesas por categoria (visão escolhida), pagamentos, variação do guardado, dívidas, diferenças de conciliação |
| Anual | Mês a mês, médias, maiores categorias |
| Evolução patrimonial | Ativos − passivos ao fim de cada mês |
| Dívidas | Saldo devedor e juros pagos ao longo do tempo |
| Metas | Progresso no tempo |
| Comparação | Dois meses lado a lado, com variação por categoria |

Exportação CSV e Excel de qualquer lista ou relatório, e PDF do relatório mensal (ADR-024). O arquivo exportado leva data e filtros no cabeçalho.

## 13. Configurações

| Tela | Conteúdo | Entrega |
|---|---|---|
| Categorias | Lista padrão editável, subcategorias, "aceita benefício", arquivar | MVP-1 |
| Recorrências | Lista, editar, encerrar | MVP-2 |
| Calendário | Feriados por ano, adicionar e remover, pré-visualização de 5º dia útil | MVP-2 |
| Saldos | Horizonte H, saldo mínimo de segurança | MVP-2 |
| Alertas | Canais, antecedência, silêncio noturno, teste de envio do Telegram | MVP-2 |
| Segurança | Trocar senha, PIN, aparelhos confiáveis (revogar), sessões, histórico de logins | MVP-1 |
| Backup | Último backup, histórico, backup agora, restaurar (F-100), retenção, pasta da nuvem, últimos testes de restauração | MVP-1 |
| Saúde | Invariantes, tarefas agendadas, espaço em disco, versão, criptografia do disco | MVP-1 |
| Aparência | Tema claro, escuro ou automático | MVP-1 |

### F-100 — Restaurar backup

1. Pede a senha de login.
2. Lista as versões com data, tipo e resultado da verificação.
3. Executa o fluxo de `architecture.md` §10.2 com barra de progresso.
4. Mostra o resumo para confirmação final.

Detalhes em `security-plan.md` §7. **Entrega:** MVP-1.

## 14. Lista padrão de categorias

**Despesas** (subcategorias entre parênteses):
- Moradia (aluguel, condomínio, manutenção)
- Contas da casa (luz, água, gás, internet, celular)
- Alimentação (mercado, restaurantes, delivery)
- Transporte (combustível, aplicativo, transporte público, estacionamento, manutenção)
- Saúde (plano, farmácia, consultas)
- Educação
- Lazer
- Compras (eletrônicos, vestuário, casa)
- Assinaturas
- Cuidados pessoais
- Presentes e doações
- Impostos e taxas
- Pets
- Outros

Categorias de sistema, conforme `business-rules.md` §2: encargos de cartão, juros de dívidas, encargos de dívidas, juros e multas por atraso, perdas com valores a receber, consórcio.

**Receitas:** salário, renda extra, 13º e férias, freelance, reembolsos, restituição de imposto, benefícios, rendimentos, outras.

"Aceita benefício" vem marcado em: mercado, restaurantes, delivery.

## 15. Mensagens padrão

| Situação | Mensagem |
|---|---|
| Lançamento salvo | "Gasto de R$ 45,90 no Cartão A salvo. Desfazer" |
| Duplicidade possível | "Já existe um gasto de R$ 45,90 hoje no Cartão A. Salvar mesmo assim?" |
| Pagamento acima do aberto | "O valor em aberto é R$ 120,00. Você está pagando R$ 135,00. O que é a diferença? Juros e multa / Valor real maior / Corrigir valor" |
| Edição concorrente | "Este item foi alterado em outro aparelho. Os dados foram recarregados." |
| Estorno repetido | "Esta transação já foi estornada em 04/11/2026." |
| Projeção | "Projeção — baseada nos compromissos e receitas previstos. Não é saldo real." |
| Simulação de dívida | Texto de RN-115 |

## 16. Alterações após a aprovação

| Versão | Seção | Alteração | Motivo |
|---|---|---|---|
| 0.2 | F-031 | Botão principal paga o valor em aberto; outro valor, juros, excedente e encerrar ficam num bloco recolhido, com botão próprio. "Desfazer" por 2 minutos depois de pagar | ADR-042 |
| 0.2 | F-033 | Salvar exige ter visto as datas daquela combinação de campos | ADR-042 |
| 0.2 | F-034 | Grupos por quando agir, no lugar de abas | ADR-040, ADR-042 |
| 0.2 | F-035 | Marcas por tipo em cada dia; a soma fica na lista do dia. A visão de lista é a própria central | ADR-042 |
| 0.2 | F-070 | O número principal é o "Pode gastar" (ADR-041); saldo bancário, guardado e benefícios ficam em Contas | ADR-040, ADR-041 |
| 0.2 | F-080 | Fila com nova tentativa em 15 minutos e validade de 24 horas. Nesta fase: vencimento, atraso, backup e segurança | ADR-042 |
