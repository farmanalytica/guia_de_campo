"""Compose modular PDF generation steps for Guia de Campo."""

import os

from .canvas_snapshot import capture_canvas_snapshot
from .html_template import build_points_html
from .links import build_mark_items
from .writer import write_report_to_pdf


class PdfReportComposer:
    """Coordinate snapshot, link generation, template rendering, and PDF writing."""

    def __init__(self, iface):
        self.iface = iface

    def generate(self, coordinates, output_path):
        """Generate a PDF report from captured WGS84 coordinates."""
        if not coordinates:
            raise ValueError("Nao ha pontos marcados para gerar o PDF.")

        output_path = self._normalize_output_path(output_path)
        snapshot_path = None

        try:
            snapshot_path = capture_canvas_snapshot(
                self.iface.mapCanvas(),
            )
            mark_items = build_mark_items(coordinates)
            points_html = build_points_html(mark_items)
            write_report_to_pdf(snapshot_path, points_html, output_path)
        finally:
            self._cleanup_temp_file(snapshot_path)

        return output_path

    def _normalize_output_path(self, output_path):
        """Ensure destination uses the PDF extension."""
        if output_path.lower().endswith(".pdf"):
            return output_path
        return "{}.pdf".format(output_path)

    def _cleanup_temp_file(self, path):
        """Remove temporary snapshot file quietly after PDF generation."""
        if not path:
            return
        if not os.path.exists(path):
            return
        try:
            os.remove(path)
        except OSError:
            # Best effort cleanup only; failure should not abort user flow.
            pass

