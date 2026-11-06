# Plano de Testes — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.1 |
| Data | 06/11/2026 |
| Etapa | 4 — Especificação (Fase B) |
| Status | Aprovado pelo usuário em 06/11/2026 (Fase B) |
| Documentos relacionados | `business-rules.md` (RN, I), `reference-scenarios.md` (S), `security-plan.md`, `implementation-roadmap.md` (portas) |

---

## 1. Objetivos

1. Provar que todo cálculo financeiro é exato ao centavo e segue as regras documentadas.
2. Provar que o Ledger nunca fica inconsistente, mesmo com falhas, duplo envio, edição concorrente e sequências arbitrárias de operações.
3. Provar que nenhuma operação gera dupla contagem.
4. Provar que backup e restauração funcionam de verdade, não só no papel.
5. Garantir que as funcionalidades de segurança funcionam e continuam funcionando.
6. Dar a cada porta de validação do MVP critérios objetivos.

## 2. Ferramentas (ADR-023)

| Ferramenta | Uso |
|---|---|
| pytest + pytest-django | Executor e integração com o Django |
| Hypothesis | Testes por propriedades (sequências aleatórias de operações) |
| time-machine | Congelar e avançar datas |
| Playwright (Python) | Ponta a ponta no navegador, inclusive com tela de celular |
| coverage.py | Cobertura de linhas e de ramificações |
| pip-audit | Vulnerabilidades em dependências |
| Ruff | Estilo e erros comuns; regra que proíbe `float` nos módulos financeiros |

Execução: um comando (`uv run pytest`) roda tudo, exceto ponta a ponta e testes lentos, que têm marcação própria (`-m e2e`, `-m slow`). O script de atualização roda a suíte completa.

## 3. Organização

```
tests/
  unit/          # funções puras: money, rateio, Price, calendário, saldos
  integration/   # serviços com banco: ledger, módulos, gatilhos, migrações
  scenarios/     # S00–S14 de reference-scenarios.md, um arquivo por cenário
  property/      # Hypothesis: invariantes sob operações aleatórias
  security/      # autenticação, sessões, PIN, cabeçalhos, rotas
  backup/        # backup, verificação, retenção, restauração
  e2e/           # Playwright
  fixtures/      # dados de referência (cadastro comum de reference-scenarios.md)
```

Os cenários de referência são dados declarativos (estado inicial, operações, resultados esperados). O teste carrega o cenário, executa as operações **pelos serviços públicos** (nunca gravando pernas diretamente) e compara cada resultado esperado em centavos.

## 4. Metas de cobertura

| Módulo | Meta (ramificações) |
|---|---|
| `money`, `calendar_br`, `ledger`, `balances` | ≥ 95% |
| `cards` (alocação, faturas), `receivables`, `debts` (Price, simulação) | ≥ 95% |
| `payables`, `accounts`, `backup`, `security` | ≥ 90% |
| Demais (views, templates, relatórios) | ≥ 80% |

Cobertura é condição necessária, não suficiente: toda regra RN tem pelo menos um teste nomeado com seu identificador (ex.: `test_RN_079_pagamento_parcial_transporta_saldo`).

## 5. Cenários de referência

