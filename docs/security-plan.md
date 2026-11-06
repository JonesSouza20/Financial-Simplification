# Plano de Segurança e Privacidade — Sistema de Gestão Financeira Pessoal

| Campo | Valor |
|---|---|
| Versão | 0.2 |
| Data | 06/11/2026 |
| Etapa | 4 — Especificação (Fase B) |
| Status | Versão 0.1 aprovada em 06/11/2026 (Fase B); versão 0.2 com os ajustes da Fase 1D (§13), aprovada em 06/11/2026 |
| Documentos relacionados | `architecture.md` §9–§11, `decisions.md` (ADR-012, 019 a 022), `testing-plan.md` §8–§9 |

Comandos e nomes de opções de ferramentas externas (Tailscale, WinSW, `age`) serão conferidos na versão instalada durante a implementação. Este plano define **o que** deve ser garantido e **como verificar**.

---

## 1. Ativos e ameaças

### 1.1 O que proteger

| Ativo | Por quê |
|---|---|
| Banco de dados (`financeiro.db`) | Toda a vida financeira do usuário |
| Backups (local e nuvem) | Cópia completa dos dados |
| Senha de login, PIN, tokens de aparelho | Acesso ao sistema |
| Senha de backup | Abre todos os backups |
| Token do bot do Telegram | Permite enviar mensagens em nome do bot |
| Integridade dos números | Decisões financeiras dependem deles |

### 1.2 Ameaças consideradas

| # | Ameaça | Probabilidade | Impacto | Controles |
|---|---|---|---|---|
| A1 | Celular perdido ou furtado, desbloqueado | Média | Alto | PIN, expiração de sessão, revogação remota (§3, §10.1) |
| A2 | PC furtado | Baixa | Alto | Criptografia do dispositivo, senha do Windows, backups criptografados (§5) |
| A3 | Alguém na mesma rede Wi-Fi tenta acessar | Média | Alto | Servidor só em `127.0.0.1`; acesso só pelo Tailscale (§4) |
| A4 | Tentativa de adivinhar senha ou PIN | Baixa | Alto | Bloqueio progressivo, Argon2id, alerta (§3.3) |
| A5 | Vazamento do backup na nuvem | Baixa | Alto | Criptografia `age` com senha forte (§7) |
| A6 | Perda de dados (falha de disco, corrupção, ransomware) | Média | Muito alto | Backup diário verificado, versões, cópia fora do PC, teste de restauração (§7) |
| A7 | Erro do próprio usuário (lançamento errado, exclusão) | Alta | Médio | Nada é excluído; estorno; auditoria; "Desfazer" (`business-rules.md` §12) |
| A8 | Bug que corrompe saldos | Média | Alto | Gatilhos, invariantes, testes, verificação no backup (`database-design.md` §11) |
| A9 | Vazamento do token do Telegram | Baixa | Baixo | Cofre do Windows; bot só envia; troca de token (§6, §10.2) |
| A10 | Dependência com vulnerabilidade | Média | Médio | Versões travadas, `pip-audit` em toda atualização (§9) |
| A11 | Script ou conteúdo externo injetado na página | Baixa | Alto | CSP sem scripts externos, escape automático de templates, CSRF (§8) |

Fora do escopo: atacante com controle total da sessão do Windows do usuário (malware no PC). Nesse caso, nenhuma proteção da aplicação é suficiente. A mitigação é a higiene do próprio Windows: atualizações, antivírus nativo e senha.

## 2. Inventário de dados que saem do PC

| Dado | Destino | Proteção | Decisão |
|---|---|---|---|
| Backup completo | Pasta da nuvem (Google Drive ou OneDrive) | Criptografado com `age` antes de sair do processo | ADR-021 |
| Nome e valor de contas em alertas | Servidores do Telegram | Nenhuma (o Telegram lê o conteúdo) | ADR-029, aceito pelo usuário |
| Nome da máquina e da tailnet | Logs públicos de certificados | Nomes neutros | ADR-012 |
| Tráfego do celular | Rede Tailscale (WireGuard) | Criptografia ponta a ponta do túnel + HTTPS | ADR-012 |

