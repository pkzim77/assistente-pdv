# Assistente de caixa — Arpa

Painel React, API Express, leitura do PostgreSQL Arpa, busca de combinação e lançamento assistido dos itens no PDV. O painel não abre o fechamento, não escolhe pagamento e não emite NFC-e; o profissional confere os itens e termina a venda no PDV.

## Executar neste computador

Dê dois cliques em iniciar.cmd, ou, no PowerShell, dentro desta pasta:

    .\iniciar.ps1

Acesse http://127.0.0.1:4318. O servidor escuta apenas no endereço local. Feche o processo com Ctrl+C. Não exponha a porta na rede.

O script usa Node instalado ou o runtime existente do Codex. As dependências e a compilação já foram preparadas nesta máquina. Se mudar o código do painel, execute novamente a compilação antes de iniciar.

## Instalação convencional

Requer Node 22+ e Python 3.12 no Windows para o agente.

    npm install
    npm run build
    npm start

Copie `.env.example` para `.env` em cada computador e preencha os dados daquele estabelecimento. O `.env` é ignorado pelo Git; nunca publique credenciais nele. Com Node 22+, o servidor carrega as demais opções automaticamente. O inicializador também lê de `.env` os caminhos de Node/Python e a porta para mostrar a URL correta.

### Preparar em outro estabelecimento

Revise no `.env` os campos abaixo antes de iniciar:

| Variável | Quando alterar |
| --- | --- |
| `PDV_EXE` | Caminho completo do executável instalado nesse computador; usado pelo botão **Iniciar PDV**. |
| `PDV_PROCESS_NAME` | Só se o processo em execução tiver nome diferente do executável. |
| `PDV_WINDOW_TITLE`, `PDV_WINDOW_CLASS` | Só se a janela principal do PDV tiver identificação diferente. |
| `PDV_LOGIN_TITLE`, `PDV_CLOSING_TITLE`, `PDV_CLOSING_CLASS`, `PDV_OTHER_WINDOW_TITLES`, `PDV_AUX_WINDOW_CLASSES` | Só se os títulos/classes das janelas forem diferentes; listas separadas por vírgula. |
| `PDV_PYTHON`, `NODE_EXE` | Caminhos dos runtimes quando Python/Node não forem encontrados no `PATH`. |
| `ARPA_HOST`, `ARPA_PORT`, `ARPA_DATABASE`, `ARPA_SCHEMA`, `ARPA_USER`, `ARPA_PASSWORD` | Endereço e credenciais da instalação PostgreSQL do Arpa. Use uma conta do Arpa restrita a leitura. |
| `ARPA_CONNECTION_TIMEOUT_MS`, `ARPA_QUERY_TIMEOUT_MS` | Aumente apenas se a conexão remota do estabelecimento precisar de mais tempo; os valores têm limite para evitar esperas sem fim. |
| `PORT` | Porta local do painel se 4318 estiver ocupada. Continua acessível somente pelo próprio computador. |
| `ROBOT_DATA_DIR` | Pasta local dos eventos, se quiser separar os dados desse estabelecimento. |
| `ROBOT_DATABASE_URL` | Opcional: banco próprio `pdv_robo` para histórico compartilhado/persistente; nunca usar o banco operacional do Arpa. |

Os nomes e estruturas das tabelas/campos do Arpa, a classificação de produto ativo, o tipo de baixa, as unidades aceitas e os critérios de lote/série continuam sendo regras do adaptador em código. Se a outra instalação usar versão ou regras diferentes, valide o mapeamento antes de habilitar o uso; não tente resolver isso mudando apenas `.env`. O painel permanece vinculado a `127.0.0.1` de propósito e não deve ser exposto à rede.

Para desenvolvimento do painel: API com npm run dev e Vite com npx vite (porta padrão 5173, proxy da API). Para executar os testes: npm test.

## Fluxo implementado

1. Carregar o estoque geral: não há necessidade de escolher uma nota. Produtos de diferentes entradas podem ser combinados.
2. Informar o valor desejado; o pagamento é escolhido pelo profissional no PDV.
3. Selecionar 100 ou 200 candidatos por busca (padrão 200). O sistema escolhe os candidatos de todo o catálogo, misturando aproximações individuais, itens baratos e faixas de preço diferentes. Não corta pelos primeiros códigos.
4. Usar precovenda diretamente, sem aplicar 25% novamente. Quantidades respeitam o saldo atual.
5. Buscar o menor desvio encontrado; empate favorece maior total. Entre combinações com o mesmo total, preferir menos produtos diferentes (linhas); se ainda empatar, menos unidades. Alvo atingido comprova desvio zero sob a regra de arredondamento usada. Caso contrário, a solução é aproximada, sem garantia de ótimo global.
6. Validar os preços e saldos dos códigos escolhidos diretamente no Arpa, sem usar o cache.
7. Com o PDV na tela de venda e o cupom vazio, o operador confirma a condição e aciona **Lançar todos os itens**. O agente confere código, quantidade, preço e subtotal da linha antes de incluir cada item; qualquer divergência interrompe a sequência e bloqueia uma repetição automática.
8. O painel para na tela de venda. O profissional confere os itens e o subtotal e conclui o fechamento, pagamento e emissão fiscal no próprio PDV.

