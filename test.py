import sys
import csv
import json
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QStackedWidget, QListWidget, 
                             QHBoxLayout, QFileDialog, QMessageBox, QListWidgetItem,
                             QCheckBox, QComboBox, QGridLayout, QSpinBox, QDoubleSpinBox,
                             QTableWidget, QTableWidgetItem)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

class UserDataTab(QWidget):
    """A reusable widget for a single tab with input fields and descriptions."""
    def __init__(self, field_definitions, columns=1, parent=None):
        super().__init__(parent)
        self.field_definitions = field_definitions
        self.fields = []
        
        self.layout = QGridLayout()
        row, col = 0, 0
        
        for field_def in self.field_definitions:
            field_label = field_def.get("label", "Unknown")
            
            if field_def["type"] == "checkbox":
                checkbox_widget = QCheckBox(field_label)
                self.fields.append((field_label, checkbox_widget))
                if "description" in field_def:
                    description_label = QLabel(field_def["description"])
                    font = QFont(); font.setPointSize(9); font.setItalic(True)
                    description_label.setFont(font)
                    description_label.setStyleSheet("color: grey;")
                    description_label.setWordWrap(True)
                    checkbox_layout = QVBoxLayout()
                    checkbox_layout.addWidget(checkbox_widget)
                    checkbox_layout.addWidget(description_label)
                    self.layout.addLayout(checkbox_layout, row, col)
                else:
                    self.layout.addWidget(checkbox_widget, row, col)

            else:
                label = QLabel(f"{field_label}:")
                self.layout.addWidget(label, row, col)
                if "description" in field_def:
                    description_widget = QLabel(field_def["description"])
                    font = QFont(); font.setPointSize(9); font.setItalic(True)
                    description_widget.setFont(font)
                    description_widget.setStyleSheet("color: grey;")
                    description_widget.setWordWrap(True)
                    self.layout.addWidget(description_widget, row + 1, col)
                
                if field_def["type"] == "dropdown":
                    entry_widget = QComboBox()
                    entry_widget.addItems(field_def.get("options", []))
                elif field_def["type"] == "numeric":
                    if "decimal_places" in field_def:
                        entry_widget = QDoubleSpinBox()
                        entry_widget.setDecimals(field_def["decimal_places"])
                    else:
                        entry_widget = QSpinBox()
                    entry_widget.setMinimum(field_def.get("min", 0))
                    entry_widget.setMaximum(field_def.get("max", 999999))
                else:
                    entry_widget = QLineEdit()
                
                self.layout.addWidget(entry_widget, row + 2, col)
                self.fields.append((field_label, entry_widget))

            col += 1
            if col >= columns:
                col = 0
                row += 3
        self.setLayout(self.layout)

    def get_data(self):
        """Returns a list of tuples with data from the tab's fields, keyed by label.
        Empty fields return None."""
        data_list = []
        for label, widget in self.fields:
            if isinstance(widget, QLineEdit):
                value = widget.text()
                data_list.append((label, value if value else None))
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
                data_list.append((label, value if widget.currentIndex() > 0 else None))
            elif isinstance(widget, QCheckBox):
                data_list.append((label, "ON" if widget.isChecked() else "OFF"))
            elif isinstance(widget, QSpinBox):
                value = widget.value()
                data_list.append((label, str(value) if value != widget.minimum() else None))
            elif isinstance(widget, QDoubleSpinBox):
                value = widget.value()
                data_list.append((label, str(value) if value != widget.minimum() else None))
        return data_list

    def set_data(self, data_list):
        """Sets the text of input fields based on a provided list of (label, value) tuples."""
        if not data_list or len(self.fields) != len(data_list):
            self.clear_fields()
            return
        
        for (label, widget), (data_label, value) in zip(self.fields, data_list):
            if label == data_label:
                if value is None:
                    self.clear_widget(widget)
                    continue
                
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(value)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(value == "ON")
                elif isinstance(widget, QSpinBox):
                    try:
                        widget.setValue(int(value))
                    except (ValueError, TypeError):
                        self.clear_widget(widget)
                elif isinstance(widget, QDoubleSpinBox):
                    try:
                        widget.setValue(float(value))
                    except (ValueError, TypeError):
                        self.clear_widget(widget)

    def clear_widget(self, widget):
        """Helper function to clear a single widget based on its type."""
        if isinstance(widget, QLineEdit):
            widget.clear()
        elif isinstance(widget, QComboBox):
            widget.setCurrentIndex(0)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(False)
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.setValue(widget.minimum())

    def clear_fields(self):
        """Clears all input fields in the tab."""
        for _, widget in self.fields:
            self.clear_widget(widget)

