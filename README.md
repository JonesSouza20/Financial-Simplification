# Financial Simplification

Sistema de gestão financeira pessoal, para uma pessoa, rodando num PC com Windows e acessado
pelo celular através de uma rede privada (Tailscale). Responde primeiro a uma pergunta:
**quanto posso gastar até receber de novo?**

O projeto foi planejado e documentado antes de qualquer código e é construído fase a fase.
Cada fase termina com testes, relatório e aprovação, e cada entrega passa por uma porta de
validação com uso real antes da próxima.

## Sumário

- [Princípios](#princípios)
- [O que o sistema faz](#o-que-o-sistema-faz)
- [Tecnologia](#tecnologia)
- [Fases do projeto](#fases-do-projeto)
- [Como rodar](#como-rodar)
- [Instalação no PC (uso real)](#instalação-no-pc-uso-real)
- [Testes](#testes)
- [Segurança e backup](#segurança-e-backup)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Documentação](#documentação)
- [Branches](#branches)
- [Licença](#licença)

## Princípios

- **Livro-razão em partidas dobradas é a fonte única da verdade.** Saldos, disponível,
  comprometido, faturas e relatórios são calculados a partir dele; nenhum módulo guarda saldo
  próprio.
- **Nada é apagado.** Lançamento confirmado é corrigido por estorno vinculado e novo lançamento;
  previsto e pendente são cancelados com motivo. Tudo fica na auditoria.
- **Dinheiro em centavos inteiros.** Um teste impede `float` nos módulos financeiros.
- **Previsto nunca afeta saldo real.** Estimativas aparecem marcadas como estimativa.
- **Todo número é rastreável.** "De onde vem" e "Como calculamos" levam até as movimentações.
- **Integridade no banco.** Gatilhos do SQLite garantem pernas que somam zero, imutabilidade e
  idempotência; invariantes são conferidas em testes, backups e atualizações.

## O que o sistema faz

**Dia a dia**

- **Pode gastar até o salário**: dinheiro das contas livres menos o que já tem dono (faturas,
  contas pendentes), as estimativas e o mínimo de segurança. Mostra a situação em frase quando
  fica abaixo do mínimo ou quando o dinheiro não cobre as contas.
- Barra do dinheiro, linha do tempo até o salário, contas até o salário, dívidas e para onde
  foi o dinheiro no mês.
- Lançamento rápido no celular, com teclado próprio e categorias mais usadas primeiro.
- Movimentações agrupadas por dia, com filtros, Corrigir, Estornar e Desfazer.

**Pagamentos**

- Contas a pagar e receitas previstas, à vista ou parceladas.
- Central de pagamentos agrupada por quando agir: atrasados, esta semana, até o salário e
  depois do salário.
- Pagar com um toque, pagar parte, pagar com juros e multa, encerrar com valor menor,
  agendar débito e desfazer por 2 minutos.
- Recorrências com prévia das datas antes de salvar; salário no 5º dia útil.
- Calendário de dias úteis com feriados nacionais e da cidade de São Paulo, editáveis.
- Cada ação diz, em uma frase, o efeito no que dá para gastar.

**Cartões, dívidas e valores a receber**

- Cartões com compras parceladas, partes de outras pessoas e faturas estimadas.
- Cartão desenhado na tela, com o banco e a cor escolhidos no cadastro.
- Empréstimos a terceiros, dívida e consórcio (registro provisório até as fases 4 e 5).
- Conciliação de saldo com o extrato do banco.

**Operação**

- Backup diário criptografado e verificado, local e numa pasta de nuvem, com histórico.
- Teste automático de restauração todo mês e restauração em dois passos.
- Tela de saúde: backups, integridade, disco, criptografia e exposição na internet.
- Avisos no Telegram: vencimentos, atrasos, falhas de backup e eventos de segurança, com
  silêncio noturno e sem repetição.

## Tecnologia

| Parte | Escolha |
|---|---|
| Linguagem | Python 3.13, dependências travadas com uv |
| Aplicação | Django 5.2 LTS, templates no servidor, htmx e Alpine.js (versão CSP) |
| Banco | SQLite em modo WAL, transações `IMMEDIATE`, gatilhos de integridade |
| Servidor | Waitress, arquivos estáticos com WhiteNoise, só em `127.0.0.1` |
| Acesso remoto | Tailscale Serve com HTTPS, sem exposição na internet |
| Interface | Tailwind CSS 4 (CSS gerado e versionado), fontes IBM Plex servidas localmente |
| Segurança | Argon2id, PIN por aparelho confiável, django-axes, CSP sem script ou estilo inline |
| Segredos | Cofre de Credenciais do Windows (keyring); backup cifrado com age (pyrage) |
| Testes | pytest, Hypothesis, time-machine, Playwright, coverage, ruff, pip-audit |

## Fases do projeto

O planejamento completo está em [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md).
As decisões ficam em [`docs/decisions.md`](docs/decisions.md) (ADR-001 a ADR-043).

### Planejamento (Etapas 1 a 8)

Descoberta com cerca de 30 perguntas; 111 requisitos e glossário; arquitetura com alternativas
comparadas; 130 regras de negócio; 15 cenários de referência calculados ao centavo; telas,
banco de dados, segurança, testes e roadmap. Revisão cruzada dos documentos e aprovação para
iniciar o desenvolvimento.

### Fase 0 — Fundação técnica

Projeto Django com Python 3.13 via uv, SQLite em WAL, localização pt-BR, hash Argon2id,
configurações separadas por ambiente e a trava contra `float` nos módulos financeiros.

### Fase 1A — Núcleo do Ledger

Transações em partidas dobradas com pernas que somam zero, estados (rascunho, previsto,
pendente, confirmado, cancelado, estornado), estorno técnico, comercial e parcial, Corrigir em
uma operação atômica, idempotência, auditoria e gatilhos no banco. Sem interface.
Testes de propriedade com 1.000 exemplos por regra.

### Fase 1B — Cadastros, lançamentos e segurança

Login com senha forte e PIN em aparelho confiável, bloqueio de tentativas, expiração de
sessão, contas e carteiras (inclusive vale-refeição), categorias editáveis, lançamento rápido
no celular, movimentações com Corrigir e Estornar, temas claro e escuro.

### Fase 1C — Cartões, valores a receber e dívida provisórios

Assistente de abertura do mês inicial, compras no cartão com parcelas e partes de terceiros,
faturas estimadas, empréstimos a terceiros, dívida e consórcio, conciliação de saldo e
"de onde vem" em cada saldo.

### Fase 1D — Operação e backup

Backup criptografado e verificado (local e nuvem) com retenção, restauração em dois passos,
teste mensal automático, agendador que recupera tarefas atrasadas, tela de saúde, scripts de
instalação, atualização com volta atrás, restauração e redefinição de senha, e guias de
Tailscale, criptografia do disco e recuperação de desastre.

### Porta MVP-1 — uso real

Instalação no PC, acesso pelo iPhone pela tailnet, PIN, backup na nuvem e teste manual de
restauração concluídos. Em andamento: abertura com todos os dados reais e duas semanas de uso
conferindo os saldos com os bancos.

### Fase 2A — Compromissos, recorrências e calendário

Calendário de dias úteis com feriados de 2026 a 2040, contas a pagar e receitas previstas,
liquidação por transação nova, pagamento parcial, juros e multa em perna própria, encerrar,
cancelar, agendar, recorrências em janela móvel de 13 meses, salário no 5º dia útil,
consórcio como compromisso fixo e reembolso.

### Fase 2B — Central de pagamentos, Pode gastar e avisos

- Comprometido, disponível e **Pode gastar** com quatro estados.
- Início, Pagamentos, Calendário, Recorrências e Ajustes (dinheiro, feriados e avisos).
- Pagar com valor cheio, parcial, juros, excedente classificado, encerrar e desfazer.
- Avisos no Telegram em fila, com nova tentativa, validade de 24 horas, silêncio noturno e
  token guardado no cofre do Windows, limpo de toda mensagem de erro.
- Novo visual, a partir de um estudo de design aprovado: IBM Plex, cor que representa estado
  e não sinal, previsão hachurada com etiqueta, blocos, carteira, cartões desenhados com banco
  e cor, e ícones com volume desenhados em SVG para o projeto.

Fica fora do sistema em uso até a Porta MVP-1 terminar.

### Próximas fases

| Fase | Conteúdo |
|---|---|
| Porta MVP-2 | Um ciclo de salário completo com datas e avisos corretos |
| 3A e 3B | Faturas reais, pagamento parcial de fatura, estornos e conciliação de fatura e limite |
| 4 | Valores a receber completos: parcelas, recebimentos parciais, atrasados e baixa |
| 5 | Dívidas: tabela Price, amortização extra e simulador de quitação |
| 6 | Dashboard completo, projeção de 30 dias e comprometimento de 12 meses |
| Pós-MVP | Metas e reserva, relatórios e exportação, orçamento, importação OFX/CSV |

## Como rodar

Requisitos: Windows 11 e [uv](https://docs.astral.sh/uv/), que instala o Python 3.13 e as
dependências travadas em `uv.lock`.

```bash
uv sync
```

```bash
uv run python manage.py migrate
```

```bash
uv run python manage.py runserver 127.0.0.1:8001
```

Abra `http://127.0.0.1:8001/` e crie a senha. As categorias e os feriados são carregados pelo
`migrate`. Depois use o assistente de abertura (`/abertura/contas/`).

O banco e os arquivos de dados ficam em `var/`, fora do Git. A pasta pode ser trocada pela
variável de ambiente `FINANCAS_DATA_DIR`.

Logotipos dos bancos (opcional). São marcas registradas e não fazem parte do repositório.
Sem eles, o cartão aparece só com a cor:

```bash
uv run python ops/logos_bancos.py
```

Gerar o CSS depois de mudar templates ou `tailwind/input.css` (o arquivo gerado fica no Git):

```bash
TAILWINDCSS_VERSION=v4.1.7 uv run tailwindcss -i tailwind/input.css -o static/css/app.css --minify
```

## Instalação no PC (uso real)

O sistema em uso roda de um clone separado da pasta de desenvolvimento (ADR-038), com início
automático ao entrar no Windows. Passo a passo em
[`ops/guides/servico-windows.md`](ops/guides/servico-windows.md):

```powershell
git clone "$env:USERPROFILE\Documents\Programa Financeiro" "$env:USERPROFILE\Financas"
```

```powershell
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Mode logon
```

Outros scripts: `ops\update.ps1` (atualizar com backup e volta atrás), `ops\restore.ps1`
(restaurar ou `-Test`) e `ops\reset-password.ps1` (senha esquecida).

Guias: [Tailscale Serve e HTTPS](ops/guides/tailscale-https.md),
[criptografia do disco](ops/guides/criptografia-do-disco.md),
[recuperação de desastre](ops/guides/recuperacao-de-desastre.md) e
[avisos no Telegram](docs/guides/telegram.md).

Comandos de terminal (com `DJANGO_SETTINGS_MODULE=config.settings.prod`, que os scripts já
definem): `backup_now`, `list_backups`, `restore_backup <nome> [--test]`, `check_invariants`,
`init_secrets [--backup-passphrase]`, `reset_password` e `run_jobs`.

## Testes

```bash
uv run pytest
```

```bash
uv run ruff check .
```

Testes de propriedade com 1.000 exemplos:

```bash
HYPOTHESIS_PROFILE=thorough uv run pytest
```

Testes de ponta a ponta no navegador (Chromium do Playwright):

```bash
uv run playwright install chromium
```

```bash
uv run pytest -m e2e
```

Situação atual: 603 testes e mais 10 no navegador, cobertura de 95% das linhas e
ramificações, sem vulnerabilidades conhecidas nas dependências (`pip-audit`). Os cenários de
referência (`docs/reference-scenarios.md`) são testes executáveis em `tests/scenarios`.

## Segurança e backup

- O servidor escuta só em `127.0.0.1`; o acesso pelo celular passa pelo Tailscale Serve com
  HTTPS. O Funnel (exposição na internet) fica desligado e é conferido na tela de saúde.
- Senha forte com Argon2id; PIN só desbloqueia um aparelho já confiável; operações sensíveis
  sempre pedem a senha.
- Segredos (chave da aplicação, senha de backup, token do Telegram) ficam no Cofre de
  Credenciais do Windows, nunca no banco, no código ou em logs.
- Backups são cifrados antes de sair do processo, verificados por checksum, integridade do banco
  e invariantes do Ledger, e testados por restauração todo mês.
- Detalhes em [`docs/security-plan.md`](docs/security-plan.md).

## Estrutura do repositório

```
apps/            módulos Django (ledger, accounts, entries, cards, payables, balances,
                 notifications, backup, security, ui e outros)
config/          configurações por ambiente e rotas
docs/            requisitos, regras, cenários, arquitetura, banco, segurança, testes,
                 roadmap, decisões e estudo de design
ops/             instalação, atualização, restauração, guias e script dos logotipos
static/          CSS gerado, fontes, ícones e bibliotecas JavaScript
tailwind/        fonte do CSS
templates/       páginas base e componentes compartilhados
tests/           unidade, integração, propriedade, cenários, backup, segurança e ponta a ponta
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [product-requirements.md](docs/product-requirements.md) | Requisitos, glossário e escopo |
| [functional-specification.md](docs/functional-specification.md) | Telas e funcionalidades |
| [business-rules.md](docs/business-rules.md) | Regras de negócio, estados e efeitos de cada movimentação |
| [reference-scenarios.md](docs/reference-scenarios.md) | Cenários com resultados exatos em centavos |
| [architecture.md](docs/architecture.md) | Arquitetura e alternativas avaliadas |
| [database-design.md](docs/database-design.md) | Modelo de dados, gatilhos e invariantes |
| [security-plan.md](docs/security-plan.md) | Segurança, backup, restauração e recuperação |
| [ui-ux-specification.md](docs/ui-ux-specification.md) | Interface e componentes |
| [design-study.md](docs/design-study.md) | Estudo de design e direção visual aprovada |
| [testing-plan.md](docs/testing-plan.md) | Estratégia de testes e metas de cobertura |
| [implementation-roadmap.md](docs/implementation-roadmap.md) | Fases, portas de validação e histórico de alterações |
| [decisions.md](docs/decisions.md) | Registro de decisões (ADR) |

## Branches

| Branch | Conteúdo |
|---|---|
| `main` | Desenvolvimento mais recente, até a Fase 2B |
| `versao-em-uso` | Versão da Fase 1D, a que está em uso durante a Porta MVP-1 |

## Licença

Código sob a licença [MIT](LICENSE). As fontes IBM Plex seguem a SIL Open Font License 1.1
(`static/fonts/LICENSE-IBM-Plex.txt`); htmx e Alpine.js seguem as próprias licenças. Os
logotipos dos bancos não fazem parte do repositório: são marcas registradas dos respectivos
bancos.
