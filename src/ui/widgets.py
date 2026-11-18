# © 2026 David Ali Caballero Pérez. All rights reserved.
from PyQt5.QtWidgets import QLineEdit, QTableWidget, QMessageBox, QTableWidgetItem, QComboBox, QPushButton, QHeaderView
from PyQt5.QtCore import Qt
from datetime import datetime
from lib.enums import IUARegistryState

class DragDropLineEdit(QLineEdit):
    """Campo de texto con soporte nativo para captura de rutas mediante Drag & Drop."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith(('.xlsx', '.xls')):
                self.setText(file_path)
                break
            else:
                QMessageBox.warning(self, "Archivo inválido", "Por favor, arrastre solo archivos de Excel (.xlsx, .xls).")

class DragDropSyncTable(QTableWidget):
    """Tabla personalizada que permite agregar múltiples archivos mediante Drag & Drop."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["Archivo Excel", "Estado", "Año por defecto", "Col. de Año (Opcional)", "Acción"])
        self.verticalHeader().setDefaultSectionSize(45)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(1, 130)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith(('.xlsx', '.xls')):
                self.add_file_row(file_path)

    def add_file_row(self, file_path):
        row = self.rowCount()
        self.insertRow(row)
        
        item_path = QTableWidgetItem(file_path)
        item_path.setFlags(item_path.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, item_path)

        combo_estado = QComboBox()
        combo_estado.addItem(IUARegistryState.TAKEN.value)
        combo_estado.addItem(IUARegistryState.RESERVED.value)
        self.setCellWidget(row, 1, combo_estado)
        
        year_input = QLineEdit(datetime.now().strftime("%Y"))
        year_input.setMaximumWidth(120)
        self.setCellWidget(row, 2, year_input)
        
        col_input = QLineEdit()
        col_input.setPlaceholderText("Ej: AÑO DE REPORTE")
        self.setCellWidget(row, 3, col_input)
        
        btn_delete = QPushButton("✕")
        btn_delete.setObjectName("danger-btn")
        btn_delete.clicked.connect(self.delete_clicked)
        self.setCellWidget(row, 4, btn_delete)

    def delete_clicked(self):
        button = self.sender()
        if button:
            index = self.indexAt(button.pos())
            if index.isValid():
                self.removeRow(index.row())

    def get_files_config(self):
        config = []
        for row in range(self.rowCount()):
            path = self.item(row, 0).text()
            estado = self.cellWidget(row, 1).currentText().strip()
            year = self.cellWidget(row, 2).text().strip()
            year_col = self.cellWidget(row, 3).text().strip()
            config.append({
                'path': path,
                'state': estado,
                'year': year, 
                'year_col': year_col
            })
        return config
