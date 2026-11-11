# Especificação de Interface e Experiência — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.4 |
| Data | 06/11/2026 |
| Etapa | 4 — Especificação (Fase B) |
| Status | Versão 0.1 aprovada em 06/11/2026 (Fase B); versão 0.2 substitui a identidade visual pelo estudo de design aprovado em 09/11/2026 (§18) |
| Documentos relacionados | `functional-specification.md` (F-xxx), `architecture.md` §4.4 (htmx, Alpine.js, Tailwind, ECharts) |

---

## 1. Princípios de experiência

1. **O que exige atenção vem primeiro.** O topo do dashboard é sempre "saldo disponível" e "atenção".
2. **Real × projetado é visível sem ler.** Projeções e estimativas têm cor, estilo e rótulo próprios (§4).
3. **Lançar é mais rápido que esquecer.** O botão "+" está em toda tela; o lançamento rápido salva em até 4 toques para o caso comum.
4. **Todo número abre sua origem.** Valores clicáveis têm sublinhado pontilhado discreto e levam ao "de onde vem" (F-071).
5. **Pouco por tela.** No máximo 5 indicadores no topo; detalhes em telas de segundo nível.
6. **Linguagem comum.** Nunca "débito/crédito" ou "perna". Sempre "gasto", "recebimento", "pagamento", "transferência", "estorno".
7. **Erros evitados antes de acontecer.** Pré-visualização do efeito antes de ações que alteram faturas, dívidas ou conciliações.

## 2. Identidade visual

**Conceito:** "clareza calma". Visual de aplicação financeira moderna e de painel SaaS: superfícies claras, muito espaço, uma cor de marca sóbria, cores de estado só onde há significado.

**Nome provisório na interface:** "Finanças" (o usuário pode trocar).

**Ícone do aplicativo (PWA):** monograma geométrico simples na cor primária. Ícones de interface: Lucide, traço de 1,75 px.

## 3. Paleta de cores

Cores definidas como variáveis (tokens) em CSS, com versão clara e escura. Contraste mínimo WCAG AA: 4,5:1 para texto e 3:1 para elementos gráficos.

| Token | Uso | Claro | Escuro |
|---|---|---|---|
| `--bg` | Fundo da página | `#F7F8FA` | `#0E1116` |
| `--surface` | Cartões, painéis | `#FFFFFF` | `#161A21` |
| `--surface-2` | Faixas, linhas alternadas, campos | `#F1F3F6` | `#1D222B` |
| `--border` | Bordas, divisórias | `#E3E6EB` | `#2A303B` |
| `--text` | Texto principal | `#14181F` | `#E8EBF0` |
| `--text-2` | Texto secundário | `#4A5260` | `#A9B1BD` |
| `--text-3` | Rótulos, legendas | `#6B7380` | `#808A97` |
| `--primary` | Marca, botões principais, foco | `#0F766E` | `#2DD4BF` |
| `--primary-hover` | | `#115E59` | `#5EEAD4` |
| `--primary-soft` | Fundo de destaque | `#E6F4F2` | `#123B37` |
| `--positive` | Entradas, sucesso | `#15803D` | `#4ADE80` |
| `--negative` | Saídas, erro, atraso | `#B42318` | `#F87171` |
| `--negative-soft` | Fundo de alerta crítico | `#FDECEA` | `#3A1715` |
| `--warning` | Vence logo, atenção | `#B45309` | `#FBBF24` |
| `--warning-soft` | Fundo de atenção | `#FEF3E2` | `#3A2A0E` |
| `--info` | Informação, links | `#1D4ED8` | `#60A5FA` |
| `--projection` | Projeções e estimativas | `#6D5BD0` | `#A78BFA` |
| `--projection-soft` | Fundo de projeção | `#EFEBFB` | `#241E3D` |

**Regras de uso**
- Verde e vermelho só para direção do dinheiro e estado (entrada, saída, atraso). Nunca decoração.
- Valores negativos: sinal "−" explícito **e** cor. Cor nunca é o único indicador (RNF-07).
- Violeta é exclusivo de projeção e estimativa.

