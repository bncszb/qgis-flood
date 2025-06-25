import os
from pathlib import Path

from qgis import processing
from qgis.core import (
    QgsFillSymbol,
    QgsMapLayer,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)
from qgis.utils import iface


def create_water_level_polygon(
    dem_layer,
    point_layer,
    level,
    base_elevation,
    extent,
    output_dir,
):
    """
    Create a polygon representing areas below a certain water level,
    filtered to only include the polygon that overlaps with the point layer.
    Args:
        dem_layer: QgsRasterLayer - DEM raster layer
        point_layer: QgsVectorLayer - Point layer for filtering
        level: Water level above base elevation
        base_elevation: Base elevation from point Z coordinate
        extent: Processing extent
        output_dir: Directory for output files
    """
    # Create output folder for this water level
    level_folder = os.path.join(output_dir, f"water_level_{level}m")
    os.makedirs(level_folder, exist_ok=True)

    # Get layer source paths
    dem_path = dem_layer.source()
    dem_name = os.path.splitext(os.path.basename(dem_path))[0]

    # Step 1: Create raster mask for water level
    raster_output = os.path.join(level_folder, f"{level}_level.tif")
    print(dem_path)
    print(f"DEM Name: {dem_name}")
    print(
        f"Creating raster mask for water level {level}m above base elevation {base_elevation}m from DEM: {dem_name}..."
    )
    processing.run(
        "native:rastercalc",
        {
            "LAYERS": [dem_path],
            "EXPRESSION": f'"{dem_name}.tif@1" < ({base_elevation}+{level})',
            "EXTENT": extent,
            "CELL_SIZE": None,
            "CRS": None,
            "OUTPUT": raster_output,
        },
    )

    # Step 2: Convert raster to polygon
    temp_polygon_output = os.path.join(level_folder, f"{level}_level_polygon_temp.shp")
    print("Converting raster to polygon...")
    processing.run(
        "gdal:polygonize",
        {
            "INPUT": raster_output,
            "BAND": 1,
            "FIELD": "DN",
            "EIGHT_CONNECTEDNESS": True,
            "EXTRA": "",
            "OUTPUT": temp_polygon_output,
        },
    )

    # Step 3: Filter polygons to keep only the one that overlaps with the point
    filtered_polygon_output = os.path.join(level_folder, f"{level}_level_polygon.shp")

    print("Filtering polygons to keep only the one overlapping with point...")

    # Load temporary polygon layer
    temp_polygon_layer = QgsVectorLayer(temp_polygon_output, "temp_polygons", "ogr")

    # Add layers to project temporarily
    QgsProject.instance().addMapLayer(temp_polygon_layer, False)

    # Use the layer objects for selectbylocation
    processing.run(
        "native:selectbylocation",
        {
            "INPUT": temp_polygon_layer,
            "PREDICATE": [0],  # intersects
            "INTERSECT": point_layer,
            "METHOD": 0,  # creating new selection
        },
    )

    # Extract selected features to new layer
    processing.run(
        "native:saveselectedfeatures",
        {
            "INPUT": temp_polygon_layer,
            "OUTPUT": filtered_polygon_output,
        },
    )

    # Remove temporary layer from project
    QgsProject.instance().removeMapLayer(temp_polygon_layer.id())

    # Step 4: Load the filtered polygon layer into QGIS project
    polygon_layer = QgsProject.instance().addMapLayer(
        QgsVectorLayer(
            filtered_polygon_output,
            f"Water Level {level}m (Base: {base_elevation:.1f}m)",
            "ogr",
        )
    )

    # Set the layer style to transparent blue

    # Create a blue transparent fill symbol
    symbol = QgsFillSymbol.createSimple(
        {
            "color": "0,100,255,100",  # RGBA: blue with transparency (alpha=100 out of 255)
            "outline_color": "0,50,200,200",  # Darker blue outline
            "outline_width": "0.5",
        }
    )

    # Apply the symbol to the layer
    polygon_layer.renderer().setSymbol(symbol)
    polygon_layer.triggerRepaint()

    # Clean up temporary file
    if os.path.exists(temp_polygon_output):
        os.remove(temp_polygon_output)
        # Remove associated files
        for ext in [".shx", ".dbf", ".prj", ".cpg"]:
            temp_file = temp_polygon_output.replace(".shp", ext)
            if os.path.exists(temp_file):
                os.remove(temp_file)

    print(f"Filtered water level polygon created in folder: {level_folder}")
    print(
        f"Base elevation: {base_elevation:.2f}m, Water level: {level}m, Total elevation: {base_elevation + level:.2f}m"
    )
    return filtered_polygon_output