Nada mais sai do PC: sem telemetria, sem CDN, sem fontes externas (RNF-08).

## 3. Autenticação e sessões

### 3.1 Senha

| Item | Regra |
|---|---|
| Comprimento | Mínimo 12 caracteres; frase-senha incentivada |
| Verificação | Contra lista de senhas comuns e contra dados óbvios (nome do sistema, datas) |
| Armazenamento | Hash Argon2id (parâmetros padrão do Django vigentes, revisados a cada atualização) |
| Troca | Exige a senha atual; revoga todos os aparelhos confiáveis e sessões, exceto a atual |
| Esquecimento | Não há recuperação por e-mail. Procedimento local no PC (§10.4) |

### 3.2 Sessões

| Item | Valor proposto |
|---|---|
| Expiração por inatividade | 30 minutos |
| Expiração absoluta | 12 horas |
| Cookie | `HttpOnly`, `Secure`, `SameSite=Strict`, nome sem prefixo identificável |
| Armazenamento | Sessões no banco, revogáveis |
| Troca de identificador | A cada login, PIN e elevação de privilégio |

### 3.3 Tentativas repetidas (django-axes)

| Situação | Reação |
|---|---|
| 5 falhas de senha | Bloqueio de 15 minutos |
| Novo bloqueio em 24 h | Bloqueio dobra (30 min, 1 h, 2 h...) até 24 h |
| Qualquer bloqueio | Registro na auditoria e alerta no Telegram (F-080) |
| Desbloqueio manual | Pelo PC (comando local), registrado na auditoria |

### 3.4 Aparelho confiável e PIN (ADR-019, ADR-035)

| Item | Regra |
|---|---|
| Ativação | Só após login com senha, por escolha do usuário, com nome do aparelho |
| Token do aparelho | 256 bits aleatórios, em cookie próprio (`HttpOnly`, `Secure`, `SameSite=Strict`); no servidor, só o hash |
| Validade | 30 dias, renovada a cada login com senha (não pelo PIN) |
| PIN | 6 dígitos; hash Argon2id; não aceita sequências triviais (123456, 000000, data do ano) |
| Uso | Reabre sessão expirada (por inatividade ou pela expiração absoluta), se o token do aparelho for válido. Ver nota abaixo |
| Falhas | 5 erros de PIN revogam o aparelho; senha exigida |
| Operações sensíveis | Sempre senha: trocar senha ou PIN, revogar aparelhos, restaurar backup, configurar Telegram, trocar senha de backup, exportação completa |
| Gestão | Tela lista aparelhos com último uso; revogação individual ou "revogar todos" |

Nota sobre a expiração absoluta: o PIN pode reabrir a sessão após a expiração absoluta de 12 horas, desde que o token do aparelho esteja válido. É isso que torna o uso diário prático. Depois de 30 dias, ou de qualquer revogação, a senha volta a ser obrigatória.

### 3.5 Biometria

"Biometria" (escolha do usuário na descoberta) fica para o pós-MVP, via passkeys (WebAuthn), como alternativa ao PIN, com as mesmas regras de aparelho confiável. O HTTPS do Tailscale já atende o requisito técnico.

## 4. Rede e acesso remoto (ADR-012)

| Controle | Regra | Como verificar |
|---|---|---|
| Endereço de escuta | Waitress só em `127.0.0.1:<porta>` | `netstat` mostra a porta só em 127.0.0.1; acesso pelo IP da rede local falha |
| Publicação | Tailscale Serve proxy HTTPS → `http://127.0.0.1:<porta>`, só na tailnet | Celular fora da tailnet não abre o endereço |
| HTTPS | Certificado automático `*.ts.net` (habilitar HTTPS e MagicDNS no painel do Tailscale) | Navegador mostra cadeado sem alerta |
| Funnel | **Nunca** ativado | `tailscale funnel status` sem entradas; verificação na tela de saúde |
| Dispositivos na tailnet | Só PC e celular do usuário; expiração de chave do Tailscale mantida ligada no celular | Painel do Tailscale |
| Nomes | Máquina e tailnet com nomes neutros (sem nome próprio) | Revisão na instalação |
| `ALLOWED_HOSTS` e origens CSRF | Só o nome `ts.net` da máquina e `localhost` | Teste de cabeçalho `Host` inválido (`testing-plan.md`) |
| Firewall do Windows | Porta da aplicação sem regra de entrada | Revisão na instalação |
| Celular | Bloqueio de tela obrigatório (recomendação no guia) | Checklist de instalação |

