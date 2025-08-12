import sys
import csv
import json
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QStackedWidget, QListWidget, 
                             QHBoxLayout, QFileDialog, QMessageBox, QListWidgetItem,
                             QCheckBox, QComboBox, QGridLayout, QSpinBox, QDoubleSpinBox,
                             QTableWidget, QTableWidgetItem, QAbstractItemView)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal

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
    # Emitted when a numeric cell that affects table structure changes (e.g., NSTR)
    structureChanged = pyqtSignal()

    def __init__(self, row_definitions, tab_name=None, parent=None):
        super().__init__(parent)
        self.row_definitions = row_definitions
        self.tab_name = tab_name  # Store tab name directly
        self.table = QTableWidget()
        self.table.setRowCount(len(self.row_definitions))
        # Ensure cell widgets are editable/interactable
        try:
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        except Exception:
            pass
        
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

        is_hydro_out = (self.tab_name == "Hydrodynamic Output Control")
        is_snapshot_out = (self.tab_name == "Snapshot Output Control")
        is_screen_out = (self.tab_name == "Screen Output Control")
        is_profile_out = (self.tab_name == "Profile Output Control")
        extra_cols = 0
        if is_snapshot_out or is_screen_out:
            # Determine extra columns from NS count values (max across columns)
            try:
                target_label = "NSNP" if is_snapshot_out else "NSCR"
                nscr_index = next((idx for idx, rd in enumerate(self.row_definitions) if rd.get("label") == target_label), 1)
                max_nscr = 0
                # Check existing widgets in NS row for a value
                for c in range(self.table.columnCount()):
                    w = self.table.cellWidget(nscr_index, c)
                    if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                        try:
                            max_nscr = max(max_nscr, int(w.value()))
                        except Exception:
                            pass
                extra_cols = max(0, max_nscr - 1)
            except Exception:
                extra_cols = 0
        elif is_profile_out:
            # Determine extra columns from product NPRF * NIPRF (minus 1 base column)
            try:
                nprf_index = next((idx for idx, rd in enumerate(self.row_definitions) if rd.get("label") == "NPRF"), 1)
                niprf_index = next((idx for idx, rd in enumerate(self.row_definitions) if rd.get("label") == "NIPRF"), 2)
                max_nprf = 1
                max_niprf = 1
                for c in range(self.table.columnCount()):
                    wn = self.table.cellWidget(nprf_index, c)
                    wi = self.table.cellWidget(niprf_index, c)
                    if isinstance(wn, (QSpinBox, QDoubleSpinBox)):
                        try:
                            max_nprf = max(max_nprf, int(wn.value()))
                        except Exception:
                            pass
                    if isinstance(wi, (QSpinBox, QDoubleSpinBox)):
                        try:
                            max_niprf = max(max_niprf, int(wi.value()))
                        except Exception:
                            pass
                extra_cols = max(0, (max_nprf * max_niprf) - 1)
            except Exception:
                extra_cols = 0
        
        total_columns = (num_columns + 3 if is_hydro_out else num_columns) + (extra_cols if (is_snapshot_out or is_screen_out or is_profile_out) else 0)
        self.table.setColumnCount(total_columns)
        
        # Use stored tab name for correct headers
        if self.tab_name in ["Timestep Limitations", "Waterbody Definition", "Calculations", "Dead Sea", 
                             "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity"]:
            column_headers = [f"WB{i+1}" for i in range(num_columns)]
        elif self.tab_name in ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures", "Distributed Tributaries"]:
            column_headers = [f"BR{i+1}" for i in range(num_columns)]
        elif self.tab_name == "Tributary":
            # Build headers TR# (Name) using TRNAME row if present
            names = [""] * num_columns
            trname_index = next((idx for idx, rd in enumerate(self.row_definitions) if rd.get("label") == "TRNAME"), None)
            if trname_index is not None:
                for col_index in range(num_columns):
                    name_widget = self.table.cellWidget(trname_index, col_index)
                    if isinstance(name_widget, QLineEdit):
                        names[col_index] = name_widget.text().strip()
            column_headers = [f"TR{i+1} ({names[i]})" if names[i] else f"TR{i+1}" for i in range(num_columns)]
        elif is_hydro_out:
            # First 3 fixed columns then HPRWBC# columns for each waterbody
            column_headers = ["HNAME", "FMTH", "HMULT"] + [f"HPRWBC{i+1}" for i in range(num_columns)]
        elif is_snapshot_out or is_screen_out:
            # First column name is SNP for snapshot/screen; extra columns have no headers
            column_headers = ["SNP"] + [""] * (total_columns - 1)
        elif is_profile_out:
            column_headers = ["PRFC"] + [""] * (total_columns - 1)
        else:
            column_headers = [f"Col{i+1}" for i in range(num_columns)]
            
        self.table.setHorizontalHeaderLabels(column_headers)
        
        # Populate each cell with the appropriate widget type
        for row_index, row_def in enumerate(self.row_definitions):
            for col_index in range(total_columns):
                # Clear any existing widget or item to avoid mixed cell content when types change
                try:
                    self.table.removeCellWidget(row_index, col_index)
                except Exception:
                    pass
                try:
                    self.table.takeItem(row_index, col_index)
                except Exception:
                    pass
                
                if is_profile_out:
                    # Only PRFD/PRFF/IPRF have data in extra columns; first column uses declared type
                    if col_index == 0:
                        if row_def.get("label") in ("NPRF", "NIPRF"):
                            pspin = QSpinBox()
                            pspin.setMinimum(1)
                            pspin.setMaximum(row_def.get("max", 999999))
                            try:
                                if pspin.value() < 1:
                                    pspin.setValue(1)
                                pspin.valueChanged.connect(self._on_numeric_value_changed)
                                pspin.valueChanged.connect(self.structureChanged.emit)
                            except Exception:
                                pass
                            self.table.setCellWidget(row_index, col_index, pspin)
                            continue
                    else:
                        if row_index in (0, 1, 2):
                            # PRFC, NPRF, NIPRF: leave blank and uneditable
                            item = QTableWidgetItem("")
                            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                            self.table.setItem(row_index, col_index, item)
                            continue
                        if row_index in (3, 4):
                            # PRFD, PRFF: numeric 2 decimals
                            spin = QDoubleSpinBox()
                            spin.setDecimals(2)
                            spin.setMinimum(0.0)
                            spin.setMaximum(999999.0)
                            try:
                                spin.valueChanged.connect(self._on_numeric_value_changed)
                            except Exception:
                                pass
                            self.table.setCellWidget(row_index, col_index, spin)
                            continue
                        if row_index == 5:
                            # IPRF integer
                            spin = QSpinBox()
                            spin.setMinimum(0)
                            spin.setMaximum(999999)
                            try:
                                spin.valueChanged.connect(self._on_numeric_value_changed)
                            except Exception:
                                pass
                            self.table.setCellWidget(row_index, col_index, spin)
                            continue
                
                if is_hydro_out:
                    # Column-specific behavior for Hydrodynamic Output Control
                    if col_index == 0:
                        # HNAME column: editable text with initial value for user to edit
                        line_edit = QLineEdit()
                        try:
                            line_edit.setText(row_def.get('label', 'HNAME'))
                            line_edit.setPlaceholderText('Edit HNAME')
                        except Exception:
                            pass
                        self.table.setCellWidget(row_index, col_index, line_edit)
                        continue
                    if col_index == 1:
                        # FMTH dropdown
                        combo_box = QComboBox()
                        combo_box.addItems(["(I10)", "(f10.3)"])
                        self.table.setCellWidget(row_index, col_index, combo_box)
                        continue
                    if col_index == 2:
                        # HMULT numeric with 3 decimals
                        spin = QDoubleSpinBox()
                        spin.setDecimals(3)
                        spin.setMinimum(0.0)
                        spin.setMaximum(999999.0)
                        try:
                            spin.valueChanged.connect(self._on_numeric_value_changed)
                        except Exception:
                            pass
                        self.table.setCellWidget(row_index, col_index, spin)
                        continue
                    # HPRWBC# columns -> all checkboxes
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    self.table.setItem(row_index, col_index, item)
                    continue
                
                if is_snapshot_out or is_screen_out:
                    # First original column uses declared type; extra columns only apply to SNPD/SNPF rows (row 2 and 3)
                    if col_index == 0:
                        # Use declared types for first column
                        if (is_snapshot_out and row_def.get("label") == "NSNP") or (is_screen_out and row_def.get("label") == "NSCR"):
                            spinbox = QSpinBox()
                            spinbox.setMinimum(1)
                            spinbox.setMaximum(row_def.get("max", 999999))
                            try:
                                spinbox.setValue(spinbox.minimum())
                            except Exception:
                                pass
                            try:
                                spinbox.valueChanged.connect(self._on_numeric_value_changed)
                                spinbox.valueChanged.connect(self.structureChanged.emit)
                            except Exception:
                                pass
                            self.table.setCellWidget(row_index, col_index, spinbox)
                            continue
                    else:
                        # Extra columns: first two rows (SNPC/NSNP or SCRC/NSCR) uneditable and blank; SNPD/SNPF get numeric editors
                        if (is_snapshot_out and row_index in (0, 1)) or (is_screen_out and row_index in (0, 1)):
                            item = QTableWidgetItem("")
                            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                            self.table.setItem(row_index, col_index, item)
                            continue
                        if row_index in (2, 3):
                            spin = QDoubleSpinBox()
                            spin.setDecimals(2)
                            spin.setMinimum(0.0)
                            spin.setMaximum(999999.0)
                            try:
                                spin.valueChanged.connect(self._on_numeric_value_changed)
                            except Exception:
                                pass
                            self.table.setCellWidget(row_index, col_index, spin)
                            continue
                    # If falling through for first column, handled below as default
                
                # Default behavior for all other tabs
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
                    # If this is the Structures tab and this numeric row is NSTR, connect signals for real-time update
                    if self.tab_name == "Structures" and row_def.get("label") == "NSTR":
                        try:
                            # Connect to a lightweight updater that only adjusts dynamic rows
                            spinbox.valueChanged.connect(self.structureChanged.emit)
                        except Exception:
                            pass
                    # Track when user actually sets a numeric value
                    try:
                        spinbox.valueChanged.connect(self._on_numeric_value_changed)
                    except Exception:
                        pass
                    # Ensure numeric widgets are enabled and editable
                    try:
                        spinbox.setEnabled(True)
                        spinbox.setReadOnly(False)
                    except Exception:
                        pass
                    self.table.setCellWidget(row_index, col_index, spinbox)
                elif cell_type == "text":
                    line_edit = QLineEdit()
                    # If Tributary TRNAME, update headers on text change
                    if self.tab_name == "Tributary" and row_def.get("label") == "TRNAME":
                        try:
                            line_edit.textChanged.connect(self.update_headers_only)
                        except Exception:
                            pass
                    self.table.setCellWidget(row_index, col_index, line_edit)
                elif cell_type == "dropdown":
                    combo_box = QComboBox()
                    combo_box.addItems(row_def.get("options", []))
                    self.table.setCellWidget(row_index, col_index, combo_box)
                elif cell_type == "file":
                    button = QPushButton("Browse...")
                    def make_handler(r=row_index, c=col_index, b=button):
                        def handler():
                            start_dir = os.path.dirname(os.path.abspath(__file__))
                            file_path, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir, "All Files (*)")
                            if file_path:
                                try:
                                    base_dir = start_dir
                                    rel_path = os.path.relpath(file_path, base_dir)
                                    if not rel_path.startswith(".."):
                                        display_path = f"./{rel_path}"
                                    else:
                                        display_path = file_path
                                except Exception:
                                    display_path = file_path
                                b.setText(display_path)
                                b.setProperty("file_path", file_path)
                        return handler
                    button.clicked.connect(make_handler())
                    self.table.setCellWidget(row_index, col_index, button)

    def _on_numeric_value_changed(self, *args):
        sender_widget = self.sender()
        if isinstance(sender_widget, (QSpinBox, QDoubleSpinBox)):
            sender_widget.setProperty("is_set", True)

    def update_headers_only(self):
        """Update only the horizontal header labels without recreating any cells."""
        num_columns = max(1, self.table.columnCount())
        if self.tab_name in ["Timestep Limitations", "Waterbody Definition", "Calculations", "Dead Sea", 
                             "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity"]:
            column_headers = [f"WB{i+1}" for i in range(num_columns)]
        elif self.tab_name in ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures", "Distributed Tributaries"]:
            column_headers = [f"BR{i+1}" for i in range(num_columns)]
        elif self.tab_name == "Tributary":
            names = [""] * num_columns
            trname_index = next((idx for idx, rd in enumerate(self.row_definitions) if rd.get("label") == "TRNAME"), None)
            if trname_index is not None:
                for col_index in range(num_columns):
                    name_widget = self.table.cellWidget(trname_index, col_index)
                    if isinstance(name_widget, QLineEdit):
                        names[col_index] = name_widget.text().strip()
                column_headers = [f"TR{i+1} ({names[i]})" if names[i] else f"TR{i+1}" for i in range(num_columns)]
        elif self.tab_name == "Hydrodynamic Output Control":
            column_headers = ["HNAME", "FMTH", "HMULT"] + [f"HPRWBC{i+1}" for i in range(num_columns)]
        elif self.tab_name == "Snapshot Output Control":
            column_headers = ["SNP"] + [""] * (num_columns - 1)
        elif self.tab_name == "Screen Output Control":
            column_headers = ["SNP"] + [""] * (num_columns - 1)
        elif self.tab_name == "Profile Output Control":
            column_headers = ["PRFC"] + [""] * (num_columns - 1)
        else:
            column_headers = [f"Col{i+1}" for i in range(num_columns)]
        self.table.setHorizontalHeaderLabels(column_headers)

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
 
        # Restore data by matching labels to preserve values across reordering
        try:
            old_by_label = {}
            for row in current_data:
                if isinstance(row, list) and row:
                    old_by_label[row[0]] = row[1:]
            remapped = []
            for row_def in self.row_definitions:
                label = row_def.get('label')
                values = old_by_label.get(label, [])
                remapped.append([label] + values)
            self.set_data(remapped)
        except Exception:
            self.set_data(current_data)

    def get_data(self):
        """Returns tabular data as a list of lists."""
        data = []
        for row_index, row_def in enumerate(self.row_definitions):
            row_data = [row_def['label']]
            for col_index in range(self.table.columnCount()):
                widget = self.table.cellWidget(row_index, col_index)
                item = self.table.item(row_index, col_index)

                # Prefer widget value if present
                if widget is not None:
                    # Checkbox widgets are represented as items, so widgets here are editors
                    if isinstance(widget, QSpinBox):
                        # Leave blank unless user explicitly set value
                        is_set = widget.property("is_set")
                        row_data.append(str(widget.value()) if is_set else "")
                    elif isinstance(widget, QDoubleSpinBox):
                        is_set = widget.property("is_set")
                        row_data.append(str(widget.value()) if is_set else "")
                    elif isinstance(widget, QLineEdit):
                        row_data.append(widget.text())
                    elif isinstance(widget, QComboBox):
                        row_data.append(widget.currentText())
                    elif isinstance(widget, QPushButton):
                        txt = widget.text().strip()
                        row_data.append(txt if txt and txt != "Browse..." else "")
                    else:
                        row_data.append("")
                    continue

                # If no widget, read from item
                if item is not None:
                    if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                        value = "ON" if item.checkState() == Qt.CheckState.Checked else "OFF"
                        row_data.append(value)
                    else:
                        row_data.append(item.text())
                else:
                    row_data.append("")
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
                        widget = self.table.cellWidget(row_index, col_index)
                        item = self.table.item(row_index, col_index)
                        if widget is not None:
                            if isinstance(widget, QSpinBox):
                                try:
                                    widget.setValue(int(value))
                                except (ValueError, TypeError, AttributeError):
                                    try:
                                        widget.setValue(widget.minimum())
                                    except Exception:
                                        pass
                            elif isinstance(widget, QDoubleSpinBox):
                                try:
                                    widget.setValue(float(value))
                                except (ValueError, TypeError, AttributeError):
                                    try:
                                        widget.setValue(widget.minimum())
                                    except Exception:
                                        pass
                            elif isinstance(widget, QLineEdit):
                                widget.setText(value)
                            elif isinstance(widget, QComboBox):
                                try:
                                    widget.setCurrentText(value)
                                except Exception:
                                    pass
                            elif isinstance(widget, QPushButton):
                                widget.setText(value)
                            continue

                        # No widget; operate on item
                        if item is not None:
                            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                                item.setCheckState(Qt.CheckState.Checked if value == "ON" else Qt.CheckState.Unchecked)
                            else:
                                item.setText(value)
                        # else: nothing to set

    def clear_fields(self):
        """Clears all fields in the table based on their type."""
        for row_index, row_def in enumerate(self.row_definitions):
            for col_index in range(self.table.columnCount()):
                widget = self.table.cellWidget(row_index, col_index)
                item = self.table.item(row_index, col_index)

                if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    item.setCheckState(Qt.CheckState.Unchecked)
                    continue

                if isinstance(widget, QSpinBox):
                    widget.setValue(widget.minimum())
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(widget.minimum())
                elif isinstance(widget, QLineEdit):
                    widget.clear()
                elif isinstance(widget, QComboBox):
                    widget.setCurrentIndex(0)
                elif isinstance(widget, QPushButton):
                    widget.setText("")
                    widget.setProperty("file_path", None)
                else:
                    # Fallback based on declared type
                    cell_type = row_def.get("type", "checkbox")
                    if cell_type == "numeric" and widget is not None:
                        try:
                            widget.setValue(widget.minimum())
                        except Exception:
                            pass
                    elif cell_type == "text" and widget is not None:
                        try:
                            widget.clear()
                        except Exception:
                            pass
                    elif cell_type == "dropdown" and widget is not None:
                        try:
                            widget.setCurrentIndex(0)
                        except Exception:
                            pass
                    # else: nothing to clear

