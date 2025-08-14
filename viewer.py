# viewer.py
import tkinter as tk
from PIL import Image, ImageTk

PDF_DPI = 180
ZOOM_STEP = 1.10
MIN_ZOOM = 0.2
MAX_ZOOM = 4.0
LANCZOS_DELAY_MS = 160

class PageViewer:
    """Encapsula canvas + zoom + pan + renderizado desde imágenes PIL cacheadas."""
    def __init__(self, root, x=50, y=70, w=400, h=500):
        self.root = root
        self.canvas = tk.Canvas(root, width=w, height=h, bg="white")
        self.scroll_y = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scroll_x = tk.Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)

        self.canvas.place(x=x, y=y)
        self.scroll_y.place(x=x + w, y=y, height=h)
        self.scroll_x.place(x=x, y=y + h, width=w)

        # item imagen único
        self.img_item = self.canvas.create_image(0, 0, anchor="nw", image=None)

        # estado zoom
        self.zoom_base = 1.0
        self.zoom = 1.0
        self.global_zoom = None 
        self._is_zooming = False
        self._lanczos_job = None
        self._last_draw_size = None
        self._photo = None

        # datos actuales
        self._get_image_fn = None  

        # pan
        self._drag_start = None

        # bindings
        self.canvas.bind("<MouseWheel>", self._on_wheel_scroll)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))  # Linux
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))   # Linux

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)

        self.canvas.bind("<Configure>", lambda e: self._fit_if_needed())

    # ------- API pública -------
    def set_image_getter(self, getter_callable):
        """getter_callable debe devolver la PIL.Image de la página actual."""
        self._get_image_fn = getter_callable

    def bind_zoom_shortcuts(self):
        """Habilita zoom con modificadores SOLO cuando el puntero está sobre el canvas."""
        # Windows / Linux
        self.canvas.bind("<Control-MouseWheel>", self._on_wheel_zoom)
        # macOS
        self.canvas.bind("<Command-MouseWheel>", self._on_wheel_zoom)
        self.canvas.bind("<Option-MouseWheel>", self._on_wheel_zoom)
        # Linux (rueda como Button-4/5 con Ctrl)
        self.canvas.bind("<Control-Button-4>", lambda e: (self.zoom_in(), "break"))
        self.canvas.bind("<Control-Button-5>", lambda e: (self.zoom_out(), "break"))

    def show_page(self, on_page_change=False):
        """Renderiza la página actual. on_page_change=True cuando cambias de página/documento."""
        img = self._img()
        if not img:
            return

        # recalcula zoom_base por si cambió el tamaño del canvas
        self._calc_fit(img)

        if on_page_change:
            # aplica zoom global si existe, si no, fit inicial
            if self.global_zoom is None:
                self.zoom = self.zoom_base
                self.global_zoom = self.zoom
            else:
                self.zoom = self._clamp(self.global_zoom)

            # fuerza redibujo limpio
            self._last_draw_size = None

        self._redraw(interim=False)

    def zoom_in(self):
        self._is_zooming = True
        self._apply_zoom(self.zoom * ZOOM_STEP, interim=True)

    def zoom_out(self):
        self._is_zooming = True
        self._apply_zoom(self.zoom / ZOOM_STEP, interim=True)

    # ------- Internos -------
    def _img(self):
        return self._get_image_fn() if self._get_image_fn else None

    def _on_wheel_scroll(self, event):
        units = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(units, "units")
        return "break" 

    def _on_wheel_zoom(self, event):
        factor = ZOOM_STEP if event.delta > 0 else (1 / ZOOM_STEP)
        self._is_zooming = True
        self._apply_zoom(self.zoom * factor, interim=True)

    def _apply_zoom(self, new_zoom, interim=False):
        if not self._img():
            return
        self.zoom = self._clamp(new_zoom)
        self.global_zoom = self.zoom  # persistir zoom global
        self._redraw(interim=True)
        if self._lanczos_job:
            self.root.after_cancel(self._lanczos_job)
        self._lanczos_job = self.root.after(LANCZOS_DELAY_MS, self._zoom_finalize)

    def _zoom_finalize(self):
        if not self._img():
            return
        self._is_zooming = False
        self.global_zoom = self.zoom  # guardar definitivo
        self._redraw(interim=False)
        self._lanczos_job = None

    def _start_drag(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self._drag_start = (event.x, event.y)

    def _on_drag(self, event):
        if self._drag_start:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _end_drag(self, event):
        self._drag_start = None

    def _calc_fit(self, img):
        cw = max(1, int(self.canvas.winfo_width()))
        ch = max(1, int(self.canvas.winfo_height()))
        fw, fh = cw * 0.95, ch * 0.95
        z = max(0.1, min(fw / img.width, fh / img.height))
        self.zoom_base = min(z, 1.2)

    def _fit_if_needed(self):
        """Si el canvas cambió de tamaño y estamos en zoom 'fit', volvemos a ajustar."""
        img = self._img()
        if not img:
            return
        prev_base = self.zoom_base
        self._calc_fit(img)
        if abs(self.zoom - prev_base) < 1e-3 and self.global_zoom is not None and abs(self.global_zoom - prev_base) < 1e-3:
            # usuario aún no cambió zoom → mantener fit
            self.zoom = self.zoom_base
            self.global_zoom = self.zoom
            self._redraw(interim=False)

    def _clamp(self, z):
        return max(self.zoom_base * MIN_ZOOM, min(z, self.zoom_base * MAX_ZOOM))

    def _redraw(self, interim=False):
        img = self._img()
        if not img:
            return
        w = max(1, int(img.width * self.zoom))
        h = max(1, int(img.height * self.zoom))
        if self._last_draw_size == (w, h) and self._photo:
            self.canvas.itemconfig(self.img_item, image=self._photo)
            return

        resample = Image.BILINEAR if interim else Image.LANCZOS
        resized = img.resize((w, h), resample=resample)
        self._photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfig(self.img_item, image=self._photo)
        self.canvas.coords(self.img_item, 0, 0)
        self.canvas.config(scrollregion=(0, 0, w, h))
        self._last_draw_size = (w, h)
