# Configurar os avisos no Telegram

São cinco minutos. O token é uma senha: não mande para ninguém nem cole em outro lugar.

## 1. Criar o bot

1. No Telegram, abra uma conversa com **@BotFather**.
2. Envie `/newbot`.
3. Escolha um nome e um usuário terminado em `bot`.
4. Guarde o token que ele responder. O formato é `123456789:AAH...`.

## 2. Descobrir o número do chat

1. Abra uma conversa com o bot que você criou e envie `/start`.
2. Abra uma conversa com **@userinfobot** e envie qualquer mensagem.
3. Anote o número que aparece em `Id`.

## 3. Colocar no sistema

1. Abra **Ajustes → Avisos**.
2. Cole o token, informe o número do chat e digite sua senha de login.
3. Salve e toque em **Enviar mensagem de teste**.

## O que chega

| Aviso | Quando |
|---|---|
| Conta perto de vencer | 3 dias antes (ajustável) e no dia, às 08:00 |
| Conta atrasada | No dia seguinte ao vencimento efetivo |
| Falha ou falta de backup | Às 08:00 |
| Bloqueio de login, aparelho novo | Na hora, mesmo no silêncio noturno |

Fatura de cartão e saldo projetado abaixo do mínimo entram nas fases 3B e 6.

## Se o token vazar

1. No @BotFather: `/revoke` e gere outro.
2. Em **Ajustes → Avisos**, cole o token novo e digite sua senha.
3. Envie a mensagem de teste.