| Cenário | Arquivo | Entrega em que passa a ser obrigatório | Regras principais |
|---|---|---|---|
| S00 Abertura por itens | `scenarios/test_s00_abertura.py` | MVP-1 (pernas, bancário, passivo, limite, despesas), MVP-2 (H, comprometido, disponível), MVP-3 (faturas, I-07) | RN-089, T23–T26, I-07 |
| S01 Rateio | `scenarios/test_s01_rateio.py` | MVP-1 | RN-005, I-06 |
| S02 Fechamento | `scenarios/test_s02_fechamento.py` | MVP-1 (estimativa), MVP-3 (faturas) | RN-070 a RN-073, RN-075 |
| S03 Terceiros | `scenarios/test_s03_terceiros.py` | MVP-1 (sem parcelas), MVP-4 | T09, T10, RN-100 a RN-102 |
| S04 Recebimentos | `scenarios/test_s04_recebimentos.py` | MVP-4 | RN-103 a RN-105 |
| S05 Baixa | `scenarios/test_s05_baixa.py` | MVP-4 | T14–T16, RN-106 |
| S06 Pagamento parcial de fatura | `scenarios/test_s06_fatura_parcial.py` | MVP-3 | RN-076, RN-079, T12 |
| S07 Pagamento acima | `scenarios/test_s07_fatura_acima.py` | MVP-3 | RN-080, RN-086 |
| S08 Transferências | `scenarios/test_s08_transferencias.py` | MVP-1 | T05–T07, RN-060, RN-061, RN-173 |
| S09 Price | `scenarios/test_s09_price.py` | MVP-5 (tabela), MVP-1 (pagamento manual) | RN-110 a RN-115 |
| S10 Estornos no cartão | `scenarios/test_s10_estornos_cartao.py` | MVP-1 (parte B: pernas, despesa por compra, passivo), MVP-3 (parte A e efeitos em faturas) | RN-082 a RN-084, RN-121 |
| S11 Correção | `scenarios/test_s11_corrigir.py` | MVP-1 | RN-120, RN-122 |
| S12 Idempotência | `scenarios/test_s12_idempotencia.py` | MVP-1 (parte A), MVP-2 (parte B), MVP-3 (parte C) | RN-043, RN-170 |
| S13 Conciliação | `scenarios/test_s13_conciliacao.py` | MVP-1 (saldo), MVP-3 (limite) | RN-130 a RN-133, RN-087, RN-088 |
| S14 Mês combinado | `scenarios/test_s14_mes_combinado.py` | MVP-2 (bancário, disponível com cartão estimado), MVP-3 (fatura real), MVP-6 (todos os indicadores) | RN-140 a RN-149, RN-160 a RN-167, I-08 |

Cada resultado esperado tem a entrega a partir da qual é verificável (coluna ou parte indicada em `reference-scenarios.md`). Antes disso, a asserção fica marcada como "aguardando entrega" e não conta como falha.

Regra: a partir da entrega indicada, o cenário precisa passar em toda execução da suíte. Um cenário nunca é editado para "passar". Se um resultado esperado estiver errado, a correção é feita em `reference-scenarios.md`, com justificativa registrada, e só então no teste.

## 6. Matriz por tipo de operação

Para cada tipo T01 a T28 (`business-rules.md` §4), os testes de integração verificam:

| Verificação | Descrição |
|---|---|
| Pernas | Contas e valores exatos; soma zero |
| Saldo bancário | Efeito da coluna "Bancário" |
| Disponível | Efeito da coluna "Disp.", com e sem o compromisso dentro de H |
| Resultado | Receita e despesa na competência correta; nada quando a coluna diz "Nenhum" |
| Limite | Efeito no limite do cartão |
| Estorno | Estornar devolve todos os indicadores ao estado anterior |
| Auditoria | Registro criado com antes e depois |

Combinações obrigatórias, além dos cenários:

| Combinação | Verificação |
|---|---|
| Pagamento parcial + juros por atraso + estorno da liquidação | Valor em aberto reaberto corretamente; juros não entram na categoria original (RN-034, RN-044) |
| Compra parcelada mista + estorno parcial | Parte própria e a receber reduzidos na proporção (RN-085) |
| Compra de terceiro + recebimento antes da fatura + estorno da compra | Excedente vira "a devolver" (RN-085) |
| Dois estornos parciais que somam mais que a compra | O segundo é recusado; estorno total depois de um parcial estorna só o restante (RN-121, I-03) |
| Encargo informado em fatura fechada | Aceito; nova compra com data após o fechamento vai para a fatura seguinte (RN-076) |
| Dia do salário antes da confirmação | H continua no salário do dia; após "Recebi", H avança; salário atrasado faz H = amanhã (RN-140) |
| Recorrência fixa + mudança de valor no meio | Só ocorrências futuras sem liquidação mudam (RN-053) |
| Recorrência variável entrando em H | Continua prevista até informar valor; não entra no comprometido (RN-052) |
| Transferência para reserva + aporte planejado | Disponível e projetado coerentes (RN-061, RN-063) |
| Amortização extra + estorno da amortização | Tabela volta à versão anterior (RN-113, RN-123) |
| Conciliação + lançamento retroativo | Marco vira "a reconciliar" (RN-133) |
| Fatura com vencimento em sábado e H no mesmo dia útil seguinte | Entra no comprometido pelo vencimento original (RN-072, RN-140) |

