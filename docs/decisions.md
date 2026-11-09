# Registro de Decisões — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.6 |
| Data | 06/11/2026 |
| Etapa | 3 — Arquitetura (Fase A) |
| Status | Versão 0.1 aprovada em 06/11/2026 (ADR-001 a 031: "Proposta" passa a valer como aceita). Versão 0.2 acrescenta ADR-032 a 036 (Fase B), aprovada em 06/11/2026. Versão 0.3 acrescenta ADR-037 e 038 (Fase 1D), aprovada em 06/11/2026. Versão 0.4 acrescenta ADR-039 (Fase 2A), aprovada em 08/11/2026. Versões 0.5 e 0.6 acrescentam ADR-040 e 041, decisões do usuário em 08/11/2026 |
| Documentos relacionados | `product-requirements.md`, `architecture.md` |

Formato: cada decisão (ADR) tem status, contexto, decisão, alternativas consideradas e consequências.

**Status possíveis**
- **Aceita (descoberta):** escolha feita pelo usuário na Etapa 1 ou nos ajustes posteriores.
- **Proposta:** recomendação técnica aguardando aprovação da Fase A.
- **Pendente:** depende de resposta do usuário (itens P-xx de `product-requirements.md`, seção 12).

Uma decisão aprovada só muda por nova ADR que a substitua, citando a anterior.

## Índice

| ADR | Título | Status |
|---|---|---|
| 001 | Livro-Razão de partidas dobradas como fonte única da verdade | Aceita (requisito) / modelo proposto |
| 002 | Dinheiro em centavos inteiros; taxas em decimal exato | Proposta |
| 003 | Nada é excluído: cancelamento e estorno | Aceita (descoberta) |
| 004 | Registro provisório de cartão e faturas como alocação sobre o passivo | Aceita (ajuste) / modelo proposto |
| 005 | Gasto no cartão reconhecido no mês da compra, com duas visões para parcelados | Aceita (descoberta) |
| 006 | Quatro saldos disjuntos, horizonte H e enquadramento das recorrências | Aceita (ajuste, P-01 e P-07) |
| 007 | Valores a receber no MVP | Aceita (ajuste) |
| 008 | Consórcio não contemplado como compromisso fixo | Proposta (P-05) |
| 009 | MVP em seis entregas com portas de validação | Aceita (ajuste) |
| 010 | Cartões e valores a receber antes de dívidas | Proposta |
| 011 | Aplicação monolítica local no PC do usuário | Aceita (descoberta) / forma proposta |
| 012 | Acesso remoto por Tailscale Serve com HTTPS | Aceita (descoberta) / HTTPS proposto |
| 013 | Python e Django, ambiente gerenciado com `uv` | Proposta |
| 014 | SQLite e ORM do Django | Proposta |
| 015 | Interface renderizada no servidor com htmx, Alpine.js e Tailwind; PWA | Proposta |
| 016 | Gráficos com Apache ECharts servido localmente | Proposta |
| 017 | Waitress como servidor web e WinSW como serviço do Windows | Proposta |
| 018 | Agendador interno com registro de execuções e recuperação | Proposta |
| 019 | Autenticação: senha Argon2id, bloqueio de tentativas, sessões e PIN como conveniência | Aceita; regra do PIN substituída em parte pela ADR-035 |
| 020 | Segredos no cofre do Windows; bot do Telegram só envia | Proposta |
| 021 | Backup: cópia online do SQLite, verificação, `age`, retenção e teste de recuperação | Aceita (ajuste) / mecanismo proposto |
| 022 | Criptografia do banco em repouso | Aceita (P-06) |
| 023 | Estratégia de testes: unidade, propriedades, cenários de referência e ponta a ponta | Proposta |
| 024 | Exportação: CSV, Excel (openpyxl) e PDF (ReportLab) | Proposta |
| 025 | Calendário de dias úteis próprio com feriados de São Paulo | Aceita (descoberta, P-02) / 9 de julho proposto (P-03) |
| 026 | Arredondamento meio para cima em pontos definidos | Proposta (rateio: P-04) |
| 027 | Pagamento extra de dívida reduz prazo por padrão | Aceita (descoberta) |
| 028 | Avalanche, bola de neve e orçamento no pós-MVP | Aceita (descoberta) |
| 029 | Alertas pelo Telegram com nome e valor | Aceita (descoberta) |
| 030 | Carteira de benefícios separada do dinheiro disponível | Aceita (descoberta) |
| 031 | Início em 01/11/2026 com saldos de abertura | Aceita (descoberta) |
| 032 | Compromissos são liquidados, nunca confirmados | Proposta (Fase B) |
| 033 | Estorno técnico e estorno comercial | Proposta (Fase B) |
| 034 | Parcelas de cartão e de valores a receber como alocações | Proposta (Fase B) |
| 035 | PIN reabre sessão até o fim da confiança do aparelho | Aceita (decisão do usuário na Fase B) |
| 036 | Horizonte H avança só com o salário confirmado | Aceita (decisão do usuário na Fase B) |
| 037 | Arquivos estáticos servidos pelo próprio processo (WhiteNoise) | Aceita (aprovada pelo usuário na Fase 1D) |
| 038 | Sistema em uso roda de um clone separado do código | Aceita (aprovada pelo usuário na Fase 1D) |
| 039 | Compromisso é alterado por cancelamento e recriação; pagamento não se corrige | Aceita (aprovada pelo usuário na Fase 2A) |
| 040 | Estudo de design e UI/UX antes das próximas telas (Fase 2B) | Aceita (decisão do usuário) |
| 041 | "Pode gastar" como número principal, descontando o mínimo de segurança | Aceita (decisão do usuário) |