class CompactApp(QWidget):
    APP_STATE_FILE = "app_state.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Compact Data Entry App")
        self.setGeometry(100, 100, 800, 600)
        # Reentrancy guard for syncs triggered by UI changes
        self._sync_in_progress = False
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
                    {"label": "DYNSTRUC", "type": "checkbox", "description": "Use dynamic centerline elevation for the structure, \
                    usually the centerline elevation is fixed and specified with ESTR. If this is ON, the model will read a separate file for each branch called dynselevX.npt where X is the branch number."}                
                ],
                "columns_from": "NBR"
            },
            "Tributary": {
                "type": "tabular",
                "rows": [
                    {"label": "TRNAME", "type": "text", "description": "Tributary name used in column header"},
                    {"label": "PTRC", "type": "dropdown", "options": ["DISTR", "DENSITY", "SPECIFIY"], "description": "Placeholder: PTRC description"},
                    {"label": "TRIC", "type": "checkbox", "description": "Placeholder: TRIC description"},
                    {"label": "ITR", "type": "numeric", "description": "Placeholder: ITR description"},
                    {"label": "ELTRT", "type": "numeric", "decimal_places": 2, "description": "Placeholder: ELTRT description"},
                    {"label": "ELTRB", "type": "numeric", "decimal_places": 2, "description": "Placeholder: ELTRB description"},
                    {"label": "QTRFN", "type": "file", "description": "Placeholder: QTRFN local path"},
                    {"label": "TTRFN", "type": "file", "description": "Placeholder: TTRFN local path"},
                    {"label": "CTRFN", "type": "file", "description": "Placeholder: CTRFN local path"}
                ],
                "columns_from": "NTR"
            },
            "Distributed Tributaries": {
                "type": "tabular",
                "rows": [
                    {"label": "DTRC", "type": "checkbox", "description": "Distributed tributary option, ON or OFF"}
                ],
                "columns_from": "NBR"
            },
            "Pipes": {
                "type": "tabular",
                "rows": [
                    {"label": "IUPI", "type": "numeric", "description": "Upstream segment number"},
                    {"label": "IDPI", "type": "numeric", "description": "Downstream segment number"},
                    {"label": "EUPI", "type": "numeric", "decimal_places": 3, "description": "Elevation upstream invert, m"},
                    {"label": "EDPI", "type": "numeric", "decimal_places": 3, "description": "Elevation downstream invert, m"},
                    {"label": "WPI", "type": "numeric", "decimal_places": 3, "description": "Pipe diameter, m"},
                    {"label": "DLXPI", "type": "numeric", "decimal_places": 3, "description": "Pipe length, m"},
                    {"label": "FPI", "type": "numeric", "decimal_places": 3, "description": "friction factor (Mannings)"},
                    {"label": "FMINPI", "type": "numeric", "decimal_places": 3, "description": "minor losses friction factor (Mannings)"},
                    {"label": "WTHLC", "type": "dropdown", "options": ["DOWN", "LAT"], "description": "DOWN or LAT, withdrawal control for at end of segment or middle"},
                    {"label": "DYNPIPE", "type": "checkbox", "description": "Dynamic pipe read input file, ON or OFF"},
                    {"label": "PUPIC", "type": "dropdown", "options": ["DISTR", "SPECIFY", "DENSITY"], "description": "PipeUp inflow: DISTR, SPECIFY, DENSITY"},
                    {"label": "ETUPI", "type": "numeric", "decimal_places": 3, "description": "PipeUp Elevation top in m if SPECIFY"},
                    {"label": "EBUPI", "type": "numeric", "decimal_places": 3, "description": "PipeUp Elevation bottom in m if SPECIFY"},
                    {"label": "KTUPI", "type": "numeric", "description": "PipeUp Selective withdrawal top layer, Top layer above which selective withdrawal will not occur"},
                    {"label": "KBUPI", "type": "numeric", "description": "PipeUp Selective withdrawal bottom layer, Bottom layer below which selective withdrawal will not occur"},
                    {"label": "PDPIC", "type": "dropdown", "options": ["DISTR", "SPECIFY", "DENSITY"], "description": "PipeDown inflow: DISTR, SPECIFY, DENSITY"},
                    {"label": "ETDPI", "type": "numeric", "decimal_places": 3, "description": "PipeDown Elevation top in m if SPECIFY"},
                    {"label": "EBDPI", "type": "numeric", "decimal_places": 3, "description": "PipeDown Elevation bottom in m if SPECIFY"},
                    {"label": "KTDPI", "type": "numeric", "description": "PipeDown Selective withdrawal top layer, Top layer above which selective withdrawal will not occur"},
                    {"label": "KBDPI", "type": "numeric", "description": "PipeDown Selective withdrawal bottom layer, Bottom layer below which selective withdrawal will not occur"}
                ],
                "columns_from": "NPI"
            },
            "Spillway": {
                "type": "tabular",
                "rows": [
                    {"label": "IUSP", "type": "numeric", "description": "Upstream segment number, spillway segment location"},
                    {"label": "IDSP", "type": "numeric", "description": "Downstream segment number, downstream segment spillway outflow enters"},
                    {"label": "ESP", "type": "numeric", "decimal_places": 3, "description": "Spillway elevation (crest), m"},
                    {"label": "BTSP1", "type": "numeric", "decimal_places": 3, "description": "Empirical coefficient for free-flowing conditions"},
                    {"label": "BTSP2", "type": "numeric", "decimal_places": 3, "description": "Empirical coefficient for submerged conditions"},
                    {"label": "LATSPC", "type": "dropdown", "options": ["DOWN", "LAT"], "description": "Downstream or lateral withdrawal, DOWN or LAT"},
                    {"label": "PUSPC", "type": "dropdown", "options": ["DISTR", "DENSITY", "SPECIFY"], "description": "How inflows enter into the upstream spillway segment, DISTR, DENSITY, or SPECIFY"},
                    {"label": "ETUSP", "type": "numeric", "description": "Top elevation spillway inflows enter using SPECIFY option, m"},
                    {"label": "EBUSP", "type": "numeric", "decimal_places": 3, "description": "Bottom elevation spillway inflows enter using SPECIFY option, m"},
                    {"label": "KTUSP", "type": "numeric", "decimal_places": 3, "description": "Top layer above which selective withdrawal will not occur"},
                    {"label": "KBUSP", "type": "numeric", "decimal_places": 3, "description": "Bottom layer below which selective withdrawal will not occur"},
                    {"label": "PDSPC", "type": "dropdown", "options": ["DISTR", "DENSITY", "SPECIFY"], "description": "How inflows enter into the downstream spillway segment, DISTR, DENSITY, or SPECIFY"},
                    {"label": "ETDSP", "type": "numeric", "decimal_places": 3, "description": "Top elevation spillway inflows enter using SPECIFY option, m"},
                    {"label": "EBDSP", "type": "numeric", "decimal_places": 3, "description": "Bottom elevation spillway inflows enter using SPECIFY option, m"},
                    {"label": "KTDSP", "type": "numeric", "description": "Top layer above which selective withdrawal will not occur"},
                    {"label": "KBDSP", "type": "numeric", "description": "Bottom layer below which selective withdrawal will not occur"},
                    {"label": "GASSPC", "type": "checkbox", "description": "Dissolved gas computations ON or OFF"},
                    {"label": "EQSP", "type": "numeric", "description": "Equation number for computing dissolved gas"},
                    {"label": "AGASSP", "type": "numeric", "decimal_places": 3, "description": "a empirical coefficient"},
                    {"label": "BGASSP", "type": "numeric", "decimal_places": 3, "description": "b empirical coefficient"},
                    {"label": "CGASSP", "type": "numeric", "decimal_places": 3, "description": "c empirical coefficient"}
                ],
                "columns_from": "NSP"
            },
            "Gates": {
                "type": "tabular",
                "rows": [
                    {"label": "IUGT", "type": "numeric", "description": "Upstream segment number"},
                    {"label": "IDGT", "type": "numeric", "description": "Downstream segment number"},
                    {"label": "EGT", "type": "numeric", "decimal_places": 3, "description": "Gate elevation, m"},
                    {"label": "A1GT", "type": "numeric", "decimal_places": 3, "description": "a1 coefficient in gate equation for free flowing conditions"},
                    {"label": "B1GT", "type": "numeric", "decimal_places": 3, "description": "b1 coefficient in gate equation for free flowing conditions"},
                    {"label": "G1GT", "type": "numeric", "decimal_places": 3, "description": "gamma1 coefficient for free flowing conditions"},
                    {"label": "A2GT", "type": "numeric", "decimal_places": 3, "description": "a2 coefficient in gate equation for submerged conditions"},
                    {"label": "B2GT", "type": "numeric", "decimal_places": 3, "description": "b2 coefficient in gate equation for submerged conditions"},
                    {"label": "G2GT", "type": "numeric", "decimal_places": 3, "description": "gamma2 coefficient for submerged conditions"},
                    {"label": "LATGTC", "type": "dropdown", "options": ["DOWN", "LAT"], "description": "Downstream or lateral withdrawal at DOWN or LAT"},
                    {"label": "PUGTC", "type": "dropdown", "options": ["DISTR", "DENSITY", "SPECIFY"], "description": "How inflows enter the upstream gate segment, DISTR, DENSITY, or SPECIFY"},
                    {"label": "ETUGT", "type": "numeric", "decimal_places": 3, "description": "Top elevation gate inflows enter using the SPECIFY option, m"},
                    {"label": "EBUGT", "type": "numeric", "decimal_places": 3, "description": "Bottom elevation gate inflows enter using the SPECIFY option, m"},
                    {"label": "KTUGT", "type": "numeric", "description": "Top layer above which selective withdrawal will not occur"},
                    {"label": "KBUGT", "type": "numeric", "description": "Bottom layer below which selective withdrawal will not occur"},
                    {"label": "PDGTC", "type": "dropdown", "options": ["DISTR", "DENSITY", "SPECIFY"], "description": "How inflows enter the downstream gate segment, DISTR, DENSITY, or SPECIFY"},
                    {"label": "ETDGT", "type": "numeric", "decimal_places": 3, "description": "Top elevation gate inflows enter using the SPECIFY option, m"},
                    {"label": "EBDGT", "type": "numeric", "decimal_places": 3, "description": "Bottom elevation gate inflows enter using the SPECIFY option, m"},
                    {"label": "KTDGT", "type": "numeric", "description": "Top layer above which selective withdrawal will not occur"},
                    {"label": "KBDGT", "type": "numeric", "description": "Bottom layer below which selective withdrawal will not occur"},
                    {"label": "DYNGTC", "type": "dropdown", "options": ["B", "ZGT", "FLOW"], "description": "Either B, ZGT, or FLOW"},
                    {"label": "GASGTC", "type": "checkbox", "description": "Dissolved gas computations ON or OFF"},
                    {"label": "EQGT", "type": "numeric", "description": "Equation number for computing dissolved gas"},
                    {"label": "AGASGT", "type": "numeric", "decimal_places": 3, "description": "a empirical coefficient"},
                    {"label": "BGASGT", "type": "numeric", "decimal_places": 3, "description": "b empirical coefficient"},
                    {"label": "CGASGT", "type": "numeric", "decimal_places": 3, "description": "c empirical coefficient"}
                ],
                "columns_from": "NGT"
            },
            "Pumps": {
                "type": "tabular",
                "rows": [
                    {"label": "IUPU", "type": "numeric", "description": "Upstream segment number where water is withdrawn"},
                    {"label": "IDPU", "type": "numeric", "description": "Downstream segment number where water enters"},
                    {"label": "EPU", "type": "numeric", "decimal_places": 3, "description": "Elevation of pump, m"},
                    {"label": "STRTPU", "type": "numeric", "decimal_places": 3, "description": "Starting day of pumping Julian day"},
                    {"label": "ENDPU", "type": "numeric", "decimal_places": 3, "description": "Ending day of pumping Julian day"},
                    {"label": "EONPU", "type": "numeric", "decimal_places": 3, "description": "Pump starting elevation, m"},
                    {"label": "EOFFPU", "type": "numeric", "decimal_places": 3, "description": "Pump stopping elevation, m"},
                    {"label": "QPU", "type": "numeric", "decimal_places": 3, "description": "Pump flow rate, m3/s"},
                    {"label": "LATPUC", "type": "dropdown", "options": ["DOWN", "LAT"], "description": "Downstream or lateral withdrawal, DOWN or LAT"},
                    {"label": "DYNPUM", "type": "checkbox", "description": "Dynamic pump control ON or OFF"},
                    {"label": "PPUC", "type": "dropdown", "options": ["DISTR", "DENSITY", "SPECIFY"], "description": "How inflows enter into the downstream pump segment, DISTR, DENSITY, or SPECIFY"},
                    {"label": "ETPU", "type": "numeric", "decimal_places": 3, "description": "Top elevation inflow enters using SPECIFY option, m"},
                    {"label": "EBPU", "type": "numeric", "decimal_places": 3, "description": "Bottom elevation inflow enters using SPECIFY option, m"},
                    {"label": "KTPU", "type": "numeric", "description": "Top layer above which selective withdrawal will not occur"},
                    {"label": "KBPU", "type": "numeric", "description": "Bottom layer below which selective withdrawal will not occur"}
                ],
                "columns_from": "NPU"
            },
            "Internal Weirs": {
                "type": "tabular",
                "rows": [
                    {"label": "IWR", "type": "numeric", "description": "Internal weir segment number (RHS)"},
                    {"label": "KTWR", "type": "numeric", "description": "Internal weir layer top"},
                    {"label": "KBWR", "type": "numeric", "description": "Internal weir layer bottom"}
                ],
                "columns_from": "NIW"
            },
            "Withdrawals": {
                "type": "tabular",
                "rows": [
                    {"label": "WDIC", "type": "checkbox", "description": "Withdrawal interpolation, ON or OFF"},
                    {"label": "IWD", "type": "numeric", "description": "Withdrawal outflow segment"},
                    {"label": "EWD", "type": "numeric", "decimal_places": 3, "description": "Withdrawal centerline elevation"},
                    {"label": "KTWD", "type": "numeric", "description": "Withdrawal selective withdrawal top, Top layer above which selective withdrawal will not occur"},
                    {"label": "KBWD", "type": "numeric", "description": "Withdrawal selective withdrawal bottom, Bottom layer below which selective withdrawal will not occur"}
                ],
                "columns_from": "NWD"
            },
            "Hydrodynamic Output Control": {
                "type": "tabular",
                "rows": [
                    {"label": "NVIOL", "type": "numeric", "description": "Placeholder"},
                    {"label": "U", "type": "numeric", "description": "Placeholder"},
                    {"label": "W", "type": "numeric", "description": "Placeholder"},
                    {"label": "T", "type": "numeric", "description": "Placeholder"},
                    {"label": "RHO", "type": "numeric", "description": "Placeholder"},
                    {"label": "AZ", "type": "numeric", "description": "Placeholder"},
                    {"label": "SHEAR", "type": "numeric", "description": "Placeholder"},
                    {"label": "ST", "type": "numeric", "description": "Placeholder"},
                    {"label": "SB", "type": "numeric", "description": "Placeholder"},
                    {"label": "ADMX", "type": "numeric", "description": "Placeholder"},
                    {"label": "DM", "type": "numeric", "description": "Placeholder"},
                    {"label": "HDG", "type": "numeric", "description": "Placeholder"},
                    {"label": "ADMZ", "type": "numeric", "description": "Placeholder"},
                    {"label": "HPG", "type": "numeric", "description": "Placeholder"},
                    {"label": "GRAV", "type": "numeric", "description": "Placeholder"}
                ],
                "columns_from": "NWB"
            },
            "Distributed Tributaries": {
                "type": "tabular",
                "rows": [
                    {"label": "DTRC", "type": "checkbox", "description": "Distributed tributary option, ON or OFF"}
                ],
                "columns_from": "NBR"
            },
            "Snapshot Output Control": {
                "type": "tabular",
                "rows": [
                    {"label": "SNPC", "type": "checkbox", "description": "Placeholder: SCRC description"},
                    {"label": "NSNP", "type": "numeric", "description": "Placeholder: NSCR description"},
                    {"label": "SNPD", "type": "numeric", "decimal_places": 2, "description": "Placeholder: SCRD description"},
                    {"label": "SNPF", "type": "numeric", "decimal_places": 2, "description": "Placeholder: SCRF description"}
                ]
            },
            "Screen Output Control": {
                "type": "tabular",
                "rows": [
                    {"label": "SCRC", "type": "checkbox", "description": "Placeholder: SCRC description"},
                    {"label": "NSCR", "type": "numeric", "description": "Placeholder: NSCR description"},
                    {"label": "SCRD", "type": "numeric", "decimal_places": 2, "description": "Placeholder: SCRD description"},
                    {"label": "SCRF", "type": "numeric", "decimal_places": 2, "description": "Placeholder: SCRF description"}
                ]
            },
            "Profile Output Control": {
                "type": "tabular",
                "rows": [
                    {"label": "PRFC", "type": "checkbox", "description": "Placeholder: PRFC description"},
                    {"label": "NPRF", "type": "numeric", "description": "Placeholder: NPRF description"},
                    {"label": "NIPRF", "type": "numeric", "description": "Placeholder: NIPRF description"},
                    {"label": "PRFD", "type": "numeric", "decimal_places": 2, "description": "Placeholder: PRFD description"},
                    {"label": "PRFF", "type": "numeric", "decimal_places": 2, "description": "Placeholder: PRFF description"},
                    {"label": "IPRF", "type": "numeric", "description": "Placeholder: IPRF description"},
                    {"label": "SPRD", "type": "numeric", "decimal_places": 2, "description": "Placeholder: SPRD description"},
                    {"label": "SPRF", "type": "numeric", "decimal_places": 2, "description": "Placeholder: SPRF description"},
                    {"label": "ISPR", "type": "numeric", "description": "Placeholder: ISPR description"}
                ]
            },
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
        # Build tabs; ensure Tributary and Distributed Tributaries are added last for display ordering
        titles = list(self.tab_data.keys())
        for last_tab in ["Tributary", "Distributed Tributaries", "Hydrodynamic Output Control", "Snapshot Output Control", "Screen Output Control"]:
            if last_tab in titles:
                titles.remove(last_tab)
        ordered_titles = titles
        if "Tributary" in self.tab_data:
            ordered_titles += ["Tributary"]
        if "Distributed Tributaries" in self.tab_data:
            ordered_titles += ["Distributed Tributaries"]
        if "Hydrodynamic Output Control" in self.tab_data:
            ordered_titles += ["Hydrodynamic Output Control"]
        if "Snapshot Output Control" in self.tab_data:
            ordered_titles += ["Snapshot Output Control"]
        if "Screen Output Control" in self.tab_data:
            ordered_titles += ["Screen Output Control"]
        if "Profile Output Control" in self.tab_data:
            ordered_titles += ["Profile Output Control"]
        for title in ordered_titles:
            data = self.tab_data[title]
            if data.get("type") == "tabular":
                tab_widget = TabularDataTab(data["rows"], tab_name=title)  # Pass tab name
            else:
                tab_widget = UserDataTab(data["fields"], columns=data["columns"])
            self.tabs[title] = tab_widget
            self.tab_list.addItem(title)
            self.stacked_widget.addWidget(tab_widget)
        
        # Connect real-time structure changes from the Structures tab to sync immediately
        if isinstance(self.tabs.get("Structures"), TabularDataTab):
            self.tabs["Structures"].structureChanged.connect(self.update_structures_dynamic_rows)
        # Connect NSCR changes to update Snapshot Output Control columns dynamically
        if isinstance(self.tabs.get("Snapshot Output Control"), TabularDataTab):
            self.tabs["Snapshot Output Control"].structureChanged.connect(self.update_snapshot_columns)
        # Connect NSCR changes to update Screen Output Control columns dynamically
        if isinstance(self.tabs.get("Screen Output Control"), TabularDataTab):
            self.tabs["Screen Output Control"].structureChanged.connect(self.update_screen_columns)
        # Connect NPRF/NIPRF changes to update Profile Output Control columns dynamically
        if isinstance(self.tabs.get("Profile Output Control"), TabularDataTab):
            self.tabs["Profile Output Control"].structureChanged.connect(self.update_profile_columns)
        
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
        if getattr(self, "_sync_in_progress", False):
            return
        self._sync_in_progress = True
        try:
            nwb_value = 0
            nbr_value = 0
            npi_value = 0
            nsp_value = 0
            ngt_value = 0
            npu_value = 0
            niw_value = 0
            nwd_value = 0
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

            # Read NPI from Inflow/Outflow Dimensions tab for Pipes columns
            inflow_tab = self.tabs.get("Inflow/Outflow Dimensions")
            if inflow_tab:
                for label, value in inflow_tab.get_data():
                    if label == "NPI" and value:
                        try:
                            npi_value = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif label == "NSP" and value:
                        try:
                            nsp_value = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif label == "NGT" and value:
                        try:
                            ngt_value = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif label == "NPU" and value:
                        try:
                            npu_value = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif label == "NIW" and value:
                        try:
                            niw_value = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif label == "NWD" and value:
                        try:
                            nwd_value = int(value)
                        except (ValueError, TypeError):
                            pass
 
            # Sync all NWB-dependent tabs
            nwb_tabs = ["Timestep Limitations", "Waterbody Definition", "Calculations", "Dead Sea",
                        "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity", "Hydrodynamic Output Control"]
            for tab_name in nwb_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, nwb_value))  # Ensure at least 1 column
                    tab.set_data(current_data)

            # Sync all NBR-dependent tabs
            nbr_tabs = ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures", "Distributed Tributaries"]
            for tab_name in nbr_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, nbr_value))  # Ensure at least 1 column
                    tab.set_data(current_data)

            # Sync NTR-dependent tabs
            ntr_tabs = ["Tributary"]
            # Read NTR from Inflow/Outflow Dimensions
            try:
                inflow_tab = self.tabs.get("Inflow/Outflow Dimensions")
                ntr_value = 0
                if inflow_tab and isinstance(inflow_tab, UserDataTab):
                    for label, value in inflow_tab.get_data():
                        if label == "NTR" and value:
                            ntr_value = int(value)
                            break
            except Exception:
                ntr_value = 0
            for tab_name in ntr_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, ntr_value))
                    tab.set_data(current_data)

            # Initialize Snapshot Output Control with one base column and let NSCR drive extras
            snap_tab = self.tabs.get("Snapshot Output Control")
            if snap_tab and isinstance(snap_tab, TabularDataTab):
                current_data = snap_tab.get_data()
                snap_tab.set_columns(1)
                snap_tab.set_data(current_data)

            # Initialize Screen Output Control with one base column and let NSCR drive extras
            screen_tab = self.tabs.get("Screen Output Control")
            if screen_tab and isinstance(screen_tab, TabularDataTab):
                current_data = screen_tab.get_data()
                screen_tab.set_columns(1)
                screen_tab.set_data(current_data)

            # Initialize Profile Output Control with one base column and let NPRF*NIPRF drive extras
            profile_tab = self.tabs.get("Profile Output Control")
            if profile_tab and isinstance(profile_tab, TabularDataTab):
                current_data = profile_tab.get_data()
                profile_tab.set_columns(1)
                profile_tab.set_data(current_data)

            # Sync all NPI-dependent tabs
            npi_tabs = ["Pipes"]
            for tab_name in npi_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, npi_value))  # Ensure at least 1 column
                    tab.set_data(current_data)

            # Sync all NSP-dependent tabs
            nsp_tabs = ["Spillway"]
            for tab_name in nsp_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, nsp_value))
                    tab.set_data(current_data)

            # Sync all NGT-dependent tabs
            ngt_tabs = ["Gates"]
            for tab_name in ngt_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, ngt_value))
                    tab.set_data(current_data)

            # Sync all NPU-dependent tabs
            npu_tabs = ["Pumps"]
            for tab_name in npu_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, npu_value))
                    tab.set_data(current_data)

            # Sync all NIW-dependent tabs
            niw_tabs = ["Internal Weirs"]
            for tab_name in niw_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, niw_value))
                    tab.set_data(current_data)

            # Sync all NWD-dependent tabs
            nwd_tabs = ["Withdrawals"]
            for tab_name in nwd_tabs:
                tab = self.tabs.get(tab_name)
                if tab and isinstance(tab, TabularDataTab):
                    current_data = tab.get_data()
                    tab.set_columns(max(1, nwd_value))
                    tab.set_data(current_data)

            # After NBR-dependent sync, adjust Structures tab rows dynamically based on max NSTR
            self.update_structures_dynamic_rows()
        
        finally:
            self._sync_in_progress = False
    
    def update_structures_dynamic_rows(self):
        """Only adjust Structures dynamic rows without rebuilding other tabs"""
        if getattr(self, "_sync_in_progress", False):
            # If a broader sync is running, let it handle updates
            return
        structures_tab = self.tabs.get("Structures")
        if structures_tab and isinstance(structures_tab, TabularDataTab):
            try:
                max_nstr = 0
                nstr_row_index = next((idx for idx, rd in enumerate(structures_tab.row_definitions) if rd.get("label") == "NSTR"), None)
                if nstr_row_index is not None:
                    for col_index in range(structures_tab.table.columnCount()):
                        widget = structures_tab.table.cellWidget(nstr_row_index, col_index)
                        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                            try:
                                max_nstr = max(max_nstr, int(widget.value()))
                            except Exception:
                                pass
                base_len = len(getattr(structures_tab, 'base_row_definitions', []))
                current_dynamic = max(0, len(structures_tab.row_definitions) - base_len)
                current_struct_groups = current_dynamic // 6
 
                if max_nstr != current_struct_groups:
                    new_rows = list(structures_tab.base_row_definitions)
                    # 1) STRIC1..N
                    for i in range(max_nstr):
                        idx = i + 1
                        new_rows.append({
                            "label": f"STRIC{idx}",
                            "type": "checkbox",
                            "description": "Turns ON/OFF interpolation of structure outflows"
                        })
                    # 2) KTSTR1..N
                    for i in range(max_nstr):
                        idx = i + 1
                        new_rows.append({
                            "label": f"KTSTR{idx}",
                            "type": "numeric",
                            "description": "Top layer above which selective withdrawal will not occur"
                        })
                    # 3) KBSTR1..N
                    for i in range(max_nstr):
                        idx = i + 1
                        new_rows.append({
                            "label": f"KBSTR{idx}",
                            "type": "numeric",
                            "description": "Bottom layer below which selective withdrawal will not occur"
                        })
                    # 4) SINKC1..N
                    for i in range(max_nstr):
                        idx = i + 1
                        new_rows.append({
                            "label": f"SINKC{idx}",
                            "type": "dropdown",
                            "options": ["LINE", "POINT"],
                            "description": "Sink type used in the selective withdrawal algorithm, LINE or POINT"
                        })
                    # 5) ESTR1..N
                    for i in range(max_nstr):
                        idx = i + 1
                        new_rows.append({
                            "label": f"ESTR{idx}",
                            "type": "numeric",
                            "decimal_places": 2,
                            "description": "Centerline elevation of structure, m"
                        })
                    # 6) WSTR1..N
                    for i in range(max_nstr):
                        idx = i + 1
                        new_rows.append({
                            "label": f"WSTR{idx}",
                            "type": "numeric",
                            "decimal_places": 2,
                            "description": "Width of structure (line sink), m"
                        })
                    structures_tab.set_row_definitions(new_rows)
            except Exception:
                pass

    def update_snapshot_columns(self):
        """Rebuild columns for Snapshot Output Control when NSCR changes without re-syncing other tabs."""
        # Reentrancy guard to avoid recursive updates while rebuilding
        if getattr(self, "_snapshot_updating", False):
            return
        self._snapshot_updating = True
        try:
            if getattr(self, "_sync_in_progress", False):
                return
            snap_tab = self.tabs.get("Snapshot Output Control")
            if snap_tab and isinstance(snap_tab, TabularDataTab):
                try:
                    current_data = snap_tab.get_data()
                    # Re-run set_columns from 1 base column; extras computed from NSCR
                    snap_tab.set_columns(1)
                    snap_tab.set_data(current_data)
                except Exception:
                    pass
        finally:
            self._snapshot_updating = False

    def update_screen_columns(self):
        """Rebuild columns for Screen Output Control when NSCR changes without re-syncing other tabs."""
        if getattr(self, "_screen_updating", False):
            return
        self._screen_updating = True
        try:
            if getattr(self, "_sync_in_progress", False):
                return
            screen_tab = self.tabs.get("Screen Output Control")
            if screen_tab and isinstance(screen_tab, TabularDataTab):
                try:
                    current_data = screen_tab.get_data()
                    screen_tab.set_columns(1)
                    screen_tab.set_data(current_data)
                except Exception:
                    pass
        finally:
            self._screen_updating = False

    def update_profile_columns(self):
        """Rebuild columns for Profile Output Control when NPRF/NIPRF change without re-syncing other tabs."""
        if getattr(self, "_profile_updating", False):
            return
        self._profile_updating = True
        try:
            if getattr(self, "_sync_in_progress", False):
                return
            profile_tab = self.tabs.get("Profile Output Control")
            if profile_tab and isinstance(profile_tab, TabularDataTab):
                try:
                    current_data = profile_tab.get_data()
                    profile_tab.set_columns(1)
                    profile_tab.set_data(current_data)
                except Exception:
                    pass
        finally:
            self._profile_updating = False

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
                                                "Heat Exchange", "Ice Cover", "Transport Scheme", "Hydaulic Coefficients", "Vertical Eddy Viscosity", "Hydrodynamic Output Control"]:
                                    if tab_name == "Hydrodynamic Output Control":
                                        # NWB-dependent columns with 3 fixed columns
                                        num_dynamic = (len(tabular_data[0]) - 1) - 3
                                        headers = ["HNAME", "FMTH", "HMULT"] + [f"HPRWBC{i+1}" for i in range(num_dynamic)]
                                    else:
                                        headers = [f"WB{i+1}" for i in range(len(tabular_data[0]) - 1)]
                                elif tab_name in ["Branch Geometry", "Initial Conditions", "Interpolation", "Structures", "Distributed Tributaries"]:
                                    headers = [f"BR{i+1}" for i in range(len(tabular_data[0]) - 1)]
                                elif tab_name == "Tributary":
                                    # Pull TRNAME values from the first row of data
                                    num_cols = len(tabular_data[0]) - 1
                                    names = []
                                    if len(tabular_data) > 0:
                                        trname_row = tabular_data[0]
                                        for i in range(num_cols):
                                            raw = trname_row[i+1] if i+1 < len(trname_row) else ""
                                            raw = raw.strip()
                                            names.append(raw)
                                    headers = [f"TR{i+1} ({names[i]})" if names[i] else f"TR{i+1}" for i in range(num_cols)]
                                elif tab_name == "Snapshot Output Control":
                                    num_cols = len(tabular_data[0]) - 1
                                    headers = ["SNP"] + [""] * (num_cols - 1)
                                elif tab_name == "Screen Output Control":
                                    num_cols = len(tabular_data[0]) - 1
                                    headers = ["SNP"] + [""] * (num_cols - 1)
                                elif tab_name == "Profile Output Control":
                                    num_cols = len(tabular_data[0]) - 1
                                    headers = ["PRFC"] + [""] * (num_cols - 1)
                                else:
                                    headers = []
                                writer.writerow(headers)
                                
                                for row_index, row_data in enumerate(tabular_data):
                                    # Skip the TRNAME row for Tributary outputs
                                    if tab_name == "Tributary" and row_index == 0:
                                        continue
                                    # For Hydrodynamic Output Control, row_data includes HNAME at index 0 and then FMTH, HMULT, HPRWBC# values
                                    if tab_name == "Hydrodynamic Output Control":
                                        # Exclude the first element (label) but include all columns after
                                        writer.writerow(row_data[1:])
                                    else:
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
