# GuiaDeCampo (QGIS Plugin)

Plugin for capturing map points, storing WGS84 coordinates, and providing automation for field workflows.

## Developer Instructions

## Project Structure

- `__init__.py`: QGIS plugin entrypoint (`classFactory`).
- `guia_de_campo.py`: plugin lifecycle (menu, toolbar, window startup).
- `guia_de_campo_dialog.py`: main UI built in code (no `.ui` dependency).
- `guia_de_campo_service.py`: service layer connecting UI events to business rules.
- `modules/canvas_marker_tool.py`: canvas click capture, visual markers, numeric labels, and WGS84 coordinates.
- `modules/map_tools.py`: map utilities (for example, adding Google Hybrid layer).
- `modules/pdf/composer.py`: PDF generation orchestration without concentrating rules in a single file.
- `modules/pdf/canvas_snapshot.py`: captures current canvas view for PDF insertion.
- `modules/pdf/links.py`: generates Google Maps links per point and per route (origin + stops + destination).
- `modules/pdf/html_template.py`: HTML template with route cards and mobile-friendly point list.
- `modules/pdf/writer.py`: PDF writing using native Qt (`QPrinter` + `QTextDocument`).
- `resources.py` / `resources.qrc`: Qt resources (icon and related assets).
- `metadata.txt`: metadata required by QGIS Plugin Manager.

## Runtime Requirements

- QGIS LTR 3.x with embedded Python.
- Must run inside QGIS environment (`qgis.*` imports do not resolve in an external Python interpreter).

## Local Dev Setup (Windows)

1. Clone or copy the plugin to the QGIS profile plugins folder.
2. Common path on Windows:
	 `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\guia_de_campo`
3. Restart QGIS or use Plugin Reloader to reload during development.
4. Enable the plugin in `Plugins > Manage and Install Plugins`.

## Feature Overview

### Mark points on the map

1. Open the plugin.
2. Enable `Mark on map (multiple clicks)`.
3. Click the canvas to add points.
4. Each point:
	 - creates a visual marker;
	 - creates an incremental numeric label with good contrast;
	 - stores WGS84 coordinates (`EPSG:4326`).

### Clear marks

- `Clear marks` button removes markers, labels, and stored coordinates.

### Remove last mark

- `Remove last mark` button undoes only the last added point.
- Keeps all previous points on the map and in the coordinate list.

### Add coordinates manually

1. Fill `Latitude` and `Longitude` in the `Add manual coordinate (WGS84)` section.
2. Click `Add coordinate`.
3. The plugin validates decimal format and WGS84 limits:
	- latitude between -90 and 90;
	- longitude between -180 and 180.
4. When valid, the point is added with marker and numbering on the map, same as click-based points.
5. When invalid, the point is blocked and a warning message is displayed.

### Export points to CSV

- `Export points CSV` button saves current points to a `.csv` file.
- Initial save path opens in system Downloads folder (when available).
- Exported structure:
	- `order`: point capture sequence;
	- `longitude`: WGS84 decimal coordinate;
	- `latitude`: WGS84 decimal coordinate.
- Export runs only when at least 1 point exists.

### Import points from CSV

- `Import points CSV` button loads points from a `.csv` file.
- CSV must contain a header with `longitude` and `latitude` columns.
- Plugin accepts decimal values with `.` or `,`.
- Import validations:
	- latitude between -90 and 90;
	- longitude between -180 and 180.
- Invalid rows are skipped and the plugin shows a summary with imported points and ignored rows.
- Valid imported points are drawn on the map with sequential numbering, same as click-captured points.

### Generate PDF

- `Generate PDF` button opens file picker to save the report.
- Initial save path opens in system Downloads folder (when available).
- PDF includes:
	- screenshot of current canvas view (with visible marks);
	- Google Maps route link(s) using points in capture order;
	- numbered WGS84 points list;
	- large tappable per-point Google Maps links (`https://maps.google.com/?q=lat,lon`) optimized for mobile usage.
- Internal method may still keep the name `generate_pfd` for integration compatibility, but functionality is real PDF generation.

### Open route in Google Maps

- `Open route in Google Maps` button opens navigation with all points as stops, preserving capture order.
- For many points, plugin automatically splits route into segments to avoid URL/stop-limit opening failures.

### Practical route limits (Google Maps)

- Common mobile flow: up to around 9 intermediate stops per URL (with origin and destination).
- Common desktop/web flow: may support more stops, but depends on client and URL length.
- Plugin strategy: automatic segmentation into route chunks for reliability across devices.

### Google Hybrid layer

- `Add Google Hybrid` button calls `hybrid_function` in `modules/map_tools.py`.

## Development Notes

- Prefer keeping map logic in `modules/` and using `guia_de_campo_service.py` as orchestrator.
- For new UI actions:
	1. add control in dialog;
	2. add method in service;
	3. connect signal in `run()` of `guia_de_campo.py` (only once).
- Avoid coupling heavy logic directly in dialog class.

## Debugging

- Use QGIS `Python Console` to inspect `print` outputs.
- User-facing flow messages should use `iface.messageBar().pushMessage(...)`.
- If plugin fails to load, check:
	- imports in `modules/`;
	- Python indentation errors;
	- stack trace in QGIS error panel.

## Suggested Next Improvements

- Support other exchange formats beyond CSV (for example, GeoJSON).
- Add basic tests for transformation and state cleanup functions.