# Custom dialog widget with both inputs


class WaterLevelDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Water Level Polygon Generator")
        self.setFixedSize(500, 350)

        # Main layout
        layout = QVBoxLayout()

        # Input layers section
        layers_group = QGroupBox("Input Layers")
        layers_layout = QVBoxLayout()

        # DEM layer selection
        from qgis.PyQt.QtWidgets import QComboBox

        dem_layout = QHBoxLayout()
        dem_layout.addWidget(QLabel("DEM Layer:"))
        self.dem_combo = QComboBox()
        self.populate_raster_layers()
        dem_layout.addWidget(self.dem_combo)
        layers_layout.addLayout(dem_layout)

        # Point layer selection
        point_layout = QHBoxLayout()
        point_layout.addWidget(QLabel("Point Layer (with Z):"))
        self.point_combo = QComboBox()
        self.populate_point_layers()
        point_layout.addWidget(self.point_combo)
        layers_layout.addLayout(point_layout)

        layers_group.setLayout(layers_layout)

        # Water level input
        level_group = QGroupBox("Water Level")
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Level (meters above base):"))

        self.level_spinbox = QDoubleSpinBox()
        self.level_spinbox.setRange(0.0, 50.0)
        self.level_spinbox.setValue(10.0)
        self.level_spinbox.setDecimals(1)
        self.level_spinbox.setSuffix(" m")
        level_layout.addWidget(self.level_spinbox)
        level_group.setLayout(level_layout)

        # Extent selection
        extent_group = QGroupBox("Processing Extent")
        extent_layout = QVBoxLayout()

        self.extent_group = QButtonGroup()
        self.canvas_radio = QRadioButton("Use current map canvas extent")
        self.custom_radio = QRadioButton("Use custom extent:")

        self.canvas_radio.setChecked(True)  # Default to canvas extent

        self.extent_group.addButton(self.canvas_radio, 0)
        self.extent_group.addButton(self.custom_radio, 1)

        extent_layout.addWidget(self.canvas_radio)
        extent_layout.addWidget(self.custom_radio)

        # Custom extent input
        from qgis.PyQt.QtWidgets import QLineEdit

        self.extent_input = QLineEdit()
        self.extent_input.setPlaceholderText("xmin,xmax,ymin,ymax [EPSG:code]")
        self.extent_input.setEnabled(False)  # Initially disabled

        # Connect radio button to enable/disable text input
        self.custom_radio.toggled.connect(self.extent_input.setEnabled)

        extent_layout.addWidget(self.extent_input)
        extent_group.setLayout(extent_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Generate Polygon")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        # Add all to main layout
        layout.addWidget(layers_group)
        layout.addWidget(level_group)
        layout.addWidget(extent_group)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def populate_raster_layers(self):
        """Populate combo box with available raster layers"""
        self.dem_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayer.RasterLayer:
                self.dem_combo.addItem(layer.name(), layer)

    def populate_point_layers(self):
        """Populate combo box with available point vector layers"""
        self.point_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if (
                layer.type() == QgsMapLayer.VectorLayer
                and layer.geometryType() == QgsWkbTypes.PointGeometry
            ):
                self.point_combo.addItem(layer.name(), layer)

    def get_base_elevation_from_point(self, point_layer):
        """Extract Z coordinate from the first point in the layer"""
        if not point_layer or point_layer.featureCount() == 0:
            raise ValueError("Point layer is empty or invalid")

        # Get the first feature
        first_feature = next(point_layer.getFeatures())
        geometry = first_feature.geometry()

        if geometry.isEmpty():
            raise ValueError("Point geometry is empty")

        # Get the point and extract Z coordinate
        point = geometry.asPoint()

        # Check if geometry has Z dimension
        if geometry.wkbType() in [
            QgsWkbTypes.Point25D,
            QgsWkbTypes.PointZ,
            QgsWkbTypes.PointZM,
        ]:
            # For 3D points, get Z coordinate
            vertex = geometry.vertexAt(0)
            if vertex.z() != vertex.z():  # Check for NaN
                raise ValueError("Point Z coordinate is not valid (NaN)")
            return vertex.z()
        else:
            # Try to get Z from attributes if geometry doesn't have Z
            for field_name in ["z", "Z", "elevation", "elev", "height"]:
                if field_name in [field.name() for field in first_feature.fields()]:
                    z_value = first_feature[field_name]
                    if z_value is not None:
                        return float(z_value)

            raise ValueError(
                "Point layer has no Z coordinate in geometry or attributes"
            )

    def get_values(self):
        """Get the selected values from the dialog"""
        # Get selected layers
        dem_layer = self.dem_combo.currentData()
        point_layer = self.point_combo.currentData()

        if not dem_layer:
            raise ValueError("No DEM layer selected")
        if not point_layer:
            raise ValueError("No point layer selected")

        # Get base elevation from point layer
        base_elevation = self.get_base_elevation_from_point(point_layer)

        # Get water level
        level = self.level_spinbox.value()

        # Get extent
        if self.canvas_radio.isChecked():
            # Get current canvas extent
            canvas = iface.mapCanvas()
            extent = canvas.extent()
            crs = canvas.mapSettings().destinationCrs().authid()
            extent_string = f"{extent.xMinimum()},{extent.xMaximum()},{extent.yMinimum()},{extent.yMaximum()} [{crs}]"
        else:
            # Use custom extent from text input
            extent_string = self.extent_input.text().strip()
            if not extent_string:
                raise ValueError("Custom extent cannot be empty")

        return dem_layer, point_layer, base_elevation, level, extent_string


def get_user_inputs():
    """Show the custom dialog and get user inputs"""
    dialog = WaterLevelDialog()

    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_values()
    else:
        return None, None, None, None, None


try:
    # Get all inputs from custom dialog
    dem_layer, point_layer, base_elevation, level, extent = get_user_inputs()

    if dem_layer is None:
        print("Operation cancelled by user")
        exit()

    print(f"DEM Layer: {dem_layer.name()}")
    print(f"Point Layer: {point_layer.name()}")
    print(f"Base elevation from point: {base_elevation:.2f}m")
    print(f"Water level: {level}m")
    print(f"Total water elevation: {base_elevation + level:.2f}m")
    print(f"Using extent: {extent}")

    project_home = Path(QgsProject.instance().homePath())

    # Create polygon with user inputs
    polygon_path = create_water_level_polygon(
        dem_layer,
        point_layer,
        level,
        base_elevation,
        extent,
        project_home / "output",
    )
    print(
        f"Created polygon for water level: {level}m above base elevation {base_elevation:.2f}m"
    )

except ValueError as e:
    from qgis.PyQt.QtWidgets import QMessageBox

    QMessageBox.warning(iface.mainWindow(), "Input Error", str(e))
    print(f"Error: {e}")
except Exception as e:
    from qgis.PyQt.QtWidgets import QMessageBox

    QMessageBox.critical(
        iface.mainWindow(), "Unexpected Error", f"An error occurred: {str(e)}"
    )
    print(f"Unexpected error: {e}")

# Option 2: Use console input (uncomment to use)
# level = get_console_input()
# polygon_path = create_water_level_polygon(level)
