"""
main_window.py
Main window: two clean toolbar rows (tools/actions on top, style & options
below), a large drawing canvas, a live graphical preview panel, the generated
TikZ code panel, and File actions. Dark violet/turquoise theme applied at
startup.

v4:
- True HiDPI/Retina rendering (crisp canvas on high-density screens).
- Pen-pressure toggle (variable stroke width from the tablet).
- SVG export (true vector) + PNG export with selectable resolution (2x-8x).
- Toolbar reorganized into two rows: less cramped, faster to scan.
"""
import sys
import os
import copy

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QKeySequence, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QAction, QActionGroup, QColorDialog,
    QSpinBox, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QPlainTextEdit, QFileDialog, QMessageBox, QPushButton, QDoubleSpinBox,
    QCheckBox, QComboBox, QToolButton, QInputDialog, QSlider, QButtonGroup, QFrame
)

from canvas import DrawingCanvas, TOOLS
from preview_widget import PreviewWidget
from tikz_export import shapes_to_tikz_body, shapes_to_standalone_tex
from shapes import save_project, load_project, Line, Arrow
from presets import PRESET_NAMES, PRESET_LABELS, PRESET_DESCRIPTIONS
import image_trace
from PyQt5.QtGui import QImage

TOOL_LABELS = {
    "pen": "Pen (freehand)",
    "line": "Line",
    "arrow": "Arrow",
    "ellipse": "Ellipse / Circle",
    "polygon": "Polygon",
    "bezier": "Pen tool (Bezier)",
    "text": "Text / LaTeX",
    "eraser": "Eraser",
    "select": "Select / Move",
}

QUICK_PALETTE = [
    "#000000", "#ffffff", "#e53935", "#1e88e5", "#43a047",
    "#fdd835", "#fb8c00", "#8e24aa", "#00acc1", "#6d4c41",
]

# ---------------------------------------------------------------- theme
ACCENT = "#7c5cff"
ACCENT2 = "#25d0c9"
BG = "#151722"
BG_PANEL = "#1e2135"
BG_ELEV = "#282c47"
BORDER = "#363b5e"
TEXT = "#eef0ff"
TEXT_DIM = "#9ea3c9"

