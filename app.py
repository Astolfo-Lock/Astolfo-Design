import json
import os
import re
import sys
import ctypes
from dataclasses import dataclass

import zint
from PyQt6.QtCore import QMarginsF, QRectF, QSettings, QSize, QSizeF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtGui import QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "Astolfo Design"
APP_VERSION = "1.3.0"
PROJECT_URL = "https://github.com/Astolfo-Lock/Astolfo-Design"
FILE_FILTER = "Diseño Astolfo (*.astolfo);;Diseño antiguo (*.astolfo.json);;Archivo JSON (*.json)"
PRINT_MODE_DRIVER = "driver"
PRINT_MODE_ASTOLFO = "astolfo"

RELEASE_NOTES = (
    (
        "1.3.0",
        "Funciones nuevas",
        (
            "Cantidad configurable en la impresión normal.",
            "Impresión limpia sin marcos ni selecciones del editor.",
            "Menú Ajustes con impresión avanzada y preferencias persistentes.",
            "Confirmación de impresión simplificada o técnica.",
            "Ventana de versión y notas accesible desde el logo.",
            "Acceso manual a GitHub para descargar actualizaciones.",
        ),
    ),
    (
        "1.2.0",
        "Funciones nuevas",
        (
            "Dos modos de tamaño de impresión.",
            "Selección de DPI.",
            "Diagnóstico previo de impresión.",
            "Formato .astolfo versión 2 en milímetros.",
            "Compatibilidad con documentos antiguos.",
        ),
    ),
    (
        "1.1.0",
        "Funciones principales",
        (
            "Diseño de etiquetas en centímetros.",
            "Textos, imágenes y códigos de barras Code 128.",
            "Impresión individual e incremental.",
            "Pegado automático de Nombre y PosCode.",
            "Edición de textos y códigos de barras.",
            "Tema claro y oscuro.",
        ),
    ),
)


def mm_to_pixels(millimeters, dpi):
    """Convert physical millimeters to device pixels, rounding only once."""
    return round(float(millimeters) * float(dpi) / 25.4)


def size_in_mm(page_layout):
    rect = page_layout.fullRect(QPageLayout.Unit.Millimeter)
    return QSizeF(rect.width(), rect.height())


def sizes_match(first, second, tolerance_mm=0.5):
    return (
        abs(first.width() - second.width()) <= tolerance_mm
        and abs(first.height() - second.height()) <= tolerance_mm
    )


def label_size_mm(label):
    """Read version 2 millimeters or migrate a version 1 centimeter label."""
    if "width_mm" in label and "height_mm" in label:
        return float(label["width_mm"]), float(label["height_mm"])
    return float(label["width_cm"]) * 10, float(label["height_cm"]) * 10


@dataclass(frozen=True)
class PrintDiagnostics:
    requested_size: QSizeF
    applied_size: QSizeF
    printable_rect: QRectF
    dpi: int
    orientation: str
    custom_size_requested: bool
    custom_size_accepted: bool

    @property
    def fits_page(self):
        return (
            self.requested_size.width() <= self.applied_size.width() + 0.5
            and self.requested_size.height() <= self.applied_size.height() + 0.5
        )

    @property
    def fits_printable_area(self):
        return (
            self.requested_size.width() <= self.printable_rect.width() + 0.5
            and self.requested_size.height() <= self.printable_rect.height() + 0.5
        )


def resource_path(filename):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, filename)


class DimensionSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ZintBarcodeItem(QGraphicsItem):
    def __init__(self, value):
        super().__init__()
        symbol = zint.Symbol()
        symbol.symbology = zint.Symbology.CODE128
        symbol.show_text = True
        symbol.height = 30
        symbol.whitespace_width = 10
        symbol.text_gap = 1
        symbol.encode(value)
        symbol.buffer_vector()
        vector = symbol.vector
        self._bounds = QRectF(0, 0, vector.width, vector.height)
        self._rectangles = [
            QRectF(rect.x, rect.y, rect.width, rect.height)
            for rect in vector.rectangles
        ]
        self._strings = [
            (text.text, text.x, text.y, text.width, text.fsize)
            for text in vector.strings
        ]

    def boundingRect(self):
        return self._bounds

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        for rectangle in self._rectangles:
            painter.drawRect(rectangle)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(Qt.GlobalColor.black)
        for value, center_x, baseline_y, width, font_size in self._strings:
            font = QFont("Arial")
            font.setPixelSize(max(1, round(font_size)))
            painter.setFont(font)
            text_rect = QRectF(
                center_x - width / 2,
                baseline_y - font_size,
                width,
                font_size * 1.4,
            )
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                value,
            )


