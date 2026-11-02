# Validação — estoque geral

- 17 testes automáticos aprovados. A busca legada exata é usada como referência em testes, não como algoritmo da API.
- Removida a necessidade de selecionar uma nota no painel e na proposta.
- Consulta somente leitura a public.produtos; deduplicação natural por chave primária.
- Revalidação direta por códigos dos itens, independente da nota e do cache.
- Catálogo com 7.861 produtos elegíveis no instante da medição.
- Medições de cálculo: benchmark-stock.json; chamadas completas de API: api-latency.json.
- Fluxo de simulação com PIX validado em Chrome, sem emissão.
- Resultado exato significa desvio zero sob o arredondamento estimado. Resultado não exato é a melhor combinação encontrada, não uma certificação de ótimo global.
- API continua bloqueando emissão real. Não houve alterações de estoque.