---

## ADR-001 — Livro-Razão de partidas dobradas como fonte única da verdade

**Status:** Aceita (requisito do usuário). Modelo de partidas dobradas proposto.

**Contexto:** o usuário exige que todos os saldos, indicadores e relatórios venham de um registro central, sem dupla contagem e com rastreabilidade total. Pede regras de débito e crédito e vínculos entre operações compostas.

**Decisão:**
- Toda operação é uma transação com duas ou mais pernas que somam zero, sobre contas contábeis (ativo, passivo, receita, despesa, patrimônio).
- Só o módulo `ledger` grava pernas; os demais módulos usam a interface de serviço dele.
- Saldos são sempre soma de pernas confirmadas.

**Alternativas:**
- *Lançamento simples tipado* (cada movimentação com tipo e sinal). Mais simples no início, mas cada tipo novo exige regra própria de saldo, e a prevenção de dupla contagem depende de cada módulo acertar. Rejeitada.
- *Saldos guardados por módulo.* Viola o requisito de fonte única. Rejeitada.

**Consequências:**
- Transferências, faturas, aportes e recebimentos não tocam contas de resultado, então não podem virar receita ou despesa por engano.
- A verificação "soma zero" detecta transações incompletas.
- A interface precisa traduzir pernas em linguagem comum; o usuário nunca vê débito e crédito.
- Exige mais rigor no desenho inicial (pago no MVP-1).

## ADR-002 — Dinheiro em centavos inteiros; taxas em decimal exato

**Status:** Proposta.

**Contexto:** o pedido exige precisão decimal sem erros de arredondamento. O SQLite não tem tipo decimal exato.

**Decisão:**
- Valores monetários como inteiro de centavos no banco e num tipo `Money` no código.
- Taxas e índices como `Decimal`, guardados como texto decimal validado.
- Proibido `float` em qualquer cálculo financeiro; regra verificada por teste e por revisão.

**Alternativas:**
- *`DecimalField` do Django sobre SQLite.* Pode perder precisão, porque o SQLite converte o valor para ponto flutuante. Rejeitada.
- *Texto decimal também para dinheiro.* Funciona, mas somas no banco ficam lentas e sujeitas a erro. Rejeitada.

**Consequências:** somas no banco são exatas e rápidas. A formatação pt-BR fica centralizada no tipo `Money`.

## ADR-003 — Nada é excluído: cancelamento e estorno

**Status:** Aceita (decisão do usuário: "tudo só por estorno").

**Contexto:** o pedido original prevê editar e excluir registros. O Ledger proíbe sobrescrever ou apagar movimentações confirmadas.

**Decisão:**
- Nenhuma movimentação é excluída fisicamente.
- Previstos e pendentes são **cancelados**, com motivo.
- Confirmados são corrigidos por **estorno** vinculado + nova transação; a ação "Corrigir" faz as duas coisas atomicamente.
- Gatilhos no banco reforçam a regra.
- Contas, cartões, categorias e pessoas são **arquivados**, nunca excluídos.

**Alternativas:**
- *Excluir previstos livremente.* Mais simples, porém perde histórico de planejamento. O usuário escolheu não fazer isso.
- *Janela curta de edição.* Prática para erros de digitação, mas abre exceção à imutabilidade. Rejeitada pelo usuário.

**Consequências:**
- Mais registros no banco (irrelevante no volume pessoal).
- Listas e relatórios ocultam cancelados e pares estornados por padrão, com filtro para exibir.
- "Corrigir" precisa ser tão rápido quanto editar, para não atrapalhar o uso.

## ADR-004 — Registro provisório de cartão e faturas como alocação sobre o passivo

**Status:** Aceita (ajuste do usuário). Modelo proposto.

**Contexto:** o uso diário com 4 ou mais cartões começa no MVP-1, mas faturas e parcelas só chegam no MVP-3. O usuário exige que o registro antecipado não prejudique a implementação futura.

**Decisão:**
- No MVP-1, compra no cartão gera pernas definitivas pelo valor total na data da compra: despesa (ou a receber) contra o passivo do cartão. Número e valor das parcelas ficam gravados no registro da compra.
- O passivo inicial de cada cartão é aberto por itens (ADR-031), com cronograma, para que o MVP-3 consiga gerar as faturas reais.
- No MVP-3, parcelas e faturas são alocações desse passivo em ciclos. Não criam pernas. São geradas por migração a partir das compras e dos itens de abertura.
- Até o MVP-3, o valor do cartão devido até H é **estimado** com os dados gravados (data, parcelas, fechamento, vencimento) e rotulado como estimativa.