class TabularDataTab(QWidget):
    """A widget for a tabular data entry based on a dynamic number of columns."""
    def __init__(self, row_definitions, tab_name=None, parent=None):
        super().__init__(parent)
        self.row_definitions = row_definitions
        self.tab_name = tab_name  # Store tab name directly
        self.table = QTableWidget()
        self.table.setRowCount(len(self.row_definitions))
        
        # Preserve the original/base row definitions to support dynamic row extension
        self.base_row_definitions = list(row_definitions)
        
        # Set the vertical headers and tooltips
        for i, row_def in enumerate(self.row_definitions):
            item = QTableWidgetItem(row_def['label'])
            item.setToolTip(row_def['description'])
            self.table.setVerticalHeaderItem(i, item)
            
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.table)
    
    def set_columns(self, num_columns):
        """Dynamically sets the number of columns and their headers."""
        # Ensure at least 1 column for display
        num_columns = max(1, num_columns)
        self.table.setColumnCount(num_columns)
        
        # Use stored tab name for correct headers
        if self.tab_name in ["Timestep Limitations", "Waterbody Definition", "Calculations", "Dead Sea", 
                             "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity"]:
            column_headers = [f"WB{i+1}" for i in range(num_columns)]
        elif self.tab_name in ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures"]:
            column_headers = [f"BR{i+1}" for i in range(num_columns)]
        else:
            column_headers = [f"Col{i+1}" for i in range(num_columns)]
            
        self.table.setHorizontalHeaderLabels(column_headers)
        
        # Populate each cell with the appropriate widget type
        for row_index, row_def in enumerate(self.row_definitions):
            for col_index in range(num_columns):
                cell_type = row_def.get("type", "checkbox")
                if cell_type == "checkbox":
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    self.table.setItem(row_index, col_index, item)
                elif cell_type == "numeric":
                    spinbox = QSpinBox()
                    spinbox.setMinimum(row_def.get("min", 0))
                    spinbox.setMaximum(row_def.get("max", 999999))
                    if "decimal_places" in row_def:
                        spinbox = QDoubleSpinBox()
                        spinbox.setDecimals(row_def["decimal_places"])
                        spinbox.setMinimum(row_def.get("min", 0.0))
                        spinbox.setMaximum(row_def.get("max", 999999.0))
                    self.table.setCellWidget(row_index, col_index, spinbox)
                elif cell_type == "text":
                    line_edit = QLineEdit()
                    self.table.setCellWidget(row_index, col_index, line_edit)
                elif cell_type == "dropdown":
                    combo_box = QComboBox()
                    combo_box.addItems(row_def.get("options", []))
                    self.table.setCellWidget(row_index, col_index, combo_box)

    def set_row_definitions(self, new_row_definitions):
        """Replace row definitions dynamically, preserving existing data where possible."""
        # Preserve current data and column count
        current_data = self.get_data()
        current_columns = self.table.columnCount()

        # Apply new row definitions
        self.row_definitions = new_row_definitions
        self.table.setRowCount(len(self.row_definitions))

        # Reset vertical headers and tooltips to match new rows
        for i, row_def in enumerate(self.row_definitions):
            item = QTableWidgetItem(row_def['label'])
            item.setToolTip(row_def.get('description', ''))
            self.table.setVerticalHeaderItem(i, item)

        # Recreate cells according to current column count and new row types
        self.set_columns(current_columns)

        # Restore any overlapping data back into the table
        self.set_data(current_data)

    def get_data(self):
        """Returns tabular data as a list of lists."""
        data = []
        for row_index, row_def in enumerate(self.row_definitions):
            row_data = [row_def['label']]
            for col_index in range(self.table.columnCount()):
                cell_type = row_def.get("type", "checkbox")
                if cell_type == "checkbox":
                    item = self.table.item(row_index, col_index)
                    value = "ON" if item and item.checkState() == Qt.CheckState.Checked else "OFF"
                    row_data.append(value)
                elif cell_type == "numeric":
                    spinbox = self.table.cellWidget(row_index, col_index)
                    value = str(spinbox.value()) if spinbox else "0"
                    row_data.append(value)
                elif cell_type == "text":
                    line_edit = self.table.cellWidget(row_index, col_index)
                    value = line_edit.text() if line_edit else ""
                    row_data.append(value)
                elif cell_type == "dropdown":
                    combo_box = self.table.cellWidget(row_index, col_index)
                    value = combo_box.currentText() if combo_box else ""
                    row_data.append(value)
            data.append(row_data)
        return data

    def set_data(self, data_list):
        """Sets the tabular data from a list of lists."""
        if not data_list:
            self.clear_fields()
            return
            
        for row_index, row_def in enumerate(self.row_definitions):
            if row_index < len(data_list):
                row_data = data_list[row_index]
                for col_index, value in enumerate(row_data[1:]):
                    if col_index < self.table.columnCount():
                        cell_type = row_def.get("type", "checkbox")
                        if cell_type == "checkbox":
                            item = self.table.item(row_index, col_index)
                            if item:
                                item.setCheckState(Qt.CheckState.Checked if value == "ON" else Qt.CheckState.Unchecked)
                        elif cell_type == "numeric":
                            spinbox = self.table.cellWidget(row_index, col_index)
                            if spinbox:
                                try:
                                    if isinstance(spinbox, QSpinBox):
                                        spinbox.setValue(int(value))
                                    elif isinstance(spinbox, QDoubleSpinBox):
                                        spinbox.setValue(float(value))
                                except (ValueError, TypeError):
                                    if isinstance(spinbox, QSpinBox):
                                        spinbox.setValue(spinbox.minimum())
                                    elif isinstance(spinbox, QDoubleSpinBox):
                                        spinbox.setValue(spinbox.minimum())
                        elif cell_type == "text":
                            line_edit = self.table.cellWidget(row_index, col_index)
                            if line_edit:
                                line_edit.setText(value)
                        elif cell_type == "dropdown":
                            combo_box = self.table.cellWidget(row_index, col_index)
                            if combo_box:
                                combo_box.setCurrentText(value)

    def clear_fields(self):
        """Clears all fields in the table based on their type."""
        for row_index, row_def in enumerate(self.row_definitions):
            for col_index in range(self.table.columnCount()):
                cell_type = row_def.get("type", "checkbox")
                if cell_type == "checkbox":
                    item = self.table.item(row_index, col_index)
                    if item:
                        item.setCheckState(Qt.CheckState.Unchecked)
                elif cell_type == "numeric":
                    spinbox = self.table.cellWidget(row_index, col_index)
                    if spinbox:
                        spinbox.setValue(spinbox.minimum())
                elif cell_type == "text":
                    line_edit = self.table.cellWidget(row_index, col_index)
                    if line_edit:
                        line_edit.clear()
                elif cell_type == "dropdown":
                    combo_box = self.table.cellWidget(row_index, col_index)
                    if combo_box:
                        combo_box.setCurrentIndex(0)

