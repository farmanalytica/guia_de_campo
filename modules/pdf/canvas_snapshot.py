"""Capture canvas snapshots for PDF embedding."""

import os
import tempfile


def capture_canvas_snapshot(canvas, max_width=None):
    """Capture current canvas view to a temporary PNG path."""
    temp = tempfile.NamedTemporaryFile(
        prefix="guia_de_campo_canvas_", suffix=".png", delete=False
    )
    temp_path = temp.name
    temp.close()

    # Use QGIS native export to capture the full map extent
    canvas.saveAsImage(temp_path, None, "PNG")
    
    # Check if file was created successfully
    if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
        raise RuntimeError("Nao foi possivel capturar a imagem atual do mapa.")

    return temp_path
