-- Snapshot de candidatos. Nao reserva estoque nem autoriza emissao.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT
    codigo AS produto_id,
    codigodefabrica AS codigo_fabrica,
    descricao,
    unidade,
    quantidade AS saldo_cadastrado,
    precovenda AS preco_unitario,
    codbarra AS codigo_barras,
    CURRENT_TIMESTAMP AS consultado_em
FROM public.produtos
WHERE ativo = 0
  AND baixa = 'P'
  AND quantidade > 0
  AND precovenda > 0
ORDER BY codigo;
COMMIT;