**Alternativas:**
- *Pernas por parcela* (cada parcela vira lançamento no mês da fatura). Contraria a decisão de reconhecer o gasto no mês da compra (ADR-005) e exigiria reescrever os lançamentos do MVP-1. Rejeitada.
- *Esperar o MVP-3 para lançar cartões.* Inviável no uso real. Rejeitada.

**Consequências:**
- Nenhum lançamento confirmado é reescrito na transição.
- O limite consumido aparece correto desde o MVP-1.
- Entre MVP-1 e MVP-3 o comprometido do cartão é estimativa. A porta do MVP-3 confere a estimativa contra as faturas reais.
- Alternativa descartada: tratar todo o passivo como devido até H. Para quem parcela muito, deixaria o disponível negativo e inútil.

## ADR-005 — Gasto no cartão reconhecido no mês da compra, com duas visões para parcelados

**Status:** Aceita (descoberta).

**Decisão:**
- Despesa por competência na data da compra.
- Relatórios oferecem visão "por compra" (total no mês da compra) e "por parcela" (cada parcela no mês da fatura), com alternador. Compra à vista no cartão conta como uma parcela no mês da sua fatura (esclarecimento da Fase B, RN-162).
- As duas visões são cálculos distintos sobre os mesmos dados e nunca se somam.

**Consequências:**
- A visão por parcela depende das faturas do MVP-3. Antes disso, só a visão por compra é exibida.
- Toda tela com totais mostra qual visão está ativa.

## ADR-006 — Quatro saldos disjuntos e horizonte H

**Status:** Aceita (ajuste do usuário). Horizonte H e enquadramento das recorrências decididos pelo usuário (P-01, P-07).

**Decisão:** saldo bancário, saldo comprometido (H), saldo disponível e saldo projetado (D), mais saldo de benefícios e comprometido total como informativos. Definições no glossário de `product-requirements.md` (seção 4.3). Cada item pertence a um único grupo.

**Horizonte H (decidido):** até a próxima data prevista de salário (exclusive), configurável para fim do mês. O salário costuma ser a próxima entrada relevante, então H responde "quanto posso gastar até o dinheiro entrar de novo".

**Alternativas:**
- *Fim do mês fixo.* Mais simples. Mas, com salário no 5º dia útil, o comprometido entre o fim do mês e o salário ficaria de fora. Mantido como opção.
- *30 dias corridos.* Sem relação com o fluxo real de renda. Rejeitado.

**Enquadramento das recorrências (decidido):**
- Recorrências de valor fixo ou contratual (aluguel, internet, assinaturas, parcelas) viram pendentes dentro de H e entram no comprometido.
- Contas variáveis estimadas (luz, água, mercado) ficam previstas e entram só no projetado.

Sem essa regra, um aluguel que vence antes do salário não reduziria o disponível, o que vai contra o objetivo "parar de atrasar contas".

**Consequências:** fórmulas e exemplos numéricos obrigatórios em `business-rules.md` e `reference-scenarios.md` (Fase B), provando que não há sobreposição.

## ADR-007 — Valores a receber no MVP

**Status:** Aceita (ajuste do usuário).

**Contexto:** compras de terceiros nos cartões e empréstimos a terceiros ocorrem desde o primeiro mês.

**Decisão:**
- Registro básico (pessoa, valor a receber, recebimento simples) no MVP-1.
- Parcelas, recebimentos parciais por parcela, atrasados e baixa no MVP-4.
- Valor a receber é ativo; recebimento não é receita; baixa é despesa de perda.

**Consequências:** gastos próprios nunca ficam inflados por compras de terceiros, já no MVP-1.

## ADR-008 — Consórcio não contemplado como compromisso fixo

**Status:** Proposta (P-05). Vale como padrão se a Fase A for aprovada sem objeção.

**Contexto:** consórcio sem contemplação não tem juros nem bem recebido. Contabilmente, o valor pago forma um direito sobre a carta de crédito. Para o usuário, que conta só com sorteio, ele funciona como parcela mensal fixa.

**Proposta:**
- Parcela lançada como despesa da categoria "Consórcio" e como compromisso fixo no comprometido e nas projeções.
- Sem passivo e sem simulação de juros.
- Reajustes informados pelo usuário.

**Alternativa:** registrar o pago como ativo "cota de consórcio" e só a taxa de administração como despesa. Mais correto contabilmente, mas exige dados (fundo comum, taxa, fundo de reserva) que o usuário teria de separar mês a mês. Reavaliar se houver contemplação.

**Consequências:** o relatório de gastos mostra o consórcio numa categoria própria, fácil de excluir da análise de consumo.

## ADR-009 — MVP em seis entregas com portas de validação

**Status:** Aceita (ajuste do usuário).

**Decisão:** MVP-1 a MVP-6, conforme `product-requirements.md` (seção 8). Cada entrega só começa após a porta de validação da anterior: testes, cenários de referência e uso real comparado com extratos e faturas.

