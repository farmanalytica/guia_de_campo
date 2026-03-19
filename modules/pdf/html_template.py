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
        .content {{ padding: 12px 14px 14px 14px; }}
        h2 {{ font-size: 17pt; margin: 0 0 8px 0; }}
        .meta {{ font-size: 10pt; color: #444; margin: 0 0 18px 0; }}
        .mark-list {{ list-style: none; padding: 0; margin: 0; }}
        .mark-item {{ margin: 0 0 28px 0; page-break-inside: avoid; }}
        .mark-link {{
          display: block;
          text-decoration: none;
          color: #0f172a;
          border: 2px solid #0b3f75;
          border-bottom-width: 5px;
          background: #fefefe;
          border-radius: 14px;
          padding: 22px 20px;
          min-height: 120px;
        }}
        .title {{ display: block; font-size: 17pt; font-weight: bold; margin-bottom: 10px; }}
        .coords {{ display: block; font-size: 12pt; color: #1f2937; margin-bottom: 16px; }}
        .action {{
          display: inline-block;
          font-size: 13pt;
          font-weight: bold;
          color: #ffffff;
          background: #0b4a8b;
          border: 1px solid #08345f;
          border-radius: 9px;
          padding: 8px 14px;
        }}
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