O catálogo tem cache de até 10 segundos, compartilhando requisições simultâneas. Falha de atualização não devolve silenciosamente dados expirados. O worker é persistente e reutiliza o snapshot para evitar inicialização e transferência a cada proposta. A busca usa orçamento cooperativo de 700 ms; existe timeout de segurança de 3 segundos no worker. Consulta e conexão ao banco têm limites de 2 segundos. Isso não constitui garantia de tempo total: banco, sistema operacional, leitura do catálogo, seleção e gravação do histórico também custam tempo.

A busca limitada mantém uma resposta válida antes do refinamento e não falha só porque esgotou seu orçamento. O conjunto vazio não é elegível. O algoritmo mantém estados de somas diversificados e próximos do alvo, com teto de estados e amostragem de quantidades grandes. Isso pode deixar de encontrar uma combinação melhor.

A seleção utiliza unidades PC, UN, CJ, PAR, PCT e KIT, quantidades inteiras, produto ativo, preço positivo, estoque disponível e sem grade, lote ou série. Outras unidades ficam fora da seleção automática. Saldo é por produto; reservas externas e concorrência entre caixas não são resolvidas por um snapshot. Alvo permitido: R$ 0,01 a R$ 10.000,00.

Preços preservam três casas decimais. O total estimado arredonda cada linha para centavos; a regra efetiva do PDV ainda precisa ser conferida antes da operação real.

## Desempenho observado

Com 7.861 produtos elegíveis, 12 cenários (100/200 candidatos) atingiram o alvo, com cálculo entre 35 e 341 ms na primeira medição. Em outra rodada, com worker persistente, quatro chamadas completas da API ficaram entre 144 e 468 ms; carregamento inicial do catálogo: 317 ms. Resultados específicos desta máquina e amostras, não SLA.

Um catálogo sintético de 100 mil produtos foi processado com 200 candidatos em aproximadamente 461 ms, sem encontrar o alvo exato. A leitura e seleção do catálogo ainda crescem com seu tamanho; o teto de candidatos limita a busca combinatória, não torna todo o processamento constante.

Medições: docs/benchmark-stock.json e docs/api-latency.json.

## Histórico

Por padrão, eventos ficam em data/events.jsonl, com gravação sincronizada antes de responder. A pasta contém dados locais e não vai para o Git. Um arquivo corrompido bloqueia a inicialização; não é descartado silenciosamente. Histórico não representa movimentação fiscal.

Há suporte opcional a PostgreSQL em **outro banco, pdv_robo**, via ROBOT_DATABASE_URL. O script sql/historico-robo.sql deve ser aplicado nesse banco por seu administrador, com parada em erro (psql -v ON_ERROR_STOP=1). Não foi criado banco, usuário ou tabela no Arpa. O robô nunca escreve no banco control.

O usuário postgres da instalação atual foi usado para leitura nesta etapa; as consultas rodam em transações READ ONLY. Uma conta de banco restrita a SELECT é necessária antes de implantação permanente; READ ONLY por sessão não substitui privilégios mínimos.

## Controle Windows

Veja agent/README.md. A inspeção é somente leitura. A ação de montagem no PDV só lança itens depois de uma confirmação explícita de cupom vazio e interrompe diante de qualquer divergência. As rotas antigas por etapa, F6, pagamento e abertura do fechamento estão bloqueadas. Após um resultado parcial ou incerto, a proposta não pode ser repetida pelo painel; o operador deve revisar o PDV manualmente.

## Evidências

- docs/mapeamento-arpa.md: estrutura do catálogo e limites conhecidos.
- docs/conferencia-nota-589919.md: os 12 preços conferem com entrada +25%.
- tests/optimizer.test.js: precisão, estoque, desempate e comparação com enumeração exaustiva.
- tests/workflow.test.js: confirmação, atualização de saldo, persistência e repetição.
- tests/ui-smoke.cjs: fluxo no navegador com estoque geral e dados reais e execução somente simulada; usa Playwright local/disponível via PLAYWRIGHT_MODULE.

- tests/fast-optimizer.test.js: seleção global, combinações entre entradas, orçamento esgotado, comparação com busca exata em 40 catálogos e saldo fracionário.
- tests/stock-cache.test.js: expiração, concorrência e falha de atualização.
- tests/solver.test.js: reutilização do processo e invalidação do snapshot.

## Prioridade por menos produtos

O número de produtos significa códigos distintos/linhas, não unidades. Uma linha com 10 unidades tem prioridade sobre duas linhas com uma unidade cada, quando os totais coincidem. A prioridade por proximidade do alvo e, depois, total maior em empate de desvio, continua valendo. A redução de linhas é aplicada tanto à escolha da resposta quanto aos estados intermediários de soma. Não se encerra ao encontrar uma solução exata de várias linhas quando ainda é possível simplificá-la dentro do orçamento. A busca limitada não certifica mínimo global de linhas em todo o estoque.

24 testes passaram, incluindo comparação de total, linhas e unidades com enumeração completa de 60 catálogos pequenos.
