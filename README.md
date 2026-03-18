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

### Gerar PFD (debug)

- Botao `Gerar PFD` imprime as coordenadas salvas no console Python do QGIS.
- Observacao: nome atual do metodo/acao esta como `PFD` para manter compatibilidade com o estado atual da UI.

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

- Renomear `Gerar PFD` para `Gerar PDF` (UI + metodo) quando quiser limpar nomenclatura.
- Persistir coordenadas em arquivo (CSV/GeoJSON) alem do console.
- Adicionar testes basicos para funcoes de transformacao e limpeza de estado.