**Paleta de categorias** (gráficos), 8 tons distinguíveis nos dois temas, atribuídos às categorias na ordem de uso:

| Claro | Escuro |
|---|---|
| `#0F766E` | `#2DD4BF` |
| `#2563EB` | `#60A5FA` |
| `#D97706` | `#FBBF24` |
| `#DB2777` | `#F472B6` |
| `#7C3AED` | `#A78BFA` |
| `#059669` | `#34D399` |
| `#DC2626` | `#F87171` |
| `#64748B` | `#94A3B8` |

Acima de 8 categorias, as menores somam "Outras".

## 4. Real, projetado e estimado

| Tipo de valor | Estilo | Rótulo |
|---|---|---|
| Real (saldo, transação confirmada) | `--text`, peso normal | Nenhum |
| Projetado (saldo projetado, comprometimento) | `--projection`, prefixo "≈" | Etiqueta "Projeção" em `--projection-soft` |
| Estimado (cartão antes do MVP-3, simulações de dívida, conta variável) | `--projection`, itálico | Etiqueta "Estimativa" |
| Previsto ou pendente em listas | Texto em `--text-2`, ícone de relógio | Status (Previsto, Pendente, Agendado) |
| Cancelado ou estornado (quando exibido) | Tachado, `--text-3` | Status |

Nos gráficos: real em linha contínua ou barra cheia; projeção em linha tracejada ou barra hachurada, na cor `--projection`.

## 5. Tipografia

- **Fonte:** Inter (servida localmente), com `font-variant-numeric: tabular-nums` em todos os valores, para alinhar colunas.
- **Escala:**

| Token | Tamanho / altura de linha | Peso | Uso |
|---|---|---|---|
| `display` | 32 / 40 | 600 | Valor principal do dashboard |
| `h1` | 24 / 32 | 600 | Título de tela |
| `h2` | 20 / 28 | 600 | Título de seção |
| `h3` | 16 / 24 | 600 | Título de cartão |
| `body` | 16 / 24 | 400 | Texto (16 px no celular, evita zoom nos campos) |
| `small` | 14 / 20 | 400 | Tabelas, detalhes |
| `caption` | 12 / 16 | 500 | Rótulos, etiquetas |

- **Valores monetários:** "R$" em tamanho 70% e peso normal; centavos no mesmo tamanho (sem truque visual).

## 6. Espaçamento, forma e elevação

| Item | Regra |
|---|---|
| Unidade de espaçamento | 4 px; usar 4, 8, 12, 16, 24, 32, 48 |
| Raio | 8 px (campos, botões), 12 px (cartões), 999 px (etiquetas) |
| Elevação | Sombra única e suave em cartões no tema claro; no escuro, borda em vez de sombra |
| Alvos de toque | Mínimo 44 × 44 px |
| Largura máxima de conteúdo | 1.280 px no computador |

## 7. Formatação pt-BR

| Dado | Formato | Exemplo |
|---|---|---|
| Moeda | `R$ 1.234,56`; negativo `−R$ 1.234,56` | R$ 3.439,40 |
| Data | `dd/mm/aaaa`; em listas `dd/mm` + dia da semana abreviado | 07/12 (seg) |
| Mês | `nov/2026`, `novembro de 2026` | |
| Percentual | Uma casa decimal | 83,5% |
| Parcela | `k/n` | 1/6 |
| Entrada de valor | Digitação em centavos, da direita para a esquerda | `4590` → R$ 45,90 |

## 8. Navegação

### 8.1 Computador (≥ 1.024 px)

Barra lateral fixa à esquerda (recolhível):
- Início
- Movimentações
- Pagamentos
- Cartões
- A receber
- Dívidas
- Contas
- Planejamento
- Relatórios

Separada no rodapé da barra: Configurações.

