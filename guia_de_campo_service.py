from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QStandardPaths, QUrl, QVariant
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

import csv
import math
import os
import random
import traceback
import xml.etree.ElementTree as ET

from .modules.canvas_marker_tool import CanvasMarkerTool
from .modules.map_tools import hybrid_function
from .modules.pdf.links import build_google_maps_directions_url
from .modules.pdf import PdfReportComposer


def _qt_class_enum(qt_class, scoped_name, member_name, legacy_name):
    """Return a Qt5/Qt6 compatible enum member from a Qt class."""
    scoped_enum = getattr(qt_class, scoped_name, None)
    if scoped_enum is not None:
        return getattr(scoped_enum, member_name)
    return getattr(qt_class, legacy_name)


def _standard_location(member_name, legacy_name):
    """Return a QStandardPaths location enum compatible with Qt5 and Qt6."""
    return _qt_class_enum(QStandardPaths, 'StandardLocation', member_name, legacy_name)


def _message_box_enum(scoped_name, member_name, legacy_name):
    """Return a QMessageBox enum member compatible with Qt5 and Qt6."""
    return _qt_class_enum(QMessageBox, scoped_name, member_name, legacy_name)


def _message_box_exec(message_box):
    """Execute a QMessageBox across Qt5/Qt6 naming differences."""
    exec_method = getattr(message_box, 'exec', None)
    if callable(exec_method):
        return exec_method()
    return message_box.exec_()


