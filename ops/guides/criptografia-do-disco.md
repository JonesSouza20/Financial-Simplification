# Criptografia do disco

Referências: ADR-022, `docs/security-plan.md` §5.

O banco e os backups locais ficam no disco do PC. Se o PC for furtado, a criptografia do disco impede a leitura direta dos arquivos. Os backups já saem criptografados com a senha de backup; o banco em uso depende da criptografia do Windows.

## 1. Conferir

No Windows 11 Home o recurso se chama **Criptografia do dispositivo**:

1. Abra **Configurações → Privacidade e segurança → Criptografia do dispositivo**.
2. O botão deve estar **Ativado**.

Se esse item não aparecer, o hardware não oferece o recurso no Windows Home.

O sistema confere sozinho (sem pedir administrador) na instalação e na tela **Saúde**. A tela mostra "criptografia do disco: ativa", "desligada" ou "não disponível neste PC".

## 2. Ligar

1. Na mesma tela, ligue a criptografia do dispositivo.
2. A chave de recuperação fica na sua conta Microsoft. Confirme que ela aparece em sua conta Microsoft, na página de chaves de recuperação do BitLocker, antes de seguir.
3. A criptografia roda em segundo plano. O PC pode ser usado normalmente.

## 3. Se não estiver disponível

O risco fica registrado na tela **Saúde** ("risco aceito na ADR-022"). Para reduzir:

- use senha forte na conta do Windows e bloqueio de tela automático;
- mantenha a pasta da nuvem configurada (os backups são criptografados);
- o banco criptografado (SQLCipher) será reavaliado no pós-MVP.
