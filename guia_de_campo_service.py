from qgis.core import Qgis
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QFileDialog

from .modules.canvas_marker_tool import CanvasMarkerTool
from .modules.map_tools import hybrid_function
from .modules.pdf import PdfReportComposer


class GuiaDeCampoService:
    """Application service that orchestrates dialog actions and map tools."""

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

        output_path, _ = QFileDialog.getSaveFileName(
            None,
            'Salvar PDF da Guia de Campo',
            'guia_de_campo.pdf',
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
