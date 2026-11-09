# Estudo de Design e UI/UX — Parte 1: Direção

| Campo | Valor |
|---|---|
| Versão | 0.3 |
| Data | 08/11/2026 |
| Status | Direção B escolhida e revisão de Início e Pagamentos aceita em 08/11/2026. Parte 2 (seções 10 a 17) em avaliação |
| Decisão | ADR-040: pré-requisito da Fase 2B |
| Protótipos | Canvas da direção B, guardado fora do repositório |

Nenhuma tela do sistema muda antes da aprovação. Mudanças em `ui-ux-specification.md` entram por seção de alterações, depois do estudo aprovado.

## 1. O pedido

- Direção principal: **painel de instrumentos**, com elementos de **livro-caixa moderno**.
- Alta densidade com hierarquia excelente; números em destaque, alinhados e consistentes.
- Tipografia escolhida, sem Inter automático.
- Poucos cartões arredondados: linhas divisórias, tabelas, seções e agrupamentos discretos.
- Paleta neutra e sóbria, com uma ou duas cores de destaque usadas com estratégia.
- Sem gradientes decorativos, excesso de sombras nem elementos flutuantes.
- Primeira pergunta da tela inicial: **quanto posso gastar até receber novamente**, com explicação do cálculo.
- "O que vence agora" e "Minhas dívidas" com destaque, como informação secundária.
- Referência citada: design, fluidez e experiência do site da Apple, mesclados com pontos de apps de banco.

## 2. Pesquisa de referências

Confiabilidade: a maior parte das análises públicas sobre Stripe, Mercury e apps de finanças é de blogs e fornecedores. Só Apple (typography), Bloomberg (acessibilidade e UX) e Nubank (Nu Sans) são fontes primárias. Elas orientam, mas não são prova. Os itens marcados como "medido" foram conferidos direto na página.

| Referência | O que levar | O que não levar |
|---|---|---|
| Apple | Hierarquia por peso, tamanho e cor; o conteúdo em primeiro plano; alinhamento rigoroso; tipografia com tracking negativo em tamanhos grandes (medido: título 80/84 px, peso 600, −1,2 px; texto 14/20 px); movimento discreto | O espaço em branco de página de produto; a fonte SF, que não pode ser distribuída fora dos aparelhos Apple |
| Bloomberg Terminal | Densidade tratada como virtude; alternativas de cor para daltonismo, porque cor sozinha não basta; mudanças visuais graduais | Preto com laranja por toda parte; curva de aprendizado alta |
| Stripe | Tabelas financeiras e números tabulares como padrão | Gradientes de marca |
| Mercury | Tipografia editorial e cor disciplinada; linguagem de software, não de banco | Densidade baixa a média |
| Nubank | Duas versões de fonte: uma para títulos, outra para grande volume de dados como extratos | Marca em cor única saturada, botões em pílula |
| YNAB, Monarch, Copilot | Uma métrica própria e central (YNAB, "Age of Money"); polimento nativo no iPhone (Copilot) | Painéis de cartões com gráficos decorativos |
| Tufte e Few | Tinta a serviço do dado; sparklines, pequenos múltiplos e gráficos de bala; posição e comprimento, nunca medidores | Sparkline sem período ou referência |
| WCAG 2.2 e Apple | Alvo de 24 px no mínimo e, no celular, 44 px (recomendação da Apple); contraste de 4,5:1 | — |

### Conclusão sobre Apple e densidade

Há uma tensão no pedido: o site da Apple é espaçoso, e o painel de instrumentos é denso. A proposta leva da Apple **o acabamento** (hierarquia, alinhamento, contenção, movimento que respeita `prefers-reduced-motion`) e não o espaço em branco.

## 3. O que dá "cara de IA"

Padrões apontados de forma recorrente: Inter, degradê roxo, três cartões arredondados, sombras suaves, cartão com borda colorida de um lado e títulos pequenos em caixa alta sobre tudo. Causa provável: modelos convergem para a média de modelos e bibliotecas populares.

O sistema atual, feito por mim, tem vários desses sinais. Nomeados com evidência:

| Sinal | Evidência |
|---|---|
| Fonte padrão | Inter em tudo |
| Cor de biblioteca | `#0F766E`, o `teal-700` do Tailwind |
| Cartões em tudo | 7 cartões com raio de 12 px na tela Início |
| Ícones padrão | Lucide, o conjunto usado por padrão no shadcn/ui |
| Botão flutuante | "+" circular central no celular |

