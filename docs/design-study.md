# Estudo de Design e UI/UX — Parte 1: Direção

| Campo | Valor |
|---|---|
| Versão | 0.1 |
| Data | 08/11/2026 |
| Status | Parte 1 em avaliação. A Parte 2 (design system completo) começa depois da escolha da direção |
| Decisão | ADR-040: pré-requisito da Fase 2B |
| Protótipos | Canvas com as 3 direções, guardado fora do repositório |

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

Pendência: `≈` e `→` não vieram nos recortes do Google Fonts de nenhuma candidata. O sistema usa `≈` nas projeções, então é preciso conferir no arquivo completo da fonte escolhida, antes de hospedá-la localmente. Licenças abertas também serão confirmadas arquivo a arquivo.

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