## 5. Dados em repouso (ADR-022)

- **Criptografia do dispositivo do Windows:** conferida na instalação e na tela de saúde. Se não estiver disponível no hardware, o risco fica registrado na tela de saúde ("Disco sem criptografia") e o SQLCipher é reavaliado no pós-MVP.
- Banco e backups locais em pasta do perfil do usuário, com permissões do Windows restritas ao usuário.
- Arquivos temporários de backup e restauração na mesma pasta protegida, apagados ao fim de cada operação (inclusive em falha).

## 6. Segredos (ADR-020)

| Segredo | Onde fica | Rotação |
|---|---|---|
| Chave secreta da aplicação (assinatura de cookies) | Cofre de Credenciais do Windows (`keyring`) | Ao suspeitar de vazamento; invalida sessões |
| Token do bot do Telegram | Cofre de Credenciais | Pelo BotFather, se vazar (§10.2) |
| Senha de backup | Cofre de Credenciais (para o backup automático) **e** fora do sistema, guardada pelo usuário | Troca gera backup novo; os antigos continuam com a senha antiga (o sistema avisa) |
| `chat_id` autorizado do Telegram | Configuração (não é segredo, mas só um é aceito) | — |

Regras:
- nenhum segredo em código, banco, logs, backups, URLs ou mensagens de erro;
- a tela de configuração mostra só "configurado em dd/mm/aaaa";
- o bot só usa o método de envio e não processa mensagens recebidas.

## 7. Backup e recuperação (ADR-021)

### 7.1 Política

| Item | Regra |
|---|---|
| Frequência | Diária, no horário configurado (padrão 03:00), com recuperação se o PC estiver desligado (ADR-018) |
| Gatilhos extras | Antes de atualização, antes de migração, antes de restauração, manual |
| Método | Cópia online do SQLite → verificação → manifesto → compressão → `age` |
| Verificação | `integrity_check`, `foreign_key_check`, invariantes I-01 a I-10, SHA-256 depois de gravar |
| Destinos | Pasta local (perfil do usuário) e pasta sincronizada da nuvem |
| Retenção | 7 diários, 4 semanais (domingo), 12 mensais (dia 1º); os gerados antes de atualização ficam 90 dias |
| Nome do arquivo | `financas-AAAAMMDD-HHMM-<gatilho>.db.age` + manifesto `.json` (sem dados financeiros) |
| Alerta | Falha, ausência de backup há mais de 36 h, ou cópia da nuvem desatualizada há mais de 72 h |

### 7.2 Restauração pelo sistema (F-100)

1. Configurações → Backup → Restaurar; informar a senha de login.
2. Escolher a versão (lista com data, gatilho, verificação, origem local ou nuvem).
3. O sistema faz backup do estado atual (gatilho `pre_restore`).
4. Descriptografa e restaura em arquivo temporário; roda todas as verificações.
5. Mostra o resumo: data do backup, número de transações, saldos das contas, último lançamento.
6. Usuário confirma; o sistema para o acesso, troca o arquivo, reinicia e registra na auditoria.
7. Se qualquer verificação falhar, nada é substituído e a falha é explicada.

### 7.3 Recuperação de desastre (PC perdido ou disco perdido)

Pré-requisito: senha de backup guardada fora do sistema.

1. Em outro computador com Windows, instalar o sistema pelo instalador (sem criar dados).
2. Instalar o Google Drive ou o OneDrive e aguardar a sincronização da pasta de backups.
3. Escolher "Restaurar de um backup" no assistente de instalação, apontar o arquivo `.age` mais recente e informar a senha de backup.
4. Recadastrar os segredos que não vão no backup: token do Telegram, senha de backup no cofre, chave da aplicação (gerada nova).
5. Reconfigurar o Tailscale nesse computador; revogar o PC antigo no painel do Tailscale.
6. Entrar com a senha de login (que está no backup); revogar todos os aparelhos confiáveis e ativá-los de novo.