## 4. Auditoria das telas atuais

Medido com dados fictícios em computador, tablet e celular.

| Tela | Problema | Consequência |
|---|---|---|
| Início | O número principal é o saldo bancário | Não responde "quanto posso gastar" |
| Início | Todo saldo positivo é verde | A cor deixa de significar algo |
| Início, celular | Página de 1.445 px; três cartões empilhados ocupam cerca de 300 px | Contas e movimentações só aparecem depois de rolar muito |
| Lançar, celular | O teclado ocupa a dobra; a categoria fica abaixo; o valor aparece duas vezes | Passos a mais para o uso mais frequente |
| Lançar | 4 de 26 alvos abaixo de 44 px | Toques imprecisos |
| Movimentações | Filtros ocupam cerca de 240 px; linhas de 65 px | Cerca de 9 linhas por tela no computador |
| Movimentações | Categoria repetida no título e na descrição | Ruído |
| Navegação | Segurança e Backup com o mesmo ícone; 5 itens de ajustes na barra principal | Espaço nobre gasto com o que é raro |
| Navegação, celular | "Contas" no lugar de "Pagamentos", previsto na especificação | Pagamentos ficará escondido na Fase 2B |

## 5. As três direções

Todas usam os mesmos dados (cenário S14) e as mesmas telas: Início no computador e no celular, Lançar no celular e a central de pagamentos, que é a tabela densa da Fase 2B.

| | B · Caderno técnico (recomendada) | A · Cockpit | C · Razão |
|---|---|---|---|
| Ideia | Instrumento com alma de livro-caixa | Instrumento levado ao limite | Livro contábil de verdade |
| Base | Papel frio | Grafite | Papel pautado de verde |
| Destaque | Azul de caneta e vermelhão | Âmbar | Vermelho de tinta |
| Número principal | IBM Plex Serif | B612 Mono | Source Serif 4 |
| Interface | IBM Plex Sans e Sans Condensed | Barlow Semi Condensed | Archivo Narrow |
| Valores | IBM Plex Mono | B612 Mono | Archivo, números tabulares |
| Navegação | Coluna lateral só com texto | Coluna lateral só com texto | Abas no topo |
| Ponto forte | Equilibra o que você pediu | Maior personalidade; ótimo no escuro | Identidade mais rara |
| Risco | Mais contida | Cansa em uso longo; pede tema claro bem diferente | Menos "painel", mais "livro" |

**Por que recomendo a B:** é a que cumpre as duas metades do pedido. Uma única família em quatro vozes dá identidade sem parecer modelo pronto. A **linha do salário**, que divide o tempo nas listas, é uma marca própria e explica por que um valor conta ou não no que você pode gastar.

### Verificação das fontes

Conferido no navegador, em cada candidata: largura igual de todos os dígitos e presença de `ã õ ç ê R$ − ·`.

| Resultado | Fontes |
|---|---|
| Aprovadas | IBM Plex Sans, Sans Condensed, Mono e Serif; Archivo; Archivo Narrow; Barlow; Barlow Semi Condensed; B612; B612 Mono; Source Serif 4; Schibsted Grotesk; Public Sans; Hanken Grotesk; Spline Sans Mono; Red Hat Mono; Newsreader; Atkinson Hyperlegible Next; Fira Sans; Fira Sans Condensed; Sometype Mono |
| Reprovadas por dígitos de largura variável | Libre Franklin, Commissioner |

Pendência: (Resolvida na seção 12: a família IBM Plex tem `≈` e `→`.) `≈` e `→` não vieram nos recortes padrão do Google Fonts de nenhuma candidata. O sistema usa `≈` nas projeções, então é preciso conferir no arquivo completo da fonte escolhida, antes de hospedá-la localmente. Licenças abertas também serão confirmadas arquivo a arquivo.

Excluídas de propósito, por já parecerem padrão de IA: Inter, Space Grotesk, DM Sans, Instrument Serif, Fraunces.

### Contraste

Calculado por script, nos fundos principal e de painel. Menor valor entre os textos: 5,04:1 (B), 5,97:1 (A) e 5,45:1 (C). Todos passam de 4,5:1. O tema oposto de cada direção entra na Parte 2.

## 6. Arquitetura proposta (preliminar)

