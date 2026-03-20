"""Build map links and point rows for PDF rendering."""

from urllib.parse import quote


def format_coordinate(value):
    """Return a fixed precision coordinate string."""
    return "{:.6f}".format(value)


def build_google_maps_url(latitude, longitude):
    """Create a robust mobile-friendly Google Maps destination URL."""
    return "https://maps.google.com/?q={},{}".format(
        format_coordinate(latitude),
        format_coordinate(longitude),
    )


def build_google_maps_directions_url(coordinates, travel_mode="driving"):
    """Create a Google Maps directions URL using ordered points as stops.

    Expects coordinates in (longitude, latitude) tuples.
    """
    if len(coordinates) < 2:
        raise ValueError("Sao necessarios ao menos 2 pontos para montar rota.")

    def pair(longitude, latitude):
        return "{},{}".format(
            format_coordinate(latitude),
            format_coordinate(longitude),
        )

    origin = pair(coordinates[0][0], coordinates[0][1])
    destination = pair(coordinates[-1][0], coordinates[-1][1])
    url = (
        "https://www.google.com/maps/dir/?api=1&travelmode={mode}"
        "&origin={origin}&destination={destination}"
    ).format(
        mode=quote(travel_mode, safe=""),
        origin=quote(origin, safe=","),
        destination=quote(destination, safe=","),
    )

    waypoints = [pair(lon, lat) for lon, lat in coordinates[1:-1]]
    if waypoints:
        waypoints_value = "|".join(waypoints)
        url = "{}&waypoints={}".format(url, quote(waypoints_value, safe=",|"))

    return url


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