class LabelCanvas(QGraphicsView):
    element_moved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.width_mm = 100.0
        self.height_mm = 50.0
        self.design_scene = QGraphicsScene(self)
        self.setScene(self.design_scene)
        self.setBackgroundBrush(QColor("#dfe3e9"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.copied_element = None

        self.label_item = QGraphicsRectItem()
        self.label_item.setBrush(QColor("white"))
        self.label_item.setPen(QPen(QColor("#aeb4bf"), 0.6))
        self.label_item.setZValue(-10)
        self.design_scene.addItem(self.label_item)
        self.set_dimensions_mm(self.width_mm, self.height_mm)

    def set_dimensions_mm(self, width_mm, height_mm):
        old_width = max(self.width_mm, 1)
        old_height = max(self.height_mm, 1)
        positions = [
            (item, item.pos().x() / old_width, item.pos().y() / old_height)
            for item in self.design_items()
        ]

        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)
        self.label_item.setRect(0, 0, width_mm, height_mm)
        self.design_scene.setSceneRect(-12, -12, width_mm + 24, height_mm + 24)

        for item, x_ratio, y_ratio in positions:
            item.setPos(x_ratio * width_mm, y_ratio * height_mm)
        self.fit_label()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_label()

    def fit_label(self):
        rect = self.label_item.rect().adjusted(-10, -10, 10, 10)
        if rect.width() > 0 and rect.height() > 0:
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def design_items(self):
        return [
            item
            for item in self.design_scene.items()
            if item is not self.label_item
            and item.data(0) in ("text", "image", "barcode")
        ]

    @staticmethod
    def make_movable(item):
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    @staticmethod
    def set_item_scale(item, logical_scale, base_scale=1.0):
        item.setData(2, float(logical_scale))
        item.setData(3, float(base_scale))
        item.setScale(float(logical_scale) * float(base_scale))

    @staticmethod
    def logical_scale(item):
        value = item.data(2)
        return float(value) if value is not None else 1.0

    def add_text(
        self,
        value,
        x_ratio=0.1,
        y_ratio=0.1,
        scale=1.0,
        bold=False,
        italic=False,
    ):
        item = QGraphicsTextItem(value)
        item.setData(0, "text")
        item.setData(1, value)
        item.setDefaultTextColor(QColor("#171b24"))
        font = QFont("Segoe UI")
        font.setPointSizeF(5.0)
        font.setBold(bold)
        font.setItalic(italic)
        item.setFont(font)
        self.make_movable(item)
        self.set_item_scale(item, scale)
        self.design_scene.addItem(item)
        item.setPos(
            x_ratio * self.width_mm,
            y_ratio * self.height_mm,
        )
        return item

    def add_image(self, path, x_ratio=0.1, y_ratio=0.3, scale=1.0):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            raise ValueError("La imagen seleccionada no se puede leer.")
        max_width = self.width_mm * 0.35
        max_height = self.height_mm * 0.35
        base_scale = min(max_width / pixmap.width(), max_height / pixmap.height(), 1.0)
        item = QGraphicsPixmapItem(pixmap)
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        item.setData(0, "image")
        item.setData(1, os.path.abspath(path))
        self.make_movable(item)
        self.set_item_scale(item, scale, base_scale)
        self.design_scene.addItem(item)
        item.setPos(
            x_ratio * self.width_mm,
            y_ratio * self.height_mm,
        )
        return item

    def add_barcode(self, value, x_ratio=0.1, y_ratio=0.55, scale=1.0):
        if not value.strip():
            raise ValueError("El contenido del código de barras no puede estar vacío.")
        item = ZintBarcodeItem(value.strip())
        bounds = item.boundingRect()
        target_width = self.width_mm * 0.78
        fit_scale = target_width / max(bounds.width(), 1)
        base_scale = max(0.14, min(0.22, fit_scale))
        item.setData(0, "barcode")
        item.setData(1, value.strip())
        item.setData(4, bounds.width() * base_scale > self.width_mm * 0.9)
        self.make_movable(item)
        self.set_item_scale(item, scale, base_scale)
        self.design_scene.addItem(item)
        item.setPos(
            x_ratio * self.width_mm,
            y_ratio * self.height_mm,
        )
        return item

    def clear_design(self):
        for item in self.design_items():
            self.design_scene.removeItem(item)

    def export_elements(self):
        width_mm = self.width_mm
        height_mm = self.height_mm
        elements = []
        for item in reversed(self.design_items()):
            element = {
                "type": item.data(0),
                "x": round(item.pos().x() / width_mm, 6),
                "y": round(item.pos().y() / height_mm, 6),
                "scale": round(self.logical_scale(item), 3),
            }
            if item.data(0) == "text":
                element["value"] = item.toPlainText()
                element["bold"] = item.font().bold()
                element["italic"] = item.font().italic()
            elif item.data(0) == "barcode":
                element["value"] = item.data(1)
                element["format"] = "code128"
            else:
                element["path"] = item.data(1)
            elements.append(element)
        return elements

    def element_data(self, item):
        element = {
            "type": item.data(0),
            "x": item.pos().x() / self.width_mm,
            "y": item.pos().y() / self.height_mm,
            "scale": self.logical_scale(item),
        }
        if item.data(0) == "text":
            element.update(
                {
                    "value": item.toPlainText(),
                    "bold": item.font().bold(),
                    "italic": item.font().italic(),
                }
            )
        elif item.data(0) == "image":
            element["path"] = item.data(1)
        elif item.data(0) == "barcode":
            element["value"] = item.data(1)
        return element

    def create_from_data(self, element, offset=0.0):
        x = min(0.95, max(0.0, float(element.get("x", 0.1)) + offset))
        y = min(0.95, max(0.0, float(element.get("y", 0.1)) + offset))
        scale = float(element.get("scale", 1.0))
        if element["type"] == "text":
            return self.add_text(
                element.get("value", ""),
                x,
                y,
                scale,
                bool(element.get("bold", False)),
                bool(element.get("italic", False)),
            )
        if element["type"] == "image":
            return self.add_image(element["path"], x, y, scale)
        if element["type"] == "barcode":
            return self.add_barcode(element.get("value", ""), x, y, scale)
        raise ValueError("Tipo de elemento desconocido.")

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item is self.label_item:
            item = None
        if item is not None and item.data(0) in ("text", "image", "barcode"):
            self.design_scene.clearSelection()
            item.setSelected(True)
        else:
            item = None

        menu = QMenu(self)
        item_type = item.data(0) if item is not None else None
        edit_label = (
            "Editar código de barras" if item_type == "barcode" else "Editar texto"
        )
        edit_action = menu.addAction(edit_label)
        bold_action = menu.addAction("Negrita")
        bold_action.setCheckable(True)
        italic_action = menu.addAction("Cursiva")
        italic_action.setCheckable(True)
        is_text = item is not None and item.data(0) == "text"
        is_barcode = item is not None and item.data(0) == "barcode"
        edit_action.setEnabled(is_text or is_barcode)
        bold_action.setEnabled(is_text)
        italic_action.setEnabled(is_text)
        if is_text:
            bold_action.setChecked(item.font().bold())
            italic_action.setChecked(item.font().italic())

        menu.addSeparator()
        copy_action = menu.addAction("Copiar")
        paste_action = menu.addAction("Pegar")
        duplicate_action = menu.addAction("Duplicar")
        delete_action = menu.addAction("Eliminar")
        copy_action.setEnabled(item is not None)
        duplicate_action.setEnabled(item is not None)
        delete_action.setEnabled(item is not None)
        paste_action.setEnabled(self.copied_element is not None)

        chosen = menu.exec(event.globalPos())
        if chosen is None:
            return
        if chosen == edit_action and is_text:
            self.edit_text_item(item)
        elif chosen == edit_action and is_barcode:
            self.edit_barcode_item(item)
        elif chosen == bold_action and is_text:
            font = item.font()
            font.setBold(not font.bold())
            item.setFont(font)
        elif chosen == italic_action and is_text:
            font = item.font()
            font.setItalic(not font.italic())
            item.setFont(font)
        elif chosen == copy_action and item is not None:
            self.copied_element = self.element_data(item)
        elif chosen == paste_action and self.copied_element is not None:
            pasted = self.create_from_data(self.copied_element, 0.03)
            self.design_scene.clearSelection()
            pasted.setSelected(True)
        elif chosen == duplicate_action and item is not None:
            duplicated = self.create_from_data(self.element_data(item), 0.03)
            self.design_scene.clearSelection()
            duplicated.setSelected(True)
        elif chosen == delete_action and item is not None:
            self.design_scene.removeItem(item)
        self.viewport().update()

    def edit_text_item(self, item):
        current_text = item.toPlainText()
        value, accepted = QInputDialog.getText(
            self,
            "Editar texto",
            "Modifica el contenido del texto:",
            text=current_text,
        )
        if accepted and value.strip():
            item.setPlainText(value.strip())
            item.setData(1, value.strip())
            self.viewport().update()

    def edit_barcode_item(self, item):
        current_value = str(item.data(1) or "")
        value, accepted = QInputDialog.getText(
            self,
            "Editar código de barras",
            "Modifica el contenido del código de barras:",
            text=current_value,
        )
        value = value.strip()
        if not accepted or not value or value == current_value:
            return item

        x_ratio = item.pos().x() / max(self.width_mm, 1)
        y_ratio = item.pos().y() / max(self.height_mm, 1)
        logical_scale = self.logical_scale(item)
        z_value = item.zValue()
        try:
            replacement = self.add_barcode(
                value, x_ratio, y_ratio, logical_scale
            )
        except (ValueError, RuntimeError) as error:
            QMessageBox.critical(
                self, "No se pudo editar el código de barras", str(error)
            )
            return item

        replacement.setZValue(z_value)
        self.design_scene.removeItem(item)
        self.design_scene.clearSelection()
        replacement.setSelected(True)
        self.viewport().update()
        if replacement.data(4):
            QMessageBox.warning(
                self,
                "El código necesita más ancho",
                "El nuevo contenido es demasiado largo para el ancho actual de "
                "la etiqueta sin reducir las barras por debajo de un tamaño seguro.",
            )
        return replacement

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item is not None and item.data(0) in ("text", "barcode"):
            self.design_scene.clearSelection()
            item.setSelected(True)
            if item.data(0) == "text":
                self.edit_text_item(item)
            else:
                self.edit_barcode_item(item)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.design_scene.selectedItems():
            self.element_moved.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.dark_mode = False
        self.auto_paste_enabled = False
        self.last_auto_clipboard = None
        self.app_settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            APP_NAME,
            APP_NAME,
        )
        self.paper_mode_value = self.app_settings.value(
            "print/paper_mode", PRINT_MODE_DRIVER, type=str
        )
        if self.paper_mode_value not in (PRINT_MODE_DRIVER, PRINT_MODE_ASTOLFO):
            self.paper_mode_value = PRINT_MODE_DRIVER
        saved_dpi = self.app_settings.value("print/dpi", "auto", type=str)
        self.dpi_value = int(saved_dpi) if saved_dpi in ("203", "300", "600") else None
        self.setWindowTitle(f"{APP_NAME} — Sin título")
        self.setWindowIcon(QIcon(resource_path("Logo.ico")))
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(LIGHT_STYLESHEET)

        self.canvas = LabelCanvas()
        self.canvas.element_moved.connect(
            lambda: self.statusBar().showMessage("Elemento movido", 2500)
        )
        self.width_input = self.dimension_input(10)
        self.height_input = self.dimension_input(5)
        self.dimension_display = QLabel()
        self.dimension_display.setObjectName("dimensionDisplay")
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(25, 400)
        self.size_slider.setValue(100)
        self.size_slider.setEnabled(False)
        self.size_slider.valueChanged.connect(self.resize_selected)
        self.size_display = QLabel("Selecciona un elemento")
        self.size_display.setObjectName("sizeDisplay")
        self.canvas.design_scene.selectionChanged.connect(self.selection_changed)
        self.printer_list = QListWidget()
        self.printer_list.setObjectName("printerList")
        self.printer_list.setMaximumHeight(128)
        self.setMenuWidget(self.build_toolbar())
        self.setCentralWidget(self.build_workspace())
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Documento nuevo")
        self.apply_dimensions()
        self.refresh_printers()
        self.printer_timer = QTimer(self)
        self.printer_timer.timeout.connect(self.refresh_printers)
        self.printer_timer.start(5000)
        QApplication.clipboard().dataChanged.connect(self.handle_clipboard_change)

    def build_toolbar(self):
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(56)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(18, 6, 12, 6)
        layout.setSpacing(4)

        logo = ClickableLabel()
        logo.setObjectName("appLogo")
        logo.setFixedSize(36, 36)
        logo.setCursor(Qt.CursorShape.PointingHandCursor)
        logo.setToolTip(f"Acerca de {APP_NAME} {APP_VERSION}")
        logo.clicked.connect(self.show_about)
        logo.setPixmap(
            QPixmap(resource_path("Logo.png")).scaled(
                32,
                32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        layout.addWidget(logo)

        brand = QLabel("ASTOLFO  DESIGN")
        brand.setObjectName("brand")
        brand.setFixedWidth(170)
        layout.addWidget(brand)
        self.theme_button = QPushButton("☾")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setToolTip("Cambiar a modo oscuro")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setFixedSize(38, 38)
        self.theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_button)
        layout.addSpacing(8)

        new_action = QAction("Nuevo archivo", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_design)
        self.addAction(new_action)

        open_action = QAction("Abrir", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_design)
        self.addAction(open_action)

        save_action = QAction("Guardar", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_design)
        self.addAction(save_action)

        save_as_action = QAction("Guardar como", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_design_as)
        self.addAction(save_as_action)

        file_menu = QMenu(self)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_button = QPushButton("Archivo")
        file_button.setObjectName("toolbarButton")
        file_button.setCursor(Qt.CursorShape.PointingHandCursor)
        file_button.setMenu(file_menu)
        layout.addWidget(file_button)

        self.clean_print_action = QAction("Impresión limpia (sin marco ni selección)", self)
        self.clean_print_action.setCheckable(True)
        self.clean_print_action.setChecked(
            self.app_settings.value("print/clean", True, type=bool)
        )
        self.clean_print_action.toggled.connect(
            lambda checked: self.app_settings.setValue("print/clean", checked)
        )
        self.print_details_action = QAction("Mostrar datos técnicos al confirmar", self)
        self.print_details_action.setCheckable(True)
        self.print_details_action.setChecked(
            self.app_settings.value("print/show_details", False, type=bool)
        )
        self.print_details_action.toggled.connect(
            lambda checked: self.app_settings.setValue("print/show_details", checked)
        )
        settings_menu = QMenu(self)
        settings_menu.addAction(self.clean_print_action)
        settings_menu.addAction(self.print_details_action)
        settings_menu.addSeparator()
        advanced_print_action = QAction("Impresión avanzada…", self)
        advanced_print_action.triggered.connect(self.show_advanced_print_settings)
        settings_menu.addAction(advanced_print_action)
        settings_button = QPushButton("Ajustes")
        settings_button.setObjectName("toolbarButton")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.setMenu(settings_menu)
        layout.addWidget(settings_button)
        layout.addSpacing(12)
        layout.addWidget(self.toolbar_button("Imprimir", self.print_current))
        layout.addWidget(
            self.toolbar_button("Impresión incremental", self.print_incremental)
        )
        layout.addStretch()
        return toolbar

    def show_about(self):
        notes_html = []
        for version, heading, changes in RELEASE_NOTES:
            items = "".join(f"<li>{change}</li>" for change in changes)
            notes_html.append(
                f"<h3>Versión {version}</h3>"
                f"<p><b>{heading}</b></p>"
                f"<ul>{items}</ul>"
            )

        dialog = QMessageBox(self)
        dialog.setWindowTitle(f"Acerca de {APP_NAME}")
        dialog.setWindowIcon(QIcon(resource_path("Logo.ico")))
        dialog.setIconPixmap(
            QPixmap(resource_path("Logo.png")).scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText(
            f"<h2>{APP_NAME}</h2>"
            f"<p>Versión instalada: <b>{APP_VERSION}</b></p>"
            "<hr>"
            + "".join(notes_html)
        )
        github_button = dialog.addButton(
            "GitHub · Descargar actualizaciones",
            QMessageBox.ButtonRole.ActionRole,
        )
        github_button.setObjectName("githubButton")
        github_icon = "github-mark-light.svg" if self.dark_mode else "github-mark.svg"
        github_button.setIcon(QIcon(resource_path(github_icon)))
        github_button.setIconSize(QSize(18, 18))
        github_button.setToolTip(
            "Abrir manualmente la página oficial de Astolfo Design en GitHub"
        )
        dialog.addButton(QMessageBox.StandardButton.Ok)
        dialog.exec()
        if dialog.clickedButton() is github_button:
            if not QDesktopServices.openUrl(QUrl(PROJECT_URL)):
                QMessageBox.warning(
                    self,
                    "No se pudo abrir GitHub",
                    f"Abre esta dirección manualmente:\n{PROJECT_URL}",
                )

    def show_advanced_print_settings(self):
        dialog = QDialog(self)
        dialog.setObjectName("advancedPrintDialog")
        dialog.setWindowTitle("Impresión avanzada")
        dialog.setWindowIcon(QIcon(resource_path("Logo.ico")))
        dialog.setModal(True)
        dialog.setMinimumWidth(430)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title = QLabel("IMPRESIÓN AVANZADA")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        description = QLabel(
            "Estas opciones se aplican a las próximas impresiones y se guardan "
            "automáticamente al cerrar esta ventana."
        )
        description.setObjectName("hint")
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        paper_mode = NoWheelComboBox()
        paper_mode.setObjectName("printOption")
        paper_mode.addItem(
            "Usar tamaño configurado en la impresora", PRINT_MODE_DRIVER
        )
        paper_mode.addItem("Solicitar tamaño desde Astolfo", PRINT_MODE_ASTOLFO)
        paper_mode.setCurrentIndex(max(0, paper_mode.findData(self.paper_mode_value)))
        paper_mode.setToolTip(
            "El primer modo respeta el papel del controlador. El segundo solicita "
            "el ancho y largo definidos en el diseño."
        )
        dpi_input = NoWheelComboBox()
        dpi_input.setObjectName("printOption")
        dpi_input.addItem("DPI automático (controlador)", None)
        for dpi in (203, 300, 600):
            dpi_input.addItem(f"{dpi} DPI", dpi)
        dpi_index = dpi_input.findData(self.dpi_value)
        dpi_input.setCurrentIndex(max(0, dpi_index))
        form.addRow("Tamaño del papel", paper_mode)
        form.addRow("Resolución", dpi_input)
        layout.addLayout(form)

        close_button = QPushButton("Guardar y cerrar")
        close_button.setObjectName("accentButton")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec()
        self.paper_mode_value = paper_mode.currentData()
        self.dpi_value = dpi_input.currentData()
        self.app_settings.setValue("print/paper_mode", self.paper_mode_value)
        self.app_settings.setValue(
            "print/dpi", "auto" if self.dpi_value is None else str(self.dpi_value)
        )
        self.app_settings.sync()
        self.statusBar().showMessage("Ajustes de impresión guardados", 2500)

    def build_workspace(self):
        workspace = QWidget()
        workspace.setObjectName("workspace")
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(self.build_sidebar())
        layout.addWidget(self.build_canvas_panel(), 1)
        return workspace

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(262)
        sidebar.setMinimumHeight(690)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(10)

        layout.addWidget(self.section_title("Herramientas"))
        layout.addWidget(self.tool_button("T    Insertar texto", self.insert_text))
        layout.addWidget(self.tool_button("▧    Insertar imagen", self.insert_image))
        layout.addWidget(
            self.tool_button("▥    Insertar código de barras", self.insert_barcode)
        )
        layout.addWidget(self.build_auto_paste_control())
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("separator")
        layout.addSpacing(8)
        layout.addWidget(separator)
        layout.addSpacing(8)

        layout.addWidget(self.section_title("Dimensiones de etiqueta"))
        layout.addLayout(self.dimension_row("Ancho", self.width_input))
        layout.addLayout(self.dimension_row("Largo", self.height_input))

        apply_button = QPushButton("Aplicar dimensiones")
        apply_button.setObjectName("accentButton")
        apply_button.setMinimumHeight(42)
        apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button.clicked.connect(self.apply_dimensions)
        layout.addWidget(apply_button)

        hint = QLabel(
            "Las medidas se guardan en centímetros.\n"
            "La vista se escala automáticamente."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setMinimumHeight(44)
        layout.addWidget(hint)

        layout.addSpacing(12)
        layout.addWidget(self.section_title("Tamaño del elemento"))
        layout.addWidget(self.size_display)
        layout.addWidget(self.size_slider)

        layout.addSpacing(10)
        printer_heading = QHBoxLayout()
        printer_heading.addWidget(self.section_title("Impresoras"))
        refresh = QPushButton("Actualizar")
        refresh.setObjectName("smallButton")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.refresh_printers)
        printer_heading.addWidget(refresh)
        layout.addLayout(printer_heading)
        layout.addWidget(self.printer_list)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("sidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(sidebar)
        scroll.setFixedWidth(282)
        return scroll

    def build_canvas_panel(self):
        panel = QFrame()
        panel.setObjectName("canvasPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("canvasHeader")
        header.setFixedHeight(46)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        title = QLabel("ÁREA DE DISEÑO")
        title.setObjectName("canvasTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.dimension_display)
        panel_layout.addWidget(header)
        panel_layout.addWidget(self.canvas, 1)

        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(40, 46, 58, 35))
        panel.setGraphicsEffect(shadow)
        return panel

    @staticmethod
    def dimension_input(value):
        field = DimensionSpinBox()
        field.setMinimumHeight(34)
        field.setRange(0.1, 200)
        field.setDecimals(2)
        field.setSingleStep(0.1)
        field.setValue(value)
        field.setSuffix(" cm")
        field.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        return field

    @staticmethod
    def dimension_row(label, field):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        text = QLabel(label)
        text.setObjectName("dimensionLabel")
        text.setFixedWidth(56)
        layout.addWidget(text)
        layout.addWidget(field)
        return layout

    @staticmethod
    def section_title(text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        label.setMinimumHeight(27)
        return label

    @staticmethod
    def toolbar_button(text, callback):
        button = QPushButton(text)
        button.setObjectName("toolbarButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def tool_button(text, callback):
        button = QPushButton(text)
        button.setObjectName("toolButton")
        button.setMinimumHeight(44)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def build_auto_paste_control(self):
        container = QFrame()
        container.setObjectName("autoPasteControl")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(11, 4, 11, 4)
        layout.setSpacing(8)
        self.auto_paste_dot = QLabel("●")
        self.auto_paste_dot.setObjectName("autoPasteOff")
        self.auto_paste_dot.setFixedWidth(16)
        self.auto_paste_button = QPushButton("Pegado automático")
        self.auto_paste_button.setObjectName("autoPasteButton")
        self.auto_paste_button.setCheckable(True)
        self.auto_paste_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_paste_button.toggled.connect(self.toggle_auto_paste)
        layout.addWidget(self.auto_paste_dot)
        layout.addWidget(self.auto_paste_button, 1)
        return container

    def apply_dimensions(self):
        width = self.width_input.value()
        height = self.height_input.value()
        self.canvas.set_dimensions_mm(width * 10, height * 10)
        self.dimension_display.setText(f"{width:g} × {height:g} cm")
        self.statusBar().showMessage(
            f"Etiqueta actualizada: {width:g} × {height:g} cm", 3000
        )

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.setStyleSheet(LIGHT_STYLESHEET + DARK_OVERRIDES)
            self.canvas.setBackgroundBrush(QColor("#171b24"))
            self.theme_button.setText("☀")
            self.theme_button.setToolTip("Cambiar a modo claro")
            self.statusBar().showMessage("Modo oscuro activado", 2000)
        else:
            self.setStyleSheet(LIGHT_STYLESHEET)
            self.canvas.setBackgroundBrush(QColor("#dfe3e9"))
            self.theme_button.setText("☾")
            self.theme_button.setToolTip("Cambiar a modo oscuro")
            self.statusBar().showMessage("Modo claro activado", 2000)

    def insert_text(self):
        value, accepted = QInputDialog.getText(
            self, "Insertar texto", "Escribe el texto de la etiqueta:"
        )
        if accepted and value.strip():
            self.canvas.add_text(value.strip())
            self.statusBar().showMessage(
                "Texto insertado. Puedes arrastrarlo para moverlo.", 3500
            )

    def insert_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Insertar imagen",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif);;Todos los archivos (*.*)",
        )
        if not path:
            return
        try:
            self.canvas.add_image(path)
            self.statusBar().showMessage(
                "Imagen insertada. Puedes arrastrarla para moverla.", 3500
            )
        except ValueError as error:
            QMessageBox.critical(self, "No se pudo insertar", str(error))

    def insert_barcode(self):
        value, accepted = QInputDialog.getText(
            self,
            "Insertar código de barras",
            "Escribe el texto, número o combinación que deseas codificar:",
        )
        if not accepted or not value.strip():
            return
        try:
            item = self.canvas.add_barcode(value)
            item.setSelected(True)
            self.statusBar().showMessage(
                f"Código de barras Code 128 generado: {value.strip()}", 4000
            )
            if item.data(4):
                QMessageBox.warning(
                    self,
                    "El código necesita más ancho",
                    "El número es demasiado largo para el ancho actual de la "
                    "etiqueta sin reducir las barras por debajo de un tamaño "
                    "seguro. Aumenta el ancho de la etiqueta para impresión.",
                )
        except (ValueError, RuntimeError) as error:
            QMessageBox.critical(
                self, "No se pudo generar el código de barras", str(error)
            )

    def toggle_auto_paste(self, enabled):
        self.auto_paste_enabled = enabled
        self.auto_paste_dot.setObjectName(
            "autoPasteOn" if enabled else "autoPasteOff"
        )
        self.auto_paste_dot.style().unpolish(self.auto_paste_dot)
        self.auto_paste_dot.style().polish(self.auto_paste_dot)
        self.auto_paste_button.setText(
            "Pegado automático: activo" if enabled else "Pegado automático"
        )
        if enabled:
            self.last_auto_clipboard = None
            self.statusBar().showMessage("Pegado automático activado", 3000)
            self.handle_clipboard_change()
        else:
            self.statusBar().showMessage("Pegado automático desactivado", 3000)

    def handle_clipboard_change(self):
        if not self.auto_paste_enabled:
            return
        clipboard_text = QApplication.clipboard().text().strip()
        if not clipboard_text or clipboard_text == self.last_auto_clipboard:
            return
        self.last_auto_clipboard = clipboard_text
        self.paste_clipboard_data(show_messages=False)

    def paste_clipboard_data(self, show_messages=True):
        clipboard_text = QApplication.clipboard().text().strip()
        if not clipboard_text:
            if show_messages:
                QMessageBox.information(
                    self, "Portapapeles vacío", "No hay texto para pegar."
                )
            return

        values = self.parse_clipboard_values(clipboard_text)
        if not values:
            if show_messages:
                QMessageBox.warning(
                    self,
                    "Datos no reconocidos",
                    "El PosCode debe contener exclusivamente números.",
                )
            return

        patterns = {
            "nombre": re.compile(r"^(\s*nombre\s*:\s*)(.*)$", re.IGNORECASE | re.DOTALL),
            "poscode": re.compile(
                r"^(\s*pos\s*code\s*:\s*)(.*)$", re.IGNORECASE | re.DOTALL
            ),
        }
        updated = []
        for item in self.canvas.design_items():
            if item.data(0) != "text":
                continue
            current = item.toPlainText()
            for field, value in values.items():
                match = patterns[field].match(current)
                if match:
                    item.setPlainText(match.group(1) + value)
                    item.setData(1, item.toPlainText())
                    updated.append(field)
                    break

        if not updated:
            expected = " y ".join(
                "Nombre:" if field == "nombre" else "PosCode:" for field in values
            )
            if show_messages:
                QMessageBox.information(
                    self,
                    "Campo no encontrado",
                    f"No existe un texto que comience con {expected} en la etiqueta.",
                )
            return

        labels = []
        if "nombre" in updated:
            labels.append("Nombre")
        if "poscode" in updated:
            labels.append("PosCode")
        self.canvas.viewport().update()
        self.statusBar().showMessage(
            f"Datos pegados en: {', '.join(labels)}", 3500
        )

    @staticmethod
    def parse_clipboard_values(text):
        values = {}
        name_match = re.search(
            r"(?im)^\s*nombre\s*:\s*(.+?)\s*$", text
        )
        poscode_match = re.search(
            r"(?im)^\s*pos\s*code\s*:\s*(.*?)\s*$", text
        )
        if name_match:
            values["nombre"] = " ".join(name_match.group(1).split())
        if poscode_match:
            candidate = "".join(poscode_match.group(1).split())
            if candidate.isdigit():
                values["poscode"] = candidate
        if name_match or poscode_match:
            return values

        compact = " ".join(text.split())
        if compact.isdigit():
            return {"poscode": compact}
        return {"nombre": compact} if compact else {}

    def selection_changed(self):
        selected = self.canvas.design_scene.selectedItems()
        if not selected:
            self.size_slider.setEnabled(False)
            self.size_display.setText("Selecciona un elemento")
            return
        item = selected[0]
        percentage = max(
            25, min(400, round(self.canvas.logical_scale(item) * 100))
        )
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(percentage)
        self.size_slider.blockSignals(False)
        self.size_slider.setEnabled(True)
        element_name = self.element_name(item)
        self.size_display.setText(f"{element_name}: {percentage}%")

    def resize_selected(self, percentage):
        selected = self.canvas.design_scene.selectedItems()
        if not selected:
            return
        item = selected[0]
        base_scale = float(item.data(3)) if item.data(3) is not None else 1.0
        self.canvas.set_item_scale(item, percentage / 100, base_scale)
        element_name = self.element_name(selected[0])
        self.size_display.setText(f"{element_name}: {percentage}%")
        self.statusBar().showMessage(
            f"Tamaño del elemento actualizado a {percentage}%", 2000
        )

    @staticmethod
    def element_name(item):
        return {
            "text": "Texto",
            "image": "Imagen",
            "barcode": "Código de barras",
        }.get(item.data(0), "Elemento")

    def document_data(self):
        return {
            "application": APP_NAME,
            "version": 2,
            "label": {
                "width_mm": self.canvas.width_mm,
                "height_mm": self.canvas.height_mm,
            },
            "elements": self.canvas.export_elements(),
        }

    def new_design(self):
        if self.canvas.design_items():
            answer = QMessageBox.question(
                self,
                "Nuevo archivo",
                "El diseño actual contiene elementos.\n"
                "¿Quieres descartarlos y crear un archivo nuevo?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.canvas.clear_design()
        self.width_input.setValue(10)
        self.height_input.setValue(5)
        self.current_file = None
        self.setWindowTitle(f"{APP_NAME} — Sin título")
        self.apply_dimensions()
        self.statusBar().showMessage("Archivo nuevo", 3000)

    def refresh_printers(self):
        selected_name = None
        current = self.printer_list.currentItem()
        if current:
            selected_name = current.data(Qt.ItemDataRole.UserRole)

        self.printer_list.clear()
        printers = QPrinterInfo.availablePrinters()
        if not printers:
            empty = QListWidgetItem("No se encontraron impresoras")
            empty.setForeground(QColor("#717784"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.printer_list.addItem(empty)
            return

        connected_states = {
            QPrinter.PrinterState.Idle,
            QPrinter.PrinterState.Active,
        }
        for printer in printers:
            connected = printer.state() in connected_states
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, printer.printerName())
            item.setSizeHint(QRectF(0, 0, 0, 31).size().toSize())
            self.printer_list.addItem(item)

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(7, 3, 7, 3)
            row_layout.setSpacing(8)
            dot = QLabel("●")
            dot.setObjectName("printerConnected" if connected else "printerDisconnected")
            dot.setToolTip("Conectada" if connected else "Desconectada o con error")
            name = QLabel(printer.printerName())
            name.setObjectName("printerName")
            name.setToolTip(printer.description() or printer.printerName())
            row_layout.addWidget(dot)
            row_layout.addWidget(name, 1)
            self.printer_list.setItemWidget(item, row)
            if printer.printerName() == selected_name:
                self.printer_list.setCurrentItem(item)
        if self.printer_list.currentItem() is None and self.printer_list.count():
            default_name = QPrinterInfo.defaultPrinter().printerName()
            match = next(
                (
                    index
                    for index in range(self.printer_list.count())
                    if self.printer_list.item(index).data(Qt.ItemDataRole.UserRole)
                    == default_name
                ),
                0,
            )
            self.printer_list.setCurrentRow(match)

    def selected_printer(self):
        item = self.printer_list.currentItem()
        if not item:
            QMessageBox.warning(
                self, "Selecciona una impresora", "Selecciona una impresora de la lista."
            )
            return None
        name = item.data(Qt.ItemDataRole.UserRole)
        printer = next(
            (info for info in QPrinterInfo.availablePrinters() if info.printerName() == name),
            None,
        )
        if printer is None:
            QMessageBox.warning(
                self,
                "Impresora no disponible",
                "La impresora seleccionada ya no está disponible. Actualiza la lista.",
            )
        return printer

    def print_current(self):
        quantity, accepted = QInputDialog.getInt(
            self,
            "Imprimir etiquetas",
            "Cantidad de etiquetas:",
            1,
            1,
            100000,
            1,
        )
        if not accepted:
            return
        printer_info = self.selected_printer()
        if printer_info is None:
            return
        printer, diagnostics = self.prepare_printer(printer_info)
        if QMessageBox.question(
            self,
            "Confirmar impresión",
            self.print_confirmation(printer_info, diagnostics, quantity)
            + "¿Enviar este trabajo de impresión?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.print_pages(printer, printer_info, diagnostics, quantity)

    def print_incremental(self):
        selected = self.canvas.design_scene.selectedItems()
        if len(selected) != 1 or selected[0].data(0) != "text":
            QMessageBox.information(
                self,
                "Selecciona el número",
                "Haz clic sobre el texto numérico que deseas incrementar y vuelve "
                "a presionar “Impresión incremental”.",
            )
            return
        text_item = selected[0]
        original_text = text_item.toPlainText().strip()
        if not original_text.isdigit():
            QMessageBox.warning(
                self,
                "El texto no es numérico",
                "La impresión incremental requiere seleccionar un texto que contenga "
                "solamente números.",
            )
            return
        quantity, accepted = QInputDialog.getInt(
            self,
            "Impresión incremental",
            "Cantidad de etiquetas:",
            50,
            1,
            100000,
            1,
        )
        if not accepted:
            return
        printer_info = self.selected_printer()
        if printer_info is None:
            return
        printer, diagnostics = self.prepare_printer(printer_info)
        start = int(original_text)
        last = start + quantity - 1
        width = len(original_text)
        last_text = str(last).zfill(width)
        confirmation = self.print_confirmation(printer_info, diagnostics, quantity) + (
            "\n"
            f"Primera: {original_text}\n"
            f"Última: {last_text}\n\n"
            "¿Enviar este trabajo de impresión?"
        )
        if QMessageBox.question(
            self, "Confirmar impresión incremental", confirmation
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.print_pages(
                printer,
                printer_info,
                diagnostics,
                quantity,
                text_item=text_item,
                start=start,
                number_width=width,
            )
        finally:
            text_item.setPlainText(original_text)
            self.canvas.viewport().update()

    def prepare_printer(self, printer_info):
        printer = QPrinter(printer_info, QPrinter.PrinterMode.HighResolution)
        selected_dpi = self.dpi_value
        if selected_dpi:
            printer.setResolution(int(selected_dpi))

        requested_size = QSizeF(self.canvas.width_mm, self.canvas.height_mm)
        custom_size_requested = self.paper_mode_value == PRINT_MODE_ASTOLFO
        layout_accepted = True
        if custom_size_requested:
            # QPageLayout swaps dimensions in landscape mode. Use a portrait custom
            # page so its physical width and height remain exactly as requested.
            page_size = QPageSize(
                requested_size,
                QPageSize.Unit.Millimeter,
                f"Astolfo {requested_size.width():g}x{requested_size.height():g} mm",
                QPageSize.SizeMatchPolicy.ExactMatch,
            )
            layout_accepted = printer.setPageLayout(
                QPageLayout(
                    page_size,
                    QPageLayout.Orientation.Portrait,
                    QMarginsF(0, 0, 0, 0),
                    QPageLayout.Unit.Millimeter,
                )
            )

        printer.setFullPage(True)
        applied_layout = printer.pageLayout()
        applied_size = size_in_mm(applied_layout)
        printable_rect = applied_layout.paintRect(QPageLayout.Unit.Millimeter)
        orientation = (
            "Horizontal"
            if applied_size.width() > applied_size.height()
            else "Vertical"
        )
        diagnostics = PrintDiagnostics(
            requested_size=requested_size,
            applied_size=applied_size,
            printable_rect=printable_rect,
            dpi=printer.resolution(),
            orientation=orientation,
            custom_size_requested=custom_size_requested,
            custom_size_accepted=(
                layout_accepted and sizes_match(requested_size, applied_size)
            ),
        )
        return printer, diagnostics

    def print_confirmation(self, printer_info, diagnostics, quantity):
        requested = diagnostics.requested_size
        applied = diagnostics.applied_size
        printable = diagnostics.printable_rect
        mode = (
            "Solicitado por Astolfo"
            if diagnostics.custom_size_requested
            else "Configurado en el controlador"
        )
        acceptance = (
            "Aceptado"
            if diagnostics.custom_size_accepted
            else "El controlador usa otro tamaño"
        )
        if not diagnostics.custom_size_requested:
            acceptance = "Sin modificación"
        fit_warning = ""
        if not diagnostics.fits_page:
            fit_warning = "\nADVERTENCIA: el diseño no cabe completo en el papel aplicado.\n"
        elif not diagnostics.fits_printable_area:
            fit_warning = (
                "\nADVERTENCIA: parte del diseño queda fuera del área imprimible "
                "reportada por el controlador.\n"
            )
        summary = (
            f"Impresora: {printer_info.printerName()}\n"
            f"Cantidad: {quantity} etiqueta(s)\n"
        )
        if not self.print_details_action.isChecked():
            return summary + f"{fit_warning}\n"
        return summary + (
            f"Modo: {mode} ({acceptance})\n"
            f"Tamaño solicitado: {requested.width():g} × {requested.height():g} mm\n"
            f"Tamaño aplicado: {applied.width():g} × {applied.height():g} mm\n"
            f"Área imprimible: {printable.width():g} × {printable.height():g} mm\n"
            f"DPI: {diagnostics.dpi}\n"
            f"Orientación: {diagnostics.orientation}\n"
            "Escalado: 100 % (tamaño físico)\n"
            f"{fit_warning}\n"
        )

    def print_pages(
        self,
        printer,
        printer_info,
        diagnostics,
        quantity,
        text_item=None,
        start=0,
        number_width=1,
    ):
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(
                self,
                "No se pudo imprimir",
                "Windows no pudo iniciar el trabajo de impresión.",
            )
            return
        source = self.canvas.label_item.rect()
        width_mm = self.canvas.width_mm
        height_mm = self.canvas.height_mm
        dpi = diagnostics.dpi
        target = QRectF(
            0,
            0,
            mm_to_pixels(width_mm, dpi),
            mm_to_pixels(height_mm, dpi),
        )
        completed = False
        selected_items = self.canvas.design_scene.selectedItems()
        label_was_visible = self.canvas.label_item.isVisible()
        clean_print = self.clean_print_action.isChecked()
        if clean_print:
            self.canvas.design_scene.clearSelection()
            self.canvas.label_item.setVisible(False)
        try:
            for index in range(quantity):
                if index and not printer.newPage():
                    raise RuntimeError("La impresora no pudo crear la siguiente etiqueta.")
                if text_item is not None:
                    text_item.setPlainText(str(start + index).zfill(number_width))
                self.canvas.design_scene.render(
                    painter,
                    target,
                    source,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
            completed = True
        except RuntimeError as error:
            QMessageBox.critical(self, "Impresión interrumpida", str(error))
        finally:
            painter.end()
            if clean_print:
                self.canvas.label_item.setVisible(label_was_visible)
                for item in selected_items:
                    if item.scene() is self.canvas.design_scene:
                        item.setSelected(True)
                self.canvas.viewport().update()
        if not completed:
            return
        self.statusBar().showMessage(
            f"Se enviaron {quantity} etiqueta(s) a {printer_info.printerName()}", 6000
        )
        if diagnostics.custom_size_requested and not diagnostics.custom_size_accepted:
            QMessageBox.information(
                self,
                "Tamaño controlado por la impresora",
                "El controlador no aceptó el tamaño personalizado. La etiqueta "
                "se envió sin deformación y en milímetros reales, pero también "
                "debes seleccionar el mismo ancho y largo en las preferencias de "
                "la impresora.",
            )

    def open_design(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir diseño", "", FILE_FILTER)
        if not path:
            return
        self.open_path(path)

    def open_path(self, path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            label = data["label"]
            width_mm, height_mm = label_size_mm(label)
            self.width_input.setValue(width_mm / 10)
            self.height_input.setValue(height_mm / 10)
            self.canvas.clear_design()
            self.apply_dimensions()
            warnings = []
            for element in data.get("elements", []):
                if element.get("type") == "text":
                    self.canvas.add_text(
                        element.get("value", ""),
                        float(element.get("x", 0.1)),
                        float(element.get("y", 0.1)),
                        float(element.get("scale", 1.0)),
                        bool(element.get("bold", False)),
                        bool(element.get("italic", False)),
                    )
                elif element.get("type") == "barcode":
                    self.canvas.add_barcode(
                        element.get("value", ""),
                        float(element.get("x", 0.1)),
                        float(element.get("y", 0.55)),
                        float(element.get("scale", 1.0)),
                    )
                elif element.get("type") == "image":
                    try:
                        self.canvas.add_image(
                            element["path"],
                            float(element.get("x", 0.1)),
                            float(element.get("y", 0.3)),
                            float(element.get("scale", 1.0)),
                        )
                    except (KeyError, ValueError):
                        warnings.append(element.get("path", "imagen desconocida"))
            self.current_file = path
            self.setWindowTitle(f"{APP_NAME} — {os.path.basename(path)}")
            message = f"Abierto: {path}"
            if warnings:
                message += f" — {len(warnings)} imagen(es) no disponibles"
            self.statusBar().showMessage(message)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            QMessageBox.critical(
                self,
                "No se pudo abrir",
                f"El archivo no es un diseño válido.\n\n{error}",
            )

    def save_design(self):
        if self.current_file:
            self.save_to(self.current_file)
        else:
            self.save_design_as()

    def save_design_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar diseño como", "", FILE_FILTER
        )
        if not path:
            return
        if not path.lower().endswith((".astolfo", ".json")):
            path += ".astolfo"
        self.save_to(path)

    def save_to(self, path):
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.document_data(), file, ensure_ascii=False, indent=2)
            self.current_file = path
            self.setWindowTitle(f"{APP_NAME} — {os.path.basename(path)}")
            self.statusBar().showMessage(f"Guardado: {path}")
        except OSError as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))


LIGHT_STYLESHEET = """
QMainWindow, #workspace {
    background: #eef1f5;
}
#toolbar {
    background: #202632;
}
#brand {
    color: white;
    font: 600 17px "Segoe UI";
}
#toolbarButton {
    color: #f7f8fa;
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 10px 14px;
    font-size: 13px;
}
#toolbarButton:hover {
    background: #343d4d;
}
QMenu {
    background: white;
    color: #252b36;
    border: 1px solid #d9dce2;
    padding: 5px;
}
QMenu::item {
    padding: 8px 28px 8px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #eeecff;
    color: #3026a8;
}
QMenu::separator {
    height: 1px;
    background: #e3e5e9;
    margin: 4px 7px;
}
#themeButton {
    color: #f7f8fa;
    background: #343d4d;
    border: 1px solid #4a5466;
    border-radius: 19px;
    font: 20px "Segoe UI Symbol";
}
#themeButton:hover {
    background: #465166;
}
#sidebar {
    background: white;
    border-radius: 7px;
}
#sidebarScroll, #sidebarScroll > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 3px 1px;
}
QScrollBar::handle:vertical {
    background: #b8bec8;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #929aa8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
#sectionTitle {
    color: #171b24;
    font: 600 16px "Segoe UI";
    margin-bottom: 3px;
}
#toolButton {
    background: white;
    color: #252b36;
    border: 1px solid #e0e2e8;
    border-radius: 5px;
    padding: 11px 12px;
    text-align: left;
}
#toolButton:hover {
    background: #f0efff;
    border-color: #cbc6ff;
}
#autoPasteControl {
    background: white;
    border: 1px solid #e0e2e8;
    border-radius: 5px;
    min-height: 34px;
}
#autoPasteControl:hover {
    background: #f0efff;
    border-color: #cbc6ff;
}
#autoPasteButton {
    background: transparent;
    color: #252b36;
    border: none;
    padding: 7px 0;
    text-align: left;
}
#autoPasteOn {
    color: #25a55f;
    font-size: 16px;
}
#autoPasteOff {
    color: #df4b4b;
    font-size: 16px;
}
#accentButton {
    background: #6d5dfc;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 11px;
    font: 600 13px "Segoe UI";
    margin-top: 7px;
}
#accentButton:hover {
    background: #5848e8;
}
#hint {
    color: #717784;
    font-size: 12px;
    margin-top: 5px;
}
#sizeDisplay {
    color: #555d6b;
    font-size: 12px;
}
#printerList {
    background: #fbfbfc;
    border: 1px solid #e0e2e8;
    border-radius: 5px;
    outline: none;
}
#printerList::item:selected {
    background: #eeecff;
}
#printerName {
    color: #171b24;
    font-size: 12px;
}
#printerConnected {
    color: #25a55f;
    font-size: 15px;
}
#printerDisconnected {
    color: #df4b4b;
    font-size: 15px;
}
#smallButton {
    background: transparent;
    color: #6d5dfc;
    border: 1px solid #cbc6ff;
    border-radius: 4px;
    padding: 4px 7px;
    font-size: 11px;
}
#smallButton:hover {
    background: #f0efff;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #d9dce2;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #6d5dfc;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    background: white;
    border: 2px solid #6d5dfc;
    border-radius: 8px;
}
QSlider:disabled {
    opacity: 0.45;
}
#dimensionLabel {
    color: #171b24;
    font: 600 13px "Segoe UI";
}
#separator {
    color: #e3e5e9;
}
QDoubleSpinBox, #printOption {
    background: #fbfbfc;
    color: #171b24;
    border: 1px solid #d9dce2;
    border-radius: 4px;
    padding: 6px 9px;
    selection-background-color: #6d5dfc;
    selection-color: white;
}
QDoubleSpinBox:focus {
    border-color: #6d5dfc;
}
#printOption {
    min-height: 22px;
    font-size: 11px;
}
#printOption::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    color: #252b36;
    background: #ffffff;
    border: 1px solid #cfd3da;
    outline: none;
    selection-color: #3026a8;
    selection-background-color: #eeecff;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 3px 8px;
}
#canvasPanel {
    background: #dfe3e9;
    border-radius: 7px;
}
#canvasHeader {
    background: #f8f9fb;
}
#canvasTitle {
    color: #555d6b;
    font: 600 12px "Segoe UI";
}
#dimensionDisplay {
    color: #6d5dfc;
    font: 600 14px "Segoe UI";
}
QStatusBar {
    background: white;
    color: #626a78;
}
QInputDialog, QMessageBox {
    background: #ffffff;
    color: #252b36;
}
QInputDialog QLabel, QMessageBox QLabel {
    color: #252b36;
    background: transparent;
}
QInputDialog QPushButton, QMessageBox QPushButton {
    min-width: 72px;
    padding: 6px 12px;
    color: #252b36;
    background: #f4f5f7;
    border: 1px solid #cfd3da;
    border-radius: 4px;
}
QInputDialog QPushButton:hover, QMessageBox QPushButton:hover {
    color: white;
    background: #6d5dfc;
    border-color: #6d5dfc;
}
#githubButton {
    color: #181717;
    background: #ffffff;
    border: 1px solid #cfd3da;
    font-weight: 600;
}
#githubButton:hover {
    color: #181717;
    background: #f0efff;
    border-color: #8c82ff;
}
#advancedPrintDialog {
    background: #ffffff;
    color: #252b36;
}
#advancedPrintDialog QLabel {
    color: #252b36;
    background: transparent;
}
#advancedPrintDialog #hint {
    color: #717784;
}
#dialogTitle {
    color: #171b24;
    font: 600 16px "Segoe UI";
}
"""

DARK_OVERRIDES = """
QMainWindow, #workspace {
    background: #11151c;
    color: #e8eaf0;
}
#toolbar {
    background: #0c1016;
    border-bottom: 1px solid #29303c;
}
#sidebar {
    background: #1b202a;
}
QScrollBar::handle:vertical {
    background: #4d5665;
}
QScrollBar::handle:vertical:hover {
    background: #687386;
}
#sectionTitle, #dimensionLabel {
    color: #f1f3f7;
}
#toolButton {
    background: #222833;
    color: #edf0f5;
    border-color: #343c49;
}
#toolButton:hover {
    background: #302d4c;
    border-color: #6d5dfc;
}
#autoPasteControl {
    background: #222833;
    border-color: #343c49;
}
#autoPasteControl:hover {
    background: #302d4c;
    border-color: #6d5dfc;
}
#autoPasteButton {
    color: #edf0f5;
}
#hint, #sizeDisplay {
    color: #a7adba;
}
#separator {
    color: #343b47;
}
QDoubleSpinBox, #printOption {
    background: #151a22;
    color: #f1f3f7;
    border-color: #3a424f;
}
QComboBox QAbstractItemView {
    color: #edf0f5;
    background: #151a22;
    border-color: #4a5466;
    selection-color: #ffffff;
    selection-background-color: #443a8a;
}
#canvasPanel {
    background: #171b24;
}
#canvasHeader {
    background: #202630;
}
#canvasTitle {
    color: #b4bac6;
}
#printerList {
    background: #151a22;
    border-color: #343c49;
}
#printerList::item:selected {
    background: #302d4c;
}
#printerName {
    color: #edf0f5;
}
#smallButton {
    background: #222833;
}
QSlider::groove:horizontal {
    background: #3a424f;
}
QStatusBar {
    background: #0f1319;
    color: #b4bac6;
    border-top: 1px solid #29303c;
}
QInputDialog, QMessageBox {
    background: #1b202a;
    color: #edf0f5;
}
QMenu {
    background: #1b202a;
    color: #edf0f5;
    border-color: #3a424f;
}
QMenu::item:selected {
    background: #302d4c;
    color: white;
}
QMenu::separator {
    background: #3a424f;
}
QInputDialog QLabel, QMessageBox QLabel {
    color: #edf0f5;
    background: transparent;
}
QInputDialog QPushButton, QMessageBox QPushButton {
    color: #edf0f5;
    background: #222833;
    border-color: #4a5466;
}
QInputDialog QPushButton:hover, QMessageBox QPushButton:hover {
    color: white;
    background: #6d5dfc;
    border-color: #6d5dfc;
}
#githubButton {
    color: #181717;
    background: #ffffff;
    border-color: #697386;
}
#githubButton:hover {
    color: #181717;
    background: #eeecff;
    border-color: #8c82ff;
}
#advancedPrintDialog {
    background: #1b202a;
    color: #edf0f5;
}
#advancedPrintDialog QLabel, #advancedPrintDialog #dialogTitle {
    color: #edf0f5;
}
#advancedPrintDialog #hint {
    color: #a7adba;
}
QInputDialog QLineEdit {
    background: #151a22;
    color: #f1f3f7;
    border: 1px solid #3a424f;
    padding: 6px;
}
"""


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "AstolfoDesign.LabelDesigner.1"
            )
        except (AttributeError, OSError):
            pass
    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setWindowIcon(QIcon(resource_path("Logo.ico")))
    application.setStyle("Fusion")
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        requested_file = os.path.abspath(sys.argv[1])
        if os.path.isfile(requested_file):
            window.open_path(requested_file)
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
