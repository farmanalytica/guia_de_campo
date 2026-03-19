"""Low-level PDF writer using Qt built-ins."""

import os

from qgis.PyQt import QtCore, QtGui, QtPrintSupport


def _create_printer(output_path):
    """Create an A4 landscape PDF printer configured for edge-to-edge content."""
    printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
    printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
    printer.setOutputFileName(output_path)
    printer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.A4))
    printer.setOrientation(QtPrintSupport.QPrinter.Landscape)
    # Use the full PDF page area; margins are controlled by document CSS instead.
    printer.setFullPage(True)
    printer.setPageMargins(
        10,
        10,
        10,
        10,
        QtPrintSupport.QPrinter.Millimeter,
    )
    return printer


def _fit_rect_inside(source_width, source_height, target_rect):
    """Return a centered rect that fits source into target while preserving aspect ratio."""
    if source_width <= 0 or source_height <= 0:
        return QtCore.QRectF(target_rect)

    scale_x = float(target_rect.width()) / float(source_width)
    scale_y = float(target_rect.height()) / float(source_height)
    scale = min(scale_x, scale_y)

    draw_width = source_width * scale
    draw_height = source_height * scale
    draw_x = target_rect.x() + (target_rect.width() - draw_width) / 2.0
    draw_y = target_rect.y() + (target_rect.height() - draw_height) / 2.0
    return QtCore.QRectF(draw_x, draw_y, draw_width, draw_height)


def write_report_to_pdf(snapshot_path, points_html, output_path):
    """Write report where page 1 is full canvas image and points start on page 2."""
    printer = _create_printer(output_path)

    image = QtGui.QImage(snapshot_path)
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise RuntimeError("Nao foi possivel carregar a imagem do mapa para o PDF.")

    page_rect = QtCore.QRectF(printer.paperRect(QtPrintSupport.QPrinter.DevicePixel))
    if page_rect.width() <= 0 or page_rect.height() <= 0:
        page_rect = QtCore.QRectF(printer.pageRect(QtPrintSupport.QPrinter.DevicePixel))

    text_page_rect = QtCore.QRectF(printer.paperRect(QtPrintSupport.QPrinter.Point))
    if text_page_rect.width() <= 0 or text_page_rect.height() <= 0:
        text_page_rect = QtCore.QRectF(printer.pageRect(QtPrintSupport.QPrinter.Point))

    scale_x = float(page_rect.width()) / float(text_page_rect.width()) if text_page_rect.width() > 0 else 1.0
    scale_y = float(page_rect.height()) / float(text_page_rect.height()) if text_page_rect.height() > 0 else 1.0

    painter = QtGui.QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Falha ao iniciar a escrita do PDF.")

    try:
        painter.fillRect(page_rect, QtGui.QColor("white"))
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        draw_rect = _fit_rect_inside(image.width(), image.height(), page_rect)
        painter.drawImage(draw_rect, image)

        # Force points to begin only on the second page.
        printer.newPage()

        document = QtGui.QTextDocument()
        document.setDocumentMargin(0)
        document.setPageSize(QtCore.QSizeF(text_page_rect.size()))
        document.setHtml(points_html)

        layout = document.documentLayout()
        page_height = text_page_rect.height()
        page_width = text_page_rect.width()
        total_height = document.size().height()
        page_count = int((total_height + page_height - 1) // page_height) if page_height > 0 else 1
        page_count = max(1, page_count)

        for page_index in range(page_count):
            if page_index > 0:
                printer.newPage()

            painter.save()
            painter.translate(page_rect.left(), page_rect.top())
            painter.scale(scale_x, scale_y)
            painter.translate(-text_page_rect.left(), -text_page_rect.top() - (page_index * page_height))

            context = QtGui.QAbstractTextDocumentLayout.PaintContext()
            context.clip = QtCore.QRectF(
                text_page_rect.left(),
                text_page_rect.top() + (page_index * page_height),
                page_width,
                page_height,
            )
            layout.draw(painter, context)
            painter.restore()
    finally:
        painter.end()

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Falha ao gravar o arquivo PDF no destino escolhido.")