| Grupo | Itens | Entrega |
|---|---|---|
| O dia a dia | Início, Pagamentos, Movimentações | 2B |
| O que devo e tenho | Cartões, Dívidas, A receber, Contas | Já existem |
| Olhar à frente | Planejamento, Relatórios | Pós-MVP |
| Ajustes | Categorias, Segurança, Backup, Saúde, Aparência, feriados, saldos e alertas | 2B |

No celular: Início, Pagar, **Lançar**, Extrato, Mais. O Lançar fica na própria barra, sem botão flutuante.

## 7. Decisões pendentes

1. Qual direção seguir.
2. **Saldo mínimo de segurança no número principal.** Você pediu para considerá-lo, mas a RN-145 aprovada define disponível = contas livres − comprometido, e o mínimo é só um alerta. Os protótipos mostram a proposta: "Pode gastar" = disponível − mínimo, com o disponível visível na conta. O mínimo de R$ 300,00 é fictício e não faz parte do S14. A escolha entra em `business-rules.md` §22.
3. **Reserva.** A RN-145 conta só as contas livres. A reserva e o VR/VA aparecem fora da conta, com o valor visível. O "saldo bancário atual" do seu pedido inclui a reserva pela RN-141, por isso a diferença fica explícita.
4. Quais são as coisas novas que você quer na Fase 6.

Até a Fase 3A, o valor das faturas é estimado (RN-075). Por isso a linha da fatura leva a etiqueta "estimativa".

## 8. Parte 2, depois da escolha

| Item pedido | Parte 1 | Parte 2 |
|---|---|---|
| 1. Referências e benchmarking | Feito | — |
| 2. Arquitetura da informação | Preliminar | Módulos completos |
| 3. Fluxos e navegação | Lançar e Início | Pagar, parcial, agendar, estornar, abertura |
| 4. Design system | Fontes e paletas comparadas | Tokens, espaçamento, ícones, componentes, tema claro e escuro, gráficos, mapeados em CSS e Tailwind v4 |
| 5. Dashboard | Início na versão da 2B | Evolução até a Fase 6; todos os estados do número: salário atrasado, sem salário, negativo, abaixo do mínimo, zero |
| 6. Telas existentes e novas | 4 telas | Todas: calendário, recorrências, ajustes e as demais |
| 7. Responsividade | Computador e celular | Tablet e regras por largura |
| 8. Acessibilidade e consistência | Contraste e alvos | Foco, leitor de tela, movimento, casos extremos |
| 9. Protótipos | 12 telas | Protótipo final para aprovação |

## Fontes

