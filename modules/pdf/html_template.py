"""HTML template used to render Guia de Campo PDF output."""

from datetime import datetime


def build_points_html(mark_items):
    """Build styled HTML for clickable point list pages (starts on page 2)."""
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    items_html = []
    for item in mark_items:
        items_html.append(
            """
            <li class=\"mark-item\">
                <a href=\"{url}\" class=\"mark-link\">
                    <span class=\"title\">Ponto {index}</span>
                    <span class=\"coords\">Lat: {lat} | Lon: {lon}</span>
                    <span class=\"action\">Abrir no Google Maps</span>
                </a>
            </li>
            """.format(
                index=item["index"],
                lat=item["latitude"],
                lon=item["longitude"],
                url=item["url"],
            )
        )

    return """
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <style>
        body {{ font-family: Arial, sans-serif; color: #111; margin: 0; padding: 0; }}
        .content {{ padding: 8px 12px 12px 12px; }}
        h2 {{ font-size: 14pt; margin: 0 0 8px 0; }}
        .meta {{ font-size: 10pt; color: #444; margin: 0 0 12px 0; }}
        .mark-list {{ list-style: none; padding: 0; margin: 0; }}
        .mark-item {{ margin: 0 0 10px 0; }}
        .mark-link {{
          display: block;
          text-decoration: none;
          color: #111;
          border: 1px solid #c7c7c7;
          background: #f7f7f7;
          border-radius: 8px;
          padding: 12px;
        }}
        .title {{ display: block; font-size: 13pt; font-weight: bold; margin-bottom: 4px; }}
        .coords {{ display: block; font-size: 11pt; margin-bottom: 6px; }}
        .action {{ display: block; font-size: 11pt; color: #0057a3; font-weight: bold; }}
      </style>
    </head>
    <body>
      <div class=\"content\">
        <h2>Lista de pontos (toque para abrir no celular)</h2>
        <p class=\"meta\">Gerado em: {generated_at} | Total de pontos: {total}</p>
        <ul class=\"mark-list\">{items}</ul>
      </div>
    </body>
    </html>
    """.format(
        generated_at=generated_at,
        total=len(mark_items),
        items="".join(items_html),
    )