## 7. Integridade do Ledger

### 7.1 Propriedades (Hypothesis)

O gerador cria sequências de 1 a 200 operações aleatórias válidas, com datas, valores, contas, cartões e pessoas sorteados: lançamentos, transferências, compras com parcelas e terceiros, pagamentos parciais, estornos, correções, recebimentos e baixas. Após **cada** operação, verifica:

| Propriedade | Origem |
|---|---|
| Toda transação soma zero | I-01 |
| Toda transação confirmada tem ≥ 2 pernas não nulas | I-02 |
| Nenhum estorno duplicado; estorno espelha a original | I-03 |
| Saldos recalculados do zero = saldos exibidos | I-04 |
| Liquidações ≤ planejado + excedente classificado | I-05 |
| Parcelas de compra e de a receber somam o total | I-06 |
| Alocações das faturas = passivo do cartão | I-07 |
| Equação patrimonial | I-08 |
| Estornar tudo leva todos os saldos de volta à abertura | Propriedade de reversibilidade |
| Disponível = livre − comprometido; projetado em D = hoje não difere do livre, exceto por itens atrasados e vencendo hoje | Coerência de RN-145 e RN-146 |
| Nenhuma compra de terceiro, transferência, pagamento de fatura ou recebimento aparece em receitas ou despesas | RN-164 |

Falhas encontradas pelo Hypothesis viram testes fixos (o exemplo mínimo é guardado).

### 7.2 Atomicidade

| Teste | Como |
|---|---|
| Falha entre pernas | Injetar erro após gravar a primeira perna de transferência, compra mista, Corrigir, abertura por itens e pagamento com juros. Verificar que nada foi gravado |
| Falha após a transação e antes da alocação | Na compra parcelada (MVP-3) e no recebimento (MVP-4). Verificar rollback total |
| Nenhuma transação `draft` após commit | Varredura no fim de cada teste de integração |

### 7.3 Gatilhos do banco

Testes com SQL direto, contornando os serviços, provam que o banco recusa:
- `UPDATE` e `DELETE` em pernas;
- `DELETE` em transações;
- alteração de transação confirmada;
- transição de estado inválida;
- finalização desequilibrada;
- `reversed` sem vínculo;
- alteração da auditoria;
- liquidação com transação não confirmada.

(`database-design.md` §11.)

### 7.4 Idempotência e concorrência

| Teste | Esperado |
|---|---|
| Mesmo formulário enviado duas vezes (mesma chave) | Uma transação; segunda resposta aponta para a primeira (S12) |
| Envios simultâneos com a mesma chave (duas threads) | Uma transação; nenhuma exceção não tratada |
| Duas sessões editam o mesmo compromisso com a mesma versão | A segunda é recusada com aviso (RN-172) |
| Duas sessões pagam a mesma conta em aberto com chaves diferentes | A segunda é recusada por exceder o aberto (RN-043) |

## 8. Cálculos isolados (unidade)

| Área | Casos |
|---|---|
| `Money` | Soma, subtração, multiplicação por inteiro, formatação pt-BR (`R$ 1.234,56`, `−R$ 0,01`), leitura de texto digitado, recusa de `float` |
| Arredondamento | `ROUND_HALF_UP` em 0,005 → 0,01; −0,005 → −0,01; valores grandes |
| Rateio | S01; n = 1; n = 48; total menor que n centavos (recusado: parcela de 0,00) |
| Price | S09 completo; taxa 0% (PMT = S/n); n = 1; divergência com parcela do contrato; reduzir parcela |
| Ciclo de fatura | Fechamento dia 31 em meses curtos; vencimento menor que fechamento; compra no dia do fechamento; virada de ano |
| Calendário | 5º dia útil de todos os meses de 2026 e 2027 (tabela abaixo); Carnaval; feriado em sexta e segunda; vencimento dia 31 |
| Saldos | Cada fórmula RN-140 a RN-149 com dados mínimos; H sem salário previsto (cai para fim do mês) |