Alternativa sem o sistema: a ferramenta `age` descriptografa o arquivo, e o resultado é um banco SQLite comum, legível por qualquer visualizador de SQLite.

### 7.4 Testes de recuperação

| Teste | Frequência | Quem | Critério |
|---|---|---|---|
| Restauração automática | Mensal (dia 1º, após o backup) | Agendador | Restaura o backup mais recente em arquivo temporário; verificações passam; contagens e saldos batem com o manifesto |
| Restauração completa manual | Trimestral (jan, abr, jul, out) | Usuário, com checklist | Checklist §7.5 completo |
| Recuperação de desastre simulada | Anual | Usuário | Abrir o backup da **nuvem** com `age` em outro computador (ou pasta separada) e conferir que o banco abre |

### 7.5 Checklist trimestral

1. Ver na tela de saúde: último backup diário OK, último teste automático OK, cópia da nuvem recente.
2. Abrir a pasta da nuvem pelo navegador (fora do PC) e confirmar que o arquivo de ontem está lá.
3. Executar "Restaurar → modo teste" (restaura em local temporário, sem substituir) a partir de um backup **da nuvem**.
4. Conferir no resumo: saldo da Corrente e total da última fatura iguais aos do sistema atual na mesma data.
5. Confirmar que a senha de backup guardada fora do sistema está acessível e correta (o passo 3 usa a senha digitada, não a do cofre).
6. Registrar o resultado na tela (cria registro `restore_test` manual).

## 8. Aplicação web

