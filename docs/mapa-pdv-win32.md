# Mapeamento do PDV por Win32

Captura e inspeção somente de leitura da janela de caixa, após login. Nenhum produto foi lançado, e nenhuma venda ou nota foi emitida.

## Janelas observadas

- Login: `CUPOM FISCAL`, classe `TSenhaAcesso`.
- Caixa: `PDV-FISCAL`, classe `TFVendas`.
- Janela raiz: `PDV - Control`, classe `TApplication`.
- A enumeração comum de janelas do computador não expôs essas janelas. Foi preciso enumerar os HWNDs diretamente via Win32.

## Controles identificados na tela do caixa

| Função, conferida com a captura do usuário | Classe observada | Posição relativa observada |
|---|---|---|
| Quantidade | `TEditArpa` | (33, 197) a (304, 220) |
| Produto / pesquisa | `TArpaEditConsultaDados` | (33, 321) a (304, 344) |
| Preço de venda | `TEditArpa` | (33, 447) a (304, 470) |
| Total | `TEditArpa` | (33, 572) a (304, 595) |
| Estado do PDV (“PDV LIVRE”) | `TEditArpa`, desabilitado | (352, 64) a (1322, 99) |
| Área de itens | `TAdvSmoothPanel` | (339, 149) a (1335, 619) |

As posições são relativas à janela e não são seletores persistentes. Os HWNDs e IDs mudam ao reabrir o PDV. Antes de qualquer entrada, reencontrar a janela e validar classe, campo e contexto. O banner superior desabilitado exibe o estado, não é campo de produto. Os títulos dos painéis são desenhados pelo próprio Arpa e não vieram como controles filhos.

## Estado seguro alcançado

Após entrar com as credenciais que o usuário já forneceu, o sistema perguntou se deveria enviar 8 notas em contingência à SEFAZ. Foi escolhida a opção **Não**. Nenhuma nota pendente foi transmitida. A tela principal ficou aberta com o caixa fechado.

## Limite atual

O controle de janela está enumerando a tela principal com a API Win32 via `ctypes`. A busca abre uma lista customizada do Arpa; ainda faltam verificar como ler e selecionar a linha exata e como conferir a lista lançada e o total no fechamento. Nenhum comando de entrada está habilitado; o pagamento real continua bloqueado.