- [Apple HIG, Typography](https://developer.apple.com/design/human-interface-guidelines/typography.md)
- [Bloomberg, Designing the Terminal for color accessibility](https://www.techatbloomberg.com/blog/designing-the-terminal-for-color-accessibility/)
- [Bloomberg, Relaunching Launchpad](https://www.bloomberg.com/ux/2017/11/10/relaunching-launchpad-disguising-ux-revolution-within-evolution/)
- [Nubank, Nu Sans](https://blog.nubank.com.br/nu-sans/)
- [Mercury Design Breakdown](https://www.925studios.co/blog/mercury-design-breakdown)
- [Stripe Redesign 2024 (comunidade)](https://skill-wiki.github.io/atom/frontend-design/feedback-stripe-redesign-2024)
- [Fintech dashboard design examples](https://adminlte.io/blog/fintech-dashboard-design-examples/)
- [YNAB vs Monarch vs Copilot](https://wallethub.com/edu/b/ynab-vs-monarch-vs-copilot-vs-wallethub/150687)
- [Stephen Few, Why Most Dashboards Fail](https://blogs.ischool.berkeley.edu/i247s13/files/2013/02/WhyMostDashboardsFail.pdf)
- [Why Your AI Keeps Building the Same Purple Gradient Website](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website)
- [AI Slop Fonts and Gradients](https://www.925studios.co/blog/ai-slop-design-tells)
- [W3C, What's New in WCAG 2.2](https://w3.org/WAI/standards-guidelines/wcag/new-in-22/)

## 9. Revisão depois da escolha da direção B

Decisões do usuário em 08/11/2026: seguir a direção B; "Pode gastar" como número principal (ADR-041); estudar as cores em relação às finanças, sem as direções A e C; reduzir números e textos em Início e Pagamentos, porque as pessoas não querem uma tela com cara de planilha.

**O pedido não é menos informação, e sim menos números à vista.** A densidade passa a ser visual: a conta vira barra, a lista vira linha do tempo, e o detalhe fica a um toque. Isso ajusta o item "alta densidade de informação" da seção 1.

| Tela | Números à vista antes | Depois |
|---|---|---|
| Início, computador | 46 | 22 |
| Início, celular | 26 | 14 |
| Pagamentos, computador | 32 | 12 |
| Pagamentos, celular | Não existia | 10 |

### O que mudou

- **Início:** o número principal ganha uma única barra do dinheiro: já tem dono, mínimo e livre. A conta completa fica em "Como calculamos". Tabela e gráfico de linha viram uma só linha do tempo até o salário. Dívidas ficam com um total e barras. O gasto do mês vira uma barra com três categorias e Outros. Lista de contas e os 12 meses saem da tela inicial.
- **Pagamentos:** a tabela de seis colunas vira lista agrupada por quando agir (esta semana, até o salário, depois do salário), com uma marca por conta e uma ação por linha. O resumo de quatro números vira uma frase e uma faixa com os próximos 31 dias. "Em aberto" só aparecerá quando a conta estiver paga em parte.
- **Celular:** versões próprias das duas telas.

### Estudo de cores

Evidência: a associação de azul com confiança vem sobretudo de pesquisas de marketing, e o efeito de convenção do setor é forte. O estudo mais robusto encontrado, com 1.995 respondentes em sites de bancos e seguros, indica que **cores sóbrias geram mais confiança do que cores vivas**, e azul mais do que vermelho. Isso sustenta uma paleta contida e o cobalto. Não há pesquisa rigorosa sobre aplicativos de finanças pessoais.

Os bancos brasileiros ocupam roxo, laranja, vermelho e amarelo. Essas cores são evitadas como identidade; os significados delas não foram verificados e não são usados aqui.

| Papel | Pergunta que responde | Preenchimento | Texto |
|---|---|---|---|
| Folga | Posso gastar? | `#2A9D5C` | `#17693F` |
| Atenção | Estou abaixo do mínimo? | `#B07A12` | `#8A5200` |
| Crítico | Atrasou ou ficou negativo? | `#8F1D0B` | `#AE240E` |
| Comprometido | Já tem dono? | `#3A3F45` | — |
| Mínimo de segurança | Está separado? | hachura `#8A8D85` | — |
| Previsão e estimativa | É certeza? | hachura `#4A43A0` | `#4A43A0` |
| Ação | Onde toco? | `#1B3FAB` | `#1B3FAB` |
| Categorias | Para onde foi? | `#2F6F73`, `#8E7CC3`, `#8C5A3C`, cinza sólido `#8A8D85` para Outros | — |

Regras:
- Cor representa **estado**, não sinal. O verde deixa de marcar todo valor positivo. A exceção é a linha do salário, um componente nomeado: ela marca o recebimento que divide o tempo.
- Cobalto só para o que se toca.
- No máximo três categorias com cor, mais Outros, sempre com o nome escrito no gráfico.

Medições por script:

| Verificação | Resultado |
|---|---|
| Textos sobre os fundos | Mínimo de 5,04:1 (alvo 4,5:1) |
| Preenchimentos sobre o painel | Mínimo de 3,22:1 (alvo 3:1) |
| Verde de texto × vermelho, com daltonismo | Diferença baixa (ΔE 8,1 em deuteranopia). Por isso o verde mais claro é usado nos preenchimentos (ΔE 18,4) |
| Folga × atenção, com daltonismo | Baixa (ΔE 7,1 a 8,2). Os estados nunca aparecem lado a lado e sempre têm palavra e ícone |
| Folga × mínimo, com daltonismo | Baixa (ΔE 4,9). O mínimo é hachurado, e o padrão faz a diferença |
| Categorias, entre si e contra os papéis, com daltonismo | Trocadas para não colidir com verde, cobalto e violeta: ΔE mínimo de 8,8 contra os papéis e de 8,2 entre si. O nome fica sempre escrito no gráfico |

O tema escuro entra na Parte 2.

### Pontos a confirmar

Decididos pelo usuário em 08/11/2026:

1. Conta variável estimada que vence antes do salário entra no desconto do "Pode gastar" (RN-154). Nos protótipos, R$ 1.559,40 passou a R$ 1.379,40.
2. "Cerca de R$ 91 por dia" foi retirado.
3. Abaixo do mínimo ou sem cobertura: frase em vez de número negativo grande.

Fontes adicionais: [CFPB, cor em visualização de dados](https://cfpb.github.io/design-manual-archive/data-visualization/color.html); [Hue Got It, 4imprint](https://info.4imprint.co.uk/blue-paper/how-brand-colours-influence-trust-customer-behaviour-market-report).

# Parte 2 — Sistema completo

Protótipos: canvas, guardado fora do repositório, com 18 quadros e dados fictícios do cenário S14.

## 10. Arquitetura da informação

| Grupo | Itens | Entrega |
|---|---|---|
| O dia a dia | Início, Pagamentos (com Calendário e Recorrências), Movimentações | 2B |
| O que devo e tenho | Cartões, Dívidas, A receber, Contas | Existem; ganham o novo visual |
| Olhar à frente | Planejamento, Relatórios | Pós-MVP. Entram nesse grupo, sem reorganizar o resto |
| Ajustes | Dinheiro (mínimo, horizonte, categorias, recorrências, feriados), Avisos, Sistema (segurança, backup, saúde, aparência) | 2B |

Mudanças em relação à navegação atual: Categorias, Segurança, Backup, Saúde e Aparência saem da barra principal e vão para Ajustes. Pagamentos entra na barra do celular.

## 11. Fluxos

| Fluxo | Como fica |
|---|---|
| Pagar | Abre com o valor cheio, e confirmar é um toque. "Pagar outro valor ou com juros" abre as outras opções. Depois: confirmação e "Desfazer" por 2 minutos |
| Pagar uma parte | A barra mostra o que foi e o que falta. A conta continua na lista |
| Pagar com juros | Juros em linha própria e categoria própria (RN-034) |
| Valor acima do aberto | Recusado até dizer se são juros ou valor maior (RN-043) |
| Informar valor real | Só para conta variável. Passa de estimativa a pendente (RN-052) |
| Agendar | Marca a data. No dia, pergunta se o débito aconteceu (RN-035) |
| Recebi (salário) | Faixa verde na lista e no Início. Move o horizonte para o próximo salário (RN-140) |
| Lançar | Tipo, valor, categoria das mais usadas e conta na primeira tela, sem rolar |
| Estornar | Só em Movimentações, com motivo. Reabre a conta se era pagamento (RN-044) |
| Abertura | Mantém o fluxo atual, com o novo visual |

Toda ação explica o efeito no que você pode gastar, em uma frase.

## 12. Design system

**Tipografia:** IBM Plex em quatro vozes. Serif no número principal e nos títulos de tela; Sans na interface; Sans Condensed nos rótulos; Mono nos valores. Conferido no arquivo da fonte: `≈ → − · ã ç` existem nas quatro versões. `⌫` não existe e virou ícone próprio.

| Token | Uso | Fonte e tamanho |
|---|---|---|
| `display` | Número principal | Serif 500, 88 px (computador), 60 px (celular) |
| `title` | Título de tela | Serif 500, 30 px |
| `mid` | Totais de seção | Serif 500, 30 px |
| `name` | Nome em lista | Sans 600, 16,5 px |
| `body` | Texto | Sans 400, 15/21 px; formulário no celular em 16 px |
| `sub` | Apoio | Sans 400, 13,5 px |
| `label` | Rótulos | Condensed 500, 13 px, maiúsculas |
| `value` | Valores | Mono 13 a 19 px, números tabulares |

**Espaço:** 4, 8, 12, 16, 24, 32, 48 px. **Canto:** 1 px em marcas, 0 em barras. **Sombra e degradê:** nenhum. **Separação:** réguas de 1 e 2 px.

**Cores:** seção 9 para o tema claro. Tema escuro:

| Token | Claro | Escuro |
|---|---|---|
| `--bg` | `#F0F1EC` | `#121416` |
| `--panel` | `#FAFAF6` | `#1A1D20` |
| `--ink` | `#14171A` | `#ECEBE5` |
| `--ink2` | `#4C5258` | `#B1B6BB` |
| `--action` | `#1B3FAB` | `#8FA8F0` |
| `--ok` / `--ok-t` | `#2A9D5C` / `#17693F` | `#3FB374` / `#6BD69A` |
| `--warn` / `--warn-t` | `#B07A12` / `#8A5200` | `#C8922E` / `#E3B056` |
| `--crit` / `--crit-t` | `#8F1D0B` / `#AE240E` | `#D2553C` / `#FF9A85` |
| `--comp` | `#3A3F45` | `#6C7279` |
| `--proj` | `#4A43A0` | `#B4AEF2` |
| Categorias | `#2F6F73`, `#8E7CC3`, `#8C5A3C` | `#62AEB3`, `#B9ABE6`, `#C99673` |

Contraste do tema escuro, medido: textos com mínimo de 5,59:1; preenchimentos com mínimo de 3,48:1. Texto sobre preenchimento, medido contra a listra mais desfavorável de cada hachura: mínimo de 4,62:1 nos dois temas.

**Componentes:** botões (principal, secundário, perigo, desabilitado, foco); campos com erro; situação com palavra e sinal (Atrasado, Pendente, Agendado, Previsto, Pago em parte, Pago, Cancelado); barra do dinheiro; barra de progresso; linha de conta; linha do salário; linha do tempo; faixa de dias; aviso; estado vazio.

**Ícones:** conjunto próprio de traço reto, no lugar do Lucide. 14 desenhados; os demais seguem o mesmo traço.

**Gráficos:** barras, linha do tempo e faixas. Sem pizza, rosca ou medidor. Nome escrito no próprio gráfico; previsão hachurada ou tracejada, com etiqueta. No ECharts, as cores vêm dos mesmos tokens.

## 13. Dashboard: do 2B à Fase 6

| Bloco | Fase 2B | Fase 6 |
|---|---|---|
| Pode gastar, barra e "Como calculamos" | Sim | Sim |
| Linha do tempo até o salário | Sim | Sim |
| Dívidas | Total e barras | Com "de onde vem" |
| Para onde foi | Barra do mês | Com comparação entre meses |
| Comprometimento de 12 meses | Não | Sim, em barras simples |
| Projeção de 7, 15 e 30 dias | Não | Sim |

Os sete estados do número principal estão desenhados no quadro "Estados".

## 14. Telas

| Tela | Situação |
|---|---|
| Início, Pagamentos, Lançar, Calendário, Recorrências, Movimentações, Cartões, Dívidas, A receber, Contas, Ajustes | Desenhadas |
| Login, PIN, formulários de cadastro, abertura, backup, saúde, faturas detalhadas (Fase 3A) | Seguem os mesmos componentes, sem quadro próprio |

## 15. Responsividade

| Largura | Regras |
|---|---|
| Computador, 1.024 px ou mais | Barra lateral de texto, conteúdo até 1.180 px |
| Tablet, 640 a 1.023 px | Navegação no topo; linha do tempo mantida; colunas em uma só abaixo de 860 px |
| Celular, abaixo de 640 px | Barra inferior com Lançar fixo; linha do tempo vira lista das próximas contas; barra sem texto dentro, com legenda abaixo |

## 16. Acessibilidade e consistência

| Item | Regra |
|---|---|
| Cor | Nunca sozinha: palavra, ícone, sinal ou hachura |
| Contraste | Texto 4,5:1 sobre fundos e preenchimentos, marcas 3:1, nos dois temas (medido) |
| Toque | 44 px no celular; 24 px no mínimo em tudo |
| Foco | Anel de 2 px visível |
| Leitor de tela | Barras e linha do tempo com descrição em texto |
| Movimento | Respeita `prefers-reduced-motion` |
| Texto | Linguagem comum: nunca "débito", "crédito" ou "perna" |

## 17. Para implementar, depois da aprovação

Nada disso foi feito.

1. Atualizar `ui-ux-specification.md` pela seção de alterações.
2. Hospedar as fontes IBM Plex localmente (a CSP só aceita arquivos próprios) e remover Inter e Lucide.
3. Levar os tokens para `tailwind/input.css` (`@theme`) e criar os componentes. O build Alpine CSP e o htmx continuam.
4. Trocar o visual das telas existentes e construir as da 2B sobre o novo sistema.

Propostas novas, fora dos requisitos atuais e a confirmar na implementação: "Veja o que pode esperar" no estado crítico; "Desfazer" logo depois de pagar (hoje existe para lançamentos); uma frase sobre o efeito no "Pode gastar" em cada ação.

Limites deste estudo: os protótipos são estáticos, com dados fictícios; só ao usar de verdade dá para validar conforto e densidade.

### Pendências de decisão

1. Coisas novas para a Fase 6. Não bloqueia a Fase 2B.
