# © 2026 David Ali Caballero Pérez. All rights reserved.
from PyQt5.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt

class PandasModel(QAbstractTableModel):
    """Adaptador entre el DataFrame de Pandas y QTableView de PyQt5."""
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole:
                return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._data.columns[col]
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        col_name = self._data.columns[column]
        is_ascending = order == Qt.SortOrder.AscendingOrder
        self._data = self._data.sort_values(by=col_name, ascending=is_ascending)
        self.layoutChanged.emit()

class IUAFilterProxyModel(QSortFilterProxyModel):
    """Modelo proxy para aplicar filtros multicriterio sobre la tabla de IUAs."""
    def __init__(self):
        super().__init__()
        self._filter_iua = ""
        self._filter_estado = ""
        self._filter_ano = ""
        self._filter_ius_iul = ""

    def setFilterIUA(self, text):
        self._filter_iua = text.lower()
        self.invalidateFilter()

    def setFilterEstado(self, text):
        self._filter_estado = text.lower()
        self.invalidateFilter()

    def setFilterAno(self, text):
        self._filter_ano = text.lower()
        self.invalidateFilter()

    def setFilterIUS_IUL(self, text):
        self._filter_ius_iul = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        iua = str(model.data(model.index(source_row, 0), Qt.ItemDataRole.DisplayRole) or "")
        estado = str(model.data(model.index(source_row, 1), Qt.ItemDataRole.DisplayRole) or "")
        ano = str(model.data(model.index(source_row, 2), Qt.ItemDataRole.DisplayRole) or "")

        if self._filter_iua and self._filter_iua not in iua.lower(): return False
        if self._filter_estado and self._filter_estado not in estado.lower(): return False
        if self._filter_ano and self._filter_ano not in ano.lower(): return False

        if self._filter_ius_iul:
            if len(iua) == 12:
                ius_iul_code = iua[1:5] 
                if self._filter_ius_iul not in ius_iul_code.lower(): return False
            else:
                return False
        return True