**Consequências:** o valor completo chega mais tarde, mas erros de cálculo são encontrados cedo, antes de outras camadas dependerem deles.

## ADR-010 — Cartões e valores a receber antes de dívidas

**Status:** Proposta.

**Contexto:** a prioridade declarada é quitar dívidas, mas o usuário tem só uma dívida com juros e usa 4 ou mais cartões todos os dias.

**Decisão:** ordem MVP-3 (cartões) → MVP-4 (a receber) → MVP-5 (dívidas). O MVP-4 e o MVP-5 podem ser invertidos a pedido do usuário.

**Consequências:** a simulação de antecipação usa saldos e compromissos já confiáveis. O cadastro da dívida existe, como passivo com saldo de abertura, desde o MVP-1, e as parcelas pagas são lançadas como pagamento normal até o MVP-5.

## ADR-011 — Aplicação monolítica local no PC do usuário

**Status:** Aceita (descoberta: servidor no PC). Forma monolítica proposta.

**Decisão:** um único processo web com agendador interno, rodando como serviço no PC, com banco em arquivo local.

**Alternativas:**
- *Hospedagem em nuvem.* PC poderia ficar desligado, mas tem custo mensal e maior exposição. O usuário escolheu o PC.
- *Frontend e backend separados.* Mais peças, sem ganho. Rejeitada.

**Consequências:** com o PC desligado, nada funciona. Mitigado por início automático e recuperação de tarefas atrasadas.

## ADR-012 — Acesso remoto por Tailscale Serve com HTTPS

**Status:** Aceita (descoberta: Tailscale). HTTPS via Tailscale Serve proposto.

**Decisão:**
- Servidor escuta só em `127.0.0.1`.
- Tailscale Serve publica o serviço apenas na rede privada do usuário, com certificado HTTPS automático `*.ts.net`.
- Tailscale Funnel nunca é ativado.

**Alternativas:**
- *HTTP puro dentro do túnel.* O tráfego já vai criptografado pelo túnel, mas o navegador bloqueia cookies `Secure`, PWA e service worker. Rejeitada.
- *Certificado próprio autoassinado.* Gera alertas no navegador e exige instalar certificado no celular. Rejeitada.

**Consequências:** o nome da máquina aparece em logs públicos de transparência de certificados; o guia orienta usar nomes neutros.

## ADR-013 — Python e Django, ambiente gerenciado com `uv`

**Status:** Proposta.

**Decisão:**
- Python estável vigente e Django na versão LTS vigente.
- `uv` instala o Python e as dependências travadas, com um comando.

**Justificativa:**
- `Decimal` nativo.
- Autenticação, sessões, CSRF, formulários, migrações, admin e transações prontos e maduros.
- Código legível para usuário intermediário.
- LTS reduz a frequência de atualizações obrigatórias.

**Alternativas:** FastAPI, Next.js, ASP.NET Core, Spring (comparação em `architecture.md`, seção 4.1).

**Consequências:** a interface terá pouco JavaScript; interações muito ricas exigem mais esforço.

## ADR-014 — SQLite e ORM do Django

**Status:** Proposta.

**Decisão:**
- SQLite em modo WAL, com chaves estrangeiras ligadas e transações em modo `IMMEDIATE`.
- Migrações e acesso pelo ORM do Django.

**Alternativas:** PostgreSQL (mais operação, sem ganho para um usuário); arquivos JSON ou planilha (sem integridade).

**Consequências:**
- Backup e restauração são operações sobre um arquivo, com API de cópia online.
- Migração futura para PostgreSQL continua possível pelo ORM.

## ADR-015 — Interface renderizada no servidor com htmx, Alpine.js e Tailwind; PWA

**Status:** Proposta.

**Decisão:**
- Páginas HTML geradas pelo Django.
- htmx para atualizações parciais; Alpine.js para pequenas interações locais; Tailwind CSS (CLI própria, sem Node) para o visual.
- Manifesto e service worker mínimos para instalar no celular como aplicativo.
- Todos os arquivos servidos localmente.

**Alternativas:** SPA com React, Vue ou Svelte (dois projetos, API, build com Node); templates sem htmx (recarregamento total).

**Consequências:**
- Validação e regras ficam só no servidor.
- O lançamento rápido no celular é um formulário leve.
- Funcionamento offline fica fora do escopo.

## ADR-016 — Gráficos com Apache ECharts servido localmente

**Status:** Proposta.

**Decisão:** ECharts para todos os gráficos, com temas claro e escuro alinhados à paleta do sistema e textos em pt-BR.

**Alternativa:** Chart.js, mais leve, com menos tipos de gráfico. Fica como alternativa se o desempenho no celular exigir.

## ADR-017 — Waitress como servidor web e WinSW como serviço do Windows

**Status:** Proposta.

**Decisão:** Waitress serve a aplicação; WinSW registra o serviço com início automático, reinício em falha e logs.

