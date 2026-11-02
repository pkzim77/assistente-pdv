# Mapeamento do Arpa — 31/10/2026

Inspeção realizada com sessões PostgreSQL configuradas com `default_transaction_read_only=on` e limite de 15 segundos por comando. Nenhuma escrita no banco, emissão ou alteração de estoque foi executada.

## Conexão observada

- Host: `127.0.0.1`; porta: `5432`; banco: `control`.
- Usuário observado nas sessões do PDV e Control: `postgres`.
- Executável: `C:\Program Files (x86)\arpa\control\pdv.exe`.
- Cliente SQL existente: `C:\Program Files (x86)\arpa\control\bin90\psql.exe`.
- A autenticação existente aceita conexão sem senha. Para a integração permanente, provisionar uma conta com privilégios apenas de consulta; a configuração de leitura da sessão não substitui permissões do banco. Não alteramos autenticação ou usuários.

## Fonte principal: public.produtos

| Campo | Uso |
|---|---|
| codigo | Identificador único; chave primária confirmada |
| codigodefabrica | Referência de pesquisa; não é única |
| descricao | Nome e variação/tamanho |
| unidade | Unidade de venda; não assumir sempre unidade inteira |
| quantidade | Saldo registrado no cadastro |
| precovenda | Preço unitário cadastrado; preservar precisão decimal |
| ativo | 0 = ativo, 1 = inativo, confirmado na função verifica_baixa_de_produtos |
| baixa | P = produto com movimentação própria de estoque; todos os registros atuais usam P |
| codbarra | Código de barras no cadastro |
| grade | Ligação com grade; nenhum produto possui grade nesta base |
| tabela_preco | Referência opcional à tabela alternativa de preços |

`produtos_codbarra.produto` relaciona códigos de barras adicionais a `produtos.codigo`; há 14.167 registros. Não fazer JOIN direto para gerar o catálogo sem agregação: isso pode duplicar produtos.

`itens_preco.produto` e `itens_preco.tabela` são os campos de associação a produtos e `cabeca_preco.codigo`. Ambas as tabelas de preços estão vazias. `grade_produtos_saldo` também está vazia.

`reserva_cliente` possui produto e quantidade, mas está vazia. Não subtrair reservas automaticamente sem confirmar a regra do Arpa. A inspeção não certifica ausência de compromissos em todos os demais módulos.

## Conferência com as capturas do PDV

| Código | Código de fábrica | Variação | Saldo atual | Preço |
|---|---|---|---|---|
| 1040 | 133M | BOXER CANELADA M | 0 | 18,250 |
| 5682 | 74 | BOXER INFANTIL MICROFIBRA G | 49 | 11,750 |
| 5681 | 74 | BOXER INFANTIL MICROFIBRA M | 0 | 10,625 |

Descrições, códigos e preços conferem com a captura. O saldo do item 5682 era 50 na captura e está em 49 na leitura; não foi investigada a origem da diferença.

## Contagens no momento da consulta

- 17.805 produtos, todos com `ativo = 0`.
- 7.865 com saldo e preço positivos.
- Nenhum saldo negativo ou produto com saldo positivo e preço ausente/não positivo.
- 287 códigos de fábrica diferentes são compartilhados por mais de um cadastro.
- Unidades incluem PC, UN, CJ, PAR, PCT, KIT, KG, PK e o valor `61`, cuja interpretação ainda requer confirmação.

## Regras para a integração

1. Usar `codigo` como identidade e conferir descrição/tamanho no PDV. Código de fábrica sozinho não identifica o item.
2. O catálogo SQL contém candidatos, não autorização para vender. Confirmar unidades, quantidade, preço aplicado pelo PDV e eventuais reservas/restrições.
3. Reconsultar saldo antes do lançamento. Um snapshot não reserva estoque nem impede vendas simultâneas.
4. Preservar NUMERIC com decimal exato; há preços com três casas. Validar arredondamento do PDV antes de usar o otimizador.
5. Não executar UPDATE de estoque: o PDV deve fazer a baixa. Após emissão confirmada, reler o saldo para atualizar o painel.
6. Não presumir empresa/filial: produtos não tem esses campos e a configuração aponta para um banco único. Confirmar o escopo antes de operar múltiplas lojas.
7. A/F2 emitem imediatamente conforme o fluxo informado. A autorização do usuário precisa anteceder essas teclas. Não repetir em caso de resultado incerto sem reconciliar a emissão.

## Entregáveis e limites

`../sql/catalogo-candidatos.sql` é uma consulta executável em transação somente leitura. Foi validada nesta base. Este levantamento não implementa ainda o painel, o otimizador, o agente Windows ou a reconciliação de NFC-e.