Topo: título da tela, busca global (transações, pessoas, contas), botão "+ Lançar" e indicador de saúde (ponto verde, amarelo ou vermelho: backup, invariantes).

### 8.2 Tablet (640–1.023 px)

Barra lateral só com ícones; o resto igual ao computador.

### 8.3 Celular (< 640 px)

Barra inferior com 5 posições:

| Início | Movimentações | **+** (botão central destacado) | Pagamentos | Mais |
|---|---|---|---|---|

"Mais" abre a lista com Cartões, A receber, Dívidas, Contas, Planejamento, Relatórios e Configurações.

Instalável como aplicativo (PWA), em tela cheia, com ícone na tela inicial.

## 9. Componentes

| Componente | Descrição |
|---|---|
| Cartão de indicador | Rótulo (`caption`), valor (`display` ou `h2`), variação ou complemento, etiqueta opcional (Projeção, Estimativa); clicável |
| Item de atenção | Ícone de gravidade, texto curto, valor, ação direta (Pagar, Ver, Conferir) |
| Linha de movimentação | Ícone da categoria, descrição, conta ou cartão, data; valor à direita com sinal e cor; status quando não confirmado |
| Tabela | Cabeçalho fixo, números alinhados à direita, linhas de 48 px, ordenação por coluna; no celular vira lista de cartões |
| Campo de valor | Teclado numérico, máscara de centavos, "R$" fixo |
| Seletor de conta ou cartão | Lista com saldo ou limite disponível ao lado |
| Seletor de categoria | Grade de atalhos (6 mais usadas) + busca |
| Etiqueta de status | Previsto, Pendente, Agendado, Atrasado, Pago parcialmente, Pago, Cancelado; cor + texto + ícone |
| Barra de progresso | Metas, parcelas pagas, comprometimento (segmentada) |
| Linha do tempo de faturas | Faturas em fichas horizontais roláveis, a atual centralizada |
| Pré-visualização de efeito | Caixa "O que vai acontecer" antes de confirmar estornos, amortizações, conciliações |
| Aviso (toast) | Rodapé no celular, canto no computador; 5 s; "Desfazer" quando aplicável |
| Diálogo de confirmação | Só para ações com efeito grande; verbo no botão ("Estornar compra"), nunca só "OK" |
| Estado vazio | Ilustração mínima, uma frase e uma ação ("Cadastre seu primeiro cartão") |
| Carregamento | Esqueleto (blocos cinza) no lugar do conteúdo; nunca tela branca |
| Etiqueta de projeção | Fundo `--projection-soft`, texto `--projection`, "Projeção" ou "Estimativa" |

## 10. Telas principais (esboços)

### 10.1 Início — celular

```
┌──────────────────────────────┐
│ Finanças            ● saúde  │
├──────────────────────────────┤
│ Disponível até 07/12         │
│ R$ 1.859,40                  │  ← display, clicável
│ Bancário R$ 4.439,40 · Guar- │
│ dado R$ 1.000,00 · VR R$ 375 │
├──────────────────────────────┤
│ ATENÇÃO (2)                  │
│ ⚠ Consórcio R$ 650,00        │
│   vence 23/11       [Pagar]  │
│ ⚠ Conciliar Digital (15 d)   │
│                   [Conferir] │
├──────────────────────────────┤
│ PRÓXIMOS ATÉ 07/12  R$1.580  │
│ 23/11 Consórcio    R$ 650,00 │
│ 05/12 Fatura Cartão A R$930  │
├──────────────────────────────┤
│ NOVEMBRO                     │
│ Entradas  R$ 5.000,00        │
│ Saídas    R$ 2.830,00        │
│ ≈ Fim do mês R$ 2.609,40 [P] │
├──────────────────────────────┤
│ Início  Mov.  (+)  Pag.  Mais│
└──────────────────────────────┘
```

### 10.2 Lançamento rápido — celular