**Alternativas:** Gunicorn (não roda no Windows); NSSM (manutenção irregular); Agendador de Tarefas do Windows (sem reinício automático; plano B).

**Consequências:**
- O serviço roda com a conta do usuário, para acessar o cofre de credenciais e a pasta da nuvem. Isso exige a senha da conta do Windows; contas Microsoft que só usam Windows Hello podem não ter uma senha utilizável. O instalador verifica esse ponto.
- Plano B: tarefa agendada "ao fazer logon", dependente de sessão aberta.
- A sincronização da nuvem depende de sessão aberta nos dois casos.

## ADR-018 — Agendador interno com registro de execuções e recuperação

**Status:** Proposta.

**Decisão:**
- Agendador dentro do processo do serviço.
- Cada tarefa é idempotente e grava início, fim e resultado.
- Ao iniciar, o serviço executa as tarefas atrasadas.
- Tarefas: backup, teste de restauração, recorrências, alertas, atrasos, janela de previstos.

**Alternativas:** Agendador de Tarefas do Windows (configuração extra; plano B); Celery e Redis (exagero).

**Consequências:** um único lugar para logs e para a tela de saúde do sistema.

## ADR-019 — Autenticação: senha Argon2id, bloqueio de tentativas, sessões e PIN como conveniência

**Status:** Aceita (descoberta: senha + PIN; ajuste: PIN não substitui a senha). Mecanismo proposto.

**Decisão:**
- Senha forte com hash Argon2id.
- django-axes para atraso progressivo, bloqueio temporário e alerta.
- Sessões com expiração por inatividade (proposta: 30 min) e absoluta (proposta: 12 h).
- Aparelho confiável com token de 30 dias e PIN que só reabre sessão expirada por inatividade. (Substituído em parte pela ADR-035.)
- 5 erros de PIN revogam o aparelho.
- Senha sempre exigida em operações sensíveis.

**Alternativas:** TOTP e passkeys (WebAuthn), avaliados para o pós-MVP como opções adicionais.

**Consequências:** o PIN agiliza o uso diário no celular sem enfraquecer a autenticação principal.

## ADR-020 — Segredos no cofre do Windows; bot do Telegram só envia

**Status:** Proposta.

**Decisão:**
- Token do Telegram, senha de backup e chave secreta da aplicação ficam no Cofre de Credenciais do Windows (DPAPI), via `keyring`.
- O bot só envia mensagens ao `chat_id` autorizado.

**Alternativas:** arquivo `.env` com permissão restrita (mais simples, porém o segredo fica legível em disco e pode ir parar em backups ou no Git). Rejeitada como padrão; aceitável só como plano B documentado.

**Consequências:** a restauração em outra máquina exige recadastrar os segredos; isso consta no guia de recuperação.

## ADR-021 — Backup: cópia online do SQLite, verificação, `age`, retenção e teste de recuperação

**Status:** Aceita (descoberta e ajuste: backup automático, nuvem, versões, verificação, restauração e testes). Mecanismo proposto.

**Decisão:** fluxo e retenção descritos em `architecture.md`, seção 10.
- Destinos: pasta local e pasta sincronizada de nuvem.
- Criptografia `age` com senha de backup própria.
- Teste mensal automático de restauração e checklist trimestral manual.

**Alternativas:** cópia simples do arquivo (risco de corrupção); ZIP com senha (criptografia fraca); criptografia própria (risco de erro).

**Consequências:** o usuário precisa guardar a senha de backup fora do sistema. Sem ela, os backups ficam ilegíveis.

## ADR-022 — Criptografia do banco em repouso

**Status:** Aceita (decisão do usuário, P-06).

**Decisão:**
- Usar a criptografia de dispositivo do Windows, se o hardware suportar, conferida na instalação.
- Sem suporte, aceitar o risco registrado e reavaliar SQLCipher no pós-MVP.
- Backups sempre criptografados.

Comparação em `architecture.md`, seção 9.4.

## ADR-023 — Estratégia de testes

**Status:** Proposta.

**Decisão:**
- pytest e pytest-django para unidade e integração.
- Hypothesis para invariantes do Ledger sob sequências aleatórias de operações.
- Cenários de referência como testes parametrizados com resultado exato em centavos.
- Playwright para fluxos de ponta a ponta, inclusive em tela de celular.
- time-machine para datas.
- Testes de backup e restauração.

**Consequências:** cada porta de validação tem critério objetivo. Metas de cobertura serão definidas em `testing-plan.md`.

## ADR-024 — Exportação: CSV, Excel e PDF

**Status:** Proposta (pós-MVP).

**Decisão:**
- CSV pela biblioteca padrão (UTF-8 com BOM, `;`, vírgula decimal).
- Excel com openpyxl.
- PDF com ReportLab.

**Alternativa descartada:** WeasyPrint, que exige bibliotecas GTK no Windows. A escolha do PDF será revista na fase de relatórios.

## ADR-025 — Calendário de dias úteis próprio com feriados de São Paulo

**Status:** Aceita (descoberta: feriados nacionais e da cidade de São Paulo; sábado não conta; P-02: Carnaval não é dia útil). Inclusão de 9 de julho proposta (P-03).