class GuiaDeCampoService:
    """Application service that orchestrates dialog actions and map tools."""

    MAX_POINTS_PER_GOOGLE_ROUTE = 10
    MAX_MARKS_PER_FEATURE = 50
    FEATURE_SAMPLE_METHOD_SPREAD = 'spread_optimized'
    FEATURE_SAMPLE_METHOD_GRID = 'systematic_grid'
    FEATURE_SAMPLE_METHOD_ZIGZAG = 'zigzag_transect'
    FEATURE_SAMPLE_QUANTITY_FIXED = 'fixed_count'
    FEATURE_SAMPLE_QUANTITY_DENSITY = 'area_density'

    def __init__(self, iface, plugin_language='en'):
        """Initialize services that require access to QGIS interface."""
        self.iface = iface
        self.plugin_language = plugin_language
        self.project = QgsProject.instance()
        self.wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
        self.marker_tool = CanvasMarkerTool(self.iface, self.plugin_language)
        self.pdf_composer = PdfReportComposer(self.iface, self.plugin_language)
        self.dialog = None
        self.project.layersAdded.connect(self._on_project_layers_changed)
        self.project.layersRemoved.connect(self._on_project_layers_changed)

    def _t(self, english_text, portuguese_text):
        """Return pt-BR text only when plugin language is Portuguese."""
        if self.plugin_language == 'pt_BR':
            return portuguese_text
        return english_text

    def bind_dialog(self, dialog):
        """Keep dialog state synced with the current marker session."""
        self.dialog = dialog
        self.marker_tool.coordinates_changed.connect(self.dialog.set_points)
        self.dialog.set_points(self.marker_tool.coordinates)
        self.refresh_polygon_layers()

    def _on_project_layers_changed(self, *_args):
        """Refresh layer-dependent controls when the current project changes."""
        self.refresh_polygon_layers()

    def _is_polygon_vector_layer(self, layer):
        """Return True when the given project layer is a polygon vector layer."""
        return (
            layer is not None
            and hasattr(layer, 'wkbType')
            and QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PolygonGeometry
        )

    def _polygon_layers(self):
        """Return current project polygon layers ordered by display name."""
        layers = [
            layer
            for layer in self.project.mapLayers().values()
            if self._is_polygon_vector_layer(layer)
        ]
        return sorted(layers, key=lambda layer: layer.name().lower())

    def refresh_polygon_layers(self):
        """Sync the dialog selector with polygon layers from the project."""
        if self.dialog is None:
            return

        selected_layer_id = self.dialog.centroid_layer_combo.currentData()
        layer_options = [
            (layer.name(), layer.id())
            for layer in self._polygon_layers()
        ]
        self.dialog.set_polygon_layers(layer_options, selected_layer_id=selected_layer_id)

    def _selected_polygon_layer(self):
        """Return the currently selected polygon layer from the dialog."""
        if self.dialog is None:
            return None

        layer_id = self.dialog.centroid_layer_combo.currentData()
        if not layer_id:
            return None

        layer = self.project.mapLayer(layer_id)
        if not self._is_polygon_vector_layer(layer):
            return None
        return layer

    def _dialog_parent(self):
        """Return the best available parent widget for child dialogs."""
        if self.dialog is not None:
            return self.dialog
        return self.iface.mainWindow()

    def _default_output_path(self, filename):
        """Return a sensible default save path on both Qt5 and Qt6 builds."""
        download_dir = QStandardPaths.writableLocation(
            _standard_location('DownloadLocation', 'DownloadLocation')
        )
        if not download_dir:
            download_dir = QStandardPaths.writableLocation(
                _standard_location('DocumentsLocation', 'DocumentsLocation')
            )
        if not download_dir:
            return filename
        return os.path.join(download_dir, filename)

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
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Action confirmed. {} point(s) captured.'.format(n),
                    'Acao confirmada. {} ponto(s) capturado(s).'.format(n),
                ),
                level=Qgis.Info,
                duration=3,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                'Action canceled. {} point(s) captured.'.format(n),
                'Acao cancelada. {} ponto(s) capturado(s).'.format(n),
            ),
            level=Qgis.Warning,
            duration=3,
        )

    def clear_marks(self):
        """Remove all map marks and reset stored coordinate state."""
        n = len(self.marker_tool.coordinates)
        if n == 0:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('No marks to clear.', 'Nenhuma marcacao para limpar.'),
                level=Qgis.Warning,
                duration=3,
            )
            return

        if n > 3:
            yes_button = _message_box_enum('StandardButton', 'Yes', 'Yes')
            no_button = _message_box_enum('StandardButton', 'No', 'No')
            confirmation = QMessageBox.question(
                self._dialog_parent(),
                self._t('Clear marks', 'Limpar marcações'),
                self._t(
                    'Clear all {} captured point(s)?'.format(n),
                    'Limpar todos os {} ponto(s) capturados?'.format(n),
                ),
                yes_button | no_button,
                no_button,
            )
            if confirmation != yes_button:
                return

        self.marker_tool.clear()
        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                '{} mark(s) removed.'.format(n),
                '{} marcacao(oes) removida(s).'.format(n),
            ),
            level=Qgis.Info,
            duration=3,
        )

    def remove_last_mark(self):
        """Remove only the most recently captured map mark."""
        removed = self.marker_tool.remove_last()
        if not removed:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('No marks to remove.', 'Nenhuma marcacao para remover.'),
                level=Qgis.Warning,
                duration=3,
            )
            return

        n = len(self.marker_tool.coordinates)
        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                'Last mark removed. {} point(s) remaining.'.format(n),
                'Ultima marcacao removida. {} ponto(s) restante(s).'.format(n),
            ),
            level=Qgis.Info,
            duration=3,
        )

    def remove_selected_mark(self):
        """Remove the point selected in the session list, keeping order consistent."""
        selected_index = -1
        if self.dialog is not None:
            selected_index = self.dialog.selected_point_index()

        if selected_index < 0:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Select a mark in the session list to delete it.',
                    'Selecione uma marcação na lista da sessão para excluí-la.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        removed_point_number = selected_index + 1
        removed = self.marker_tool.remove_at(selected_index)
        if not removed:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Unable to delete the selected mark.',
                    'Não foi possível excluir a marcação selecionada.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        remaining_points = len(self.marker_tool.coordinates)
        if self.dialog is not None:
            self.dialog.select_point_index(min(selected_index, remaining_points - 1))

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                'Point {} deleted. {} point(s) remaining.'.format(
                    removed_point_number,
                    remaining_points,
                ),
                'Ponto {} excluido. {} ponto(s) restante(s).'.format(
                    removed_point_number,
                    remaining_points,
                ),
            ),
            level=Qgis.Info,
            duration=4,
        )

    def add_hybrid_layer(self):
        """Call map_tools.hybrid_function and show feedback in QGIS."""
        try:
            hybrid_function()
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Google Hybrid layer command executed.',
                    'Comando de camada Google Hybrid executado.',
                ),
                level=Qgis.Info,
                duration=3,
            )
        except Exception:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Error adding Google Hybrid.',
                    'Erro ao adicionar Google Hybrid.',
                ),
                level=Qgis.Critical,
                duration=5,
            )

    def mark_selected_layer_centroids(self):
        """Place one or more sample marks for every feature in the selected layer."""
        layer = self._selected_polygon_layer()
        if layer is None:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Select a polygon layer from the current project first.',
                    'Selecione primeiro uma camada poligonal do projeto atual.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        sampling_settings = self._selected_feature_sampling_settings()
        action_title = self._polygon_sampling_action_title(sampling_settings)

        try:
            sampled_points, skipped_count = self._extract_layer_sample_points(
                layer,
                sampling_settings,
            )
        except Exception:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Error generating marks from layer {}.'.format(layer.name()),
                    'Erro ao gerar marcações da camada {}.'.format(layer.name()),
                ),
                level=Qgis.Critical,
                duration=6,
            )
            return

        if not sampled_points:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'No valid sample marks found in layer {}.'.format(layer.name()),
                    'Nenhuma marcação válida encontrada na camada {}.'.format(layer.name()),
                ),
                level=Qgis.Warning,
                duration=5,
            )
            return

        merge_mode = 'append'
        existing_points = len(self.marker_tool.coordinates)
        if existing_points > 0:
            merge_mode = self._choose_points_merge_mode(
                existing_points,
                action_title,
                self._t(
                    'Choose whether to append the generated marks or replace the current list.',
                    'Escolha se deseja adicionar as marcações geradas ou substituir a lista atual.',
                ),
            )
            if merge_mode is None:
                return

        if merge_mode == 'replace':
            self.marker_tool.clear()

        self.marker_tool.add_wgs84_points(sampled_points)

        points_label = self._sampling_points_label(sampling_settings)
        method_label = self._sampling_method_label(sampling_settings)
        sampled_point_count = len(sampled_points)

        if skipped_count > 0:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    '{} {} added from {} using {}; {} feature(s) skipped.'.format(
                        sampled_point_count,
                        points_label,
                        layer.name(),
                        method_label,
                        skipped_count,
                    ),
                    '{} {} adicionada(s) de {} usando {}; {} feição(ões) ignorada(s).'.format(
                        sampled_point_count,
                        points_label,
                        layer.name(),
                        method_label,
                        skipped_count,
                    ),
                ),
                level=Qgis.Info,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                '{} {} added from {} using {}.'.format(
                    sampled_point_count,
                    points_label,
                    layer.name(),
                    method_label,
                ),
                '{} {} adicionada(s) de {} usando {}.'.format(
                    sampled_point_count,
                    points_label,
                    layer.name(),
                    method_label,
                ),
            ),
            level=Qgis.Success,
            duration=5,
        )

    def _selected_feature_sampling_settings(self):
        """Return the current polygon sampling quantity and distribution settings."""
        quantity_mode = self.FEATURE_SAMPLE_QUANTITY_FIXED
        sample_count = 1
        hectares_per_mark = 1.0
        distribution_method = self.FEATURE_SAMPLE_METHOD_SPREAD

        if self.dialog is not None:
            quantity_mode = self.dialog.sample_quantity_mode()
            sample_count = self.dialog.sample_count_per_feature()
            hectares_per_mark = self.dialog.sample_density_hectares()
            distribution_method = self.dialog.sample_distribution_method()

        if quantity_mode not in {
            self.FEATURE_SAMPLE_QUANTITY_FIXED,
            self.FEATURE_SAMPLE_QUANTITY_DENSITY,
        }:
            quantity_mode = self.FEATURE_SAMPLE_QUANTITY_FIXED
        sample_count = max(1, min(self.MAX_MARKS_PER_FEATURE, int(sample_count)))
        hectares_per_mark = max(0.1, float(hectares_per_mark))

        valid_methods = {
            self.FEATURE_SAMPLE_METHOD_SPREAD,
            self.FEATURE_SAMPLE_METHOD_GRID,
            self.FEATURE_SAMPLE_METHOD_ZIGZAG,
        }
        if distribution_method not in valid_methods:
            distribution_method = self.FEATURE_SAMPLE_METHOD_SPREAD
        if quantity_mode == self.FEATURE_SAMPLE_QUANTITY_FIXED and sample_count == 1:
            distribution_method = 'centroid'
        return {
            'quantity_mode': quantity_mode,
            'sample_count': sample_count,
            'hectares_per_mark': hectares_per_mark,
            'distribution_method': distribution_method,
        }

    def _polygon_sampling_action_title(self, sampling_settings):
        """Return a context-appropriate title for polygon sampling actions."""
        if (
            sampling_settings['quantity_mode'] == self.FEATURE_SAMPLE_QUANTITY_FIXED
            and sampling_settings['sample_count'] == 1
        ):
            return self._t('Mark feature centroids', 'Marcar centroides da camada')
        return self._t('Mark feature samples', 'Marcar amostras da camada')

    def _format_density_value(self, value):
        """Return a compact numeric label for hectares-per-mark values."""
        return '{:g}'.format(round(float(value), 2))

    def _sampling_method_label(self, sampling_settings):
        """Return a localized label for the currently selected sampling method."""
        distribution_method = sampling_settings['distribution_method']
        quantity_mode = sampling_settings['quantity_mode']
        sample_count = sampling_settings['sample_count']

        if (
            (
                quantity_mode == self.FEATURE_SAMPLE_QUANTITY_FIXED
                and sample_count == 1
            )
            or distribution_method == 'centroid'
        ):
            return self._t('centroid', 'centroide')

        if distribution_method == self.FEATURE_SAMPLE_METHOD_GRID:
            base_label = self._t('systematic grid', 'grade sistematica')
        elif distribution_method == self.FEATURE_SAMPLE_METHOD_ZIGZAG:
            base_label = self._t('zigzag transect', 'transecto em zig-zag')
        else:
            base_label = self._t('spread optimized', 'otimizado por distribuição')

        if quantity_mode == self.FEATURE_SAMPLE_QUANTITY_DENSITY:
            density_label = self._format_density_value(sampling_settings['hectares_per_mark'])
            return self._t(
                '{} at 1 mark per {} ha'.format(base_label, density_label),
                '{} em 1 marcação a cada {} ha'.format(base_label, density_label),
            )
        return base_label

    def _sampling_points_label(self, sampling_settings):
        """Return a localized label for the generated mark type."""
        if (
            sampling_settings['quantity_mode'] == self.FEATURE_SAMPLE_QUANTITY_FIXED
            and (
                sampling_settings['sample_count'] == 1
                or sampling_settings['distribution_method'] == 'centroid'
            )
        ):
            return self._t('centroid mark(s)', 'marcação(ões) de centroide')
        return self._t('sample mark(s)', 'marcação(ões) de amostra')

    def _extract_layer_sample_points(self, layer, sampling_settings):
        """Return WGS84 sample marks for each feature in the selected polygon layer."""
        sampled_points = []
        skipped_count = 0
        transform = QgsCoordinateTransform(layer.crs(), self.wgs84, self.project)
        area_measure = None
        if sampling_settings['quantity_mode'] == self.FEATURE_SAMPLE_QUANTITY_DENSITY:
            area_measure = self._build_area_measure(layer)

        for feature in layer.getFeatures():
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                skipped_count += 1
                continue

            try:
                feature_sample_count = self._feature_sample_count(
                    geometry,
                    sampling_settings,
                    area_measure=area_measure,
                )
                feature_points = self._build_feature_sample_points(
                    layer,
                    feature,
                    geometry,
                    feature_sample_count,
                    sampling_settings['distribution_method'],
                )
            except Exception:
                skipped_count += 1
                continue

            if len(feature_points) != feature_sample_count:
                skipped_count += 1
                continue

            feature_wgs84_points = []
            failed_feature = False
            for point in feature_points:
                try:
                    wgs84_point = transform.transform(point)
                except Exception:
                    failed_feature = True
                    break
                feature_wgs84_points.append((wgs84_point.y(), wgs84_point.x()))

            if failed_feature:
                skipped_count += 1
                continue

            sampled_points.extend(feature_wgs84_points)

        return sampled_points, skipped_count

    def _build_area_measure(self, layer):
        """Return a configured area measurer for geometries in the layer CRS."""
        area_measure = QgsDistanceArea()
        area_measure.setSourceCrs(layer.crs(), self.project.transformContext())
        ellipsoid = self.project.ellipsoid()
        if not ellipsoid or str(ellipsoid).upper() == 'NONE':
            ellipsoid = 'WGS84'
        area_measure.setEllipsoid(ellipsoid)
        return area_measure

    def _feature_sample_count(self, geometry, sampling_settings, area_measure=None):
        """Resolve the number of marks to generate for a single feature."""
        if sampling_settings['quantity_mode'] != self.FEATURE_SAMPLE_QUANTITY_DENSITY:
            return max(1, min(self.MAX_MARKS_PER_FEATURE, sampling_settings['sample_count']))

        if area_measure is None:
            return 1

        area_square_meters = abs(area_measure.measureArea(geometry))
        area_hectares = area_square_meters / 10000.0
        hectares_per_mark = max(0.1, float(sampling_settings['hectares_per_mark']))
        sample_count = int(math.ceil(max(area_hectares, 1e-9) / hectares_per_mark))
        return max(1, min(self.MAX_MARKS_PER_FEATURE, sample_count))

    def _build_feature_sample_points(
        self,
        layer,
        feature,
        geometry,
        sample_count,
        distribution_method,
    ):
        """Build the requested sampling pattern for a single polygon feature."""
        if sample_count <= 1 or distribution_method == 'centroid':
            centroid_point = self._feature_centroid_point(geometry)
            return [centroid_point] if centroid_point is not None else []

        bounds = geometry.boundingBox()
        if bounds.isEmpty() or bounds.width() <= 0 or bounds.height() <= 0:
            return []

        seed_token = '{}:{}:{}:{}:{:.6f}:{:.6f}:{:.6f}:{:.6f}'.format(
            layer.name(),
            feature.id(),
            distribution_method,
            sample_count,
            bounds.xMinimum(),
            bounds.yMinimum(),
            bounds.xMaximum(),
            bounds.yMaximum(),
        )
        sampling_geometry = self._preferred_sampling_geometry(
            geometry,
            sample_count,
            distribution_method,
        )
        sampling_bounds = sampling_geometry.boundingBox()
        candidates = self._build_feature_candidate_points(
            sampling_geometry,
            sample_count,
            seed_token,
        )
        if len(candidates) < sample_count:
            return []

        if distribution_method == self.FEATURE_SAMPLE_METHOD_GRID:
            selected_points = self._systematic_grid_points(
                sampling_geometry,
                candidates,
                sample_count,
            )
        elif distribution_method == self.FEATURE_SAMPLE_METHOD_ZIGZAG:
            targets = self._zigzag_targets(candidates, sample_count)
            selected_points = self._select_points_from_targets(targets, candidates)
        else:
            selected_points = self._select_maximin_points(candidates, sample_count)
            selected_points = self._sort_points_top_down(selected_points)

        selected_points = self._extend_selection_with_spread(
            selected_points,
            candidates,
            sample_count,
        )
        if len(selected_points) < sample_count:
            return []
        return selected_points[:sample_count]

    def _feature_centroid_point(self, geometry):
        """Return the polygon centroid point when available."""
        centroid_geometry = geometry.centroid()
        if centroid_geometry is None or centroid_geometry.isEmpty():
            return None
        return QgsPointXY(centroid_geometry.asPoint())

    def _feature_point_on_surface(self, geometry):
        """Return an interior point for the polygon when available."""
        point_geometry = geometry.pointOnSurface()
        if point_geometry is None or point_geometry.isEmpty():
            return None
        return QgsPointXY(point_geometry.asPoint())

    def _preferred_sampling_geometry(self, geometry, sample_count, distribution_method):
        """Return an inset polygon when possible so marks stay away from borders."""
        bounds = geometry.boundingBox()
        min_dimension = min(bounds.width(), bounds.height())
        if min_dimension <= 0:
            return geometry

        if distribution_method == self.FEATURE_SAMPLE_METHOD_GRID:
            inset_ratios = [0.05, 0.035, 0.02, 0.01]
        elif distribution_method == self.FEATURE_SAMPLE_METHOD_ZIGZAG:
            inset_ratios = [0.10, 0.07, 0.05, 0.03]
        else:
            inset_ratios = [0.12, 0.08, 0.05, 0.03]

        if sample_count >= 7 and distribution_method != self.FEATURE_SAMPLE_METHOD_GRID:
            inset_ratios = [0.10, 0.07, 0.05, 0.03]

        for inset_ratio in inset_ratios:
            inset_distance = min_dimension * inset_ratio
            if inset_distance <= 0:
                continue

            inset_geometry = geometry.buffer(-inset_distance, 8)
            if inset_geometry is None or inset_geometry.isEmpty():
                continue

            inset_bounds = inset_geometry.boundingBox()
            if inset_bounds.isEmpty() or inset_bounds.width() <= 0 or inset_bounds.height() <= 0:
                continue
            return inset_geometry

        return geometry

    def _build_feature_candidate_points(self, geometry, sample_count, seed_token):
        """Build a deterministic pool of candidate points inside one polygon."""
        bounds = geometry.boundingBox()
        if bounds.isEmpty() or bounds.width() <= 0 or bounds.height() <= 0:
            return []

        tolerance = max(bounds.width(), bounds.height()) / 1000000.0
        if tolerance <= 0:
            tolerance = 1e-9

        candidates = []
        seen_keys = set()

        self._append_candidate_point(
            candidates,
            seen_keys,
            self._feature_point_on_surface(geometry),
            geometry,
            tolerance,
            allow_boundary=True,
        )
        self._append_candidate_point(
            candidates,
            seen_keys,
            self._feature_centroid_point(geometry),
            geometry,
            tolerance,
            allow_boundary=False,
        )

        grid_divisions = max(6, int(math.ceil(math.sqrt(sample_count * 24))))
        self._append_grid_candidates(
            candidates,
            seen_keys,
            geometry,
            bounds,
            tolerance,
            grid_divisions,
            x_offset_ratio=0.5,
            y_offset_ratio=0.5,
        )
        self._append_grid_candidates(
            candidates,
            seen_keys,
            geometry,
            bounds,
            tolerance,
            grid_divisions,
            x_offset_ratio=0.25,
            y_offset_ratio=0.75,
        )

        rng = random.Random(seed_token)
        target_candidate_count = max(sample_count * 18, 80)
        max_attempts = max(target_candidate_count * 10, 400)
        attempts = 0
        while len(candidates) < target_candidate_count and attempts < max_attempts:
            attempts += 1
            candidate = QgsPointXY(
                rng.uniform(bounds.xMinimum(), bounds.xMaximum()),
                rng.uniform(bounds.yMinimum(), bounds.yMaximum()),
            )
            self._append_candidate_point(
                candidates,
                seen_keys,
                candidate,
                geometry,
                tolerance,
                allow_boundary=False,
            )

        return candidates

    def _append_grid_candidates(
        self,
        candidates,
        seen_keys,
        geometry,
        bounds,
        tolerance,
        grid_divisions,
        x_offset_ratio,
        y_offset_ratio,
    ):
        """Append deterministic grid candidates inside the polygon bounds."""
        x_step = bounds.width() / float(grid_divisions)
        y_step = bounds.height() / float(grid_divisions)
        if x_step <= 0 or y_step <= 0:
            return

        for row_index in range(grid_divisions):
            y = bounds.yMinimum() + (row_index + y_offset_ratio) * y_step
            for column_index in range(grid_divisions):
                x = bounds.xMinimum() + (column_index + x_offset_ratio) * x_step
                self._append_candidate_point(
                    candidates,
                    seen_keys,
                    QgsPointXY(x, y),
                    geometry,
                    tolerance,
                    allow_boundary=False,
                )

    def _append_candidate_point(
        self,
        candidates,
        seen_keys,
        point,
        geometry,
        tolerance,
        allow_boundary=False,
    ):
        """Add a point to the candidate pool when it is valid and unique."""
        if point is None:
            return

        point = QgsPointXY(point)
        point_key = (
            int(round(point.x() / tolerance)),
            int(round(point.y() / tolerance)),
        )
        if point_key in seen_keys:
            return

        point_geometry = QgsGeometry.fromPointXY(point)
        is_inside = geometry.contains(point_geometry)
        if not is_inside and allow_boundary:
            is_inside = geometry.intersects(point_geometry)
        if not is_inside:
            return

        candidates.append(point)
        seen_keys.add(point_key)

    def _systematic_grid_points(self, geometry, candidates, sample_count):
        """Return grid-aligned points that preserve shared rows and columns."""
        if not candidates:
            return []

        origin_point, axis_x, axis_y = self._feature_reference_frame(candidates)
        local_candidates = [
            self._project_point_to_frame(point, origin_point, axis_x, axis_y)
            for point in candidates
        ]

        major_min = min(local_point[0] for local_point in local_candidates)
        major_max = max(local_point[0] for local_point in local_candidates)
        minor_min = min(local_point[1] for local_point in local_candidates)
        minor_max = max(local_point[1] for local_point in local_candidates)
        major_span = major_max - major_min
        minor_span = minor_max - minor_min
        if major_span <= 0 or minor_span <= 0:
            return []

        column_count, row_count = self._best_grid_dimensions(
            sample_count,
            major_span / float(max(minor_span, 1e-9)),
        )
        row_sizes = self._balanced_row_sizes(sample_count, row_count, column_count)

        minor_step = minor_span / float(row_count)
        major_step = major_span / float(column_count)
        column_positions = [
            major_min + (column_index + 0.5) * major_step
            for column_index in range(column_count)
        ]
        remaining_candidates = list(candidates)
        selected_points = []
        selected_keys = set()
        for row_index, row_size in enumerate(row_sizes):
            minor_coord = minor_max - (row_index + 0.5) * minor_step
            column_indexes = self._grid_slot_indexes(row_size, column_count)
            for column_index in column_indexes:
                target_point = self._point_from_frame(
                    column_positions[column_index],
                    minor_coord,
                    origin_point,
                    axis_x,
                    axis_y,
                )
                point_signature = self._point_signature(target_point)
                if (
                    point_signature not in selected_keys
                    and self._geometry_accepts_point(geometry, target_point)
                ):
                    selected_points.append(target_point)
                    selected_keys.add(point_signature)
                    remaining_candidates = [
                        candidate
                        for candidate in remaining_candidates
                        if self._point_signature(candidate) != point_signature
                    ]
                    continue

                if not remaining_candidates:
                    continue

                nearest_index = min(
                    range(len(remaining_candidates)),
                    key=lambda index: self._distance_squared(
                        remaining_candidates[index],
                        target_point,
                    ),
                )
                chosen_point = remaining_candidates.pop(nearest_index)
                chosen_signature = self._point_signature(chosen_point)
                if chosen_signature in selected_keys:
                    continue
                selected_points.append(chosen_point)
                selected_keys.add(chosen_signature)

        return selected_points

    def _best_grid_dimensions(self, sample_count, aspect_ratio):
        """Choose grid dimensions that fit the feature aspect while staying balanced."""
        best_columns = sample_count
        best_rows = 1
        best_score = None

        for row_count in range(1, sample_count + 1):
            column_count = int(math.ceil(float(sample_count) / float(row_count)))
            grid_aspect = column_count / float(max(row_count, 1))
            empty_slots = row_count * column_count - sample_count
            score = abs(math.log(max(grid_aspect, 1e-9) / max(aspect_ratio, 1e-9)))
            score += empty_slots * 0.18
            score += abs(column_count - row_count) * 0.03

            if best_score is None or score < best_score:
                best_score = score
                best_columns = column_count
                best_rows = row_count

        return best_columns, best_rows

    def _balanced_row_sizes(self, sample_count, row_count, column_count):
        """Distribute points across rows as evenly as possible."""
        row_sizes = [sample_count // row_count] * row_count
        remainder = sample_count % row_count
        start_index = max(0, (row_count - remainder) // 2)

        for offset_index in range(remainder):
            target_index = start_index + offset_index
            if target_index >= row_count:
                target_index = row_count - 1 - (target_index - row_count)
            row_sizes[target_index] += 1

        return [min(column_count, max(1, row_size)) for row_size in row_sizes]

    def _grid_slot_indexes(self, slot_count, total_slots):
        """Return evenly spread slot indexes from a fixed column grid."""
        if slot_count <= 0 or total_slots <= 0:
            return []
        if slot_count >= total_slots:
            return list(range(total_slots))
        if slot_count == 1:
            return [total_slots // 2]

        last_slot_index = total_slots - 1
        last_point_index = slot_count - 1
        return [
            int(round(point_index * last_slot_index / float(last_point_index)))
            for point_index in range(slot_count)
        ]

    def _geometry_accepts_point(self, geometry, point):
        """Return True when the point lies inside or on the polygon boundary."""
        point_geometry = QgsGeometry.fromPointXY(QgsPointXY(point))
        return geometry.contains(point_geometry) or geometry.intersects(point_geometry)

    def _zigzag_targets(self, candidates, sample_count):
        """Return classic zigzag targets using the feature's long axis and side edges."""
        if not candidates:
            return []

        origin_point, axis_x, axis_y = self._feature_reference_frame(candidates)
        local_candidates = [
            {
                'point': point,
                'major': projected_point[0],
                'minor': projected_point[1],
            }
            for point in candidates
            for projected_point in [self._project_point_to_frame(point, origin_point, axis_x, axis_y)]
        ]

        major_min = min(item['major'] for item in local_candidates)
        major_max = max(item['major'] for item in local_candidates)
        minor_min = min(item['minor'] for item in local_candidates)
        minor_max = max(item['minor'] for item in local_candidates)

        major_span = major_max - major_min
        minor_span = minor_max - minor_min
        if major_span <= 0 or minor_span <= 0:
            return []

        start_major = major_max - major_span * 0.06
        end_major = major_min + major_span * 0.06
        if sample_count == 1:
            major_targets = [(start_major + end_major) / 2.0]
        else:
            major_step = (start_major - end_major) / float(sample_count - 1)
            major_targets = [
                start_major - point_index * major_step
                for point_index in range(sample_count)
            ]

        band_half_window = max(
            major_span / float(max(sample_count * 2, 4)),
            major_span * 0.06,
        )
        remaining_candidates = list(local_candidates)
        selected_points = []
        prefer_high_minor = False
        low_minor_target = minor_min + minor_span * 0.24
        high_minor_target = minor_max - minor_span * 0.24

        for target_major in major_targets:
            if not remaining_candidates:
                break

            band_candidates = [
                candidate
                for candidate in remaining_candidates
                if abs(candidate['major'] - target_major) <= band_half_window
            ]
            if not band_candidates:
                nearest_major_distance = min(
                    abs(candidate['major'] - target_major)
                    for candidate in remaining_candidates
                )
                band_candidates = [
                    candidate
                    for candidate in remaining_candidates
                    if abs(candidate['major'] - target_major) <= nearest_major_distance
                ]

            chosen_candidate = max(
                band_candidates,
                key=lambda candidate: self._zigzag_candidate_score(
                    candidate,
                    target_major,
                    high_minor_target if prefer_high_minor else low_minor_target,
                    major_span,
                ),
            )
            selected_points.append(chosen_candidate['point'])
            remaining_candidates.remove(chosen_candidate)
            prefer_high_minor = not prefer_high_minor

        return selected_points

    def _zigzag_candidate_score(
        self,
        candidate,
        target_major,
        target_minor,
        major_span,
    ):
        """Score a candidate for one zigzag slice using interior lane plus slice fit."""
        if major_span <= 0:
            major_span = 1.0

        minor_penalty = abs(candidate['minor'] - target_minor)
        distance_penalty = abs(candidate['major'] - target_major) / major_span
        return -minor_penalty - distance_penalty * 0.30

    def _feature_reference_frame(self, points):
        """Return origin plus orthogonal axes aligned to the dominant point spread."""
        center_x = sum(point.x() for point in points) / float(len(points))
        center_y = sum(point.y() for point in points) / float(len(points))

        sxx = 0.0
        syy = 0.0
        sxy = 0.0
        for point in points:
            dx = point.x() - center_x
            dy = point.y() - center_y
            sxx += dx * dx
            syy += dy * dy
            sxy += dx * dy

        if abs(sxy) < 1e-12 and abs(sxx - syy) < 1e-12:
            angle = 0.0
        else:
            angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)

        axis_x = (math.cos(angle), math.sin(angle))
        axis_y = (-axis_x[1], axis_x[0])
        return QgsPointXY(center_x, center_y), axis_x, axis_y

    def _project_point_to_frame(self, point, origin_point, axis_x, axis_y):
        """Project a map point into the local oriented frame."""
        dx = point.x() - origin_point.x()
        dy = point.y() - origin_point.y()
        return (
            dx * axis_x[0] + dy * axis_x[1],
            dx * axis_y[0] + dy * axis_y[1],
        )

    def _point_from_frame(self, major_coord, minor_coord, origin_point, axis_x, axis_y):
        """Return a world-coordinate point from oriented-frame coordinates."""
        return QgsPointXY(
            origin_point.x() + major_coord * axis_x[0] + minor_coord * axis_y[0],
            origin_point.y() + major_coord * axis_x[1] + minor_coord * axis_y[1],
        )

    def _select_points_from_targets(self, targets, candidates):
        """Assign one unique candidate point to each target in order."""
        remaining_candidates = list(candidates)
        selected_points = []

        for target in targets:
            if not remaining_candidates:
                break
            nearest_index = min(
                range(len(remaining_candidates)),
                key=lambda index: self._distance_squared(
                    remaining_candidates[index],
                    target,
                ),
            )
            selected_points.append(remaining_candidates.pop(nearest_index))

        return selected_points

    def _select_maximin_points(self, candidates, sample_count):
        """Choose points that maximize separation inside the polygon."""
        if sample_count <= 0 or not candidates:
            return []
        if sample_count >= len(candidates):
            return list(candidates)
        if len(candidates) == 1:
            return [candidates[0]]

        first_index = 0
        second_index = 1
        best_pair_distance = -1.0
        for left_index in range(len(candidates) - 1):
            for right_index in range(left_index + 1, len(candidates)):
                pair_distance = self._distance_squared(
                    candidates[left_index],
                    candidates[right_index],
                )
                if pair_distance > best_pair_distance:
                    best_pair_distance = pair_distance
                    first_index = left_index
                    second_index = right_index

        selected_points = [candidates[first_index], candidates[second_index]]
        selected_keys = {
            self._point_signature(candidates[first_index]),
            self._point_signature(candidates[second_index]),
        }
        remaining_candidates = [
            point
            for point in candidates
            if self._point_signature(point) not in selected_keys
        ]

        while len(selected_points) < sample_count and remaining_candidates:
            best_index = max(
                range(len(remaining_candidates)),
                key=lambda index: self._minimum_distance_squared(
                    remaining_candidates[index],
                    selected_points,
                ),
            )
            selected_points.append(remaining_candidates.pop(best_index))

        return selected_points

    def _extend_selection_with_spread(self, selected_points, candidates, sample_count):
        """Fill any missing slots using the best remaining spatial spread."""
        selected_points = list(selected_points)
        selected_keys = {
            self._point_signature(point)
            for point in selected_points
        }
        remaining_candidates = [
            point
            for point in candidates
            if self._point_signature(point) not in selected_keys
        ]

        while len(selected_points) < sample_count and remaining_candidates:
            if selected_points:
                best_index = max(
                    range(len(remaining_candidates)),
                    key=lambda index: self._minimum_distance_squared(
                        remaining_candidates[index],
                        selected_points,
                    ),
                )
            else:
                bounds = self._points_bounds(remaining_candidates)
                center_point = QgsPointXY(
                    (bounds.xMinimum() + bounds.xMaximum()) / 2.0,
                    (bounds.yMinimum() + bounds.yMaximum()) / 2.0,
                )
                best_index = max(
                    range(len(remaining_candidates)),
                    key=lambda index: self._distance_squared(
                        remaining_candidates[index],
                        center_point,
                    ),
                )

            selected_points.append(remaining_candidates.pop(best_index))

        return selected_points

    def _sort_points_top_down(self, points):
        """Sort points in a stable north-to-south, west-to-east order."""
        return sorted(points, key=lambda point: (-point.y(), point.x()))

    def _points_bounds(self, points):
        """Return a bounding box that covers the given points."""
        x_min = min(point.x() for point in points)
        x_max = max(point.x() for point in points)
        y_min = min(point.y() for point in points)
        y_max = max(point.y() for point in points)
        return QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(x_min, y_min),
                QgsPointXY(x_max, y_min),
                QgsPointXY(x_max, y_max),
                QgsPointXY(x_min, y_max),
                QgsPointXY(x_min, y_min),
            ]]
        ).boundingBox()

    def _minimum_distance_squared(self, point, other_points):
        """Return the minimum squared distance from point to a list of points."""
        return min(
            self._distance_squared(point, other_point)
            for other_point in other_points
        )

    def _distance_squared(self, left_point, right_point):
        """Return squared planar distance between two QgsPointXY objects."""
        dx = left_point.x() - right_point.x()
        dy = left_point.y() - right_point.y()
        return dx * dx + dy * dy

    def _point_signature(self, point):
        """Return a stable point signature for set membership."""
        return (round(point.x(), 9), round(point.y(), 9))

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
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Add at least 2 points to open a route in Google Maps.',
                    'Adicione ao menos 2 pontos para abrir rota no Google Maps.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        route_urls = []
        try:
            for batch in self._iter_route_batches(coordinates):
                route_urls.append(build_google_maps_directions_url(batch))
        except Exception:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Could not build route.',
                    'Não foi possível montar a rota.',
                ),
                level=Qgis.Critical,
                duration=5,
            )
            return

        if len(route_urls) > 1:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Large route detected. Opening {} Google Maps segments.'.format(len(route_urls)),
                    'Rota grande detectada. Abrindo {} trechos no Google Maps.'.format(len(route_urls)),
                ),
                level=Qgis.Info,
                duration=5,
            )

        opened_count = 0
        for url in route_urls:
            if QDesktopServices.openUrl(QUrl(url)):
                opened_count += 1

        if opened_count == 0:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Could not open route in Google Maps.',
                    'Não foi possível abrir a rota no Google Maps.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        if len(route_urls) == 1:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Route opened in Google Maps with {} point(s).'.format(len(coordinates)),
                    'Rota aberta no Google Maps com {} ponto(s).'.format(len(coordinates)),
                ),
                level=Qgis.Success,
                duration=4,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                'Large route split into {} segments in Google Maps.'.format(opened_count),
                'Rota grande dividida em {} trechos no Google Maps.'.format(opened_count),
            ),
            level=Qgis.Info,
            duration=5,
        )

    def add_manual_coordinate(self, dialog):
        """Validate manual decimal WGS84 input and create a numbered map point."""
        latitude_text = dialog.manual_latitude_input.text().strip()
        longitude_text = dialog.manual_longitude_input.text().strip()

        if not latitude_text or not longitude_text:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Fill latitude and longitude to add a manual coordinate.',
                    'Preencha latitude e longitude para adicionar a coordenada manual.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        try:
            latitude = self._parse_decimal(latitude_text)
            longitude = self._parse_decimal(longitude_text)
        except ValueError:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Invalid coordinates. Use decimal format (e.g.: -23.550520).',
                    'Coordenadas invalidas. Use formato decimal (ex.: -23.550520).',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        if latitude < -90 or latitude > 90:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Latitude is out of allowed range (-90 to 90).',
                    'Latitude fora do intervalo permitido (-90 a 90).',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        if longitude < -180 or longitude > 180:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Longitude is out of allowed range (-180 to 180).',
                    'Longitude fora do intervalo permitido (-180 a 180).',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        try:
            self.marker_tool.add_wgs84_point(latitude, longitude)
        except Exception:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Error adding manual coordinate.',
                    'Erro ao adicionar coordenada manual.',
                ),
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
                self._t('Field Guide', 'Guia de Campo'),
                self._t('There are no points to export.', 'Não há pontos para exportar.'),
                level=Qgis.Warning,
                duration=4,
            )
            return

        default_csv_path = self._default_output_path('field_guide_points.csv')

        output_path, _ = QFileDialog.getSaveFileName(
            self._dialog_parent(),
            self._t('Save points to CSV', 'Salvar pontos em CSV'),
            default_csv_path,
            'CSV Files (*.csv)',
        )
        if not output_path:
            return

        try:
            with open(output_path, mode='w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([
                    self._t('order', 'ordem'),
                    self._t('longitude', 'longitude'),
                    self._t('latitude', 'latitude'),
                ])
                for index, (longitude, latitude) in enumerate(coordinates, start=1):
                    writer.writerow([index, '{:.8f}'.format(longitude), '{:.8f}'.format(latitude)])
        except Exception:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('Error exporting CSV.', 'Erro ao exportar CSV.'),
                level=Qgis.Critical,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t('CSV exported successfully: {}'.format(output_path), 'CSV exportado com sucesso: {}'.format(output_path)),
            level=Qgis.Success,
            duration=5,
        )

    def export_marks_gpx(self):
        """Export captured WGS84 points to a GPS-compatible GPX file."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('There are no points to export.', 'Não há pontos para exportar.'),
                level=Qgis.Warning,
                duration=4,
            )
            return

        default_gpx_path = self._default_output_path('field_guide_points.gpx')

        output_path, _ = QFileDialog.getSaveFileName(
            self._dialog_parent(),
            self._t('Save points to GPX', 'Salvar pontos em GPX'),
            default_gpx_path,
            'GPX Files (*.gpx)',
        )
        if not output_path:
            return
        if not output_path.lower().endswith('.gpx'):
            output_path += '.gpx'

        try:
            self._write_marks_gpx(output_path, coordinates)
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(),
                'Field Guide',
                level=Qgis.Critical,
            )
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('Error exporting GPX.', 'Erro ao exportar GPX.'),
                level=Qgis.Critical,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                'GPX exported successfully: {}'.format(output_path),
                'GPX exportado com sucesso: {}'.format(output_path),
            ),
            level=Qgis.Success,
            duration=5,
        )

    def _write_marks_gpx(self, output_path, coordinates):
        """Write the captured marks as GPS waypoints and an optional ordered route."""
        gpx = ET.Element(
            'gpx',
            attrib={
                'version': '1.1',
                'creator': 'Field Guide QGIS Plugin',
                'xmlns': 'http://www.topografix.com/GPX/1/1',
                'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'xsi:schemaLocation': (
                    'http://www.topografix.com/GPX/1/1 '
                    'http://www.topografix.com/GPX/1/1/gpx.xsd'
                ),
            },
        )

        metadata = ET.SubElement(gpx, 'metadata')
        ET.SubElement(metadata, 'name').text = 'Field Guide Marks'
        ET.SubElement(metadata, 'desc').text = (
            'Captured marks exported from the Field Guide QGIS plugin.'
        )

        for index, (longitude, latitude) in enumerate(coordinates, start=1):
            waypoint = ET.SubElement(
                gpx,
                'wpt',
                attrib={
                    'lat': '{:.8f}'.format(latitude),
                    'lon': '{:.8f}'.format(longitude),
                },
            )
            waypoint_name = self._portable_waypoint_name(index)
            ET.SubElement(waypoint, 'name').text = waypoint_name
            ET.SubElement(waypoint, 'cmt').text = 'Field Guide mark {}'.format(index)
            ET.SubElement(
                waypoint,
                'desc',
            ).text = 'Mark {} ({:.8f}, {:.8f})'.format(index, latitude, longitude)
            ET.SubElement(waypoint, 'sym').text = 'Waypoint'
            ET.SubElement(waypoint, 'type').text = 'user'

        if len(coordinates) >= 2:
            route = ET.SubElement(gpx, 'rte')
            ET.SubElement(route, 'name').text = 'Field Guide Route'
            ET.SubElement(route, 'desc').text = (
                'Ordered route built from captured Field Guide marks.'
            )
            for index, (longitude, latitude) in enumerate(coordinates, start=1):
                route_point = ET.SubElement(
                    route,
                    'rtept',
                    attrib={
                        'lat': '{:.8f}'.format(latitude),
                        'lon': '{:.8f}'.format(longitude),
                    },
                )
                ET.SubElement(route_point, 'name').text = self._portable_waypoint_name(index)

        tree = ET.ElementTree(gpx)
        try:
            ET.indent(tree, space='  ')
        except AttributeError:
            pass
        tree.write(output_path, encoding='utf-8', xml_declaration=True)

    def _portable_waypoint_name(self, index):
        """Return a short waypoint name that works well on handheld GPS units."""
        return 'FG{:03d}'.format(index)

    def add_marks_to_temporary_layer(self):
        """Add the current marks to the project as a temporary point vector layer."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('There are no points to add.', 'Não há pontos para adicionar.'),
                level=Qgis.Warning,
                duration=4,
            )
            return

        target_crs = self.project.crs()
        if target_crs is None or not target_crs.isValid():
            target_crs = self.wgs84

        layer_name = self._temporary_marks_layer_name()
        layer_uri = 'Point?crs={}'.format(target_crs.authid())
        layer = QgsVectorLayer(layer_uri, layer_name, 'memory')
        if not layer.isValid():
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Could not create the temporary point layer.',
                    'Não foi possível criar a camada temporária de pontos.',
                ),
                level=Qgis.Critical,
                duration=6,
            )
            return

        try:
            provider = layer.dataProvider()
            provider.addAttributes([
                QgsField('order', QVariant.Int),
                QgsField('name', QVariant.String),
                QgsField('longitude', QVariant.Double, 'double', 20, 8),
                QgsField('latitude', QVariant.Double, 'double', 20, 8),
            ])
            layer.updateFields()

            transform = None
            if target_crs.authid() != self.wgs84.authid():
                transform = QgsCoordinateTransform(self.wgs84, target_crs, self.project)

            features = []
            for index, (longitude, latitude) in enumerate(coordinates, start=1):
                point = QgsPointXY(longitude, latitude)
                if transform is not None:
                    point = transform.transform(point)

                feature = QgsFeature(layer.fields())
                feature.setGeometry(QgsGeometry.fromPointXY(point))
                feature.setAttributes([
                    index,
                    self._portable_waypoint_name(index),
                    float(longitude),
                    float(latitude),
                ])
                features.append(feature)

            provider.addFeatures(features)
            layer.updateExtents()
            self.project.addMapLayer(layer)
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(),
                'Field Guide',
                level=Qgis.Critical,
            )
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'Error adding the temporary point layer.',
                    'Erro ao adicionar a camada temporária de pontos.',
                ),
                level=Qgis.Critical,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                'Temporary layer added to the project: {} ({} point(s)).'.format(
                    layer.name(),
                    len(features),
                ),
                'Camada temporária adicionada ao projeto: {} ({} ponto(s)).'.format(
                    layer.name(),
                    len(features),
                ),
            ),
            level=Qgis.Success,
            duration=5,
        )

    def _temporary_marks_layer_name(self):
        """Return a readable layer name for temporary project exports."""
        base_name = self._t('Field Guide Marks', 'Marcações Guia de Campo')
        existing_names = {
            layer.name()
            for layer in self.project.mapLayers().values()
            if hasattr(layer, 'name')
        }
        if base_name not in existing_names:
            return base_name

        suffix = 2
        while True:
            candidate_name = '{} {}'.format(base_name, suffix)
            if candidate_name not in existing_names:
                return candidate_name
            suffix += 1

    def import_marks_csv(self):
        """Import WGS84 points from CSV and draw them on the map canvas."""
        input_path, _ = QFileDialog.getOpenFileName(
            self._dialog_parent(),
            self._t('Import points CSV', 'Importar pontos CSV'),
            '',
            'CSV Files (*.csv);;All Files (*)',
        )
        if not input_path:
            return

        import_mode = 'append'
        existing_points = len(self.marker_tool.coordinates)
        if existing_points > 0:
            import_mode = self._choose_points_merge_mode(
                existing_points,
                self._t('Import points CSV', 'Importar pontos CSV'),
                self._t(
                    'Choose whether to append imported points or replace the current list.',
                    'Escolha se deseja adicionar os pontos importados ou substituir a lista atual.',
                ),
            )
            if import_mode is None:
                return

        valid_points = []
        skipped_count = 0

        try:
            with open(input_path, mode='r', newline='', encoding='utf-8-sig') as csv_file:
                reader = csv.DictReader(csv_file)

                if not reader.fieldnames:
                    raise ValueError(self._t('CSV file has no header.', 'Arquivo CSV sem cabecalho.'))

                fieldnames = [name.strip().lower() for name in reader.fieldnames]
                has_required_columns = 'longitude' in fieldnames and 'latitude' in fieldnames
                if not has_required_columns:
                    raise ValueError(
                        self._t(
                            'Header must contain longitude and latitude columns.',
                            'Cabecalho deve conter colunas longitude e latitude.',
                        )
                    )

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

                    valid_points.append((latitude, longitude))
        except ValueError as exc:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                str(exc),
                level=Qgis.Warning,
                duration=6,
            )
            return
        except Exception:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('Error importing CSV.', 'Erro ao importar CSV.'),
                level=Qgis.Critical,
                duration=6,
            )
            return

        imported_count = len(valid_points)
        if imported_count == 0:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t('No valid points found in CSV.', 'Nenhum ponto valido encontrado no CSV.'),
                level=Qgis.Warning,
                duration=5,
            )
            return

        if import_mode == 'replace':
            self.marker_tool.clear()

        self.marker_tool.add_wgs84_points(valid_points)

        if skipped_count > 0:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    '{} point(s) imported; {} row(s) skipped.'.format(imported_count, skipped_count),
                    '{} ponto(s) importado(s); {} linha(s) ignorada(s).'.format(imported_count, skipped_count),
                ),
                level=Qgis.Info,
                duration=6,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t(
                '{} point(s) imported successfully.'.format(imported_count),
                '{} ponto(s) importado(s) com sucesso.'.format(imported_count),
            ),
            level=Qgis.Success,
            duration=5,
        )

    def generate_pfd(self):
        """Generate PDF report with current canvas screenshot and map links."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'No points marked. Add map points before generating the PDF.',
                    'Nenhum ponto marcado. Adicione pontos no mapa antes de gerar o PDF.',
                ),
                level=Qgis.Warning,
                duration=4,
            )
            return

        default_pdf_path = self._default_output_path('field_guide.pdf')

        output_path, _ = QFileDialog.getSaveFileName(
            self._dialog_parent(),
            self._t('Save Field Guide PDF', 'Salvar PDF da Guia de Campo'),
            default_pdf_path,
            'PDF Files (*.pdf)',
        )
        if not output_path:
            return

        try:
            final_path = self.pdf_composer.generate(coordinates, output_path)
        except Exception as exc:
            QgsMessageLog.logMessage(
                traceback.format_exc(),
                'Field Guide',
                level=Qgis.Critical,
            )
            error_detail = str(exc).strip()
            if error_detail:
                user_message = self._t(
                    'Error generating PDF: {}'.format(error_detail),
                    'Erro ao gerar PDF: {}'.format(error_detail),
                )
            else:
                user_message = self._t('Error generating PDF.', 'Erro ao gerar PDF.')
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                user_message,
                level=Qgis.Critical,
                duration=8,
            )
            return

        self.iface.messageBar().pushMessage(
            self._t('Field Guide', 'Guia de Campo'),
            self._t('PDF generated successfully: {}'.format(final_path), 'PDF gerado com sucesso: {}'.format(final_path)),
            level=Qgis.Success,
            duration=5,
        )

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(final_path))
        if not opened:
            self.iface.messageBar().pushMessage(
                self._t('Field Guide', 'Guia de Campo'),
                self._t(
                    'PDF saved, but could not be opened automatically.',
                    'PDF salvo, mas nao foi possivel abrir automaticamente.',
                ),
                level=Qgis.Warning,
                duration=4,
            )

    def _choose_points_merge_mode(self, existing_points, window_title, informative_text):
        """Ask whether new points should append to or replace current points."""
        message_box = QMessageBox(self._dialog_parent())
        message_box.setIcon(_message_box_enum('Icon', 'Question', 'Question'))
        message_box.setWindowTitle(window_title)
        message_box.setText(
            self._t(
                'There are already {} point(s) in this session.'.format(existing_points),
                'Já existem {} ponto(s) nesta sessão.'.format(existing_points),
            )
        )
        message_box.setInformativeText(informative_text)
        append_button = message_box.addButton(
            self._t('Append', 'Adicionar'),
            _message_box_enum('ButtonRole', 'AcceptRole', 'AcceptRole'),
        )
        replace_button = message_box.addButton(
            self._t('Replace', 'Substituir'),
            _message_box_enum('ButtonRole', 'DestructiveRole', 'DestructiveRole'),
        )
        cancel_button = message_box.addButton(
            self._t('Cancel', 'Cancelar'),
            _message_box_enum('ButtonRole', 'RejectRole', 'RejectRole'),
        )
        message_box.setDefaultButton(append_button)
        _message_box_exec(message_box)

        clicked = message_box.clickedButton()
        if clicked == append_button:
            return 'append'
        if clicked == replace_button:
            return 'replace'
        if clicked == cancel_button:
            return None
        return None
