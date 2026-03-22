from qgis.core import Qgis
from qgis.PyQt.QtCore import QStandardPaths, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QFileDialog

import csv
import os

from .modules.canvas_marker_tool import CanvasMarkerTool
from .modules.map_tools import hybrid_function
from .modules.pdf.links import build_google_maps_directions_url
from .modules.pdf import PdfReportComposer


class GuiaDeCampoService:
    """Application service that orchestrates dialog actions and map tools."""

    MAX_POINTS_PER_GOOGLE_ROUTE = 10

    def __init__(self, iface):
        """Initialize services that require access to QGIS interface."""
        self.iface = iface
        self.marker_tool = CanvasMarkerTool(self.iface)
        self.pdf_composer = PdfReportComposer(self.iface)

    def toggle_mark_mode(self, enabled):
        """Enable or disable interactive point capture from the checkbox."""
        if enabled:
            self.marker_tool.enable()
        else:
            self.marker_tool.disable()

    def disable_mark_mode(self):
        """Force capture mode off, typically when dialog closes."""
        self.marker_tool.disable()

    def on_dialog_button_clicked(self, button_name):
        """Handle both button-box actions with a single, consistent summary."""
        self.disable_mark_mode()
        n = len(self.marker_tool.coordinates)
        if button_name == 'ok':
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Ação confirmada. {} ponto(s) capturado(s).'.format(n),
                level=Qgis.Info,
                duration=3,
            )
            return

        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            'Ação cancelada. {} ponto(s) capturado(s).'.format(n),
            level=Qgis.Warning,
            duration=3,
        )

    def clear_marks(self):
        """Remove all map marks and reset stored coordinate state."""
        n = len(self.marker_tool.coordinates)
        self.marker_tool.clear()
        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            '{} marcação(ões) removida(s).'.format(n),
            level=Qgis.Info,
            duration=3,
        )

    def remove_last_mark(self):
        """Remove only the most recently captured map mark."""
        removed = self.marker_tool.remove_last()
        if not removed:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Nenhuma marcação para remover.',
                level=Qgis.Warning,
                duration=3,
            )
            return

        n = len(self.marker_tool.coordinates)
        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            'Última marcação removida. {} ponto(s) restante(s).'.format(n),
            level=Qgis.Info,
            duration=3,
        )

    def add_hybrid_layer(self):
        """Call map_tools.hybrid_function and show feedback in QGIS."""
        try:
            hybrid_function()
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Comando de camada Google Hybrid executado.',
                level=Qgis.Info,
                duration=3,
            )
        except Exception as exc:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Erro ao adicionar Google Hybrid: {}'.format(exc),
                level=Qgis.Critical,
                duration=5,
            )

    def _iter_route_batches(self, coordinates):
        """Yield route chunks with overlap so segment continuity is preserved."""
        max_points = self.MAX_POINTS_PER_GOOGLE_ROUTE
        if len(coordinates) <= max_points:
            yield coordinates
            return

        start = 0
        while start < len(coordinates) - 1:
            end = min(start + max_points, len(coordinates))
            yield coordinates[start:end]
            if end >= len(coordinates):
                break
            start = end - 1

    def open_all_points_route(self):
        """Open Google Maps directions using all captured points as ordered stops."""
        coordinates = self.marker_tool.coordinates
        if len(coordinates) < 2:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Adicione ao menos 2 pontos para abrir rota no Google Maps.',
                level=Qgis.Warning,
                duration=4,
            )
            return

        route_urls = []
        try:
            for batch in self._iter_route_batches(coordinates):
                route_urls.append(build_google_maps_directions_url(batch))
        except Exception as exc:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Nao foi possivel montar a rota: {}'.format(exc),
                level=Qgis.Critical,
                duration=5,
            )
            return

        opened_count = 0
        for url in route_urls:
            if QDesktopServices.openUrl(QUrl(url)):
                opened_count += 1

        if opened_count == 0:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Nao foi possivel abrir a rota no Google Maps.',
                level=Qgis.Warning,
                duration=4,
            )
            return

        if len(route_urls) == 1:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Rota aberta no Google Maps com {} ponto(s).'.format(len(coordinates)),
                level=Qgis.Success,
                duration=4,
            )
            return

        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            'Rota grande dividida em {} trechos no Google Maps.'.format(opened_count),
            level=Qgis.Info,
            duration=5,
        )

    def add_manual_coordinate(self, dialog):
        """Validate manual decimal WGS84 input and create a numbered map point."""
        latitude_text = dialog.manual_latitude_input.text().strip()
        longitude_text = dialog.manual_longitude_input.text().strip()

        if not latitude_text or not longitude_text:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Preencha latitude e longitude para adicionar a coordenada manual.',
                level=Qgis.Warning,
                duration=4,
            )
            return

        try:
            latitude = self._parse_decimal(latitude_text)
            longitude = self._parse_decimal(longitude_text)
        except ValueError:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Coordenadas inválidas. Use formato decimal (ex.: -23.550520).',
                level=Qgis.Warning,
                duration=4,
            )
            return

        if latitude < -90 or latitude > 90:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Latitude fora do intervalo permitido (-90 a 90).',
                level=Qgis.Warning,
                duration=4,
            )
            return

        if longitude < -180 or longitude > 180:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Longitude fora do intervalo permitido (-180 a 180).',
                level=Qgis.Warning,
                duration=4,
            )
            return

        try:
            self.marker_tool.add_wgs84_point(latitude, longitude)
        except Exception as exc:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Erro ao adicionar coordenada manual: {}'.format(exc),
                level=Qgis.Critical,
                duration=5,
            )
            return

        dialog.manual_latitude_input.clear()
        dialog.manual_longitude_input.clear()
        dialog.manual_latitude_input.setFocus()

    def _parse_decimal(self, value):
        """Parse decimal coordinate text, accepting comma or dot separators."""
        normalized = value.replace(',', '.')
        return float(normalized)

    def export_marks_csv(self):
        """Export captured WGS84 points to a CSV file (longitude, latitude)."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Nao ha pontos para exportar.',
                level=Qgis.Warning,
                duration=4,
            )
            return

        download_dir = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        default_csv_path = os.path.join(download_dir, 'guia_de_campo_pontos.csv') if download_dir else 'guia_de_campo_pontos.csv'

        output_path, _ = QFileDialog.getSaveFileName(
            None,
            'Salvar pontos em CSV',
            default_csv_path,
            'CSV Files (*.csv)',
        )
        if not output_path:
            return

        try:
            with open(output_path, mode='w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(['ordem', 'longitude', 'latitude'])
                for index, (longitude, latitude) in enumerate(coordinates, start=1):
                    writer.writerow([index, '{:.8f}'.format(longitude), '{:.8f}'.format(latitude)])
        except Exception as exc:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Erro ao exportar CSV: {}'.format(exc),
                level=Qgis.Critical,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            'CSV exportado com sucesso: {}'.format(output_path),
            level=Qgis.Success,
            duration=5,
        )

    def import_marks_csv(self):
        """Import WGS84 points from CSV and draw them on the map canvas."""
        input_path, _ = QFileDialog.getOpenFileName(
            None,
            'Importar pontos CSV',
            '',
            'CSV Files (*.csv);;All Files (*)',
        )
        if not input_path:
            return

        imported_count = 0
        skipped_count = 0

        try:
            with open(input_path, mode='r', newline='', encoding='utf-8-sig') as csv_file:
                reader = csv.DictReader(csv_file)

                if not reader.fieldnames:
                    raise ValueError('Arquivo CSV sem cabecalho.')

                fieldnames = [name.strip().lower() for name in reader.fieldnames]
                has_required_columns = 'longitude' in fieldnames and 'latitude' in fieldnames
                if not has_required_columns:
                    raise ValueError('Cabecalho deve conter colunas longitude e latitude.')

                longitude_key = reader.fieldnames[fieldnames.index('longitude')]
                latitude_key = reader.fieldnames[fieldnames.index('latitude')]

                for row in reader:
                    try:
                        longitude = self._parse_decimal(str(row.get(longitude_key, '')).strip())
                        latitude = self._parse_decimal(str(row.get(latitude_key, '')).strip())
                    except (TypeError, ValueError):
                        skipped_count += 1
                        continue

                    if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
                        skipped_count += 1
                        continue

                    self.marker_tool.add_wgs84_point(latitude, longitude)
                    imported_count += 1
        except Exception as exc:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Erro ao importar CSV: {}'.format(exc),
                level=Qgis.Critical,
                duration=6,
            )
            return

        if imported_count == 0:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Nenhum ponto valido encontrado no CSV.',
                level=Qgis.Warning,
                duration=5,
            )
            return

        if skipped_count > 0:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                '{} ponto(s) importado(s); {} linha(s) ignorada(s).'.format(imported_count, skipped_count),
                level=Qgis.Info,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            '{} ponto(s) importado(s) com sucesso.'.format(imported_count),
            level=Qgis.Success,
            duration=5,
        )

    def generate_pfd(self):
        """Generate PDF report with current canvas screenshot and map links."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Nenhum ponto marcado. Adicione pontos no mapa antes de gerar o PDF.',
                level=Qgis.Warning,
                duration=4,
            )
            return

        download_dir = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        default_pdf_path = os.path.join(download_dir, 'guia_de_campo.pdf') if download_dir else 'guia_de_campo.pdf'

        output_path, _ = QFileDialog.getSaveFileName(
            None,
            'Salvar PDF da Guia de Campo',
            default_pdf_path,
            'PDF Files (*.pdf)',
        )
        if not output_path:
            return

        try:
            final_path = self.pdf_composer.generate(coordinates, output_path)
        except Exception as exc:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'Erro ao gerar PDF: {}'.format(exc),
                level=Qgis.Critical,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            'Guia de Campo',
            'PDF gerado com sucesso: {}'.format(final_path),
            level=Qgis.Success,
            duration=5,
        )

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(final_path))
        if not opened:
            self.iface.messageBar().pushMessage(
                'Guia de Campo',
                'PDF salvo, mas nao foi possivel abrir automaticamente.',
                level=Qgis.Warning,
                duration=4,
            )
