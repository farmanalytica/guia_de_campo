"""Build map links and point rows for PDF rendering."""


def format_coordinate(value):
    """Return a fixed precision coordinate string."""
    return "{:.6f}".format(value)


def build_google_maps_url(latitude, longitude):
    """Create a robust mobile-friendly Google Maps destination URL."""
    return "https://maps.google.com/?q={},{}".format(
        format_coordinate(latitude),
        format_coordinate(longitude),
    )


def build_mark_items(coordinates):
    """Transform (lon, lat) tuples into display rows used by the HTML template."""
    marks = []
    for index, (longitude, latitude) in enumerate(coordinates, start=1):
        marks.append(
            {
                "index": index,
                "latitude": format_coordinate(latitude),
                "longitude": format_coordinate(longitude),
                "url": build_google_maps_url(latitude, longitude),
            }
        )
    return marks