**Decisão:**
- Tabela de feriados editável, pré-carregada.
- Dois calendários lógicos: dia útil do salário e dia útil bancário. Hoje coincidem; ficam separados para permitir divergência futura.
- Segunda e terça de Carnaval não são dias úteis, nos dois calendários.
- Verificação: 5º dia útil em 09/11/2026 e 07/12/2026.

**Consequências:** o usuário revisa a lista de feriados uma vez por ano. O sistema lembra de fazer isso em dezembro.

## ADR-026 — Arredondamento meio para cima em pontos definidos

**Status:** Proposta, incluindo a regra de rateio de parcelas (P-04).

**Decisão:**
- `ROUND_HALF_UP` para centavos.
- Arredondamento só em pontos definidos: valor de cada parcela, juros de cada período, valor de cada perna.
- Cálculos intermediários em `Decimal` com 28 dígitos.
- Resto de rateio na primeira parcela (proposta).
- Na Tabela Price, a última parcela absorve o resíduo.

**Alternativa:** arredondamento bancário (meio para o par), que não é o padrão usado por bancos e emissores no Brasil. Rejeitada.

## ADR-027 — Pagamento extra de dívida reduz prazo por padrão

**Status:** Aceita (descoberta).

**Decisão:** padrão "reduzir prazo"; simulador mostra também "reduzir parcela" lado a lado.

## ADR-028 — Avalanche, bola de neve e orçamento no pós-MVP

**Status:** Aceita (descoberta e proposta aceita no plano).

**Decisão:**
- Estratégias avalanche e bola de neve no pós-MVP, com desenho genérico para várias dívidas. Hoje há só uma dívida com juros.
- Orçamento por categoria no pós-MVP, depois de alguns meses de histórico.

## ADR-029 — Alertas pelo Telegram com nome e valor

**Status:** Aceita (descoberta).

**Decisão:** alertas incluem nome e valor; o usuário aceitou que o Telegram veja esse conteúdo. A antecedência é configurável.

**Consequências:** nenhum outro dado (saldos totais, lista de contas) é enviado sem nova decisão.

## ADR-030 — Carteira de benefícios separada do dinheiro disponível

**Status:** Aceita (descoberta).

**Decisão:** VR/VA em conta de classe "benefício". Saldo próprio, fora do bancário, do disponível e do projetado. Gastos com benefício saem dela.

## ADR-031 — Início em 01/11/2026 com saldos de abertura

**Status:** Aceita (descoberta).

**Decisão:**
- Saldos das contas financeiras em 01/11/2026 entram como transações de abertura contra a conta de patrimônio.
- Cartões, dívida, consórcio e empréstimos a terceiros abrem por **itens de abertura**, cada um com seu cronograma:
  - cartões: fatura fechada a vencer, compras da fatura aberta e parcelas restantes de compras antigas (data original, total, parcelas, parcelas já faturadas, própria ou de terceiro);
  - dívida: saldo devedor, taxa e parcelas restantes;
  - consórcio e empréstimos a terceiros: parcelas restantes.
- Itens próprios vão contra patrimônio, para não inflar as despesas de novembro. Itens de terceiro vão contra o valor a receber da pessoa.
- O que aconteceu de 01/11 até a data de início do uso é lançado normalmente.

**Alternativa descartada:** um valor único por cartão ou dívida. Mais rápido de cadastrar, mas perde o cronograma. As faturas do MVP-3 e o comprometimento de renda ficariam errados por meses.

**Consequências:**
- O cadastro inicial leva mais tempo; um guia de abertura indica o que copiar de cada app.
- A primeira conciliação compara o saldo calculado com o banco logo após os lançamentos do mês.

## ADR-032 — Compromissos são liquidados, nunca confirmados

**Status:** Proposta (Fase B).

**Contexto:** contas a pagar, receitas previstas e parcelas podem ser pagas de uma vez, em partes ou com valor diferente do planejado.

**Decisão:**
- Previsto e pendente nunca passam a confirmado.
- Todo pagamento ou recebimento é uma transação confirmada nova, ligada ao compromisso por uma liquidação (`settlement`).
- Valor em aberto = planejado − liquidações confirmadas (RN-040 a RN-044).

**Alternativa:** confirmar o próprio compromisso quando pago integralmente. Criaria dois caminhos para dinheiro real entrar no Ledger e exigiria editar o valor planejado em pagamentos parciais. Rejeitada.

**Consequências:**
- Pagamento parcial, juros por atraso e estorno de pagamento usam o mesmo mecanismo.
- Planejado × realizado fica sempre comparável.
- O botão "Pagar" esconde essa mecânica do usuário.

## ADR-033 — Estorno técnico e estorno comercial

**Status:** Proposta (Fase B).

**Contexto:** "estornar" pode significar corrigir um lançamento errado ou registrar uma devolução real feita pelo lojista. Os dois casos têm efeito diferente nos relatórios mensais.