APP_STYLESHEET = f"""
QMainWindow {{
    background-color: {BG};
}}
QWidget {{
    color: {TEXT};
    background-color: transparent;
    font-size: 11.5px;
}}
QToolBar {{
    background-color: {BG_PANEL};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 2px 8px;
}}
QToolBar QLabel {{
    color: {TEXT_DIM};
    padding-top: 2px;
}}
QToolButton, QPushButton {{
    background-color: {BG_ELEV};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 3px 8px;
}}
QToolButton:hover, QPushButton:hover {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: white;
}}
QToolButton:pressed, QPushButton:pressed {{
    background-color: #6247d9;
}}
QToolButton:checked {{
    background-color: {ACCENT2};
    border-color: {ACCENT2};
    color: #072320;
    font-weight: 600;
}}
QComboBox, QDoubleSpinBox, QSpinBox {{
    background-color: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px 6px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background-color: {BG_ELEV};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}
QCheckBox {{
    padding: 2px 0;
}}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border-radius: 3px;
    border: 1px solid {BORDER};
    background: {BG_ELEV};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT2};
    border-color: {ACCENT2};
}}
QPlainTextEdit {{
    background-color: {BG_PANEL};
    color: #d7f7d2;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
}}
QSplitter::handle {{
    background-color: {BG};
}}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical {{ height: 4px; }}
QStatusBar {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QMessageBox, QFileDialog, QColorDialog, QInputDialog {{
    background-color: {BG_PANEL};
}}
QScrollBar:vertical {{
    background: {BG_PANEL}; width: 10px; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {BG_ELEV}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

PNG_SCALES = ["2x", "3x", "4x", "6x", "8x"]


class MainWindow(QMainWindow):
    # Keeps strong references to windows opened via "Duplicate to new
    # window" so Python doesn't garbage-collect (and silently close) them
    # the moment this method returns.
    _open_windows: list = []

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VanovaTikZSketch — hand-drawn geometry to LaTeX/TikZ")
        self.resize(1900, 980)
        # Everything is consolidated into exactly 3 compact toolbar rows:
        # (1) Tools, (2) Design -- shape actions + style/options + presets,
        # (3) Navigation + Arrange. Buttons keep their tight padding so the
        # whole toolbar stack stays short and most of the window is left for
        # the actual drawing canvas. The window needs to stay reasonably
        # wide so row 2 (the busiest one) never wraps or hides a button.
        self.setMinimumSize(1650, 640)

        self.canvas = DrawingCanvas()
        self.canvas.shapes_changed.connect(self.refresh_all)
        self.canvas.status_message.connect(self.statusBar().showMessage)
        self.canvas.selection_changed.connect(self.on_selection_changed)
        self.canvas.view_changed.connect(self.on_view_changed)

        self.preview = PreviewWidget()

        self.tikz_view = QPlainTextEdit()
        self.tikz_view.setReadOnly(True)
        self.tikz_view.setStyleSheet(
            f"font-family: Menlo, monospace; font-size: 12px; background-color: {BG_PANEL}; color: #d7f7d2;"
        )
        self.tikz_view.setPlaceholderText("The generated TikZ code will appear here live...")

        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)

        preview_title = QLabel("Live preview")
        preview_title.setStyleSheet(f"color: {ACCENT2}; font-weight: 600; font-size: 13px; padding: 4px 0;")
        side_layout.addWidget(preview_title)
        side_layout.addWidget(self.preview, stretch=3)

        code_title = QLabel("TikZ code (updated live)")
        code_title.setStyleSheet(f"color: {ACCENT2}; font-weight: 600; font-size: 13px; padding: 4px 0;")
        side_layout.addWidget(code_title)
        side_layout.addWidget(self.tikz_view, stretch=2)

        btn_row = QHBoxLayout()
        self.btn_copy = QPushButton("Copy code")
        self.btn_copy.clicked.connect(self.copy_tikz)
        self.btn_export_tex = QPushButton("Export .tex")
        self.btn_export_tex.setToolTip("Standalone .tex, compilable with pdflatex.")
        self.btn_export_tex.clicked.connect(self.export_tex)
        self.btn_export_svg = QPushButton("Export SVG")
        self.btn_export_svg.setToolTip(
            "True vector export: infinite resolution, editable in "
            "Inkscape/Illustrator/Figma."
        )
        self.btn_export_svg.clicked.connect(self.export_svg)
        self.btn_export_png = QPushButton("Export PNG...")
        self.btn_export_png.setToolTip(
            "High-resolution raster export (choose 2x to 8x scale): white "
            "background, no grid/selection -- ready for an article or slide."
        )
        self.btn_export_png.clicked.connect(self.export_png)
        btn_row.addWidget(self.btn_copy)
        btn_row.addWidget(self.btn_export_tex)
        btn_row.addWidget(self.btn_export_svg)
        btn_row.addWidget(self.btn_export_png)
        side_layout.addLayout(btn_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.canvas)
        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self._build_toolbars()
        self.statusBar().showMessage(
            "Ready. Auto-finish is on: draw normally, strokes are cleaned up automatically."
        )
        self.current_file = None

    # ---------------------------------------------------------------- UI
    def _build_toolbars(self):
        # ---- row 1: tools + actions ------------------------------------
        tb = QToolBar("Tools")
        tb.setMovable(False)
        tb.setOrientation(Qt.Horizontal)
        self.addToolBar(Qt.TopToolBarArea, tb)

        group = QActionGroup(self)
        group.setExclusive(True)
        self.tool_actions = {}
        for tool in TOOLS:
            act = QAction(TOOL_LABELS[tool], self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, t=tool: self.canvas.set_tool(t))
            group.addAction(act)
            tb.addAction(act)
            self.tool_actions[tool] = act
        self.tool_actions["pen"].setChecked(True)

        tb.addSeparator()

        act_undo = QAction("↶ Undo", self)
        act_undo.setToolTip("Undo (Ctrl+Z)")
        act_undo.setShortcut(QKeySequence.Undo)
        act_undo.triggered.connect(self.canvas.undo)
        tb.addAction(act_undo)

        act_redo = QAction("↷ Redo", self)
        act_redo.setToolTip("Redo (Ctrl+Shift+Z)")
        act_redo.setShortcut(QKeySequence.Redo)
        act_redo.triggered.connect(self.canvas.redo)
        tb.addAction(act_redo)

        act_delete = QAction("Delete", self)
        act_delete.setToolTip("Delete selected shape (Del)")
        act_delete.triggered.connect(self.canvas.delete_selected)
        tb.addAction(act_delete)

        # File operations moved here (row 1 has spare width, so nothing on
        # row 2 -- the busiest row -- ever ends up hidden behind an overflow
        # arrow; every button stays always visible).
        tb.addSeparator()

        act_new = QAction("New", self)
        act_new.triggered.connect(self.new_project)
        tb.addAction(act_new)

        act_new_window = QAction("❐ New window", self)
        act_new_window.setToolTip(
            "Open a second, independent, blank window (does not copy the "
            "current design -- for that, use 'Duplicate to new window' in "
            "the Arrange row)."
        )
        act_new_window.setShortcut("Ctrl+Shift+N")
        act_new_window.triggered.connect(self.open_new_window)
        tb.addAction(act_new_window)

        act_open = QAction("Open...", self)
        act_open.triggered.connect(self.open_project)
        tb.addAction(act_open)

        act_save = QAction("Save...", self)
        act_save.triggered.connect(self.save_project)
        tb.addAction(act_save)

        act_help = QAction("Help", self)
        act_help.triggered.connect(self.show_help)
        tb.addAction(act_help)

        # ---- row 1b: shape actions (its own row, so nothing ever ends up
        # hidden behind an overflow arrow -- every button always visible) --
        self.addToolBarBreak(Qt.TopToolBarArea)
        tb_shape = QToolBar("Shape actions")
        tb_shape.setMovable(False)
        tb_shape.setOrientation(Qt.Horizontal)
        self.addToolBar(Qt.TopToolBarArea, tb_shape)

        # No more "Idealize" / "★ Machine finish" buttons to click -- the
        # cleanup they used to do by hand is now simply always-on as you
        # draw (see canvas.py: every stroke is corrected automatically,
        # nothing to ask for). Kept as canvas.idealize_selected() /
        # canvas.machine_finish_all() methods internally in case a future
        # shortcut wants them, just not exposed as toolbar buttons anymore.

        act_label = QAction("Name (L)", self)
        act_label.setToolTip(
            "Select a shape (Select tool), then press this (or the L key) "
            "to type a name/label directly onto it."
        )
        act_label.triggered.connect(self.canvas.label_selected)
        tb_shape.addAction(act_label)

        act_clear = QAction("Clear all", self)
        act_clear.triggered.connect(self.confirm_clear)
        tb_shape.addAction(act_clear)

        tb_shape.addSeparator()

        act_import = QAction("Import photo...", self)
        act_import.setToolTip(
            "Open a photo from your computer. You can then EXTRACT its design "
            "as editable vector shapes (select, move, erase, recolor, machine-"
            "finish them), and/or keep the photo as a faded tracing layer."
        )
        act_import.triggered.connect(self.import_photo_file)
        tb_shape.addAction(act_import)

        act_import_url = QAction("Photo URL...", self)
        act_import_url.setToolTip(
            "Paste the address of an image on the web (https://...); it is "
            "downloaded and treated exactly like an imported photo."
        )
        act_import_url.triggered.connect(self.import_photo_url)
        tb_shape.addAction(act_import_url)

        # ---- row 2: everything else about a shape's look (style, options,
        # presets) shares the SAME row as "Shape actions" above -- only 3
        # toolbar rows total in the whole window, as compact as possible ---
        tb2 = tb_shape

        act_color = QAction("Stroke color...", self)
        act_color.triggered.connect(self.pick_color)
        tb2.addAction(act_color)

        tb2.addWidget(QLabel(" Width:"))
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(2.5)
        self.width_spin.valueChanged.connect(self.canvas.set_width)
        tb2.addWidget(self.width_spin)

        tb2.addWidget(QLabel(" Eraser:"))
        self.eraser_spin = QDoubleSpinBox()
        self.eraser_spin.setRange(4.0, 80.0)
        self.eraser_spin.setSingleStep(2.0)
        self.eraser_spin.setValue(16.0)
        self.eraser_spin.valueChanged.connect(self.canvas.set_eraser_radius)
        tb2.addWidget(self.eraser_spin)

        tb2.addSeparator()

        self.fill_check = QCheckBox("Fill closed shapes")
        self.fill_check.toggled.connect(self.canvas.set_fill_enabled)
        tb2.addWidget(self.fill_check)

        act_fill_color = QAction("Fill color...", self)
        act_fill_color.triggered.connect(self.pick_fill_color)
        tb2.addAction(act_fill_color)

        palette_widget = QWidget()
        palette_layout = QGridLayout(palette_widget)
        palette_layout.setSpacing(3)
        palette_layout.setContentsMargins(4, 4, 4, 4)
        for i, hexcolor in enumerate(QUICK_PALETTE):
            btn = QToolButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(
                f"background-color: {hexcolor}; border: 2px solid {BORDER}; border-radius: 5px;"
            )
            btn.setToolTip(f"{hexcolor}  (click = stroke, Alt+click = fill)")
            btn.clicked.connect(lambda checked, c=hexcolor: self._quick_color(c))
            palette_layout.addWidget(btn, i // 10, i % 10)
        tb2.addWidget(palette_widget)

        tb2.addSeparator()

        self.pressure_check = QCheckBox("Pen pressure")
        self.pressure_check.setToolTip(
            "Variable stroke width from the stylus pressure (graphics tablet). "
            "The pressure profile is kept in the project file and exported to "
            "TikZ and SVG. Uncheck for a constant, machine-uniform width."
        )
        self.pressure_check.setChecked(True)
        self.pressure_check.toggled.connect(self.canvas.set_pressure_enabled)
        tb2.addWidget(self.pressure_check)

        self.vectorize_check = QCheckBox("Auto-finish")
        self.vectorize_check.setToolTip(
            "Automatically corrects freehand strokes: a nearly-straight line "
            "becomes perfectly straight, a round shape becomes an exact "
            "circle, any closed outline is cleaned up and smoothed."
        )
        self.vectorize_check.setChecked(True)
        self.vectorize_check.toggled.connect(self.canvas.set_auto_vectorize)
        tb2.addWidget(self.vectorize_check)

        # "Smooth finish" is no longer a checkbox to remember to turn on --
        # it is now simply always active (canvas.py: self.smooth_finish is
        # permanently True), so every curve is re-fit with a clean tolerance
        # automatically, with nothing to ask for.

        self.grid_check = QCheckBox("Snap to grid")
        self.grid_check.toggled.connect(self.canvas.set_snap_to_grid)
        tb2.addWidget(self.grid_check)

        tb2.addSeparator()

        self.show_bg_check = QCheckBox("Show photo")
        self.show_bg_check.setToolTip("Show/hide the imported tracing photo (it is never exported).")
        self.show_bg_check.setChecked(True)
        self.show_bg_check.toggled.connect(self.canvas.set_show_background)
        tb2.addWidget(self.show_bg_check)

        act_clear_bg = QAction("Remove photo", self)
        act_clear_bg.setToolTip("Remove the imported tracing photo from the canvas.")
        act_clear_bg.triggered.connect(self.canvas.clear_background)
        tb2.addAction(act_clear_bg)

        tb2.addSeparator()

        tb2.addWidget(QLabel(" Presets:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("None", None)  # default: nothing pre-selected
        self.preset_combo.setItemData(0, "No preset selected.", Qt.ToolTipRole)
        for name in PRESET_NAMES:
            self.preset_combo.addItem(PRESET_LABELS[name], name)
            idx = self.preset_combo.count() - 1
            self.preset_combo.setItemData(idx, PRESET_DESCRIPTIONS.get(name, ""), Qt.ToolTipRole)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.setToolTip(
            "Survole un preset dans la liste pour voir sa definition "
            "mathematique et son usage typique (aussi dans PRESETS_REFERENCE.md)."
        )
        tb2.addWidget(self.preset_combo)
        btn_insert_preset = QPushButton("Insert preset")
        btn_insert_preset.clicked.connect(self.insert_selected_preset)
        tb2.addWidget(btn_insert_preset)

        # ---- row 3: navigation (pan/zoom) + arrange, sharing ONE row so
        # the whole app fits in exactly 3 toolbar rows ---------------------
        self.addToolBarBreak(Qt.TopToolBarArea)
        tb3 = QToolBar("Navigation")
        tb3.setMovable(False)
        tb3.setOrientation(Qt.Horizontal)
        self.addToolBar(Qt.TopToolBarArea, tb3)

        tb3.addWidget(QLabel(" View:"))
        act_zoom_out = QAction("−", self)
        act_zoom_out.setToolTip("Zoom out (also: mouse wheel, or the - key)")
        act_zoom_out.triggered.connect(self.canvas.zoom_out)
        tb3.addAction(act_zoom_out)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(48)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet(f"color: {TEXT}; font-weight: 600;")
        tb3.addWidget(self.zoom_label)

        act_zoom_in = QAction("+", self)
        act_zoom_in.setToolTip("Zoom in (also: mouse wheel, or the + key)")
        act_zoom_in.triggered.connect(self.canvas.zoom_in)
        tb3.addAction(act_zoom_in)

        act_zoom_reset = QAction("100%", self)
        act_zoom_reset.setToolTip("Reset zoom to 100% (also: the 0 key)")
        act_zoom_reset.triggered.connect(self.canvas.reset_zoom)
        tb3.addAction(act_zoom_reset)

        act_fit = QAction("Fit to drawing", self)
        act_fit.setToolTip("Frame the whole drawing in the visible canvas.")
        act_fit.triggered.connect(self.canvas.fit_to_drawing)
        tb3.addAction(act_fit)

        act_fit.setToolTip(act_fit.toolTip() + "  (Scroll to zoom, hold Space/middle-click and drag to pan.)")

        tb3.addSeparator()

        # Arrange (copy/paste/duplicate, z-order, flip/rotate, duplicate to
        # new window) shares this SAME row -- only 3 toolbar rows total.
        tb4 = tb3

        tb4.addWidget(QLabel(" Shape:"))
        act_copy = QAction("Copy", self)
        act_copy.setToolTip("Copy the selected shape (Ctrl/Cmd+C).")
        act_copy.triggered.connect(self.canvas.copy_selected)
        tb4.addAction(act_copy)

        act_paste = QAction("Paste", self)
        act_paste.setToolTip("Paste the copied shape, slightly offset (Ctrl/Cmd+V).")
        act_paste.triggered.connect(self.canvas.paste_shape)
        tb4.addAction(act_paste)

        act_duplicate = QAction("Duplicate", self)
        act_duplicate.setToolTip("Copy + paste in one step (Ctrl/Cmd+D).")
        act_duplicate.triggered.connect(self.canvas.duplicate_selected)
        tb4.addAction(act_duplicate)

        tb4.addSeparator()
        tb4.addWidget(QLabel(" Order:"))
        act_front = QAction("Bring to front", self)
        act_front.triggered.connect(self.canvas.bring_to_front)
        tb4.addAction(act_front)

        act_forward = QAction("Forward", self)
        act_forward.triggered.connect(self.canvas.bring_forward)
        tb4.addAction(act_forward)

        act_backward = QAction("Backward", self)
        act_backward.triggered.connect(self.canvas.send_backward)
        tb4.addAction(act_backward)

        act_back = QAction("Send to back", self)
        act_back.triggered.connect(self.canvas.send_to_back)
        tb4.addAction(act_back)

        tb4.addSeparator()
        tb4.addWidget(QLabel(" Transform:"))
        act_flip_h = QAction("Flip H", self)
        act_flip_h.setToolTip("Mirror the selected shape left-right.")
        act_flip_h.triggered.connect(self.canvas.flip_selected_horizontal)
        tb4.addAction(act_flip_h)

        act_flip_v = QAction("Flip V", self)
        act_flip_v.setToolTip("Mirror the selected shape top-bottom.")
        act_flip_v.triggered.connect(self.canvas.flip_selected_vertical)
        tb4.addAction(act_flip_v)

        act_rotate = QAction("Rotate 90°", self)
        act_rotate.setToolTip("Rotate the selected shape 90° clockwise around its own center.")
        act_rotate.triggered.connect(self.canvas.rotate_selected_90)
        tb4.addAction(act_rotate)

        tb4.addSeparator()
        act_dup_window = QAction("⧉ Duplicate to new window", self)
        act_dup_window.setToolTip(
            "Open a new window with a copy of the WHOLE current design, so "
            "you can work on a variant of the same design side by side -- "
            "the two windows are independent from that point on."
        )
        act_dup_window.triggered.connect(self.duplicate_to_new_window)
        tb4.addAction(act_dup_window)

        # ---- Quiver-style floating "Edge" panel: shown over the canvas
        # whenever a Line/Arrow is selected, for fast curve/style editing
        # without reopening dialogs.
        self._build_edge_panel()

    def _build_edge_panel(self):
        panel = QFrame(self.canvas)
        panel.setObjectName("edgePanel")
        panel.setStyleSheet(
            f"QFrame#edgePanel {{ background-color: {BG_PANEL}; "
            f"border: 1px solid {BORDER}; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self.edge_panel_title = QLabel("Style")
        self.edge_panel_title.setStyleSheet(f"color: {ACCENT2}; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.edge_panel_title)

        # Curve/Reverse/Double: Line/Arrow only ("edge" controls)
        self.btn_reverse_edge = QPushButton("⇌ Reverse")
        self.btn_reverse_edge.setToolTip("Swap the two endpoints (flips the arrow head side).")
        self.btn_reverse_edge.clicked.connect(self.canvas.reverse_selected_edge)
        layout.addWidget(self.btn_reverse_edge)

        self.curve_row_widget = QWidget()
        curve_row = QHBoxLayout(self.curve_row_widget)
        curve_row.setContentsMargins(0, 0, 0, 0)
        curve_row.addWidget(QLabel("Curve"))
        self.curve_slider = QSlider(Qt.Horizontal)
        self.curve_slider.setRange(-100, 100)
        self.curve_slider.setValue(0)
        self.curve_slider.setFixedWidth(130)
        self.curve_slider.setToolTip("Bend the edge into an arc, like Quiver's Curve control.")
        self.curve_slider.valueChanged.connect(lambda v: self.canvas.set_selected_bend(v / 100.0))
        curve_row.addWidget(self.curve_slider)
        layout.addWidget(self.curve_row_widget)

        # Style (solid/dashed/dotted): works on ANY selected shape. Dashed/
        # dotted is always rendered/exported as one continuous, constant-
        # width path -- perfectly even dash size and spacing automatically,
        # e.g. for a hand-drawn hidden 'waist' curve on a torus.
        style_row = QHBoxLayout()
        self._edge_style_buttons = {}
        style_group = QButtonGroup(panel)
        style_group.setExclusive(True)
        for key, label, tip in (("solid", "―", "Solid"), ("dashed", "╌", "Dashed — evenly spaced automatically"),
                                ("dotted", "⋯", "Dotted — evenly spaced automatically")):
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda checked, k=key: checked and self.canvas.set_selected_line_style(k))
            style_group.addButton(b)
            self._edge_style_buttons[key] = b
            style_row.addWidget(b)
        layout.addLayout(style_row)

        self.double_line_check = QCheckBox("Double line")
        self.double_line_check.setToolTip("Two parallel strokes (e.g. for a monomorphism/faithful arrow).")
        self.double_line_check.toggled.connect(self.canvas.set_selected_double)
        layout.addWidget(self.double_line_check)

        # Arrowhead style (Quiver-style picker): Arrow only.
        self.head_row_widget = QWidget()
        head_row = QHBoxLayout(self.head_row_widget)
        head_row.setContentsMargins(0, 0, 0, 0)
        head_row.addWidget(QLabel("Head"))
        self._head_style_buttons = {}
        head_group = QButtonGroup(panel)
        head_group.setExclusive(True)
        for key, label, tip in (
            ("stealth", "➤", "Stealth (filled) -- the default"),
            ("classical", "→", "Classical (plain open V, no arrows.meta needed)"),
            ("harpoon", "⇀", "Harpoon (single one-sided barb)"),
            ("none", "―", "None (reads as a plain line)"),
        ):
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda checked, k=key: checked and self.canvas.set_selected_head_style(k))
            head_group.addButton(b)
            self._head_style_buttons[key] = b
            head_row.addWidget(b)
        layout.addWidget(self.head_row_widget)

        panel.adjustSize()
        panel.hide()
        self.edge_panel = panel
        self.canvas.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.canvas and event.type() == event.Resize:
            self._position_edge_panel()
        return super().eventFilter(obj, event)

    def _position_edge_panel(self):
        w = self.edge_panel.width()
        self.edge_panel.move(max(self.canvas.width() - w - 14, 0), 14)

    def on_selection_changed(self, shape):
        is_edge = isinstance(shape, Line)  # Arrow is-a Line
        is_arrow = isinstance(shape, Arrow)
        is_styleable = shape is not None and hasattr(shape, "line_style")
        if is_styleable:
            self.edge_panel_title.setText("Edge" if is_edge else "Style")
            self.btn_reverse_edge.setVisible(is_edge)
            self.curve_row_widget.setVisible(is_edge)
            self.double_line_check.setVisible(is_edge)
            self.head_row_widget.setVisible(is_arrow)
            if is_edge:
                self.curve_slider.blockSignals(True)
                self.curve_slider.setValue(int(round(shape.bend * 100)))
                self.curve_slider.blockSignals(False)
                self.double_line_check.blockSignals(True)
                self.double_line_check.setChecked(shape.double)
                self.double_line_check.blockSignals(False)
            if is_arrow:
                head_btn = self._head_style_buttons.get(getattr(shape, "head_style", "stealth"))
                if head_btn is not None:
                    head_btn.setChecked(True)
            btn = self._edge_style_buttons.get(shape.line_style)
            if btn is not None:
                btn.setChecked(True)
            self.edge_panel.adjustSize()
            self._position_edge_panel()
            self.edge_panel.show()
            self.edge_panel.raise_()
        else:
            self.edge_panel.hide()

    def on_view_changed(self, scale):
        self.zoom_label.setText(f"{int(round(scale * 100))}%")

    # ------------------------------------------------------------ actions
    def show_help(self):
        QMessageBox.information(
            self, "Tips",
            "- Pen tool: click = anchor point, drag = handles.\n"
            "  Enter = finish path, Esc = cancel.\n"
            "- Polygon: click each vertex, double-click to close.\n"
            "- Select: click a shape then drag to move it, Del to delete it.\n"
            "- Eraser: click-drag over part of a shape to erase just that "
            "part (the rest is kept as separate shapes).\n"
            "- Pen pressure (on by default): with a graphics tablet, the "
            "stroke width follows the stylus pressure -- kept in the project "
            "file and in the TikZ/SVG export. Uncheck for a constant width.\n"
            "- Auto-finish (on by default): draw normally, the stroke is "
            "cleaned up and symmetrized on its own.\n"
            "- Navigation (Quiver-style, fast/fluid): mouse wheel to zoom "
            "in/out under the cursor, hold Space (or middle-click) and drag "
            "to pan. Toolbar row 3 (Navigation + Arrange) has Zoom -/+, "
            "100%, and 'Fit to drawing'. Keyboard: +/- to zoom, 0 to reset.\n"
            "- Arrange (same toolbar row 3): Copy/Paste/Duplicate a selected "
            "shape (Ctrl/Cmd+C, +V, +D), reorder it with Bring to front/"
            "Forward/Backward/Send to back, or Flip H/Flip V/Rotate 90°.\n"
            "- '⧉ Duplicate to new window' opens a second, independent "
            "window preloaded with a copy of the WHOLE current design -- "
            "handy for trying a variant of the same figure side by side "
            "without touching the original.\n"
            "- Perfectly even dashes/dots: select ANY shape (even a "
            "hand-drawn curve) and use the Style buttons (Solid/Dashed/"
            "Dotted) in the floating panel. A dashed/dotted stroke is "
            "always drawn as one continuous path at constant width, so the "
            "tick marks come out evenly sized and spaced automatically -- "
            "both on screen and in the exported TikZ -- even if your hand "
            "wasn't perfectly steady.\n"
            "- Select a Line/Arrow: the floating panel also gains 'Edge' "
            "controls -- drag the Curve slider to bend it into an arc, "
            "click Reverse to flip direction, or check Double line (e.g. "
            "for a monomorphism). Changes apply live, exactly like Quiver's "
            "arrow controls, and export as real curved / double TikZ paths.\n"
            "- Labels are keyboard-typed, Quiver-diagram style -- never "
            "hand-drawn: use the Text/LaTeX tool (click on the canvas) or "
            "select an object and press L. Type real LaTeX, e.g. \\varphi, "
            "\\Sigma_g, f_1, x^2, \\to, \\circ -- it's shown as the actual "
            "symbol on the canvas and exported as real, compilable LaTeX. "
            "Labeling a Line/Arrow (a morphism) centers the label just "
            "above its midpoint, like an arrow label in a commutative "
            "diagram.\n"
            "- Cleanup is fully automatic now: jitter removal and curve "
            "smoothing happen on every stroke as you draw, nothing to click "
            "for it. (Auto-finish still recognizes clean circles/lines/"
            "polygons; uncheck it if you want raw freehand strokes kept "
            "as-is.)\n"
            "- Export SVG: true vector file (infinite resolution), editable "
            "in Inkscape/Illustrator.\n"
            "- Export PNG...: choose the resolution factor (2x to 8x).\n"
            "- Name (L): select a shape, then press L to type a name/label "
            "directly onto it.\n"
            "- Arrows export as TikZ '-{Stealth}' heads: the standalone "
            ".tex already includes \\usetikzlibrary{arrows.meta}; add that "
            "line to your own preamble when pasting the body code.\n"
        )

    # ------------------------------------------------------- photo import
    def import_photo_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import photo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.tif *.tiff)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            self.statusBar().showMessage("Could not read this image file.", 5000)
            return
        self._handle_imported_photo(img)

    def import_photo_url(self):
        url, ok = QInputDialog.getText(
            self, "Photo from the web", "Image URL (https://...):")
        if not (ok and url.strip()):
            return
        self.statusBar().showMessage("Downloading photo...", 3000)
        QApplication.processEvents()
        try:
            img = image_trace.load_qimage_from_url(url.strip())
        except Exception as exc:
            img = None
            self.statusBar().showMessage(f"Download failed: {exc}", 6000)
        if img is None:
            self.statusBar().showMessage(
                "Download failed (check the URL points to an actual image).", 6000)
            return
        self._handle_imported_photo(img)

    def _handle_imported_photo(self, img: QImage):
        box = QMessageBox(self)
        box.setWindowTitle("Imported photo")
        box.setText("What do you want to do with this photo?")
        b_extract = box.addButton("Extract the design (editable shapes)", QMessageBox.AcceptRole)
        b_bg = box.addButton("Trace over it (faded layer)", QMessageBox.ActionRole)
        b_both = box.addButton("Both", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.exec_()
        clicked = box.clickedButton()
        if clicked not in (b_extract, b_bg, b_both):
            return
        if clicked in (b_bg, b_both):
            self.canvas.set_background_image(img)
            self.show_bg_check.setChecked(True)
        if clicked in (b_extract, b_both):
            self.statusBar().showMessage("Extracting the design from the photo...", 3000)
            QApplication.processEvents()
            c = self.canvas
            margin = 60
            target = (margin, margin, max(c.width() - 2 * margin, 100),
                      max(c.height() - 2 * margin, 100))
            try:
                # v4.16: extraction now ignores source colors/shading/fill
                # entirely and only traces the pure black-line skeleton of
                # the drawing -- a "blank" outline made of plain editable
                # shapes, with none of the color-sampling / hatch-fill logic
                # that used to misfire on shaded regions. The user re-adds
                # colors, fills, and labels by hand afterward exactly like
                # any other shape on the canvas.
                traced = image_trace.trace_qimage(img, target, color=c.color,
                                                  width=c.stroke_width,
                                                  use_source_colors=False)
            except Exception as exc:
                self.statusBar().showMessage(f"Design extraction failed: {exc}", 6000)
                return
            n = c.insert_traced_shapes(traced)
            if n:
                self.statusBar().showMessage(
                    f"Design extracted: {n} blank editable shape(s) added (outline "
                    "only, no colors/fills). Use Select to move/edit them, then "
                    "add color or labels yourself.", 7000)
            else:
                self.statusBar().showMessage(
                    "No clear design found in this photo (try a higher-contrast "
                    "image, or use it as a tracing layer instead).", 7000)

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.canvas.color))
        if color.isValid():
            self.canvas.set_color(color.name())

    def pick_fill_color(self):
        color = QColorDialog.getColor(QColor(self.canvas.fill_color))
        if color.isValid():
            self.canvas.set_fill_color(color.name())
            self.fill_check.setChecked(True)

    def _quick_color(self, hexcolor):
        mods = QApplication.keyboardModifiers()
        if mods & Qt.AltModifier:
            self.canvas.set_fill_color(hexcolor)
            self.fill_check.setChecked(True)
        else:
            self.canvas.set_color(hexcolor)

    def insert_selected_preset(self):
        name = self.preset_combo.currentData()
        if name is None:
            self.statusBar().showMessage("Pick a preset from the list first (currently: None).", 4000)
            return
        self.canvas.insert_preset(name)

    def confirm_clear(self):
        if QMessageBox.question(self, "Confirm", "Clear the entire drawing?") == QMessageBox.Yes:
            self.canvas.clear()

    def refresh_all(self):
        body = shapes_to_tikz_body(self.canvas.shapes)
        self.tikz_view.setPlainText(body if body else "% (draw something)")
        self.preview.set_shapes(self.canvas.shapes)

    def copy_tikz(self):
        QApplication.clipboard().setText(self.tikz_view.toPlainText())
        self.statusBar().showMessage("TikZ code copied to clipboard.", 3000)

    def export_tex(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export as .tex", "figure.tex", "LaTeX files (*.tex)")
        if path:
            tex = shapes_to_standalone_tex(self.canvas.shapes)
            with open(path, "w", encoding="utf-8") as f:
                f.write(tex)
            self.statusBar().showMessage(f"Exported to {path}", 4000)

    def export_svg(self):
        if not self.canvas.shapes:
            self.statusBar().showMessage("Nothing to export yet -- draw something first.", 4000)
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export as SVG", "figure.svg", "SVG image (*.svg)")
        if path:
            ok = self.canvas.export_svg(path)
            self.statusBar().showMessage(
                f"SVG exported to {path}" if ok else "Export failed.", 4000)

    def export_png(self):
        if not self.canvas.shapes:
            self.statusBar().showMessage("Nothing to export yet -- draw something first.", 4000)
            return
        choice, ok = QInputDialog.getItem(
            self, "PNG resolution", "Scale factor:", PNG_SCALES, 1, False)
        if not ok:
            return
        scale = float(choice.rstrip("x"))
        path, _ = QFileDialog.getSaveFileName(self, "Export as image", "figure.png", "PNG image (*.png)")
        if path:
            ok = self.canvas.export_image(path, scale=scale)
            if ok:
                self.statusBar().showMessage(f"Image exported at {choice} to {path}", 4000)
            else:
                self.statusBar().showMessage("Export failed.", 4000)

    def duplicate_to_new_window(self):
        """
        Opens a SECOND, independent window pre-loaded with a deep copy of
        the current design, so you can keep the original untouched and try
        a variant side by side -- like duplicating a document, but without
        having to save/reopen a file. The two windows share nothing after
        this point: editing one never affects the other.
        """
        win = MainWindow()
        win.canvas.shapes = copy.deepcopy(self.canvas.shapes)
        win.canvas._invalidate_cache()
        win.canvas.shapes_changed.emit()
        win.canvas.update()
        win.setWindowTitle(self.windowTitle() + " — copy")
        MainWindow._open_windows.append(win)
        win.show()
        self.statusBar().showMessage(
            f"Design duplicated into a new window ({len(self.canvas.shapes)} shapes).", 4000)

    def open_new_window(self):
        """Opens a SECOND, independent, completely BLANK window -- unlike
        'Duplicate to new window' this does not copy the current design, it
        starts empty (the same idea as Cmd+N in most apps)."""
        win = MainWindow()
        MainWindow._open_windows.append(win)
        win.show()
        self.statusBar().showMessage("New blank window opened.", 3000)

    def new_project(self):
        if QMessageBox.question(self, "Confirm", "New project (unsaved changes will be lost)?") == QMessageBox.Yes:
            self.canvas.shapes = []
            self.current_file = None
            self.canvas._invalidate_cache()
            self.canvas.shapes_changed.emit()
            self.canvas.update()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "VanovaTikZSketch project (*.json)")
        if path:
            self.canvas.shapes = load_project(path)
            self.current_file = path
            self.canvas._invalidate_cache()
            self.canvas.shapes_changed.emit()
            self.canvas.update()

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save project", "figure.json", "VanovaTikZSketch project (*.json)")
        if path:
            save_project(self.canvas.shapes, path)
            self.current_file = path
            self.statusBar().showMessage(f"Project saved: {path}", 3000)


def _install_crash_guard():
    """
    PyQt5 aborts the whole process if an unhandled Python exception bubbles
    up from a reimplemented Qt method — UNLESS we install our own
    sys.excepthook. With this safety net, an unexpected error is just printed
    to the terminal instead of crashing the whole application.
    """
    import traceback

    def handler(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = handler
    sys.setrecursionlimit(10000)


def main():
    _install_crash_guard()
    # HiDPI/Retina: must be set BEFORE the QApplication is created.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    # Force the "Fusion" base style instead of the native macOS one. On Mac,
    # the native style makes QComboBox behave like a real NSPopUpButton:
    # press-and-HOLD, drag down to the item, then release to select it. A
    # normal quick click opens the popup and the release (still part of the
    # same click) immediately "selects" whatever is under the cursor, so the
    # dropdown looks like it flashes and closes instantly. Fusion gives the
    # standard click-to-open / click-to-select combo box behavior instead.
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
