import os
from typing import Dict, Optional
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import QSize, Qt
from lib.paths import resource_path


class IconManager:
    # Paleta por defecto para todos los iconos normales
    DEFAULT_THEME_COLORS = {
        "Light Theme": "#15234A",       # Azul oscuro CREG
        "Dark Theme": "#f4f5f7",        # Blanco / Gris claro
        "Glass Theme": "#ffffff",     # Blanco puro
        "Hacker Theme": "#00ffcc",   # Cian neón
        "Sci-Fi Theme": "#00e5ff",        # Azul eléctrico HUD
        "Bento Theme": "#0099dd"    # Celeste primario
    }

    def __init__(self):
        # Lista de tuplas: (widget, svg_name, size, custom_colors)
        self._registered_widgets = []
        self._cache = {} # Clave: (svg_name, color_hex, width, height) -> QPixmap

    def get_tinted_pixmap(self, svg_name: str, color_hex: str, size: QSize = QSize(18, 18)) -> QPixmap:
        """Carga cualquier SVG base y lo colorea en memoria."""
        cache_key = (svg_name, color_hex, size.width(), size.height())
        
        # 1. Si ya existe en memoria, retorna la instancia existente
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Si no, genera el pixmap coloreado una única vez
        svg_path = resource_path(os.path.join("src", "assets", "icons", svg_name))
        pixmap = QIcon(svg_path).pixmap(size)
        
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color_hex))
        painter.end()
        
        # 3. Almacenar en caché y retornar
        self._cache[cache_key] = tinted
        return tinted

    def register_widget(
        self, 
        widget, 
        svg_name: str, 
        size: QSize = QSize(18, 18), 
        custom_colors: Optional[Dict[str, str]] = None
    ):
        """
        Registra un widget para tintado automático.
        
        :param custom_colors: Diccionario opcional {'Tema': '#HEX'} que sobreescribe
                              la paleta global para este icono en particular.
        """
        self._registered_widgets.append((widget, svg_name, size, custom_colors or {}))

    def update_all_icons(self, theme_name: str):
        """Actualiza todos los iconos registrados aplicando la jerarquía de colores."""
        default_color = self.DEFAULT_THEME_COLORS.get(theme_name, "#15234A")

        for widget, svg_name, size, custom_colors in self._registered_widgets:
            # 1. Mayor prioridad: Color específico asignado al icono para este tema
            # 2. Menor prioridad: Color por defecto del tema actual
            resolved_color = custom_colors.get(theme_name, default_color)

            pixmap = self.get_tinted_pixmap(svg_name, resolved_color, size)
            
            # Soporte para QLabel
            if hasattr(widget, "setPixmap"):
                widget.setPixmap(pixmap)
            # Soporte para QPushButton / QToolButton / QAction
            elif hasattr(widget, "setIcon"):
                widget.setIcon(QIcon(pixmap))
                if hasattr(widget, "setIconSize"):
                    widget.setIconSize(size)