class CompactApp(QWidget):
    APP_STATE_FILE = "app_state.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Compact Data Entry App")
        self.setGeometry(100, 100, 800, 600)
        self.tab_data = {
            "Grid Dimensions and General Settings": {
                "fields": [
                    {"label": "NWB", "type": "numeric", "description": "Number of waterbodies in the computational grid"},
                    {"label": "NBR", "type": "numeric", "description": "Number of branches in the computational grid"},
                    {"label": "IMX", "type": "numeric", "description": "Number of segments in the computational grid"},
                    {"label": "KMX", "type": "numeric", "description": "Number of layers in the computational grid"},
                    {"label": "NPROC", "type": "numeric", "description": "# of processors (INACTIVE at this time)"},
                    {"label": "CLOSEC", "type": "checkbox", "description": "close dialog box after executing if checked"}
                ], "columns": 2
            },
            "Inflow/Outflow Dimensions": {
                "fields": [
                    {"label": "NTR", "type": "numeric", "description": "Number of tributaries"},
                    {"label": "NST", "type": "numeric", "description": "Number of structures"},
                    {"label": "NIW", "type": "numeric", "description": "Number of internal weirs"},
                    {"label": "NWD", "type": "numeric", "description": "Number of withdrawals"},
                    {"label": "NGT", "type": "numeric", "description": "Number of gates"},
                    {"label": "NSP", "type": "numeric", "description": "Number of spillways"},
                    {"label": "NPI", "type": "numeric", "description": "Number of pipes"},
                    {"label": "NPU", "type": "numeric", "description": "Number of pumps"}
                ], "columns": 2
            },
            "Constituent Dimensions": {
                "fields": [
                    {"label": "NGC", "type": "numeric", "description": "Number of generic constituents"},
                    {"label": "NSS", "type": "numeric", "description": "Number of inorganic suspended solids"},
                    {"label": "NAL", "type": "numeric", "description": "Number of algal groups"},
                    {"label": "NEP", "type": "numeric", "description": "Number of epiphyton groups"},
                    {"label": "NBOD", "type": "numeric", "description": "Number of CBOD groups"},
                    {"label": "NMC", "type": "numeric", "description": "Number of macrophyte groups"},
                    {"label": "NZP", "type": "numeric", "description": "Number of zooplankton groups"}
                ], "columns": 2
            },
            "Miscellaneous Dimensions": {
                "fields": [
                    {"label": "NDAY", "type": "numeric", "description": "Maximum number of output dates or timestep related changes"},
                    {"label": "SELECTC", "type": "checkbox", "description": "Turn ON/OFF USGS automatic port selection from a multiple outlet structure where level is chosen by model to reach temperature target"},
                    {"label": "HABTATC", "type": "checkbox", "description": "Turn ON/OFF habitat analyses for fish and eutrophication variables"},
                    {"label": "ENVIRPC", "type": "checkbox", "description": "Turn ON/OFF environmental performance criteria"},
                    {"label": "AERATEC", "type": "checkbox", "description": "Turn ON/OFF aeration to waterbody with dissolved oxygen probe control"},
                    {"label": "INITUWL", "type": "checkbox", "description": "Turn ON/OFF initial water surface slope and velocity calculation for a river system"},
                    {"label": "ORGCC", "type": "checkbox", "description": "Turn ON/OFF simulates the organic matter as C rather than organic matter"},
                    {"label": "SED_DIAG", "type": "checkbox", "description": "Turn ON/OFF sediment diagenesis"}
                ], "columns": 2
            },
            "Time Control": {
                "fields": [
                    {"label": "TMSTRT", "type": "numeric", "description": "Starting time, Julian day"},
                    {"label": "TMEND", "type": "numeric", "description": "Ending time, Julian day"},
                    {"label": "YEAR", "type": "numeric", "description": "Starting year"}
                ], "columns": 1
            },
            "Timestep Control": {
                "fields": [
                    {"label": "NDLT", "type": "numeric", "description": "Number of timestep intervals"},
                    {"label": "DLTMIN", "type": "numeric", "decimal_places": 5, "description": "Minimum timestep, sec"}
                ], "columns": 1
            },
            "Timestep Date": {
                "fields": [
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Beginning of timestep interval, Julian day"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTD", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"}
                ], "columns": 2
            },
            "Maximum Timestep": {
                "fields": [
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Maximum timestep, sec"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTMAX", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"}
                ], "columns": 2
            },
            "Timestep Fraction": {
                "fields": [
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Fraction of calculated maximum timestep necessary for numerical stability"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"},
                    {"label": "DLTF", "type": "numeric", "decimal_places": 2, "description": "Additional intervals can be specified"}
                ], "columns": 2
            },
            "Timestep Limitations": {
                "type": "tabular",
                "rows": [
                    {"label": "VISC", "type": "checkbox", "description": "Turn ON/OFF waterbody viscosity and density calculations (e.g., for stratification)"},
                    {"label": "CELC", "type": "checkbox", "description": "Turn ON/OFF cell by cell heat exchange computations"},
                    {"label": "DLTADD", "type": "checkbox", "description": "Turn ON/OFF calculation of a minimum time step for waterbodies by adding the waterbody time step to the calculated minimum channel time step"}                    
                ],
                "columns_from": "NWB"
            },
            "Branch Geometry": { 
                "type": "tabular",
                "rows": [
                    {"label": "US", "type": "numeric", "description": "Branch upstream segment"},
                    {"label": "DS", "type": "numeric", "description": "Branch downstream segment"},
                    {"label": "UHS", "type": "numeric", "description": "Upstream boundary condition"},
                    {"label": "DHS", "type": "numeric", "description": "Downstream boundary condition"},
                    {"label": "NLMIN", "type": "numeric", "description": "Number of Layers"},
                    {"label": "SLOPE", "type": "numeric", "decimal_places": 4, "description": "Actual slope"},
                    {"label": "SLOPEC", "type": "numeric", "decimal_places": 4, "description": "Hydraulic equivalent slope (less than or equal to SLOPE)"}
                ],
                "columns_from": "NBR"
            },
            "Waterbody Definition": {
                "type": "tabular",
                "rows": [
                    {"label": "LAT", "type": "numeric", "decimal_places": 4, "description": "Upstream latitude of branch"},
                    {"label": "LONG", "type": "numeric", "decimal_places": 4, "description": "Upstream longitude of branch"},
                    {"label": "EBOT", "type": "numeric", "decimal_places": 4, "description": "Bottom elevation of the last cell of the branch"},
                    {"label": "BS", "type": "numeric", "decimal_places": 4, "description": "Distance from branch upstream end to last segment cell"},
                    {"label": "BE", "type": "numeric", "decimal_places": 4, "description": "Distance from branch upstream end to tributary"},
                    {"label": "JBDN", "type": "numeric", "description": "Downstream branch number"}
                ],
                "columns_from": "NWB"
            },
            "Initial Conditions": {
                "type": "tabular",
                "rows": [
                    {"label": "T2I", "type": "numeric", "decimal_places": 2, "description": "Initial temperature in Celcius"},
                    {"label": "ICEI", "type": "numeric", "decimal_places": 2, "description": "Initial ice thickness in meters"},
                    {"label": "WTYPEC", "type": "dropdown", "options": ["FRESH", "SALT"], "description": "Water type (FRESH or SALT)"},
                    {"label": "GRIDC", "type": "dropdown", "options": ["RECT", "TRAP"], "description": "Grid cell shape (RECT or TRAP)"}
                ],
                "columns_from": "NBR"
            },
            "Calculations": {
                "type": "tabular",
                "rows": [
                    {"label": "VBC", "type": "checkbox", "description": "Volume balance calculation, ON or OFF"},
                    {"label": "EBC", "type": "checkbox", "description": "Thermal energy balance calculation, ON or OFF"},
                    {"label": "MBC", "type": "checkbox", "description": "Mass balance calculation, ON or OFF"},
                    {"label": "PQC", "type": "checkbox", "description": "Density placed inflows, ON or OFF"},
                    {"label": "EVC", "type": "checkbox", "description": "Evaporation included in water budget, ON or OFF"},
                    {"label": "PRC", "type": "checkbox", "description": "Precipitation included, ON or OFF"},                    
                ],
                "columns_from": "NWB"
            },
            "Dead Sea": {
                "type": "tabular",
                "rows": [
                    {"label": "WINDC", "type": "checkbox", "description": "Turn ON/OFF wind"},
                    {"label": "QINC", "type": "checkbox", "description": "Turn ON/OFF all sources of water"},
                    {"label": "QOUTC", "type": "checkbox", "description": "Turn ON/OFF all sinks of water"},
                    {"label": "HEATC", "type": "checkbox", "description": "Turn ON/OFF heat exchange"}                
                ],
                "columns_from": "NWB"
            },
            "Interpolation": {
                "type": "tabular",
                "rows": [                    
                    {"label": "QINC", "type": "checkbox", "description": "Turn ON/OFF all sources of water"},
                    {"label": "DTRIC", "type": "checkbox", "description": "Turn ON/OFF all sinks of water"},
                    {"label": "HDIC", "type": "checkbox", "description": "Turn ON/OFF heat exchange"}                
                ],
                "columns_from": "NBR"
            },
            "Heat Exchange": {
                "type": "tabular",
                "rows": [
                    {"label": "SLHTC", "type": "dropdown", "options": ["TERM", "ET"],
                     "description": "Specify either term-by-term (TERM) or equilibrium temperature computations (ET) for surface heat exchange"},
                    {"label": "SROC", "type": "checkbox", "description": "Read in observed short wave solar radiation, ON or OFF"},
                    {"label": "RHEVC", "type": "checkbox", "description": "Turns ON/OFF Ryan-Harleman evaporation formula"},
                    {"label": "METIC", "type": "checkbox", "description": "Turns ON/OFF meteorological data interpolation"},
                    {"label": "FETCHC", "type": "checkbox", "description": "Turns ON/OFF fetch calculation"},
                    {"label": "AFW", "type": "numeric", "decimal_places": 2, "description": "a coefficient in the wind speed formulation"},
                    {"label": "BFW", "type": "numeric", "decimal_places": 2, "description": "b coefficient in the wind speed formulation"},
                    {"label": "CFW", "type": "numeric", "decimal_places": 2, "description": "ac coefficient in the wind speed formulation"},
                    {"label": "WINDH", "type": "numeric", "decimal_places": 2, "description": "Wind speed measurement height, m"}               
                ],
                "columns_from": "NWB"
            },
            "Ice Cover": {
                "type": "tabular",
                "rows": [
                    {"label": "ICEC", "type": "checkbox", "description": "Allow ice calculations"},
                    {"label": "SLICEC", "type": "dropdown", "options": ["SIMPLE", "DETAIL"], "description": "Specifies the method of ice cover calculations - either SIMPLE or DETAIL"},
                    {"label": "ALBEDO", "type": "numeric", "decimal_places": 2, "description": "Ratio of reflection to incident radiation (albedo of ice)"},
                    {"label": "HWI", "type": "numeric", "decimal_places": 2, "description": "Coefficient of water-ice heat exchange"},
                    {"label": "BETAI", "type": "numeric", "decimal_places": 2, "description": "Fraction of solar radiation absorbed in the ice surface"},
                    {"label": "GAMMAI", "type": "numeric", "decimal_places": 2, "description": "Solar radiation extinction coefficient, m-1"},
                    {"label": "ICEMIN", "type": "numeric", "decimal_places": 2, "description": "Minimum ice thickness before ice formation is allowed, m"},
                    {"label": "ICET2", "type": "numeric", "decimal_places": 2, "description": "Temperature above which ice formation is not allowed, °C"}                
                ],
                "columns_from": "NWB"
            },
            "Transport Scheme": {
                "type": "tabular",
                "rows": [
                    {"label": "SLTRC", "type": "dropdown", "options": ["ULTIMATE", "QUICKEST", "UPWIND"], 
                     "description": "Transport solution scheme, ULTIMATE, QUICKEST, or UPWIND"},
                    {"label": "THETA", "type": "numeric", "decimal_places": 2, "description": "Time-weighting for vertical advection scheme"}           
                ],
                "columns_from": "NWB"
            },
            "Hydaulic Coefficients": {
                "type": "tabular",
                "rows": [
                    {"label": "AX", "type": "numeric", "decimal_places": 2, "description": "Longitudinal eddy viscosity, m2 sec-1"},
                    {"label": "DX", "type": "numeric", "decimal_places": 2, "description": "Longitudinal eddy diffusivity, m2 sec-1"},
                    {"label": "CBHE", "type": "numeric", "decimal_places": 2, "description": "Coefficient of bottom heat exchange, W m-2 sec-1"},
                    {"label": "TSED", "type": "numeric", "decimal_places": 2, "description": "Sediment temperature, ºC"},
                    {"label": "FI", "type": "numeric", "decimal_places": 2, "description": "Interfacial friction factor"},
                    {"label": "TSEDF", "type": "numeric", "decimal_places": 2, "description": "Heat lost to sediments that is added back to water column"},
                    {"label": "FRICC", "type": "dropdown", "options": ["MANN", "CHEZY"], 
                     "description": "Bottom friction solution, MANN or CHEZY"}                
                ],
                "columns_from": "NWB"
            },
            "Vertical Eddy Viscosity": {
                "type": "tabular",
                "rows": [                    
                    {"label": "AZC", "type": "dropdown", "options": ["NICK", "PARAB", "RNG", "W2", "W2N", "TKE"],
                     "description": "Form of vertical turbulence closure algorithm, NICK, PARAB, RNG, W2, W2N, or TKE"},
                    {"label": "AZSLC", "type": "dropdown", "options": ["IMP", "EXP"], 
                     "description": "Specifies either implicit, IMP, or explicit, EXP, treatment of the vertical eddy viscosity in the longitudinal momentum equation"}, 
                    {"label": "AZMAX", "type": "numeric", "decimal_places": 5, "description": "Maximum value for vertical eddy viscosity, m2 s-1"}                
                ],
                "columns_from": "NWB"
            },
            "Structures": {
                "type": "tabular",
                "rows": [
                    {"label": "NSTR", "type": "numeric",  "description": "Number of branch outlet structures"},
                    {"label": "DYNSTRUC", "type": "checkbox", "description": "Use dynamic centerline elevation for the structure, "
                    "usually the centerline elevation is fixed and specified with ESTR. If this is ON, the model will read a separate file for each branch called dynselevX.npt where X is the branch number."}                
                ],
                "columns_from": "NBR"
            }
        }
        self.initUI()
        self.load_gui_state()
        self.sync_tabs()

    def initUI(self):
        main_layout = QHBoxLayout()
        self.tab_list = QListWidget()
        self.tab_list.itemClicked.connect(self.display_tab)
        self.stacked_widget = QStackedWidget()

        self.tabs = {}
        for title, data in self.tab_data.items():
            if data.get("type") == "tabular":
                tab_widget = TabularDataTab(data["rows"], tab_name=title)  # Pass tab name
            else:
                tab_widget = UserDataTab(data["fields"], columns=data["columns"])
            self.tabs[title] = tab_widget
            self.tab_list.addItem(title)
            self.stacked_widget.addWidget(tab_widget)
        
        self.tab_list.currentRowChanged.connect(self.sync_tabs)

        self.save_all_button = QPushButton("Save All to CSV")
        self.save_all_button.clicked.connect(self.save_all_to_csv)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.stacked_widget)
        right_layout.addWidget(self.save_all_button)

        main_layout.addWidget(self.tab_list, 1)
        main_layout.addLayout(right_layout, 3)
        self.setLayout(main_layout)

        if self.tab_list.count() > 0:
            self.tab_list.setCurrentRow(0)
            self.display_tab(self.tab_list.item(0))

    def sync_tabs(self):
        """Syncs data between tabs, particularly for dynamic table sizes."""
        nwb_value = 0
        nbr_value = 0
        grid_tab = self.tabs.get("Grid Dimensions and General Settings")
        if grid_tab:
            for label, value in grid_tab.get_data():
                if label == "NWB" and value:
                    try:
                        nwb_value = int(value)
                    except (ValueError, TypeError):
                        pass
                elif label == "NBR" and value:
                    try:
                        nbr_value = int(value)
                    except (ValueError, TypeError):
                        pass

        # Sync all NWB-dependent tabs
        nwb_tabs = ["Timestep Limitations", "Waterbody Definition", "Calculations", "Dead Sea",
                    "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity"]
        for tab_name in nwb_tabs:
            tab = self.tabs.get(tab_name)
            if tab and isinstance(tab, TabularDataTab):
                current_data = tab.get_data()
                tab.set_columns(max(1, nwb_value))  # Ensure at least 1 column
                tab.set_data(current_data)

        # Sync all NBR-dependent tabs
        nbr_tabs = ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures"]
        for tab_name in nbr_tabs:
            tab = self.tabs.get(tab_name)
            if tab and isinstance(tab, TabularDataTab):
                current_data = tab.get_data()
                tab.set_columns(max(1, nbr_value))  # Ensure at least 1 column
                tab.set_data(current_data)

        # After NBR-dependent sync, adjust Structures tab rows dynamically based on max NSTR
        structures_tab = self.tabs.get("Structures")
        if structures_tab and isinstance(structures_tab, TabularDataTab):
            try:
                # Compute maximum NSTR across branches (row labeled 'NSTR')
                max_nstr = 0
                # Find index of NSTR row in current definitions (should be 0, but search defensively)
                nstr_row_index = next((idx for idx, rd in enumerate(structures_tab.row_definitions) if rd.get("label") == "NSTR"), None)
                if nstr_row_index is not None:
                    for col_index in range(structures_tab.table.columnCount()):
                        widget = structures_tab.table.cellWidget(nstr_row_index, col_index)
                        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                            try:
                                max_nstr = max(max_nstr, int(widget.value()))
                            except Exception:
                                pass
                # Determine current dynamic rows count beyond the base definitions
                base_len = len(getattr(structures_tab, 'base_row_definitions', []))
                current_dynamic = max(0, len(structures_tab.row_definitions) - base_len)

                if max_nstr != current_dynamic:
                    # Build new row definitions: keep base rows, then add placeholders for each structure
                    new_rows = list(structures_tab.base_row_definitions)
                    for i in range(max_nstr):
                        new_rows.append({
                            "label": f"STRUCT_{i+1}",
                            "type": "text",
                            "description": f"Structure {i+1} parameters for each branch"
                        })
                    structures_tab.set_row_definitions(new_rows)
            except Exception:
                # Fail-safe: do not break sync if anything unexpected occurs
                pass
    
    def display_tab(self, item: QListWidgetItem):
        self.sync_tabs()
        tab_name = item.text()
        tab_widget = self.tabs[tab_name]
        self.stacked_widget.setCurrentWidget(tab_widget)

    def save_all_to_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save All Data to CSV", "w2_con.csv", "CSV Files (*.csv)")

        if file_path:
            try:
                with open(file_path, 'w', newline='') as file:
                    writer = csv.writer(file)
                    
                    for tab_name, tab_widget in self.tabs.items():
                        if isinstance(tab_widget, UserDataTab):
                            current_tab_data = tab_widget.get_data()
                            labels = [label for label, _ in current_tab_data]
                            values = [value if value is not None else "" for _, value in current_tab_data]
                            writer.writerow(labels)
                            writer.writerow(values)
                        elif isinstance(tab_widget, TabularDataTab):
                            tabular_data = tab_widget.get_data()
                            if tabular_data:
                                if tab_name in ["Timestep Limitations", "Waterbody Definition", "Calculations", "Dead Sea",
                                                "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity"]:
                                    headers = [f"WB{i+1}" for i in range(len(tabular_data[0]) - 1)]
                                elif tab_name in ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures"]:
                                    headers = [f"BR{i+1}" for i in range(len(tabular_data[0]) - 1)]
                                else:
                                    headers = []
                                writer.writerow(headers)
                                
                                for row_data in tabular_data:
                                    writer.writerow(row_data[1:])
                        writer.writerow([])
                
                QMessageBox.information(self, "Success", "All data saved successfully!")
                self.save_gui_state()
                for tab_widget in self.tabs.values():
                    if isinstance(tab_widget, UserDataTab) or isinstance(tab_widget, TabularDataTab):
                        tab_widget.clear_fields()

            except IOError as e:
                QMessageBox.critical(self, "Error", f"Error saving file: {e}")

    def save_gui_state(self):
        all_gui_data = {}
        for tab_name, tab_widget in self.tabs.items():
            if isinstance(tab_widget, UserDataTab):
                data_list_of_lists = [list(item) for item in tab_widget.get_data()]
                all_gui_data[tab_name] = data_list_of_lists
            elif isinstance(tab_widget, TabularDataTab):
                all_gui_data[tab_name] = tab_widget.get_data()

        try:
            with open(self.APP_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_gui_data, f, indent=4)
        except IOError as e:
            QMessageBox.warning(self, "Save State Error", f"Could not save application state: {e}")

    def load_gui_state(self):
        if not os.path.exists(self.APP_STATE_FILE):
            return

        try:
            with open(self.APP_STATE_FILE, 'r', encoding='utf-8') as f:
                saved_gui_data = json.load(f)

            for tab_name, tab_data in saved_gui_data.items():
                if tab_name in self.tabs:
                    tab_widget = self.tabs[tab_name]
                    if isinstance(tab_widget, UserDataTab):
                        data_list = []
                        if isinstance(tab_data, list):
                            data_list = [tuple(item) for item in tab_data]
                        elif isinstance(tab_data, dict):
                            data_list = list(tab_data.items())
                        tab_widget.set_data(data_list)
                    elif isinstance(tab_widget, TabularDataTab):
                        tab_widget.set_data(tab_data)

        except (IOError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Load State Error", f"Could not load application state: {e}\nStarting with empty fields.")
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CompactApp()
    window.show()
    sys.exit(app.exec())
