# Validação da primeira versão

- Build Vite concluído.
- 8 testes Node aprovados, incluindo 80 catálogos conferidos por enumeração exaustiva.
- Fluxo Chrome validado com nota 589919: consulta, proposta, preparação e confirmação de PIX simulada.
- Exemplo: alvo R$ 100,00; combinação R$ 92,31; acréscimo sugerido R$ 7,69.
- Layout desktop inspecionado; largura móvel de 390 px sem transbordamento.
- Nenhum erro JavaScript no navegador.
- Operação sem token retorna 403; endpoint de operação real retorna 409.
- Conexão Arpa confirmou transaction_read_only = on.
- Agente Python passou por compilação sintática; interface real ainda não validada. Não havia janela do PDV disponível na inspeção final do Windows.
- Nenhuma emissão ou alteração de estoque realizada.

Limites: histórico local por padrão; suporte a banco separado opcional. Arredondamento por linha ainda é hipótese a confirmar no PDV.
