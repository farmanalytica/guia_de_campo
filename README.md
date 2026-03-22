# GuiaDeCampo (QGIS Plugin)

Plugin para captura de pontos no mapa, armazenamento de coordenadas em WGS84 e automacoes de apoio para fluxo de campo.

## Developer Instructions

## Project Structure

- `__init__.py`: entrypoint do plugin para o QGIS (`classFactory`).
- `guia_de_campo.py`: ciclo de vida do plugin (menu, toolbar, abertura da janela).
- `guia_de_campo_dialog.py`: UI principal criada em codigo (sem dependencia de `.ui`).
- `guia_de_campo_service.py`: camada de servico que conecta eventos da UI com regras de negocio.
- `modules/canvas_marker_tool.py`: captura de clique no canvas, marcadores visuais, labels numericos e coordenadas WGS84.
- `modules/map_tools.py`: utilitarios de mapa (ex.: adicionar camada Google Hybrid).
- `modules/pdf/composer.py`: orquestracao da geracao de PDF sem acoplar regras em um unico arquivo.
- `modules/pdf/canvas_snapshot.py`: captura da visao atual do canvas para inserir no PDF.
- `modules/pdf/links.py`: geracao de links Google Maps por ponto e por rota (origem + paradas + destino).
- `modules/pdf/html_template.py`: template HTML com cards de rota e lista mobile-friendly de pontos.
- `modules/pdf/writer.py`: escrita de PDF usando Qt nativo (`QPrinter` + `QTextDocument`).
- `resources.py` / `resources.qrc`: recursos Qt (icone e afins).
- `metadata.txt`: metadados exigidos pelo QGIS Plugin Manager.

## Runtime Requirements

- QGIS LTR 3.x com Python embutido.
- Execucao dentro do ambiente do QGIS (imports `qgis.*` nao resolvem em interpretador Python externo).

## Local Dev Setup (Windows)

1. Clone ou copie o plugin para a pasta de plugins do perfil do QGIS.
2. Caminho comum no Windows:
	 `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\guia_de_campo`
3. Reinicie o QGIS ou use Plugin Reloader para recarregar durante desenvolvimento.
4. Ative o plugin em `Plugins > Manage and Install Plugins`.

## Feature Overview

### Marcar pontos no mapa

1. Abrir o plugin.
2. Marcar `Marcar no mapa (cliques multiplos)`.
3. Clicar no canvas para adicionar pontos.
4. Cada ponto:
	 - cria um marcador visual;
	 - cria um label numerico incremental com bom contraste;
	 - salva coordenadas em WGS84 (`EPSG:4326`).

### Limpar marcacoes

- Botao `Limpar marcacoes` remove marcadores, labels e coordenadas salvas.

### Remover ultima marcacao

- Botao `Remover ultima marcacao` desfaz apenas o ultimo ponto adicionado.
- Mantem os demais pontos no mapa e na lista de coordenadas.

### Inserir coordenadas manualmente

1. Preencher `Latitude` e `Longitude` na secao `Adicionar coordenada manual (WGS84)`.
2. Clicar em `Adicionar coordenada`.
3. O plugin valida formato decimal e limites WGS84:
	- latitude entre -90 e 90;
	- longitude entre -180 e 180.
4. Em caso valido, o ponto e adicionado com marcador e numeracao no mapa, igual aos pontos por clique.
5. Em caso invalido, o ponto e bloqueado e uma mensagem de aviso e exibida.

### Exportar pontos para CSV

- Botao `Exportar pontos CSV` salva os pontos atuais em arquivo `.csv`.
- O caminho inicial de salvamento abre na pasta Downloads do sistema (quando disponivel).
- Estrutura exportada:
	- `ordem`: sequencia de captura do ponto;
	- `longitude`: coordenada WGS84 em decimal;
	- `latitude`: coordenada WGS84 em decimal.
- O export so e realizado quando ha ao menos 1 ponto marcado.

### Importar pontos de CSV

- Botao `Importar pontos CSV` permite carregar pontos de um arquivo `.csv`.
- O CSV deve conter cabecalho com as colunas `longitude` e `latitude`.
- O plugin aceita decimal com `.` ou `,`.
- Validacoes aplicadas na importacao:
	- latitude entre -90 e 90;
	- longitude entre -180 e 180.
- Linhas invalidas sao ignoradas e o plugin exibe resumo com pontos importados e linhas ignoradas.
- Pontos validos importados sao desenhados no mapa com numeracao sequencial, igual aos pontos capturados por clique.

### Gerar PDF

- Botao `Gerar PDF` abre o seletor de arquivo para salvar o relatorio.
- O caminho inicial de salvamento abre na pasta Downloads do sistema (quando disponivel).
- O PDF inclui:
	- screenshot da visao atual do canvas (com marcacoes visiveis);
	- link(s) de rota no Google Maps usando os pontos em ordem de captura;
	- lista numerada de pontos em WGS84;
	- links clicaveis grandes por ponto para Google Maps (`https://maps.google.com/?q=lat,lon`) com foco em uso mobile.
- O metodo interno ainda pode manter o nome `generate_pfd` por compatibilidade de integracao, mas a funcionalidade agora e PDF real.

### Abrir rota no Google Maps

- Botao `Abrir rota no Google Maps` abre navegacao com todos os pontos como paradas, respeitando a ordem de captura.
- Para muitos pontos, o plugin divide automaticamente em trechos para evitar falhas de abertura por limite de URL/paradas.

### Limites praticos de rota (Google Maps)

- Fluxo comum mobile: ate cerca de 9 paradas intermediarias por URL (com origem e destino).
- Fluxo comum desktop/web: pode suportar mais paradas, mas varia por cliente e tamanho da URL.
- Estrategia do plugin: usar divisao automatica em trechos para manter confiabilidade entre dispositivos.

### Camada Google Hybrid

- Botao `Adicionar Google Hybrid` chama `hybrid_function` em `modules/map_tools.py`.

## Development Notes

- Prefira manter logica de mapa em `modules/` e deixar `guia_de_campo_service.py` como orquestrador.
- Para novas acoes de UI:
	1. adicionar controle no dialogo;
	2. adicionar metodo no service;
	3. conectar sinal no `run()` de `guia_de_campo.py` (apenas uma vez).
- Evite acoplar logica pesada diretamente no dialogo.

## Debugging

- Use o `Python Console` do QGIS para verificar saidas de `print`.
- Mensagens de fluxo para usuario final devem usar `iface.messageBar().pushMessage(...)`.
- Se o plugin falhar ao carregar, verificar:
	- imports em `modules/`;
	- erros de identacao em Python;
	- stack trace no painel de erros do QGIS.

## Suggested Next Improvements

- Suportar outros formatos de intercambio alem do CSV (ex.: GeoJSON).
- Adicionar testes basicos para funcoes de transformacao e limpeza de estado.