```
┌──────────────────────────────┐
│ ✕  Novo gasto                │
│ [Gasto] Recebimento  Transf. │
│                              │
│          R$ 45,90            │
│                              │
│ Forma   [Cartão A ▾] 1x ▾    │
│ Categ.  🛒 🍽 🚗 💊 🏠 ⋯       │
│ Data    Hoje · Ontem · 📅    │
│ Descr.  (opcional)           │
│ + Dividir com alguém         │
│                              │
│ [ 1 ][ 2 ][ 3 ]              │
│ [ 4 ][ 5 ][ 6 ]              │
│ [ 7 ][ 8 ][ 9 ]              │
│ [ ⌫ ][ 0 ][  Salvar  ]       │
└──────────────────────────────┘
```

Caminho mais curto: abrir "+" → digitar valor → tocar categoria → Salvar. A forma e a data vêm preenchidas.

### 10.3 Fatura — computador

```
Cartão A   Limite R$ 5.000,00 · Usado R$ 2.390,00 · Disponível R$ 2.610,00 [Conferir limite]
◀ 05/11 Paga │ 05/12 Aberta R$ 930,00 │ 05/01 Futura R$ 340,00 │ 05/02 ... ▶
───────────────────────────────────────────────────────────────────────────
Fatura 05/12 · fecha 25/11 · vence 05/12 (sáb) → pague até 07/12
Data   Descrição              Parcela  Pessoa   Valor
25/10+ Compras da abertura      —        —      R$ 340,00
15/06  TV                      6/10      —      R$ 240,00
10/11  Notebook                1/6       —      R$ 100,00
14/11  Jantar                   —      Ana 150  R$ 250,00
───────────────────────────────────────────────────────────────────────────
Total R$ 930,00 · sua parte R$ 780,00 · a receber R$ 150,00    [Pagar fatura]
```

### 10.4 Simulador de dívida — computador

Tabela comparativa de três colunas (F-062), com a coluna "Reduzir prazo" destacada como padrão, a etiqueta "Estimativa" e o aviso RN-115 abaixo. Gráfico de saldo devedor ao longo do tempo: atual contínuo, simulado tracejado.

## 11. Gráficos (ECharts)

| Gráfico | Tipo | Observação |
|---|---|---|
| Receitas × despesas | Barras agrupadas por mês, 6 meses | Mês atual com barra de projeção hachurada até o fim do mês |
| Gastos por categoria | Rosca com até 8 fatias + lista ao lado | Alternador visão por compra ou por parcela |
| Evolução do patrimônio | Linha | Ativos − passivos ao fim de cada mês |
| Evolução das dívidas | Área | Por dívida, empilhada |
| Evolução das economias | Linha | Total guardado |
| Projeção diária | Linha tracejada | Faixa do saldo mínimo de segurança em `--negative-soft` |
| Comprometimento 12 meses | Barras empilhadas | Linha de renda prevista |
| Calendário de vencimentos | Mapa de calor mensal | Intensidade pelo valor a pagar no dia |

Regras:
- Eixos com valores formatados em R$ abreviados (R$ 1,2 mil).
- Tooltip com valor exato.
- Legenda clicável.
- Sem 3D, sem animações longas (máximo 300 ms).
- Respeitar a preferência "reduzir movimento" do sistema.

## 12. Formulários

- Um campo por linha no celular; dois por linha no computador quando relacionados (ex.: fechamento e vencimento).
- Rótulo sempre visível acima do campo (nunca só placeholder).
- Validação ao sair do campo e ao enviar. Mensagem abaixo do campo, em `--negative`, com o que fazer: "Informe um valor maior que zero."
- Botão principal à direita no computador e em largura total no celular. O botão fica desabilitado durante o envio, para evitar duplo toque. A idempotência (RN-170) protege mesmo assim.
- Campos avançados recolhidos em "Mais opções".

## 13. Feedback e estados

