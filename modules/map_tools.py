"""Map helper utilities used by the plugin service layer."""

from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsRasterLayer
from qgis.utils import iface


def hybrid_function():
    """Add Google Hybrid XYZ layer to the project when not already present."""
    existing_layers = QgsProject.instance().mapLayers().values()
    layer_names = [layer.name() for layer in existing_layers]
    if "Google Hybrid" in layer_names:
        print("Google Hybrid layer already added.")
        return

    google_hybrid_url = (
        "type=xyz&zmin=0&zmax=20&url="
        "https://mt1.google.com/vt/lyrs%3Dy%26x%3D{x}%26y%3D{y}%26z%3D{z}"
    )
    layer_name = "Google Hybrid"
    provider_type = "wms"

    try:
        google_hybrid_layer = QgsRasterLayer(google_hybrid_url, layer_name, provider_type)

        if not google_hybrid_layer.isValid():
            print("Failed to load {}. Invalid layer.".format(layer_name))
            return

        QgsProject.instance().addMapLayer(google_hybrid_layer, False)

        # Keep plugin behavior explicit by forcing a known geographic CRS.
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        QgsProject.instance().setCrs(crs_4326)

        google_hybrid_layer.setOpacity(1)
        root = QgsProject.instance().layerTreeRoot()
        root.addLayer(google_hybrid_layer)

        iface.mapCanvas().refresh()
        iface.mapCanvas().zoomToFullExtent()
        print("{} layer added successfully in EPSG:4326.".format(layer_name))
    except Exception as exc:
        print("Error loading {}: {}".format(layer_name, exc))
