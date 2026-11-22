import ctypes
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, QLabel, 
    QLineEdit, QComboBox, QTabWidget, QMessageBox, QHeaderView, QFileDialog,
    QSpinBox, QListWidget, QInputDialog, QFrame, QCheckBox,
    QGraphicsBlurEffect, QProgressBar, QApplication, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QSize, QUrl
from PyQt5.QtGui import QIcon, QDesktopServices, QKeySequence

# Importaciones locales de tu nueva arquitectura
from lib.paths import ICON_PATH, resource_path, get_saved_theme, save_theme, get_admin_password_hash, verify_password, hash_password, save_admin_password_hash
from src.icon_manager import IconManager
from lib.enums import IUAInfrastructure, IUAType, GlobalRegistryTableColumn, IUARegistryState
from src.ui.models import PandasModel
from src.ui.workers import SyncWorker, BatchWorker, ConsultaWorker
from src.ui.widgets import DragDropLineEdit, DragDropSyncTable

myappid = 'AIRE.IUA_Machine.version_1' 
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# ==========================================
# VENTANA PRINCIPAL DE LA APLICACIÓN
# ==========================================

class IUAApp(QMainWindow):
    """Controlador central de la interfaz gráfica y gestor de eventos de la aplicación."""
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.icon_mgr = IconManager()
        
        self.resize(1466, 825)
        self.setWindowTitle("IUA Machine - 2.0")
        self.setWindowIcon(QIcon(ICON_PATH))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.setup_header()

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Variables de Paginación y Estado
        self.current_page = 0
        self.rows_per_page = 200
        self.filtered_df = pd.DataFrame()

        self.setup_tab_registro()
        self.setup_tab_buscador()
        self.setup_tab_consultas()
        self.setup_tab_sincronizacion()
        
        # Estado de Sesión
        self.restricted_tabs = [3]
        self.is_admin_unlocked = False
        self.is_syncing = False
        self.last_valid_tab = 0
     
        self.tabs.currentChanged.connect(self.verify_tab_access)

        self.inactivity_timeout_ms = 3 * 60 * 1000
        self.inactivity_timer = QTimer(self)
        self.inactivity_timer.setInterval(self.inactivity_timeout_ms)
        self.inactivity_timer.timeout.connect(self.handle_inactivity_timeout)

        QApplication.instance().installEventFilter(self)

        self.setup_shortcuts()


    def setup_shortcuts(self):
        # Atajo para Deshacer
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.trigger_undo)
        
        # Atajo para Rehacer
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.trigger_redo)

    def update_undo_redo_buttons(self):
        """Activa o desactiva los botones según el estado de las pilas."""
        self.btn_undo_global.setEnabled(len(self.manager.undo_stack) > 0)
        self.btn_redo_global.setEnabled(len(self.manager.redo_stack) > 0)

    def trigger_undo(self):
        if self.manager.undo():
            self.apply_pandas_filters() # Refrescamos la tabla
            self.update_undo_redo_buttons() # Actualizamos botones
        else:
            QMessageBox.warning(self, "Deshacer", "No hay más acciones para deshacer.")

    def trigger_redo(self):
        if self.manager.redo():
            self.apply_pandas_filters()
            self.update_undo_redo_buttons()
        else:
            QMessageBox.information(self, "Rehacer", "No hay acciones para rehacer.")

    # -------------------------------- HEADER --------------------------------        
    def setup_header(self):
        # Header Setup
            self.header_layout = QHBoxLayout()
            self.setup_logo()
    
            # --- NUEVOS BOTONES GLOBALES: Deshacer / Rehacer ---
            self.btn_undo_global = QPushButton()
            self.btn_undo_global.setToolTip("Deshacer último cambio en BD (Ctrl+Z)")
            self.btn_undo_global.setEnabled(False) # Inicia apagado
            self.btn_undo_global.clicked.connect(self.trigger_undo)
            self.icon_mgr.register_widget(self.btn_undo_global, "arrow-back-up.svg")
            
            self.btn_redo_global = QPushButton()
            self.btn_redo_global.setToolTip("Rehacer último cambio (Ctrl+Y)")
            self.btn_redo_global.setEnabled(False) # Inicia apagado
            self.btn_redo_global.clicked.connect(self.trigger_redo)
            self.icon_mgr.register_widget(self.btn_redo_global, "arrow-forward-up.svg")
    
            self.header_layout.addWidget(self.btn_undo_global)
            self.header_layout.addWidget(self.btn_redo_global)
            # ---------------------------------------------------
    
            self.header_layout.addStretch()
            self.setup_logo_aire()
            self.setup_theme_selector()
    
            self.layout.addLayout(self.header_layout)

    # ------------------ SECCIÓN 1: PESTAÑA REGISTRO GLOBAL ------------------
    def setup_tab_registro(self):
        """Construye la vista de registro principal con filtros, paginación y acciones masivas."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        filter_layout = QHBoxLayout()

        self.filter_icon_label_1 = QLabel()
        self.filter_icon_label_2 = QLabel()
        self.filter_icon_label_3 = QLabel()
        self.filter_icon_label_4 = QLabel()
        self.filter_icon_label_5 = QLabel()
        self.filter_icon_label_6 = QLabel()
        self.filter_icon_label_7 = QLabel()
        self.icon_mgr.register_widget(self.filter_icon_label_1, "filter-search.svg")
        self.icon_mgr.register_widget(self.filter_icon_label_2, "filter-search.svg")
        self.icon_mgr.register_widget(self.filter_icon_label_3, "filter-search.svg")
        self.icon_mgr.register_widget(self.filter_icon_label_4, "filter-search.svg")
        self.icon_mgr.register_widget(self.filter_icon_label_5, "filter-search.svg")
        self.icon_mgr.register_widget(self.filter_icon_label_6, "filter-search.svg")
        self.icon_mgr.register_widget(self.filter_icon_label_7, "filter-search.svg")

        self.combo_tipo_iua = QComboBox()
        self.combo_tipo_iua.addItem("TODOS", "ALL")
        for state in IUAType:
            self.combo_tipo_iua.addItem(state.value.upper(), state.value)
        filter_layout.addWidget(self.filter_icon_label_1)
        filter_layout.addWidget(QLabel("Tipo:"))
        filter_layout.addWidget(self.combo_tipo_iua)

        self.input_f_iua = QLineEdit()
        self.input_f_iua.setPlaceholderText("Filtrar IUA...")
        filter_layout.addWidget(self.filter_icon_label_2)
        filter_layout.addWidget(QLabel("IUA:"))
        filter_layout.addWidget(self.input_f_iua)

        self.input_f_ius = QLineEdit()
        self.input_f_ius.setPlaceholderText("Filtrar IUL/IUS (4 chars)")
        self.input_f_ius.setMaxLength(4)
        filter_layout.addWidget(self.filter_icon_label_3)
        filter_layout.addWidget(QLabel("IUL/IUS:"))
        filter_layout.addWidget(self.input_f_ius)

        self.combo_tipo_estado = QComboBox()
        self.combo_tipo_estado.addItem("TODOS", "ALL")
        for state in IUARegistryState:
            self.combo_tipo_estado.addItem(state.value.upper(), state.value)
        filter_layout.addWidget(self.filter_icon_label_1)
        filter_layout.addWidget(QLabel("Estado:"))
        filter_layout.addWidget(self.combo_tipo_estado)

        self.input_f_ano = QLineEdit()
        self.input_f_ano.setPlaceholderText("Filtrar Año...")
        filter_layout.addWidget(self.filter_icon_label_5)
        filter_layout.addWidget(QLabel("Año:"))
        filter_layout.addWidget(self.input_f_ano)

        self.input_f_bdi = QLineEdit()
        self.input_f_bdi.setPlaceholderText("Filtrar Cód. BDI...")
        filter_layout.addWidget(self.filter_icon_label_6)
        filter_layout.addWidget(QLabel("BDI:"))
        filter_layout.addWidget(self.input_f_bdi)

        self.input_f_activo = QLineEdit()
        self.input_f_activo.setPlaceholderText("Filtrar Activo...")
        filter_layout.addWidget(self.filter_icon_label_7)
        filter_layout.addWidget(QLabel("Activo:"))
        filter_layout.addWidget(self.input_f_activo)

        layout.addLayout(filter_layout)

        # --- Fila 2 - Filtros de Rango ---
        filter_layout_2 = QHBoxLayout()
        
        self.filter_icon_label_rango = QLabel()
        self.icon_mgr.register_widget(self.filter_icon_label_rango, "filter-search.svg")
        filter_layout_2.addWidget(self.filter_icon_label_rango)
        
        # Rango Inicial (Desde)
        self.input_f_iua_desde = QLineEdit()
        self.input_f_iua_desde.setPlaceholderText("IUA Desde (Ej: 10Z3EY0000)")
        filter_layout_2.addWidget(QLabel("Rango Desde:"))
        filter_layout_2.addWidget(self.input_f_iua_desde)

        # Rango Final (Hasta)
        self.input_f_iua_hasta = QLineEdit()
        self.input_f_iua_hasta.setPlaceholderText("IUA Hasta (Ej: 10Z3EY0500)")
        filter_layout_2.addWidget(QLabel("Hasta:"))
        filter_layout_2.addWidget(self.input_f_iua_hasta)

        # --- NUEVO: Rango de Años ---
        self.filter_icon_label_rango_ano = QLabel()
        self.icon_mgr.register_widget(self.filter_icon_label_rango_ano, "filter-search.svg")
        filter_layout_2.addWidget(self.filter_icon_label_rango_ano)

        self.input_f_ano_desde = QLineEdit()
        self.input_f_ano_desde.setPlaceholderText("Año Desde (Ej: 2020)")
        self.input_f_ano_desde.setMaximumWidth(130)
        filter_layout_2.addWidget(QLabel("Año Desde:"))
        filter_layout_2.addWidget(self.input_f_ano_desde)

        self.input_f_ano_hasta = QLineEdit()
        self.input_f_ano_hasta.setPlaceholderText("Hasta (Ej: 2024)")
        self.input_f_ano_hasta.setMaximumWidth(130)
        filter_layout_2.addWidget(QLabel("Hasta:"))
        filter_layout_2.addWidget(self.input_f_ano_hasta)
        
        filter_layout_2.addStretch() # Empuja los filtros a la izquierda

        layout.addLayout(filter_layout_2)
        # ----------------------------------------

        self.table_view = QTableView()
        self.pandas_model = PandasModel(self.manager.df_iua)
        self.table_view.setModel(self.pandas_model)

        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_view)

        pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("<< Anterior")
        self.btn_prev.clicked.connect(self.prev_page)
        
        self.lbl_page = QLabel("Página 1 de 1")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.btn_next = QPushButton("Siguiente >>")
        self.btn_next.clicked.connect(self.next_page)

        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addWidget(self.lbl_page)
        pagination_layout.addWidget(self.btn_next)

        layout.addLayout(pagination_layout)

        bottom_layout = QHBoxLayout()
        custom_colors = {'Light Theme': '#ffffff'}
        
        self.btn_refresh = QPushButton("Actualizar Tabla")
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.icon_mgr.register_widget(self.btn_refresh, "reload.svg", custom_colors=custom_colors)

        self.btn_clear_filters = QPushButton("Limpiar Filtros")
        self.btn_clear_filters.clicked.connect(self.clear_all_filters)
        self.icon_mgr.register_widget(self.btn_clear_filters, "filter-x.svg", custom_colors={
            'Light Theme': '#ffffff', 'Bento Theme': '#ffffff'
        })
        
        self.btn_export = QPushButton("Exportar")
        self.btn_export.setObjectName("export-btn")
        self.btn_export.clicked.connect(self.export_to_excel)
        self.icon_mgr.register_widget(self.btn_export, "table-export.svg", custom_colors={
            'Light Theme': '#ffffff',
            'Bento Theme': '#ffffff'
        })

        self.btn_free_reserved = QPushButton("Liberar Seleccionados")
        self.icon_mgr.register_widget(self.btn_free_reserved, "bookmark-minus.svg", custom_colors={
            'Light Theme': '#ffffff',
            'Sci-Fi Theme': '#ff007f',
            'Bento Theme': '#ffffff'
        })
        self.btn_free_reserved.setObjectName("danger-btn") 
        self.btn_free_reserved.clicked.connect(self.free_selected_iuas)

        self.btn_free_all_filtered = QPushButton("Liberar Filtrados")
        self.icon_mgr.register_widget(self.btn_free_all_filtered, "bookmark-off.svg", custom_colors={
            'Light Theme': '#ffffff',
            'Sci-Fi Theme': '#ff3399',
            'Bento Theme': '#ffffff'
        })
        self.btn_free_all_filtered.setObjectName("danger-all-btn") 
        self.btn_free_all_filtered.clicked.connect(self.free_all_filtered_iuas)

        self.btn_select_all = QPushButton("Seleccionar Todo")
        self.icon_mgr.register_widget(self.btn_select_all, 'select-all.svg', custom_colors=custom_colors)
        self.btn_select_all.clicked.connect(self.table_view.selectAll)

        self.btn_copy = QPushButton("Copiar Selección")
        self.icon_mgr.register_widget(self.btn_copy, 'clipboard-copy.svg', custom_colors=custom_colors)
        self.btn_copy.clicked.connect(self.copy_selection_to_clipboard)

        self.btn_copy_all_filtered = QPushButton("Copiar Filtrados")
        self.icon_mgr.register_widget(self.btn_copy_all_filtered, 'clipboard-copy.svg', custom_colors={
            'Sci-Fi Theme': '#ffbb00'
        })
        self.btn_copy_all_filtered.setObjectName("warning-btn") 
        self.btn_copy_all_filtered.clicked.connect(self.copy_all_filtered_to_clipboard)

        bottom_layout.addWidget(self.btn_refresh)
        bottom_layout.addWidget(self.btn_clear_filters)
        bottom_layout.addWidget(self.btn_select_all) 
        bottom_layout.addWidget(self.btn_copy)
        bottom_layout.addWidget(self.btn_copy_all_filtered)
        bottom_layout.addWidget(self.btn_export)
        bottom_layout.addWidget(self.btn_free_reserved)
        bottom_layout.addWidget(self.btn_free_all_filtered) 
        
        layout.addLayout(bottom_layout)

        # --- NUEVO: Temporizador para no saturar los filtros ---
        self.filter_timer = QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.setInterval(400) # Espera 400ms después de la última tecla
        self.filter_timer.timeout.connect(self.apply_pandas_filters)

        # --- NUEVAS CONEXIONES OPTIMIZADAS ---
        # Ahora inician el temporizador en lugar de llamar directamente a apply_pandas_filters
        self.input_f_iua.textChanged.connect(self.filter_timer.start)
        self.input_f_ius.textChanged.connect(self.filter_timer.start)
        self.input_f_ano.textChanged.connect(self.filter_timer.start)
        self.input_f_bdi.textChanged.connect(self.filter_timer.start) 
        self.input_f_activo.textChanged.connect(self.filter_timer.start)
        self.input_f_iua_desde.textChanged.connect(self.filter_timer.start)
        self.input_f_iua_hasta.textChanged.connect(self.filter_timer.start)
        # NUEVAS CONEXIONES DE RANGO DE AÑOS
        self.input_f_ano_desde.textChanged.connect(self.filter_timer.start)
        self.input_f_ano_hasta.textChanged.connect(self.filter_timer.start)
        
        # Los ComboBox sí pueden ir directos porque son clics únicos
        self.combo_tipo_estado.currentIndexChanged.connect(self.apply_pandas_filters)
        self.combo_tipo_iua.currentIndexChanged.connect(self.apply_pandas_filters)
        
        self.apply_pandas_filters()

        self.tabs.addTab(tab, "Registro Global IUA")

        self.update_undo_redo_buttons()

    def apply_pandas_filters(self):
        """Filtra el DataFrame subyacente y actualiza la paginación."""
        df = self.manager.df_iua.copy()
        tipo_seleccionado = self.combo_tipo_iua.currentData()
        
        if tipo_seleccionado == IUAType.SUBSTATION.value:
            df = df[
                df[GlobalRegistryTableColumn.IUA.value].str.startswith(IUAInfrastructure.SUBSTATION.value, na=False) & 
                (df[GlobalRegistryTableColumn.IUA.value].str.len() != 10)
            ]
        elif tipo_seleccionado == IUAType.BT_NETWORK.value:
            df = df[
                df[GlobalRegistryTableColumn.IUA.value].str.startswith(IUAInfrastructure.LINE.value, na=False) & 
                (df[GlobalRegistryTableColumn.IUA.value].str.len() == 10)
            ]
        elif tipo_seleccionado == IUAType.LINE.value:
            df = df[
                df[GlobalRegistryTableColumn.IUA.value].str.startswith(IUAInfrastructure.LINE.value, na=False) & 
                (df[GlobalRegistryTableColumn.IUA.value].str.len() != 10)
            ]
        elif tipo_seleccionado == IUAType.TRAFO.value:
            df = df[
                df[GlobalRegistryTableColumn.IUA.value].str.startswith(IUAInfrastructure.SUBSTATION.value, na=False) & 
                (df[GlobalRegistryTableColumn.IUA.value].str.len() == 10)
            ]

        f_iua = self.input_f_iua.text().strip()
        if f_iua:
            df = df[df[GlobalRegistryTableColumn.IUA.value].str.contains(f_iua, case=False, na=False)]
            
        estado_seleccionado = self.combo_tipo_estado.currentData()
        if estado_seleccionado != "ALL":
            df = df[df[GlobalRegistryTableColumn.STATE.value] == estado_seleccionado]
            
        f_ano = self.input_f_ano.text().strip()
        if f_ano:
            df = df[df[GlobalRegistryTableColumn.REPORT_YEAR.value].str.contains(f_ano, case=False, na=False)]

        f_codigo = self.input_f_ius.text().strip()
        if f_codigo:
            df = df[df[GlobalRegistryTableColumn.IUX.value].str.contains(f_codigo, case=False, na=False)]

        f_bdi = self.input_f_bdi.text().strip()
        if f_bdi:
            df = df[df[GlobalRegistryTableColumn.BDI_CODES.value].str.contains(f_bdi, case=False, na=False)]

        f_activo = self.input_f_activo.text().strip()
        if f_activo:
            df = df[df[GlobalRegistryTableColumn.ASSET_TYPE.value].str.contains(f_activo, case=False, na=False)]

        # --- Filtro por Rangos de IUA ---
        f_desde = self.input_f_iua_desde.text().strip().upper()
        if f_desde:
            # Filtra los que sean alfabéticamente mayores o iguales al límite inferior
            df = df[df[GlobalRegistryTableColumn.IUA.value] >= f_desde]

        f_hasta = self.input_f_iua_hasta.text().strip().upper()
        if f_hasta:
            # Filtra los que sean alfabéticamente menores o iguales al límite superior
            df = df[df[GlobalRegistryTableColumn.IUA.value] <= f_hasta]

        # --- NUEVA LÓGICA: Filtro por Rangos de Año ---
        f_ano_desde = self.input_f_ano_desde.text().strip()
        if f_ano_desde.isdigit():
            anos_numericos = pd.to_numeric(df[GlobalRegistryTableColumn.REPORT_YEAR.value], errors='coerce')
            df = df[anos_numericos >= int(f_ano_desde)]

        f_ano_hasta = self.input_f_ano_hasta.text().strip()
        if f_ano_hasta.isdigit():
            anos_numericos = pd.to_numeric(df[GlobalRegistryTableColumn.REPORT_YEAR.value], errors='coerce')
            df = df[anos_numericos <= int(f_ano_hasta)]

        self.filtered_df = df
        self.current_page = 0
        self.load_current_page()

    def clear_all_filters(self):
        """Reinicia los controles de filtrado."""
        self.combo_tipo_iua.blockSignals(True)
        self.input_f_iua.blockSignals(True)
        self.input_f_ius.blockSignals(True)
        self.combo_tipo_estado.blockSignals(True)
        self.input_f_ano.blockSignals(True)
        self.input_f_bdi.blockSignals(True)
        self.input_f_activo.blockSignals(True)
        self.input_f_iua_desde.blockSignals(True)
        self.input_f_iua_hasta.blockSignals(True)
        self.input_f_ano_desde.blockSignals(True)
        self.input_f_iua_hasta.blockSignals(True)

        self.combo_tipo_iua.setCurrentIndex(0) 
        self.input_f_iua.clear()
        self.input_f_ius.clear()
        self.combo_tipo_estado.setCurrentIndex(0)
        self.input_f_ano.clear()
        self.input_f_bdi.clear()
        self.input_f_activo.clear()
        self.input_f_iua_desde.clear()
        self.input_f_iua_hasta.clear()
        self.input_f_ano_desde.clear()
        self.input_f_iua_hasta.clear()

        self.combo_tipo_iua.blockSignals(False)
        self.input_f_iua.blockSignals(False)
        self.input_f_ius.blockSignals(False)
        self.combo_tipo_estado.blockSignals(False)
        self.input_f_ano.blockSignals(False)
        self.input_f_bdi.blockSignals(False)
        self.input_f_activo.blockSignals(False)
        self.input_f_iua_desde.blockSignals(False)
        self.input_f_iua_hasta.blockSignals(False)
        self.input_f_ano_desde.blockSignals(False)
        self.input_f_iua_hasta.blockSignals(False)

        self.apply_pandas_filters()

    def load_current_page(self):
        """Gestiona la paginación de la tabla."""
        total_rows = len(self.filtered_df)
        total_pages = max(1, (total_rows + self.rows_per_page - 1) // self.rows_per_page)
        
        start_idx = self.current_page * self.rows_per_page
        end_idx = start_idx + self.rows_per_page
        chunk_df = self.filtered_df.iloc[start_idx:end_idx]
        
        self.pandas_model.update_data(chunk_df)

        columnas_ocultas = [
            GlobalRegistryTableColumn.BDI_CODES.value,
            GlobalRegistryTableColumn.UC.value,
            GlobalRegistryTableColumn.FORMAT.value,
            GlobalRegistryTableColumn.OPERATION.value
        ]
        for col_name in columnas_ocultas:
            if col_name in chunk_df.columns:
                col_index = chunk_df.columns.get_loc(col_name)
                self.table_view.setColumnHidden(col_index, True)

        self.lbl_page.setText(f"Página {self.current_page + 1} de {total_pages} (Total: {total_rows} registros)")
        
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)

    def prev_page(self):
        self.current_page -= 1
        self.load_current_page()

    def next_page(self):
        self.current_page += 1
        self.load_current_page()

    # ------------------ SECCIÓN 2: PESTAÑA BUSCADOR Y RESERVAS ------------------

    def setup_tab_buscador(self):
        """Construye la vista de búsqueda de vacíos y generación masiva (lotes)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        search_layout = QHBoxLayout()
        self.combo_infra = QComboBox()
        self.combo_infra.addItem("Subestación (12 Chars)", IUAType.SUBSTATION.value)
        self.combo_infra.addItem("Línea (12 Chars)", IUAType.LINE.value)
        self.combo_infra.addItem("Red BT (10 Chars)", IUAType.BT_NETWORK.value)
        self.combo_infra.addItem("Transformador (10 Chars)", IUAType.TRAFO.value)
        self.combo_infra.currentIndexChanged.connect(self.update_buscador_ui)
        
        self.input_code = QLineEdit()

        self.input_cantidad = QSpinBox()
        self.input_cantidad.setMinimumWidth(80)
        self.input_cantidad.setMinimum(1)
        self.input_cantidad.setMaximum(30000)
        self.input_cantidad.setValue(1)

        btn_search_free = QPushButton("Generar IUA(s)")
        btn_search_free.clicked.connect(self.find_free_iua)

        search_layout.addWidget(QLabel("Infraestructura:"))
        search_layout.addWidget(self.combo_infra)
        
        self.lbl_codigo = QLabel("Código IUS/IUL:")
        search_layout.addWidget(self.lbl_codigo)
        search_layout.addWidget(self.input_code)
        
        self.input_year = QLineEdit()
        self.input_year.setPlaceholderText("Año proyectado (Ej: 2025)")
        self.input_year.setMaximumWidth(200)

        search_layout.addWidget(QLabel("Cantidad:"))
        search_layout.addWidget(self.input_cantidad)
        search_layout.addWidget(btn_search_free)

        layout.addLayout(search_layout)

        result_layout = QVBoxLayout()
        self.list_results = QListWidget()
        

        result_layout.addWidget(QLabel("IUAs Disponibles:"))
        result_layout.addWidget(self.list_results)
        result_layout.addWidget(QLabel("Año:"))
        result_layout.addWidget(self.input_year)

        layout.addLayout(result_layout)

        action_buttons_layout = QHBoxLayout()

        self.btn_reserve = QPushButton("Solo Reservar")
        self.btn_reserve.setObjectName("success-btn")
        self.btn_reserve.setEnabled(False)
        self.btn_reserve.clicked.connect(self.reserve_current_iua)

        self.btn_export_reserva = QPushButton("Solo Exportar a Excel")
        self.btn_export_reserva.setEnabled(False)
        self.btn_export_reserva.clicked.connect(self.export_reservation_excel)

        self.btn_export_and_reserve = QPushButton("Exportar y Reservar")
        self.btn_export_and_reserve.setObjectName("export-btn")
        self.btn_export_and_reserve.setEnabled(False)
        self.btn_export_and_reserve.clicked.connect(self.export_and_reserve_action)

        action_buttons_layout.addWidget(self.btn_reserve)
        action_buttons_layout.addWidget(self.btn_export_reserva)
        action_buttons_layout.addWidget(self.btn_export_and_reserve)

        result_layout.addLayout(action_buttons_layout)
        layout.addLayout(result_layout)

        batch_layout = QVBoxLayout()
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        batch_layout.addWidget(line)
        
        title_batch_layout = QHBoxLayout()
        lbl_batch_title = QLabel("Generación Masiva por Lotes (Excel)")
        lbl_batch_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        title_batch_layout.addWidget(lbl_batch_title)
        
        title_batch_layout.addStretch() 
        self.btn_download_template = QPushButton("Descargar Plantilla Excel")
        self.btn_download_template.setObjectName("success-btn") 
        self.btn_download_template.clicked.connect(self.download_excel_template)
        self.icon_mgr.register_widget(self.btn_download_template, "table-export.svg", custom_colors={
            'Light Theme': '#ffffff', 'Bento Theme': '#ffffff', 'Sci-Fi Theme': '#00ff66'
        })
        
        title_batch_layout.addWidget(self.btn_download_template)
        batch_layout.addLayout(title_batch_layout)
        
        file_batch_layout = QHBoxLayout()
        self.input_batch_file = DragDropLineEdit()
        self.input_batch_file.setPlaceholderText("Seleccione o arrastre el archivo aquí...")
        self.input_batch_file.textChanged.connect(lambda text: self.btn_run_batch.setEnabled(bool(text)))
        
        btn_browse_batch = QPushButton("Explorar Excel...")
        btn_browse_batch.clicked.connect(self.select_batch_file)
        self.icon_mgr.register_widget(btn_browse_batch, "file-search.svg", QSize(16, 16), custom_colors={
            'Light Theme': '#ffffff'
        })
        
        file_batch_layout.addWidget(self.input_batch_file)
        file_batch_layout.addWidget(btn_browse_batch)
        batch_layout.addLayout(file_batch_layout)
        
        cols_req_layout = QHBoxLayout()
        self.input_col_code = QLineEdit("CODIGO")
        self.input_col_qty = QLineEdit("CANTIDAD")
        cols_req_layout.addWidget(QLabel("Columna de Códigos:"))
        cols_req_layout.addWidget(self.input_col_code)
        cols_req_layout.addWidget(QLabel("Columna de Cantidad:"))
        cols_req_layout.addWidget(self.input_col_qty)
        batch_layout.addLayout(cols_req_layout)

        cols_opt_layout = QHBoxLayout()
        self.input_col_type = QLineEdit()
        self.input_col_type.setPlaceholderText("Opcional (Ej: TIPO_IUA)")
        
        self.input_col_year = QLineEdit()
        self.input_col_year.setPlaceholderText("Opcional (Ej: AÑO)")

        self.input_col_type.setToolTip(
            "<b>Valores exactos permitidos en el Excel:</b><br>"
            "<ul>"
            "<li>SUBESTACIÓN</li>"
            "<li>LÍNEA</li>"
            "<li>RED BT</li>"
            "<li>TRANSFORMADOR</li>"
            "</ul>"
        )

        cols_opt_layout.addWidget(QLabel("Col. Tipo (Opcional):"))
        cols_opt_layout.addWidget(self.input_col_type)
        cols_opt_layout.addWidget(QLabel("Col. Año (Opcional):"))
        cols_opt_layout.addWidget(self.input_col_year)
        batch_layout.addLayout(cols_opt_layout)

        self.chk_reserve_batch = QCheckBox("Marcar como RESERVADO en la base de datos local")
        self.chk_reserve_batch.setChecked(True) 
        batch_layout.addWidget(self.chk_reserve_batch)
        
        progress_layout = QHBoxLayout()
        self.progress_batch = QProgressBar()
        self.progress_batch.setFixedHeight(18)
        self.progress_batch.setValue(0)
        self.progress_batch.setVisible(False)
        progress_layout.addWidget(self.progress_batch)

        self.btn_cancel_batch = QPushButton("Cancelar")
        self.btn_cancel_batch.setObjectName("danger-btn")
        self.btn_cancel_batch.setVisible(False)
        self.btn_cancel_batch.clicked.connect(self.cancel_batch_reservation)
        progress_layout.addWidget(self.btn_cancel_batch)

        batch_layout.addLayout(progress_layout)
        
        self.btn_run_batch = QPushButton("Procesar Archivo y Reservar Lote")
        self.btn_run_batch.setObjectName("run-batch-btn")
        self.btn_run_batch.setEnabled(False)
        self.btn_run_batch.clicked.connect(self.run_batch_reservation)
        batch_layout.addWidget(self.btn_run_batch)
        
        layout.addLayout(batch_layout)
        layout.addStretch()

        self.tabs.addTab(tab, "Generar y Reservar Libres")
        self.update_buscador_ui()

    # ------------------ EVENTOS: PESTAÑA BUSCADOR ------------------

    def download_excel_template(self):
        """Proporciona una plantilla de Excel con datos de ejemplo para el proceso masivo."""
        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar Plantilla Excel", 
            "Plantilla_Lotes_IUA.xlsx", 
            "Archivos Excel (*.xlsx)"
        )
        
        if save_path:
            if not save_path.endswith('.xlsx'):
                save_path += '.xlsx'
                
            col_code_name = self.input_col_code.text().strip() or "CODIGO"
            col_qty_name = self.input_col_qty.text().strip() or "CANTIDAD"
            col_type_name = self.input_col_type.text().strip() or "TIPO_IUA"
            col_year_name = self.input_col_year.text().strip() or "AÑO_REPORTE" 
            
            template_data = {
                col_code_name: ['0001', '0002', 'N/A', 'N/A'],
                col_qty_name: [10, 5, 20, 15],
                col_type_name: ['SUBESTACIÓN', 'LÍNEA', 'RED BT', 'TRANSFORMADOR'],
                col_year_name: ['2024', '2025', '2024', '2026'] 
            }
            
            df_template = pd.DataFrame(template_data)
            
            try:
                df_template.to_excel(save_path, index=False)
                self.prompt_open_file(save_path, "Plantilla descargada correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar la plantilla. Verifique que no tenga el archivo abierto.\n\nDetalle: {str(e)}")

    def update_buscador_ui(self):
        """Ajusta las restricciones de los campos según la infraestructura seleccionada."""
        tipo_iua = self.combo_infra.currentData()
        
        if tipo_iua in [IUAType.SUBSTATION.value, IUAType.LINE.value]:
            tipo_iux = 'IUS' if tipo_iua == IUAType.SUBSTATION.value else 'IUL'

            self.lbl_codigo.setText(f"Código {tipo_iux} (4 Num):")
            self.input_code.setPlaceholderText("Ej: 0001")
            self.input_code.setMaxLength(4)
            self.input_code.setEnabled(True) 
        else: 
            self.lbl_codigo.setText("Código Base:")
            self.input_code.setPlaceholderText("Generación 100% Automática")
            self.input_code.setEnabled(False) 
            
        self.input_code.clear()
        
        if hasattr(self, 'input_cantidad'): self.input_cantidad.setValue(1) 
        if hasattr(self, 'list_results'): self.list_results.clear() 
            
        self.btn_reserve.setEnabled(False)
        if hasattr(self, 'btn_export_reserva'): self.btn_export_reserva.setEnabled(False)
        if hasattr(self, 'btn_export_and_reserve'): self.btn_export_and_reserve.setEnabled(False)

    def find_free_iua(self):
        """Localiza en la base de datos la próxima secuencia de IUAs disponibles."""
        tipo_iua = self.combo_infra.currentData()
        code = self.input_code.text().strip().upper()
        cantidad = self.input_cantidad.value()
        
        if tipo_iua in [IUAType.SUBSTATION.value, IUAType.LINE.value]:
            tipo_iux = 'IUS' if tipo_iua == IUAType.SUBSTATION.value else 'IUL'

            if not code.isdigit():
                QMessageBox.warning(self, "Error", f"El código {tipo_iux} debe tener solo caracteres numéricos.")
                return
            elif len(code) != 4:
                QMessageBox.warning(self, "Error", f"El código {tipo_iux} debe tener exactamente 4 caracteres.")
                return
            elif 'ñ' in code.lower():
                QMessageBox.warning(self, "Error", f"El código {tipo_iux} no debe tener ñ.")
                return
        else:
            code = ""

        self.current_free_iuas = self.manager.get_available_iuas(tipo_iua, code, cantidad)
        
        self.list_results.clear()
        if self.current_free_iuas:
            if code:
                display_items = [f"{iua}  ({tipo_iux}: {code})" for iua in self.current_free_iuas]
            else:
                display_items = [f"{iua}  (Auto-Generado)" for iua in self.current_free_iuas]
                
            self.list_results.addItems(display_items)
            
            self.btn_reserve.setEnabled(True)
            self.btn_export_reserva.setEnabled(True)
            if hasattr(self, 'btn_export_and_reserve'): self.btn_export_and_reserve.setEnabled(True)
            
            if len(self.current_free_iuas) < cantidad:
                QMessageBox.warning(self, "Límite", "Se alcanzó el límite máximo de Base36. Se encontraron menos de los solicitados.")
        else:
            self.list_results.addItem("No hay disponibilidad.")
            self.btn_reserve.setEnabled(False)
            self.btn_export_reserva.setEnabled(False)
            if hasattr(self, 'btn_export_and_reserve'): self.btn_export_and_reserve.setEnabled(False)

    def reserve_current_iua(self):
        """Asienta los IUAs localizados como reservas en la base de datos."""
        year = self.input_year.text().strip()
        if not year:
            QMessageBox.warning(self, "Error", "Debe ingresar un año.")
            return

        self.manager.reserve_iuas(self.current_free_iuas, year)
        self.update_undo_redo_buttons()
        QMessageBox.information(self, "Éxito", f"{len(self.current_free_iuas)} IUAs reservados correctamente.")
        self.list_results.clear()
        self.btn_reserve.setEnabled(False)
        self.btn_export_reserva.setEnabled(False)
        self.refresh_table()

    def select_batch_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Seleccionar Archivo de Lotes", 
            "", 
            "Archivos Excel (*.xlsx *.xls)"
        )
        if file_path:
            self.input_batch_file.setText(file_path)
            self.btn_run_batch.setEnabled(True)

    def run_batch_reservation(self):
        """Despacha la tarea de generación de lotes hacia el hilo en segundo plano (BatchWorker)."""
        file_path = self.input_batch_file.text()
        col_code = self.input_col_code.text().strip()
        col_qty = self.input_col_qty.text().strip()
        col_type = self.input_col_type.text().strip() 
        col_year = self.input_col_year.text().strip() 
        year = self.input_year.text().strip()
        
        if not year and not col_year:
            QMessageBox.warning(self, "Falta Año", "Por favor, ingrese el 'Año proyectado' en la sección de arriba antes de procesar el lote o un nombra a la columna opcional Año.")
            return
            
        tipo_iua = self.combo_infra.currentData()
        do_reserve = self.chk_reserve_batch.isChecked()

        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar Reporte del Lote", 
            "Reporte_Reservas_Lote.xlsx", 
            "Archivos Excel (*.xlsx)"
        )

        if not save_path:
            return 
        
        self.btn_run_batch.setEnabled(False)
        self.btn_run_batch.setText("Generando... por favor espere")
        self.progress_batch.setValue(0)
        self.progress_batch.setVisible(True)
        self.btn_cancel_batch.setVisible(True) 
        self.btn_cancel_batch.setEnabled(True)
        self.btn_cancel_batch.setText("Cancelar")

        self.batch_thread = BatchWorker(
            self.manager, file_path, col_code, col_qty, year, tipo_iua, do_reserve, save_path, col_type, col_year
        )
        self.batch_thread.progress.connect(self.progress_batch.setValue)
        self.batch_thread.finished.connect(self.on_batch_finished)
        self.batch_thread.start()

    def cancel_batch_reservation(self):
        if hasattr(self, 'batch_thread') and self.batch_thread.isRunning():
            self.batch_thread.requestInterruption()
            self.btn_cancel_batch.setEnabled(False)
            self.btn_cancel_batch.setText("Cancelando...")

    def on_batch_finished(self, success, message, do_reserve, save_path):
        self.btn_run_batch.setText("Procesar Archivo y Reservar Lote")
        self.btn_run_batch.setEnabled(True)
        self.progress_batch.setVisible(False)
        self.btn_cancel_batch.setVisible(False) 
        
        if success:
            self.input_batch_file.clear()
            self.btn_run_batch.setEnabled(False)
            
            if do_reserve:
                self.refresh_table()
                self.prompt_open_file(save_path, f"{message}\n\nLos registros se han guardado en la base de datos.")
            else:
                self.prompt_open_file(save_path, f"{message}\n\nSolo se generó el Excel, la base de datos no fue alterada.")
        else:
            QMessageBox.critical(self, "Error en Lote", message)

    def free_selected_iuas(self):
        selection = self.table_view.selectionModel().selectedRows()

        if not selection:
            QMessageBox.warning(self, "Selección Vacía", "Por favor, seleccione al menos una fila en la tabla para liberar.\n(Puede arrastrar el mouse para seleccionar varias).")
            return

        iuas_to_free = []
        for index in selection:
            row_data = self.pandas_model._data.iloc[index.row()]
            iua_val = row_data[GlobalRegistryTableColumn.IUA.value]
            estado_val = row_data[GlobalRegistryTableColumn.STATE.value]

            if estado_val == IUARegistryState.RESERVED.value:
                iuas_to_free.append(iua_val)

        if not iuas_to_free:
            QMessageBox.information(self, "Aviso", "No se encontraron IUAs en estado 'RESERVADO' dentro de su selección. (Los ocupados oficialmente no se pueden liberar desde aquí).")
            return

        reply = QMessageBox.question(
            self, 
            'Confirmar Liberación',
            f"¿Está seguro de liberar {len(iuas_to_free)} IUA(s) reservado(s)?\nEstos códigos volverán a estar disponibles de inmediato en el buscador.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            liberados = self.manager.free_reserved_iuas(iuas_to_free)
            self.update_undo_redo_buttons()
            QMessageBox.information(self, "Éxito", f"Se han liberado {liberados} IUAs correctamente.")
            self.apply_pandas_filters()

    def free_all_filtered_iuas(self):
        if self.filtered_df.empty:
            QMessageBox.warning(self, "Tabla Vacía", "No hay datos en la tabla para liberar.")
            return

        mask_reservados = self.filtered_df[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value
        iuas_to_free = self.filtered_df[mask_reservados][GlobalRegistryTableColumn.IUA.value].tolist()

        if not iuas_to_free:
            QMessageBox.information(self, "Aviso", "No hay registros en estado 'RESERVADO' dentro de los resultados actuales de su búsqueda.\nLos ocupados oficialmente no se pueden liberar.")
            return

        reply = QMessageBox.question(
            self, 
            'Confirmar Liberación Masiva',
            f"⚠️ ATENCIÓN ⚠️\n\n¿Está seguro de querer liberar {len(iuas_to_free)} IUA(s) reservado(s) de golpe?\n\nEsta acción aplicará a TODOS los registros que cumplen con su búsqueda actual, incluso los que no está viendo en esta página debido a la paginación.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            liberados = self.manager.free_reserved_iuas(iuas_to_free)
            self.update_undo_redo_buttons()
            QMessageBox.information(self, "Éxito", f"Se han liberado {liberados} IUAs masivamente. Ya vuelven a estar disponibles.")
            self.apply_pandas_filters()

    def copy_selection_to_clipboard(self):
        selection = self.table_view.selectionModel().selectedRows()

        if not selection:
            QMessageBox.warning(self, "Selección Vacía", "Por favor, seleccione al menos una fila para copiar.")
            return

        indices = sorted([index.row() for index in selection])
        selected_df = self.pandas_model._data.iloc[indices]
        
        expanded_df = self._expand_json_column_for_export(selected_df)
        text_to_copy = expanded_df.to_csv(sep='\t', index=False)
        QApplication.clipboard().setText(text_to_copy)
        
        QMessageBox.information(self, "Copiado", f"Se han copiado {len(indices)} registros al portapapeles.")

    def copy_all_filtered_to_clipboard(self):
        if self.filtered_df.empty:
            QMessageBox.warning(self, "Tabla Vacía", "No hay datos filtrados para copiar.")
            return
        
        expanded_df = self._expand_json_column_for_export(self.filtered_df)
        text_to_copy = expanded_df.to_csv(sep='\t', index=False)
        QApplication.clipboard().setText(text_to_copy)
        
        QMessageBox.information(
            self, 
            "Copiado Masivo", 
            f"Se han copiado {len(self.filtered_df)} registros al portapapeles.\nYa puede pegarlos en Excel."
        )

    def _expand_json_column_for_export(self, df):
        """Desempaqueta las estructuras JSON de códigos para que sean visibles en Excel como columnas separadas."""
        import json
        df_copy = df.copy() 
        
        col_codigos = GlobalRegistryTableColumn.BDI_CODES.value
        col_iux = GlobalRegistryTableColumn.IUX.value
        
        if col_iux in df_copy.columns:
            df_copy[col_iux] = df_copy[col_iux].apply(
                lambda x: f'="{str(x).strip()}"' if pd.notna(x) and str(x).strip() else ""
            )
        
        if col_codigos in df_copy.columns:
            def safe_parse_json(val):
                try:
                    return json.loads(val) if pd.notna(val) and str(val).strip() else {}
                except Exception:
                    return {}

            serie_diccionarios = df_copy[col_codigos].apply(safe_parse_json)
            df_expandido = pd.DataFrame(serie_diccionarios.tolist(), index=df_copy.index)
            
            df_copy = df_copy.drop(columns=[col_codigos])
            df_copy = pd.concat([df_copy, df_expandido], axis=1)
            
        return df_copy
    
    def export_to_excel(self):
        if self.filtered_df.empty:
            QMessageBox.warning(self, "Tabla Vacía", "No hay datos para exportar con los filtros actuales.")
            return

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte Filtrado", "Reporte_IUA_Filtrado.xlsx", "Archivos Excel (*.xlsx)", options=options
        )

        if file_path:
            try:
                if not file_path.endswith('.xlsx'):
                    file_path += '.xlsx'
                    
                expanded_df = self._expand_json_column_for_export(self.filtered_df)
                expanded_df.to_excel(file_path, index=False)
                
                self.prompt_open_file(file_path, "Reporte de búsqueda guardado correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo.\n\nDetalle: {str(e)}")

    def export_reservation_excel(self):
        if not hasattr(self, 'current_free_iuas') or not self.current_free_iuas: return False
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar Libres", "IUAs_Libres.xlsx", "Archivos Excel (*.xlsx)")
        
        if file_path:
            if not file_path.endswith('.xlsx'): file_path += '.xlsx'

            code = self.input_code.text().strip().upper()
            tipo_iua = self.combo_infra.currentData()
            year = self.input_year.text().strip()
            
            if tipo_iua in [IUAType.SUBSTATION.value, IUAType.LINE.value]:
                code_text = f'="{code:0>4}"'
            else:
                code_text = "N/A (Generación Automática)"
            
            df_export = pd.DataFrame({
                'IUA_LIBRE': self.current_free_iuas,
                'IUL/IUS': [code_text] * len(self.current_free_iuas),
                'AÑO_DE_REPORTE': [str(year)] * len(self.current_free_iuas)
            })

            try:
                df_export.to_excel(file_path, index=False)
                self.prompt_open_file(file_path, "Exportado correctamente con su código asociado y año.")
                return True 
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error de Exportación", 
                    f"No se pudo guardar el archivo. Asegúrese de que no esté abierto en otro programa y vuelva a intentarlo.\n\nDetalle: {str(e)}"
                )
                return False
            
        return False

    def export_and_reserve_action(self):
        year = self.input_year.text().strip()
        if not year:
            QMessageBox.warning(self, "Error", "Debe ingresar un año para poder reservar.")
            return

        if self.export_reservation_excel():
            self.reserve_current_iua()

    def refresh_table(self):
        """Actualiza la tabla aplicando los filtros y respetando la paginación."""
        self.apply_pandas_filters()


    # ------------------ SECCIÓN 3: PESTAÑA SINCRONIZACIÓN INVA ------------------

    def setup_tab_sincronizacion(self):
        """Construye la vista de sincronización masiva con restricciones de seguridad."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        lbl_instruccion = QLabel("Arrastre aquí uno o varios reportes INVA, o use el botón Explorar:")
        lbl_instruccion.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_instruccion)

        self.sync_table = DragDropSyncTable()
        layout.addWidget(self.sync_table)

        btn_browse = QPushButton("Explorar Archivos...")
        btn_browse.clicked.connect(self.select_multiple_inva_files)
        self.icon_mgr.register_widget(btn_browse, "file-search.svg", QSize(16, 16), custom_colors={
            'Light Theme': '#ffffff'
        })
        layout.addWidget(btn_browse)

        progress_layout = QHBoxLayout()

        self.progress_sync = QProgressBar()
        self.progress_sync.setFixedHeight(18)
        self.progress_sync.setValue(0)
        self.progress_sync.setVisible(False)
        progress_layout.addWidget(self.progress_sync)

        self.btn_cancel_sync = QPushButton("Cancelar")
        self.btn_cancel_sync.setObjectName("danger-btn")
        self.btn_cancel_sync.setVisible(False)
        self.btn_cancel_sync.clicked.connect(self.cancel_sync)
        progress_layout.addWidget(self.btn_cancel_sync)

        layout.addLayout(progress_layout)

        self.btn_sync = QPushButton("Iniciar Sincronización Masiva")
        self.btn_sync.setObjectName("success-btn")
        self.btn_sync.clicked.connect(self.run_sync)
        self.icon_mgr.register_widget(self.btn_sync, "upload.svg", QSize(16, 16), custom_colors={
            'Light Theme': '#ffffff', 'Bento Theme': '#ffffff', 'Sci-Fi Theme': '#00ff66'
        })
        layout.addWidget(self.btn_sync)

        self.btn_change_pass = QPushButton("Cambiar Contraseña de Administrador")
        self.btn_change_pass.setObjectName("config-btn")
        self.btn_change_pass.clicked.connect(self.change_admin_password_dialog)
        self.icon_mgr.register_widget(self.btn_change_pass, "password-user.svg", QSize(16, 16), custom_colors={
            'Light Theme': '#ffffff'
        })
        layout.addWidget(self.btn_change_pass)

        self.btn_wipe = QPushButton("Borrar TODA la Base de Datos")
        self.btn_wipe.setObjectName("danger-all-btn") 
        self.btn_wipe.clicked.connect(self.wipe_database_action)
        self.icon_mgr.register_widget(self.btn_wipe, "trash-x.svg", QSize(16, 16), custom_colors={
            'Light Theme': '#ffffff', 'Bento Theme': '#ffffff', 'Sci-Fi Theme': '#ff3399'
        })
        layout.addWidget(self.btn_wipe)

        layout.addStretch()
        self.tabs.addTab(tab, "Sincronizar INVA")

    def select_multiple_inva_files(self):
        if hasattr(self, 'inactivity_timer'): self.inactivity_timer.stop()
        
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar reportes INVA", "", "Archivos Excel (*.xlsx *.xls)"
        )
        
        for file_path in files:
            self.sync_table.add_file_row(file_path)
            
        if self.is_admin_unlocked and hasattr(self, 'inactivity_timer'):
            self.inactivity_timer.start()

    def wipe_database_action(self):
        text, ok = QInputDialog.getText(
            self, 
            "Peligro: Borrado Total", 
            "Esta acción ELIMINARÁ permanentemente todos los registros (Ocupados y Reservados).\n\nPara continuar, escriba la palabra BORRAR en mayúsculas:"
        )

        if ok and text == "BORRAR":
            self.manager.wipe_all_data()
            if hasattr(self, 'apply_pandas_filters'):
                self.apply_pandas_filters()
            QMessageBox.information(self, "Éxito", "La base de datos ha sido eliminada y reiniciada desde cero.")
        elif ok:
            QMessageBox.warning(self, "Cancelado", "La palabra clave es incorrecta. No se borró nada.")

    def select_inva_file(self):
        if hasattr(self, 'inactivity_timer'):
            self.inactivity_timer.stop()

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Seleccionar reporte INVA", 
            "", 
            "Archivos Excel (*.xlsx *.xls);;Todos los archivos (*)", 
            options=options
        )

        if self.is_admin_unlocked and hasattr(self, 'inactivity_timer'):
            self.inactivity_timer.start()

        if file_path:
            self.input_file_path.setText(file_path)
            self.btn_sync.setEnabled(True)

    def run_sync(self):
        """Despacha la tarea de sincronización profunda al hilo en segundo plano (SyncWorker)."""
        files_config = self.sync_table.get_files_config()
        
        if not files_config:
            QMessageBox.warning(self, "Tabla vacía", "Debe agregar al menos un archivo para sincronizar.")
            return

        self.is_syncing = True
        self.btn_sync.setText("Sincronizando Múltiples Archivos... por favor espere")
        self.btn_sync.setEnabled(False)

        self.progress_sync.setValue(0)
        self.progress_sync.setVisible(True)
        self.btn_cancel_sync.setVisible(True) 
        self.btn_cancel_sync.setEnabled(True)
        self.btn_cancel_sync.setText("Cancelar")

        self.sync_thread = SyncWorker(self.manager, files_config)
        self.sync_thread.progress.connect(self.progress_sync.setValue)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.start()

    def cancel_sync(self):
        if hasattr(self, 'sync_thread') and self.sync_thread.isRunning():
            self.sync_thread.requestInterruption()
            self.btn_cancel_sync.setEnabled(False)
            self.btn_cancel_sync.setText("Cancelando...")

    def on_sync_finished(self, success, message):
        self.is_syncing = False
        self.btn_sync.setText("Iniciar Sincronización Masiva")
        self.btn_sync.setEnabled(True)
        self.progress_sync.setVisible(False)
        self.btn_cancel_sync.setVisible(False)

        if success:
            QMessageBox.information(self, "Éxito", message)
            self.sync_table.setRowCount(0) 
            self.refresh_table()
            self.update_undo_redo_buttons()
        else:
            QMessageBox.critical(self, "Error", message)

        if self.is_admin_unlocked:
            self.inactivity_timer.start()

    # ------------------ SECCIÓN 4: PESTAÑA CONSULTAS MASIVAS ------------------

    def setup_tab_consultas(self):
        """Construye la vista para operaciones de consulta, cruce de datos y auditoría de BDIs."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- TÍTULO Y DESCRIPCIÓN DINÁMICOS (Añadimos self.) ---
        self.lbl_titulo_consulta = QLabel("Consulta Masiva por Códigos BDI / Externos")
        self.lbl_titulo_consulta.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(self.lbl_titulo_consulta)
        
        self.lbl_desc_consulta = QLabel("Cargue un archivo Excel que contenga los códigos BDI a consultar.\n"
                                        "El sistema buscará esos códigos en la base de datos y devolverá la fila completa.")
        layout.addWidget(self.lbl_desc_consulta)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # --- SELECTOR DE MODO ---
        modo_layout = QHBoxLayout()
        modo_layout.addWidget(QLabel("Tipo de Consulta:"))
        
        self.combo_consulta_modo = QComboBox()
        self.combo_consulta_modo.addItem("Consultar por Códigos BDI / Externos", "BDI")
        self.combo_consulta_modo.addItem("Consultar por Identificadores IUA", "IUA")
        
        # Conectamos el cambio de opción a la nueva función
        self.combo_consulta_modo.currentIndexChanged.connect(self.update_consulta_ui)
        
        modo_layout.addWidget(self.combo_consulta_modo)
        modo_layout.addStretch()
        layout.addLayout(modo_layout)

        file_layout = QHBoxLayout()
        self.input_consulta_file = DragDropLineEdit()
        self.input_consulta_file.setPlaceholderText("Seleccione o arrastre el archivo de códigos aquí...")
        self.input_consulta_file.textChanged.connect(lambda text: self.btn_run_consulta.setEnabled(bool(text)))
        
        btn_browse_consulta = QPushButton("Explorar Excel...")
        btn_browse_consulta.clicked.connect(self.select_consulta_file)
        self.icon_mgr.register_widget(btn_browse_consulta, "file-search.svg", QSize(16, 16), custom_colors={
            'Light Theme': '#ffffff'
        })
        
        file_layout.addWidget(self.input_consulta_file)
        file_layout.addWidget(btn_browse_consulta)
        layout.addLayout(file_layout)

        col_layout = QHBoxLayout()
        col_layout.addWidget(QLabel("Nombre de la columna en el Excel:"))
        self.input_consulta_colname = QLineEdit("CODIGO")
        self.input_consulta_colname.setMaximumWidth(200)
        col_layout.addWidget(self.input_consulta_colname)
        col_layout.addStretch()
        layout.addLayout(col_layout)

        progress_layout = QHBoxLayout()
        
        self.progress_consulta = QProgressBar()
        self.progress_consulta.setFixedHeight(18)
        self.progress_consulta.setValue(0)
        self.progress_consulta.setVisible(False)
        progress_layout.addWidget(self.progress_consulta)

        self.btn_cancel_consulta = QPushButton("Cancelar")
        self.btn_cancel_consulta.setObjectName("danger-btn")
        self.btn_cancel_consulta.setVisible(False)
        self.btn_cancel_consulta.clicked.connect(self.cancel_consulta_masiva)
        progress_layout.addWidget(self.btn_cancel_consulta)

        layout.addLayout(progress_layout)

        self.btn_run_consulta = QPushButton("Procesar Consulta y Exportar Resultados")
        self.btn_run_consulta.setObjectName("export-btn")
        self.btn_run_consulta.setEnabled(False)
        self.btn_run_consulta.clicked.connect(self.run_consulta_masiva)
        
        self.icon_mgr.register_widget(self.btn_run_consulta, "table-export.svg", custom_colors={
            'Light Theme': '#ffffff', 'Bento Theme': '#ffffff'
        })
        
        layout.addWidget(self.btn_run_consulta)
        layout.addStretch()
        self.tabs.addTab(tab, "Consultas Masivas")

    def update_consulta_ui(self):
        """Actualiza los títulos, descripciones y placeholders según el tipo de consulta."""
        modo = self.combo_consulta_modo.currentData()
        
        if modo == "BDI":
            self.lbl_titulo_consulta.setText("Consulta Masiva por Códigos BDI / Externos")
            self.lbl_desc_consulta.setText("Cargue un Excel con códigos de otros sistemas (SAP, BDI, etc.).\n"
                                           "El sistema cruzará la información y generará un reporte con el activo correspondiente.")
            self.input_consulta_colname.setText("CODIGO") # Sugerencia por defecto
        
        elif modo == "IUA":
            self.lbl_titulo_consulta.setText("Consulta Masiva por Identificadores IUA")
            self.lbl_desc_consulta.setText("Cargue un Excel con una lista de Identificadores IUA.\n"
                                           "El sistema extraerá todos los datos de esos activos, marcando como 'NO ENCONTRADO' los que no existan.")
            self.input_consulta_colname.setText("IUA") # Sugerencia por defecto

    def select_consulta_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Seleccionar Archivo de Códigos a Consultar", 
            "", 
            "Archivos Excel (*.xlsx *.xls)"
        )
        if file_path:
            self.input_consulta_file.setText(file_path)
            self.btn_run_consulta.setEnabled(True)

    def run_consulta_masiva(self):
        """Despacha la consulta masiva hacia el hilo secundario (ConsultaWorker)."""
        modo = self.combo_consulta_modo.currentData()
        file_path = self.input_consulta_file.text()
        col_code = self.input_consulta_colname.text().strip()

        if not col_code:
            QMessageBox.warning(self, "Error", "Debe especificar el nombre de la columna donde están los códigos.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar Reporte de Consulta", 
            f"Reporte_Cruce_{modo}.xlsx", 
            "Archivos Excel (*.xlsx)"
        )
        
        if not save_path:
            return 
            
        if not save_path.endswith('.xlsx'): 
            save_path += '.xlsx'

        self.btn_run_consulta.setEnabled(False)
        self.btn_run_consulta.setText("Procesando... por favor espere")
        
        self.progress_consulta.setValue(0)
        self.progress_consulta.setVisible(True)
        self.btn_cancel_consulta.setVisible(True) 
        self.btn_cancel_consulta.setEnabled(True)
        self.btn_cancel_consulta.setText("Cancelar")

        # --- NUEVO: Extraemos el modo desde el ComboBox y se lo pasamos al Worker ---
        query_mode = self.combo_consulta_modo.currentData()

        self.consulta_thread = ConsultaWorker(
            self.manager,
            file_path,
            col_code,
            save_path,
            mode=query_mode,
            expand_func=self._expand_json_column_for_export
        )
        self.consulta_thread.progress.connect(self.progress_consulta.setValue)
        self.consulta_thread.finished.connect(self.on_consulta_finished)
        self.consulta_thread.start()

    def cancel_consulta_masiva(self):
        if hasattr(self, 'consulta_thread') and self.consulta_thread.isRunning():
            self.consulta_thread.requestInterruption()
            self.btn_cancel_consulta.setEnabled(False)
            self.btn_cancel_consulta.setText("Cancelando...")

    def on_consulta_finished(self, success, message, save_path):
        self.btn_run_consulta.setText("Procesar Consulta y Exportar Resultados")
        self.progress_consulta.setVisible(False)
        self.btn_cancel_consulta.setVisible(False) 
        
        if success:
            self.input_consulta_file.clear()
            self.btn_run_consulta.setEnabled(False)
            self.prompt_open_file(save_path, message)
        else:
            self.btn_run_consulta.setEnabled(True)
            QMessageBox.critical(self, "Error en la Consulta", message)

    # ------------------ EVENTOS GLOBALES Y SEGURIDAD ------------------

    def eventFilter(self, watched, event):
        """Monitorea eventos de usuario para reiniciar el temporizador de sesión de administrador."""
        if self.is_admin_unlocked:
            if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
                if not self.is_syncing:
                    self.inactivity_timer.start()
        return super().eventFilter(watched, event)

    def verify_tab_access(self, index):
        """Filtra y bloquea el acceso a pestañas restringidas solicitando contraseña administrativa."""
        if index in self.restricted_tabs and not self.is_admin_unlocked:
            blur_effect = QGraphicsBlurEffect()
            blur_effect.setBlurRadius(15)
            self.central_widget.setGraphicsEffect(blur_effect)

            password, ok = QInputDialog.getText(
                self, "Acceso Restringido", f"{'Ingrese la contraseña':<60}", QLineEdit.EchoMode.Password
            )

            stored_hash = get_admin_password_hash()

            if ok and verify_password(stored_hash, password):
                self.is_admin_unlocked = True
                self.last_valid_tab = index
                self.inactivity_timer.start()
                QMessageBox.information(self, "Acceso Concedido", "Modo administrador activado.")
            else:
                if ok:
                    QMessageBox.warning(self, "Acceso Denegado", "Contraseña incorrecta.")
                self.tabs.blockSignals(True)
                self.tabs.setCurrentIndex(self.last_valid_tab)
                self.tabs.blockSignals(False)
                
            self.central_widget.setGraphicsEffect(None)
        else:
            self.last_valid_tab = index

    def handle_inactivity_timeout(self):
        """Evalúa el estado del temporizador de seguridad y finaliza la sesión si es aplicable."""
        if self.is_syncing:
            self.inactivity_timer.start()
            return

        self.lock_admin_session()

    def lock_admin_session(self):
        """Ejecuta el cierre de la sesión de administrador por seguridad o inactividad."""
        self.inactivity_timer.stop()
        self.is_admin_unlocked = False

        if self.tabs.currentIndex() in self.restricted_tabs:
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(0)

            self.last_valid_tab = 0

            self.tabs.blockSignals(False)
            QMessageBox.warning(self, "Sesión Caducada", "Sesión de administrador cerrada por inactividad.")

    def change_admin_password_dialog(self):
        """Interfaz y lógica segura para la rotación de la contraseña administrativa."""
        current_pass, ok1 = QInputDialog.getText(
            self, "Seguridad", "Ingrese la contraseña actual:", QLineEdit.EchoMode.Password
        )
        if not ok1:
            return

        stored_hash = get_admin_password_hash()
        if not verify_password(stored_hash, current_pass):
            QMessageBox.critical(self, "Error", "La contraseña actual es incorrecta.")
            return

        new_pass, ok2 = QInputDialog.getText(
            self, "Nueva Contraseña", "Ingrese la nueva contraseña (mínimo 6 caracteres):", QLineEdit.EchoMode.Password
        )
        if not ok2 or len(new_pass.strip()) < 6:
            QMessageBox.warning(self, "Aviso", "La nueva contraseña debe tener al menos 6 caracteres.")
            return

        confirm_pass, ok3 = QInputDialog.getText(
            self, "Confirmar", "Repita la nueva contraseña:", QLineEdit.EchoMode.Password
        )
        if not ok3 or new_pass != confirm_pass:
            QMessageBox.critical(self, "Error", "Las contraseñas no coinciden.")
            return

        new_hash = hash_password(new_pass.strip())
        save_admin_password_hash(new_hash)
        QMessageBox.information(self, "Éxito", "Contraseña de administrador actualizada correctamente.")

    # ------------------ EVENTOS VISUALES ------------------
    def setup_logo(self):
        label_height = 96

        self.logo_label = QLabel()
        self.logo_label.setFixedHeight(label_height)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QIcon(resource_path("src/assets/IUA-Machine-LOGO-remove-bg-io.ico")).pixmap(QSize(128, 128))
        self.logo_label.setPixmap(logo_pixmap)
        self.logo_label.setVisible(False)

        self.logo2_label = QLabel()
        self.logo2_label.setFixedHeight(label_height)
        self.logo2_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo2_pixmap = QIcon(resource_path("src/assets/IUA-Machine-LOGO-white-remove-bg-io.ico")).pixmap(QSize(128, 128))
        self.logo2_label.setPixmap(logo2_pixmap)
        self.logo2_label.setVisible(False)

        self.header_layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.header_layout.addWidget(self.logo2_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def setup_logo_aire(self):
        label_height = 96

        self.logo_aire_label = QLabel()
        self.logo_aire_label.setFixedHeight(label_height)
        self.logo_aire_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_aire_pixmap = QIcon(resource_path("src/assets/LOGO NORMAL.png")).pixmap(QSize(146, 146))
        self.logo_aire_label.setPixmap(logo_aire_pixmap)
        self.logo_aire_label.setVisible(False)

        self.logo2_aire_label = QLabel()
        self.logo2_aire_label.setFixedHeight(label_height)
        self.logo2_aire_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo2_aire_pixmap = QIcon(resource_path("src/assets/LOGO BLANCO.png")).pixmap(QSize(128, 128))
        self.logo2_aire_label.setPixmap(logo2_aire_pixmap)
        self.logo2_aire_label.setVisible(False)

        self.header_layout.addWidget(self.logo2_aire_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.header_layout.addWidget(self.logo_aire_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def change_logos(self, theme_name):
        """Alterna el uso de logotipos claros u oscuros en base al tema actual."""
        logo2_themes = ["Dark Theme", "Glass Theme", "Hacker Theme", "Sci-Fi Theme"]
        logo2_aire_themes = ["Dark Theme", "Glass Theme"]

        logo_condition = not theme_name in logo2_themes
        logo_aire_condition = not theme_name in logo2_aire_themes

        self.logo_label.setVisible(logo_condition)
        self.logo2_label.setVisible(not logo_condition)
        self.logo_aire_label.setVisible(logo_aire_condition)
        self.logo2_aire_label.setVisible(not logo_aire_condition)

    def setup_theme_selector(self):
        self.theme_layout = QHBoxLayout()
        self.theme_layout.addStretch()

        self.theme_icon_label = QLabel()
        self.icon_mgr.register_widget(self.theme_icon_label, "palette.svg", QSize(32, 32))

        self.theme_layout.addWidget(self.theme_icon_label)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems([
            "Light Theme", "Dark Theme", "Glass Theme", 
            "Hacker Theme", "Sci-Fi Theme", "Bento Theme"
        ])

        saved_theme = get_saved_theme()
        index = self.combo_theme.findText(saved_theme)
        if index >= 0:
            self.combo_theme.setCurrentIndex(index)
            
        self.combo_theme.currentTextChanged.connect(self.change_theme)
        self.combo_theme.currentTextChanged.connect(self.change_logos)

        self.theme_layout.addWidget(self.combo_theme)
        self.header_layout.addLayout(self.theme_layout)

    def change_theme(self, theme_name):
        import os
        from lib.paths import resource_path

        theme_files = {
            "Light Theme": "theme_light.qss",
            "Dark Theme": "theme_dark.qss",
            "Glass Theme": "theme_glass.qss",
            "Hacker Theme": "theme_terminal.qss",
            "Sci-Fi Theme": "theme_scifi_hud.qss",
            "Bento Theme": "theme_bento.qss"
        }

        file_name = theme_files.get(theme_name, "theme_light.qss")
        qss_path = resource_path(os.path.join("src/assets", file_name))

        try:
            with open(qss_path, "r", encoding="utf-8") as file:
                styles = file.read()
                QApplication.instance().setStyleSheet(styles)

            save_theme(theme_name)
        except Exception as e:
            print(f"Error cargando el tema {theme_name}: {e}")

        self.icon_mgr.update_all_icons(theme_name)

    def prompt_open_file(self, file_path, mensaje="Archivo exportado correctamente."):
        reply = QMessageBox.question(
            self,
            "Exportación Exitosa",
            f"{mensaje}\n\n¿Desea abrir el archivo ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