| Situação | Feedback |
|---|---|
| Salvar | Toast com resumo e "Desfazer" (10 s nos lançamentos rápidos) |
| Ação longa (backup, restauração, migração) | Barra de progresso com etapas nomeadas |
| Erro de servidor | Mensagem clara e o dado digitado preservado |
| Sem conexão (fora do Tailscale) | Tela "Sem conexão com seu computador. Verifique se o Tailscale está ativo e o PC ligado." |
| Edição concorrente | Aviso e recarga (RN-172) |
| Sessão expirada | Tela de PIN (aparelho confiável) ou senha; o rascunho do formulário é mantido no navegador |

## 14. Acessibilidade

- Contraste AA nos dois temas (tokens da §3).
- Foco visível em todos os elementos (`--primary`, anel de 2 px).
- Navegação completa por teclado no computador; atalhos:
  - `N`: novo lançamento;
  - `/`: busca;
  - `G` seguido de `I`: Início;
  - `G` seguido de `P`: Pagamentos.
- Texto alternativo nos gráficos: resumo em texto ("Despesas de novembro: R$ 2.830,00; maior categoria Moradia, 53%").
- Tamanho de texto respeita a configuração do sistema até 200% sem quebrar o layout.
- Estados nunca só por cor (§3).

## 15. Responsividade

| Faixa | Layout |
|---|---|
| < 640 px | Uma coluna; barra inferior; tabelas viram listas; gráficos em largura total |
| 640–1.023 px | Duas colunas no dashboard; barra lateral com ícones |
| ≥ 1.024 px | Grade de 12 colunas; dashboard em 3 colunas; barra lateral completa |

## 16. Tema claro e escuro

- Padrão "automático" (segue o sistema); escolha manual em Configurações (RF-CFG-04).
- Troca sem recarregar a página.
- Gráficos usam tema ECharts derivado dos mesmos tokens.

## 17. Textos da interface

- Tom: direto, tranquilo, sem jargão nem culpa ("Conta atrasada" em vez de "Você esqueceu de pagar").
- Verbos nos botões: Salvar, Pagar, Recebi, Estornar compra, Corrigir, Conferir limite.
- Datas relativas quando ajudam: "vence amanhã", "venceu há 2 dias", sempre com a data absoluta ao lado.
- Toda projeção e estimativa diz em que se baseia (RN-153).

## 18. Alterações após a aprovação

O `design-study.md` (ADR-040, aprovado em 09/11/2026) substitui os trechos abaixo. Onde houver diferença, vale o estudo.

| Seção | Alteração |
|---|---|
| §1, princípios 1 e 5 | O topo da tela inicial é "Pode gastar" (RN-154, ADR-041). Poucos números à vista; o detalhe fica a um toque |
| §2, §3, §5, §6 | Identidade "clareza calma", Inter e `#0F766E` dão lugar à direção "Caderno técnico": família IBM Plex, papel frio, cobalto só para ação, cores com função financeira, réguas no lugar de cartões, sem sombra e sem degradê |
| §2 | Lucide dá lugar a um conjunto próprio de ícones de traço reto |
| §4 | Mantido: real, projetado e estimado com cor, estilo e rótulo próprios. Hachura e etiqueta passam a ser a marca de previsão |
| §8 | Navegação reorganizada: Início, Pagamentos e Movimentações; Cartões, Dívidas, A receber e Contas; Ajustes reúne Categorias, Segurança, Backup, Saúde e Aparência. No celular, Lançar fica na barra, sem botão flutuante |
| §10, §11 | Esboços e regras de gráficos substituídos pelos quadros e pela seção 12 do estudo |
| §15, §16 | Regras de largura e tema das seções 12, 15 e 16 do estudo |
| §8 | Ajustes ganha Dinheiro, Feriados e Avisos. Recorrências e Calendário ficam dentro de Pagamentos. Tablet com navegação no topo | Fase 2B; ADR-042 |
| §9, §12 | Blocos com canto de 14 px e sombra leve; menu lateral em bloco com ícones; cartão de crédito desenhado com cor e logotipo do banco; ícones com volume em SVG no Início, em Pagamentos e em Cartões. Quadros "Proposta 2" no canvas do estudo | ADR-043 |