**Decisão:**
- **Estorno técnico** (via Corrigir ou "lançamento errado") anula na **competência original**, como se a transação nunca tivesse existido.
- **Estorno comercial** (devolução ou cancelamento) é um fato novo, com data e competência do estorno, total ou parcial (RN-082 a RN-085).

**Consequências:**
- Corrigir um erro antigo muda o relatório do mês original, o que é desejado.
- Uma devolução real aparece no mês em que aconteceu.
- A interface pergunta qual é o caso ao estornar compra no cartão.

## ADR-034 — Parcelas de cartão e de valores a receber como alocações

**Status:** Proposta (Fase B).

**Contexto:** parcelas de cartão e de valores a receber distribuem no tempo um passivo ou ativo **que já existe** no Ledger. Parcelas de dívida e de contas, ao contrário, ainda vão gerar pernas novas (juros, despesa).

**Decisão:**
- Parcelas de cartão (`invoice_allocation`) e de valores a receber (`receivable_installment`) são alocações, sem pernas.
- Parcelas de dívida, consórcio e contas são compromissos (`commitment`) com pernas pretendidas.

**Consequências:**
- Comprometido e projetado somam compromissos e alocações de fontes diferentes. Por isso nada é contado duas vezes (RN-143, RN-146).
- As invariantes I-06 e I-07 conferem que as alocações fecham com os saldos do Ledger.

## ADR-035 — PIN reabre sessão até o fim da confiança do aparelho

**Status:** Aceita (decisão do usuário em 06/11/2026). Substitui a regra do PIN da ADR-019.

**Decisão:**
- Com o token do aparelho válido (30 dias), o PIN de 6 dígitos reabre a sessão expirada, tanto por inatividade (30 min) quanto pela expiração absoluta (12 h).
- O PIN não cria nem renova a confiança do aparelho: só a senha faz isso.
- Continuam valendo da ADR-019: 5 erros de PIN revogam o aparelho, e operações sensíveis pedem senha.

**Alternativa:** senha a cada 12 horas. Mais rígida, mas pouco prática para lançar gastos na hora pelo celular.

**Consequências:** quem tiver o celular desbloqueado **e** souber o PIN acessa o sistema por até 30 dias. Mitigação: bloqueio de tela do celular e revogação remota (`security-plan.md` §10.1).

## ADR-036 — Horizonte H avança só com o salário confirmado

**Status:** Aceita (decisão do usuário em 06/11/2026). Complementa a ADR-006.

**Decisão:**
- H = data do salário previsto mais antigo ainda não recebido.
- No dia do salário, até o "Recebi", H continua sendo esse dia.
- Se o salário atrasar, H = amanhã até a confirmação, e o dashboard mostra "salário atrasado" (RN-140).

**Consequências:** o disponível não despenca enquanto o dinheiro não entrou. Com salário atrasado, o disponível passa a considerar só o que vence até hoje, e o alerta de atenção deixa a situação explícita.

## ADR-037 — Arquivos estáticos servidos pelo próprio processo (WhiteNoise)

**Status:** Aceita (aprovada pelo usuário em 06/11/2026, Fase 1D).

**Contexto:** em produção o Django roda com `DEBUG=False` e o Waitress só executa a aplicação. Nesse modo o Django não serve `/static/` (CSS, htmx, Alpine, ícones). Sem uma solução, as telas abririam sem estilo e sem scripts. Os testes de ponta a ponta não mostravam o problema, porque o servidor de testes serve estáticos sozinho.

**Decisão:**
- Biblioteca WhiteNoise (`whitenoise` 6.x), como middleware logo depois do `SecurityMiddleware` e antes do login obrigatório.
- Armazenamento simples, sem nomes com hash. Os nomes com hash exigiriam `{% static %}` em todo lugar, inclusive na lista de cache do service worker e nos ícones do manifesto.
- `collectstatic` roda no `install.ps1` e no `update.ps1`. Em desenvolvimento e nos testes, o WhiteNoise lê as pastas de origem (`WHITENOISE_USE_FINDERS`).
- Teste automático com `DEBUG=False` confirma que o CSS e o JavaScript respondem sem login (`tests/backup/test_production_static.py`).

**Alternativas:**
- `django.views.static.serve` numa rota própria: sem dependência nova, mas a documentação do Django desaconselha em produção e não há controle de cache.
- Servir os arquivos pelo Tailscale Serve: não cobre o acesso por `127.0.0.1` no PC.

**Consequências:** uma dependência pequena e madura a mais, travada no `uv.lock` e auditada pelo `pip-audit`. Arquivos estáticos não exigem login, como já previa o `security-plan.md` §8.

## ADR-038 — Sistema em uso roda de um clone separado do código

**Status:** Aceita (aprovada pelo usuário em 06/11/2026, Fase 1D). Complementa o `architecture.md` §11.

**Contexto:** o desenvolvimento acontece em `%USERPROFILE%\Documents\Programa Financeiro`. Se o serviço rodasse dessa mesma pasta, cada mudança no código chegaria ao sistema em uso sem backup nem testes. O `update.ps1` também não teria de onde baixar a nova versão nem como voltar atrás com segurança.

