# Ponte local do PDV-Fiscal

O servidor usa os scripts deste diretório para localizar o PDV e, após autorização explícita no painel, lançar os itens de uma proposta na tela de venda.

## Diagnóstico e abertura

- `inspect_pdv_win32.py --stdout`: enumera as janelas e lê somente os campos necessários para conferir a tela de venda.
- `launch_pdv_win32.py`: abre o PDV se ainda não estiver em execução. A autenticação continua sendo feita pelo operador no PDV.
- `restore_pdv_win32.py`: traz a janela de venda para frente; não inclui produto nem envia pagamento.

Os parâmetros locais do executável e da identificação de janelas ficam no `.env` da raiz (`PDV_EXE`, `PDV_PROCESS_NAME`, `PDV_WINDOW_TITLE`, `PDV_WINDOW_CLASS` e títulos de login/fechamento). `pdv_config.py` mantém os padrões da versão atualmente mapeada.

## Montagem assistida

`build_sale_win32.py` é chamado pelo botão único **Lançar todos os itens no PDV**. Antes de qualquer entrada, verifica que há exatamente uma janela principal visível, que não há fechamento aberto e que quantidade, produto, preço e total estão no estado inicial. A caixa de confirmação exige que o operador confira manualmente que o cupom está vazio; a grade do PDV é desenhada pelo próprio aplicativo e não é legível com segurança pela ponte atual.

Para cada item, o agente:

1. Confere os dados e a conta do subtotal antes de interagir.
2. Informa a quantidade e verifica a leitura do campo.
3. Digita o código interno e confirma que ele está integral no campo Produto; não precisa abrir a grade.
4. Envia um Enter e verifica o que o PDV fez. Envia o segundo somente se o primeiro ainda deixou o código e a quantidade corretos, ou confirmou preço e subtotal do produto esperado.
5. Confirma que a linha foi adicionada e o PDV voltou ao estado inicial.

Qualquer divergência interrompe a sequência. Se a resposta do agente se perder ou o resultado ficar incerto, o painel bloqueia nova tentativa para evitar duplicidade; o operador deve conferir o cupom manualmente. Depois da inclusão, o painel para na tela de venda. Não envia F6, forma de pagamento, A/F2, não abre o fechamento e não emite NFC-e.

## Limites

Se o código não ficar integral no campo Produto, se houver uma lista aberta, se o foco sair do PDV ou se preço/quantidade divergirem, a rotina para sem continuar. Se o PDV mudar de versão, layout, resolução ou comportamento, a rotina deve parar e ser revalidada antes de uso operacional.
