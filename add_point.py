import os

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from qgis.utils import iface


class CreatePointLayerDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Create Point Layer")

        # Main layout
        layout = QVBoxLayout()

        # Layer name section
        name_group = QGroupBox("Layer Settings")
        name_layout = QVBoxLayout()

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Layer Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter layer name")
        self.name_input.setText("measurement_point")
        name_row.addWidget(self.name_input)
        name_layout.addLayout(name_row)

        name_group.setLayout(name_layout)

        # Coordinates section
        coords_group = QGroupBox("Point Coordinates")
        coords_layout = QVBoxLayout()

        # X coordinate
        x_row = QHBoxLayout()
        x_row.addWidget(QLabel("X Coordinate:"))
        self.x_spinbox = QDoubleSpinBox()
        self.x_spinbox.setRange(-999999999.0, 999999999.0)
        self.x_spinbox.setValue(641056.0)
        self.x_spinbox.setDecimals(3)
        x_row.addWidget(self.x_spinbox)
        coords_layout.addLayout(x_row)

        # Y coordinate
        y_row = QHBoxLayout()
        y_row.addWidget(QLabel("Y Coordinate:"))
        self.y_spinbox = QDoubleSpinBox()
        self.y_spinbox.setRange(-999999999.0, 999999999.0)
        self.y_spinbox.setValue(162787.0)
        self.y_spinbox.setDecimals(3)
        y_row.addWidget(self.y_spinbox)
        coords_layout.addLayout(y_row)

        # Z coordinate
        z_row = QHBoxLayout()
        z_row.addWidget(QLabel("Z Elevation:"))
        self.z_spinbox = QDoubleSpinBox()
        self.z_spinbox.setRange(-999999.0, 999999.0)
        self.z_spinbox.setValue(88.86)
        self.z_spinbox.setDecimals(3)
        self.z_spinbox.setSuffix(" m")
        z_row.addWidget(self.z_spinbox)
        coords_layout.addLayout(z_row)

        coords_group.setLayout(coords_layout)

        # Output section
        output_group = QGroupBox("Output Options")
        output_layout = QVBoxLayout()

        # Save to file option
        file_row = QHBoxLayout()
        self.save_to_file_btn = QPushButton("Choose Output File (Optional)")
        self.save_to_file_btn.clicked.connect(self.choose_output_file)
        file_row.addWidget(self.save_to_file_btn)
        output_layout.addLayout(file_row)

        self.output_file_label = QLabel("Will create temporary layer if no file chosen")
        self.output_file_label.setStyleSheet("color: gray; font-style: italic;")
        output_layout.addWidget(self.output_file_label)

        output_group.setLayout(output_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Create Point Layer")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        # Add all to main layout
        layout.addWidget(name_group)
        layout.addWidget(coords_group)
        layout.addWidget(output_group)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Store output file path
        self.output_file_path = None

    def choose_output_file(self):
        """Open file dialog to choose output shapefile location"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Point Layer As", "", "Shapefiles (*.shp);;All Files (*)"
        )

        if file_path:
            if not file_path.endswith(".shp"):
                file_path += ".shp"
            self.output_file_path = file_path
            self.output_file_label.setText(f"Save to: {os.path.basename(file_path)}")
            self.output_file_label.setStyleSheet("color: black;")
        else:
            self.output_file_path = None
            self.output_file_label.setText(
                "Will create temporary layer if no file chosen"
            )
            self.output_file_label.setStyleSheet("color: gray; font-style: italic;")

    def get_values(self):
        """Get the values from the dialog"""
        layer_name = self.name_input.text().strip()
        if not layer_name:
            raise ValueError("Layer name cannot be empty")

        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        z = self.z_spinbox.value()

        return layer_name, x, y, z, self.output_file_path


def create_point_layer(layer_name, x, y, z, output_file_path=None):
    """
    Create a point layer with a single point containing X, Y, Z coordinates

    Args:
        layer_name: Name for the layer
        x, y, z: Coordinates for the point
        output_file_path: Optional path to save as shapefile

    Returns:
        QgsVectorLayer: The created layer
    """

    # Get current project CRS
    project_crs = QgsProject.instance().crs()

    # Create fields for the layer
    fields = QgsFields()
    fields.append(QgsField("id", QVariant.Int))
    fields.append(QgsField("x", QVariant.Double))
    fields.append(QgsField("y", QVariant.Double))
    fields.append(QgsField("z", QVariant.Double))
    fields.append(QgsField("name", QVariant.String))

    if output_file_path:
        # Create shapefile
        writer = QgsVectorFileWriter(
            output_file_path,
            "utf-8",
            fields,
            QgsWkbTypes.PointZ,  # Use PointZ for 3D points
            project_crs,
            "ESRI Shapefile",
        )

        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise Exception(f"Error creating shapefile: {writer.errorMessage()}")

        # Create feature
        feature = QgsFeature(fields)
        point_geom = QgsGeometry.fromPoint(QgsPoint(x, y, z))
        feature.setGeometry(point_geom)

        # Set attributes
        feature.setAttributes([1, x, y, z, layer_name])

        # Write feature
        writer.addFeature(feature)
        del writer  # Close the file

        # Load the created shapefile
        layer = QgsVectorLayer(output_file_path, layer_name, "ogr")

    else:
        # Create temporary memory layer
        layer_uri = f"Point?crs={project_crs.authid()}&field=id:integer&field=x:double&field=y:double&field=z:double&field=name:string"
        layer = QgsVectorLayer(layer_uri, layer_name, "memory")

        if not layer.isValid():
            raise Exception("Failed to create memory layer")

        # Start editing
        layer.startEditing()

        # Create feature
        feature = QgsFeature(layer.fields())
        point_geom = QgsGeometry.fromPoint(QgsPoint(x, y, z))
        feature.setGeometry(point_geom)

        # Set attributes
        feature.setAttributes([1, x, y, z, layer_name])

        # Add feature
        layer.addFeature(feature)
        layer.commitChanges()

    if not layer.isValid():
        raise Exception("Created layer is not valid")

    # Add layer to project
    QgsProject.instance().addMapLayer(layer)

    print(f"Created point layer '{layer_name}' with point at ({x}, {y}, {z})")

    if output_file_path:
        print(f"Layer saved to: {output_file_path}")
    else:
        print("Layer created as temporary memory layer")

    return layer


def get_user_inputs():
    """Show the dialog and get user inputs"""
    dialog = CreatePointLayerDialog()

    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_values()
    else:
        return None, None, None, None, None


# Main execution
try:
    # Get inputs from dialog
    layer_name, x, y, z, output_file = get_user_inputs()

    if layer_name is None:
        print("Operation cancelled by user")
    else:
        print(f"Creating point layer: {layer_name}")
        print(f"Coordinates: X={x}, Y={y}, Z={z}")

        # Create the point layer
        layer = create_point_layer(layer_name, x, y, z, output_file)

        # Zoom to the created point
        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

        QMessageBox.information(
            iface.mainWindow(),
            "Success",
            f"Point layer '{layer_name}' created successfully!\nPoint coordinates: ({x}, {y}, {z})",
        )

except ValueError as e:
    QMessageBox.warning(iface.mainWindow(), "Input Error", str(e))
    print(f"Error: {e}")
except Exception as e:
    QMessageBox.critical(
        iface.mainWindow(), "Unexpected Error", f"An error occurred: {str(e)}"
    )
    print(f"Unexpected error: {e}")