**Decisão:**
- O sistema em uso roda de um clone, por exemplo `%USERPROFILE%\Financas`, cuja origem Git é a pasta de desenvolvimento.
- O `update.ps1` faz `git pull --ff-only` dessa origem. Em falha, volta o clone para a versão anterior (`git reset --hard`), o que não afeta o histórico da pasta de desenvolvimento.
- O `install.ps1` avisa quando é rodado numa pasta sem origem Git.
- Uma cópia do código (`git bundle`) vai para a pasta da nuvem depois de cada atualização, para a recuperação de desastre (`ops/guides/recuperacao-de-desastre.md` §6).

**Consequências:** duas pastas no PC. O banco real fica em `var\` do clone, longe dos testes do desenvolvimento.

## ADR-039 — Compromisso é alterado por cancelamento e recriação; pagamento não se corrige

**Status:** Aceita (aprovada pelo usuário em 08/11/2026, Fase 2A). Complementa a ADR-032.

**Contexto:** as pernas de uma transação são imutáveis em qualquer estado, inclusive previsto e pendente. O compromisso guarda o valor planejado, e o "Corrigir" cria uma transação nova que não sabe de liquidações.

**Decisão:**
- Trocar valor, categoria ou conta de um compromisso cancela o atual, com motivo, e cria outro. Vale para "informar valor real" (RN-052) e para alterar recorrências (RN-053).
- Compromisso com pagamento não muda de valor nem é cancelado: é encerrado (RN-036, RN-042).
- "Corrigir" é recusado em transação que liquida um compromisso. O usuário estorna (a conta reabre, RN-044) e paga de novo.

**Alternativas:**
- Liberar a edição de pernas de previstos: abriria uma exceção na regra mais importante do Ledger, inclusive nos gatilhos.
- Fazer o "Corrigir" mover a liquidação para a transação nova: cobre o caso comum, mas traz regras novas para pagamento parcial e juros.

**Consequências:** o histórico guarda cada valor planejado, com motivo. As listas precisam ocultar os compromissos cancelados.

## ADR-040 — Estudo de design e UI/UX antes das próximas telas (Fase 2B)

**Status:** Aceita (decisão do usuário em 08/11/2026). Complementa o `ui-ux-specification.md`, que continua valendo até o estudo ser aprovado.

**Contexto:** a Fase 6 entrega a tela principal do sistema, e o usuário quer acrescentar itens novos e melhorar o que já existe. As Fases 2B a 5 criam muitas telas antes disso; se seguissem o visual atual, precisariam ser refeitas.

**Decisão:**
- A Fase 2B só começa depois de um estudo completo de design e UI/UX, aprovado pelo usuário. A Fase 6 aplica o estudo ao dashboard.
- O sistema não pode ter "cara de IA": isso vale para cores, fontes, composição e demais escolhas visuais.
- O dashboard não pode ser genérico: precisa ser robusto e, ao mesmo tempo, simplificado.
- O resultado precisa ter personalidade, aparência de software profissional e excelente usabilidade. Um dashboard apenas bonito não atende.
- O estudo define o que muda em `ui-ux-specification.md` e cobre, obrigatoriamente:
  1. pesquisa de referências e benchmarking de produtos financeiros;
  2. arquitetura da informação e organização dos módulos;
  3. fluxos de navegação e experiência do usuário;
  4. design system: cores, tipografia, espaçamento, ícones e componentes;
  5. dashboard: visualização densa de informações sem perder simplicidade;
  6. telas existentes e telas novas;
  7. responsividade para desktop, tablet e celular;
  8. acessibilidade, consistência e usabilidade;
  9. protótipos ou referências visuais para aprovação.

**Consequências:** mudanças no `ui-ux-specification.md` entram por seção de alterações após a aprovação do estudo. O escopo exato dos itens novos sai do estudo, com o usuário.

## ADR-041 — "Pode gastar" como número principal, descontando o mínimo de segurança

**Status:** Aceita (decisão do usuário em 08/11/2026). Complementa a ADR-006.

**Contexto:** a tela inicial deve responder primeiro quanto o usuário pode gastar até receber de novo, considerando o saldo mínimo de segurança. A RN-145 define o disponível sem esse desconto, e o cenário S14 e os testes dependem dela.

**Decisão:** a RN-145 não muda. Entra um indicador derivado, "Pode gastar" = disponível − saldo mínimo − contas previstas (estimadas) que vencem antes do salário (RN-154), que é o número principal. O disponível aparece na explicação do cálculo. As estimativas são descontadas por prudência e continuam com a etiqueta.

**Alternativa:** redefinir o disponível. Quebraria a regra aprovada, os cenários e os testes, sem ganho.

**Consequências:** a Fase 2B implementa o indicador e seus estados. Quando o resultado ficar abaixo do mínimo ou o dinheiro não cobrir as contas, a tela não mostra um número negativo grande, e sim a situação em frase ("Abaixo do mínimo em R$ X", "Faltam R$ X até o salário").