| Controle | Regra |
|---|---|
| Autenticação obrigatória | Todas as URLs, exceto login, PIN e arquivos estáticos; teste automático percorre todas as rotas |
| CSRF | Proteção do Django em todo `POST`; htmx envia o token |
| CSP | `default-src 'self'`; scripts e estilos só locais; sem `unsafe-inline` em scripts; `frame-ancestors 'none'` |
| Outros cabeçalhos | HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy` restritiva |
| Templates | Escape automático do Django; nada de HTML vindo do usuário |
| Validação | Formulários Django no servidor (RN-180 a RN-186); limites de tamanho de texto |
| Mensagens de erro | Sem detalhes técnicos para o usuário; detalhes só no log local |
| Modo de depuração | Desligado em produção; a tela de saúde alerta se estiver ligado |
| Arquivos enviados | Só na importação (pós-MVP): tamanho máximo, tipo verificado, processados em memória |

## 9. Atualizações e dependências

1. Dependências travadas no `uv.lock`.
2. A cada atualização, o script:
   - faz backup (`pre_update`);
   - roda `pip-audit`;
   - roda a suíte de testes;
   - aplica migrações;
   - roda as invariantes;
   - reinicia.
3. Em falha, volta à versão anterior do código e ao backup.
4. Revisão mensal sugerida de atualizações de segurança do Django e do Python (lembrete no dashboard).
5. Windows Update e Tailscale com atualização automática ligada (checklist de instalação).

## 10. Resposta a incidentes

### 10.1 Celular perdido ou furtado

1. No PC: Configurações → Segurança → revogar o aparelho (ou "revogar todos").
2. No painel do Tailscale: remover o celular da tailnet.
3. Trocar a senha do sistema, se ela estava salva no celular.
4. Conferir a auditoria por ações após a perda.

### 10.2 Token do Telegram vazado

1. No BotFather: revogar o token e gerar outro.
2. No sistema: Configurações → Alertas → atualizar o token (pede senha).
3. Enviar mensagem de teste.

### 10.3 Suspeita de acesso indevido

1. Revogar todos os aparelhos e trocar a senha.
2. Revisar a auditoria (logins, aparelhos, ações) e o histórico de bloqueios.
3. Rodar as invariantes e conciliar as contas com os bancos.
4. Se houver alteração indevida, usar estornos (nada foi apagado) ou restaurar o backup anterior ao incidente.

### 10.4 Senha de login esquecida

No próprio PC, com a sessão do Windows aberta, um comando local de redefinição pede a senha de backup como prova adicional e define nova senha. Todos os aparelhos e sessões são revogados.

### 10.5 Senha de backup perdida

- Backups antigos ficam ilegíveis. Isso é consequência da criptografia, não há como contornar.
- Com o sistema funcionando: definir nova senha de backup (pede senha de login) e gerar backup imediatamente. A partir daí os backups usam a nova senha.
- O sistema avisa que os backups antigos continuam com a senha antiga.

### 10.6 PC furtado

Seguir §7.3 em outro computador, remover o PC da tailnet, trocar a senha do sistema e a senha de backup após a restauração, e revogar o token do Telegram.

## 11. Registro de operações e logs

| Registro | Conteúdo | Retenção |
|---|---|---|
| Auditoria (`audit_log`) | Toda operação financeira e de configuração (RN-190, RN-191) | Permanente |
| Log da aplicação | Erros, avisos, início e fim de tarefas | 90 dias, rotação diária |
| Log de acesso | Data, hora, rota, status, aparelho; sem corpo das requisições | 90 dias |

Logs nunca contêm senhas, PIN, tokens, cookies nem segredos (RN-192). O teste automático procura padrões de segredo nos logs gerados pela suíte.

## 12. Checklist de instalação (segurança)

1. Conta do Windows com senha (necessária para o serviço; ver `architecture.md` §11) e bloqueio de tela automático.
2. Criptografia do dispositivo ativa, ou risco aceito e registrado.
3. Windows Update automático.
4. Tailscale instalado no PC e no celular; MagicDNS e HTTPS habilitados; nomes neutros; Funnel desligado.
5. Serviço rodando com início automático; porta só em `127.0.0.1`.
6. Senha do sistema criada; senha de backup criada **e guardada fora do sistema**.
7. Pasta da nuvem configurada; primeiro backup gerado e visível na nuvem.
8. Primeiro teste de restauração em modo teste executado com sucesso.
9. Telegram configurado com `chat_id` único; mensagem de teste recebida.
10. Celular com bloqueio de tela; aparelho confiável ativado com PIN.

## 13. Alterações após a aprovação

| Seção | Alteração | Motivo |
|---|---|---|
| §7.1 | Nome do arquivo com segundos: `financas-AAAAMMDD-HHMMSS-<gatilho>.db.age` | Dois backups no mesmo minuto (ex.: manual e `pre_restore`) não colidem |
| §7.1 | Retenção: o semanal é o mais novo de cada semana ISO (domingo); o mensal é o primeiro de cada mês (dia 1º); os de `pre_update`, `pre_migration`, `pre_restore` e `manual` ficam 90 dias | Detalhe do que já estava previsto |
| §7.1 | Alerta também quando a última cópia na pasta da nuvem tem mais de 72 horas | Implementado na tela de saúde |
| §7.2 | Passos 4 e 5 em duas telas: "Ver resumo para restaurar" restaura num arquivo temporário e mostra data, transações, saldos e último lançamento; a confirmação pede as senhas de novo | Ninguém substitui os dados sem ver o resumo |
| §7.2 | Passo 6 sem reiniciar o serviço: durante a troca, um bloqueio de manutenção responde 503 às outras requisições e pausa o agendador; as conexões com o banco são fechadas antes e depois | O processo é único (ADR-011); reiniciar o serviço exigiria privilégio de administrador pela tela |
| §7.3 | Passo 3: `ops\install.ps1 -RestoreFrom <arquivo .db.age>`; o código vem de uma cópia `git bundle` guardada na pasta da nuvem | `ops/guides/recuperacao-de-desastre.md`; ADR-038 |
| §4 | Verificação do Funnel lê `tailscale serve status --json`; "desligado" só com resposta válida, senão "não verificado" | Falha segura: dúvida nunca vira "tudo certo" |
| §9 | Ordem do `update.ps1`: backup `pre_update`, `git pull`, `uv sync`, `pip-audit`, testes, `collectstatic`, backup `pre_migration`, migrações, invariantes. Em falha depois das migrações, o código volta primeiro e o backup `pre_migration` é restaurado em seguida | Testes antes de tocar no banco; restaurar com o código antigo evita banco antigo com código novo |