**5º dia útil esperado** (RN-091, sem sábado, feriados nacionais, estadual de 9/7, municipais de SP e Carnaval):

| Ano | Jan | Fev | Mar | Abr | Mai | Jun | Jul | Ago | Set | Out | Nov | Dez |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026 | 08/01 | 06/02 | 06/03 | 08/04 | 08/05 | 08/06 | 07/07 | 07/08 | 08/09 | 07/10 | 09/11 | 07/12 |
| 2027 | 08/01 | 05/02 | 05/03 | 07/04 | 07/05 | 07/06 | 07/07 | 06/08 | 08/09 | 07/10 | 08/11 | 07/12 |

Datas móveis conferidas: Carnaval 16–17/02/2026 e 08–09/02/2027; Sexta-feira Santa 03/04/2026 e 26/03/2027; Corpus Christi 04/06/2026 e 27/05/2027.

## 9. Segurança

| Teste | Esperado |
|---|---|
| Todas as rotas sem login | Redirecionam para o login (teste percorre a lista de rotas do projeto), exceto login, PIN e estáticos |
| 5 senhas erradas | Bloqueio de 15 min; auditoria; alerta enfileirado |
| Bloqueio repetido | Duração dobra |
| Sessão ociosa 31 min | Pede PIN (aparelho confiável) ou senha |
| PIN com token válido | Reabre a sessão; troca o identificador da sessão |
| 5 PIN errados | Aparelho revogado; senha exigida |
| Token de aparelho vencido (31 dias) | Senha exigida |
| Operação sensível com sessão aberta por PIN | Pede senha |
| `POST` sem token CSRF | 403 |
| Cabeçalho `Host` não permitido | 400 |
| Cabeçalhos de segurança | CSP, HSTS, `nosniff`, `Referrer-Policy` presentes |
| Modo de depuração | Desligado na configuração de produção |
| Logs e auditoria após a suíte | Nenhum padrão de senha, PIN, token ou chave |
| Servidor | Escuta só em 127.0.0.1 (teste de configuração) |
| Dependências | `pip-audit` sem vulnerabilidade conhecida não tratada |

## 10. Backup e recuperação

| Teste | Esperado |
|---|---|
| Backup com escrita simultânea | Cópia consistente; invariantes passam na cópia |
| Arquivo de backup corrompido (bytes alterados) | Verificação de checksum falha; alerta |
| Banco com invariante violada (montado no teste) | Backup marcado com falha de verificação; alerta |
| Senha de backup errada na restauração | Recusa clara; nada substituído |
| Ida e volta | Backup → restauração em banco vazio → todos os saldos, transações e auditoria iguais |
| Restauração com falha no meio | Banco original intacto |
| Retenção | Após 400 dias simulados: 7 diários, 4 semanais, 12 mensais, e os de atualização com menos de 90 dias |
| Recuperação de tarefa atrasada | PC "desligado" no horário (avanço de relógio): backup roda ao iniciar |
| Teste mensal automático | Executa, registra `restore_test`, alerta em falha |
| Descriptografia independente | Arquivo abre com a ferramenta `age` de linha de comando e resulta em SQLite válido |
| Pasta da nuvem indisponível | Backup local ainda gravado; alerta de cópia da nuvem |

## 11. Migrações entre entregas

| Migração | Teste |
|---|---|
| MVP-1 → MVP-3 (faturas a partir de compras e itens de abertura) | Base com S00 + S14 (eventos de novembro) e pagamentos de cartão do MVP-1. Após migrar: nenhuma perna alterada (hash das pernas igual antes e depois); faturas iguais às de S14; I-07 válida |
| MVP-1 → MVP-4 (parcelas a receber) | Partes de terceiros do MVP-1 viram parcelas alinhadas às faturas; recebimentos já feitos são alocados; soma igual |
| MVP-4 → MVP-5 (tabela da dívida) | Pagamentos manuais do MVP-1 reconhecidos como parcelas pagas; tabela recalculada a partir do saldo do Ledger |
| Toda migração | Roda em cópia de um banco real (anonimizado: só nomes trocados) antes de ir para produção |

## 12. Ponta a ponta (Playwright)

Executados em viewport de celular (390 × 844) e de computador (1.440 × 900), nos temas claro e escuro.

| Fluxo | Verificações |
|---|---|
| Assistente de abertura completo (S00) | Totais da revisão iguais aos esperados |
| Lançamento rápido de gasto no cartão em 4 toques | Toast, "Desfazer" funciona |
| Duplo toque no "Salvar" | Uma transação |
| Compra com "dividir com alguém" | A receber criado; despesa só da parte própria |
| Pagar conta com valor parcial e depois o resto | Status "Pago parcialmente" → "Pago" |
| Corrigir lançamento | Lista mostra só o corrigido; filtro mostra o par |
| Fatura: pagar parcial (MVP-3) | Alerta forte; saldo transportado |
| Simulador de dívida (MVP-5) | Valores de S09 |
| Conciliação com diferença | Ajuste criado; relatório mostra diferença |
| Restaurar backup em modo teste | Resumo exibido; banco intacto |
| Sessão expirada no celular | Tela de PIN; rascunho preservado |
| "De onde vem este número" no disponível | Fórmula e lista batem com S14 |

## 13. Portas de validação

Cada entrega só é aprovada com **todos** os itens. O usuário aprova a passagem para a próxima entrega.

| Entrega | Automático | Uso real (validação do usuário) |
|---|---|---|
| MVP-1 | Suíte completa verde; partes MVP-1 de S00, S01, S08, S10-B, S11, S12-A e S13 (saldo) passando; propriedades com 1.000 exemplos sem falha; gatilhos; segurança §9; backup §10 | Duas semanas de lançamentos reais; conciliação semanal de todas as contas sem diferença não explicada; um teste de restauração manual (checklist `security-plan.md` §7.5) |
| MVP-2 | + recorrências, liquidações, calendário (§8), alertas; partes MVP-2 de S00 e S12-B; S14 parcial (bancário e disponível com cartão estimado) | Um ciclo de salário completo: datas de vencimento e salário corretas; nenhum alerta errado ou faltando no Telegram; disponível conferido à mão em 3 datas |
| MVP-3 | + S02, S06, S07, S10-A, S12-C, S13 (limite), partes MVP-3 de S00; migração MVP-1 → MVP-3 (§11) | Faturas calculadas de todos os cartões iguais às do emissor por 1 ciclo de fechamento (diferenças só por encargos lançados depois) |
| MVP-4 | + S03 completo, S04, S05; migração MVP-1 → MVP-4 | Saldo a receber por pessoa conferido com o usuário |
| MVP-5 | + S09; simulador; migração MVP-4 → MVP-5 | Tabela de amortização igual ao extrato do banco na próxima parcela (juros e saldo) |
| MVP-6 | + S14 completo; "de onde vem" de todos os indicadores; E2E §12 | Projeção de 30 dias conferida à mão; comprometimento de renda revisado pelo usuário |

## 14. Validação manual pelo usuário (roteiro)

Para cada entrega, o roteiro guiado mostra:
1. o que conferir e onde encontrar o número no app do banco;
2. a tolerância aceita (zero, salvo encargos ainda não informados);
3. como registrar o resultado (aprovado ou com diferença).

Diferenças viram registro com causa. A causa pode ser:
- **erro de lançamento:** o usuário corrige;
- **regra do emissor diferente:** ajuste de configuração do cartão;
- **bug:** novo teste que reproduz o problema, depois a correção.
