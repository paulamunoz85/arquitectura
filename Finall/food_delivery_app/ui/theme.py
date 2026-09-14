import tkinter as tk
from tkinter import ttk

ROJO = "#E8452C"        
ROJO_OSCURO = "#C7371F"
NARANJA = "#F4A340"   
VERDE = "#3AA655"       
AMARILLO = "#F2C230"    
CREMA = "#FFF8F0"       
BLANCO = "#FFFFFF"
GRIS_CLARO = "#EFE7DE"
GRIS = "#8B8378"
CARBON = "#2B2320"      
CARBON_SUAVE = "#5A4F47"
ROJO_SUAVE_BG = "#FCEAE6"

FUENTE = "Segoe UI"


def aplicar_tema(root: tk.Tk):
    root.configure(bg=CREMA)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=CREMA, foreground=CARBON, font=(FUENTE, 10))

    style.configure("TFrame", background=CREMA)
    style.configure("Card.TFrame", background=BLANCO, relief="flat")
    style.configure("Header.TFrame", background=ROJO)
    style.configure("Sidebar.TFrame", background=BLANCO)

    style.configure("TLabel", background=CREMA, foreground=CARBON, font=(FUENTE, 10))
    style.configure("Card.TLabel", background=BLANCO, foreground=CARBON, font=(FUENTE, 10))
    style.configure("Titulo.TLabel", background=CREMA, foreground=CARBON,
                     font=(FUENTE, 20, "bold"))
    style.configure("TituloCard.TLabel", background=BLANCO, foreground=CARBON,
                     font=(FUENTE, 12, "bold"))
    style.configure("Subtitulo.TLabel", background=CREMA, foreground=CARBON_SUAVE,
                     font=(FUENTE, 10))
    style.configure("Precio.TLabel", background=BLANCO, foreground=ROJO_OSCURO,
                     font=(FUENTE, 12, "bold"))
    style.configure("HeaderTitulo.TLabel", background=ROJO, foreground=BLANCO,
                     font=(FUENTE, 18, "bold"))
    style.configure("HeaderSub.TLabel", background=ROJO, foreground="#FFE3DC",
                     font=(FUENTE, 9))
    style.configure("Estrella.TLabel", background=BLANCO, foreground=AMARILLO,
                     font=(FUENTE, 10, "bold"))
    style.configure("Estado.TLabel", background=BLANCO, foreground=VERDE,
                     font=(FUENTE, 9, "bold"))
    style.configure("Muted.TLabel", background=BLANCO, foreground=GRIS, font=(FUENTE, 9))
    style.configure("MutedApp.TLabel", background=CREMA, foreground=GRIS, font=(FUENTE, 9))

    # ---- Botones ----
    style.configure("TButton", font=(FUENTE, 10), padding=8, relief="flat")
    style.configure("Primario.TButton", background=ROJO, foreground=BLANCO,
                     font=(FUENTE, 10, "bold"), padding=10, borderwidth=0)
    style.map("Primario.TButton",
              background=[("active", ROJO_OSCURO), ("disabled", GRIS_CLARO)],
              foreground=[("disabled", GRIS)])

    style.configure("Secundario.TButton", background=BLANCO, foreground=ROJO,
                     font=(FUENTE, 10, "bold"), padding=10, borderwidth=1)
    style.map("Secundario.TButton", background=[("active", ROJO_SUAVE_BG)])

    style.configure("Exito.TButton", background=VERDE, foreground=BLANCO,
                     font=(FUENTE, 10, "bold"), padding=8, borderwidth=0)
    style.map("Exito.TButton", background=[("active", "#2E8A46")])

    style.configure("Peligro.TButton", background="#D64545", foreground=BLANCO,
                     font=(FUENTE, 10, "bold"), padding=8, borderwidth=0)
    style.map("Peligro.TButton", background=[("active", "#B93A3A")])

    style.configure("Ghost.TButton", background=CREMA, foreground=CARBON_SUAVE,
                     font=(FUENTE, 9), padding=6, borderwidth=0)
    style.map("Ghost.TButton", background=[("active", GRIS_CLARO)])

    # ---- Entradas ----
    style.configure("TEntry", padding=8, fieldbackground=BLANCO, borderwidth=1)
    style.configure("TSpinbox", padding=6, fieldbackground=BLANCO)

    # ---- Notebook (pestañas) ----
    style.configure("TNotebook", background=CREMA, borderwidth=0)
    style.configure("TNotebook.Tab", background=GRIS_CLARO, foreground=CARBON_SUAVE,
                     font=(FUENTE, 10, "bold"), padding=(16, 10))
    style.map("TNotebook.Tab",
              background=[("selected", BLANCO)],
              foreground=[("selected", ROJO)])

    # ---- Treeview (tablas) ----
    style.configure("Treeview", background=BLANCO, fieldbackground=BLANCO,
                     foreground=CARBON, rowheight=30, font=(FUENTE, 10), borderwidth=0)
    style.configure("Treeview.Heading", background=GRIS_CLARO, foreground=CARBON,
                     font=(FUENTE, 9, "bold"), padding=6)
    style.map("Treeview", background=[("selected", ROJO_SUAVE_BG)],
              foreground=[("selected", CARBON)])

    style.configure("TSeparator", background=GRIS_CLARO)
    style.configure("TRadiobutton", background=BLANCO, font=(FUENTE, 10))
    style.configure("TCheckbutton", background=BLANCO, font=(FUENTE, 10))

    return style


def tarjeta(parent, **kwargs):
    """Frame con apariencia de tarjeta (fondo blanco) reutilizable."""
    marco = tk.Frame(parent, bg=BLANCO, highlightbackground=GRIS_CLARO,
                      highlightthickness=1, bd=0)
    marco.configure(**kwargs)
    return marco


def area_desplazable(parent, bg=CREMA):
    """Crea un Canvas + Frame interior con scroll vertical, donde el frame
    interior siempre ocupa el ancho completo visible del canvas (evita que
    las tarjetas se corten al redimensionar la ventana)."""
    canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    interior = tk.Frame(canvas, bg=bg)
    ventana_id = canvas.create_window((0, 0), window=interior, anchor="nw")

    def _on_interior_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfig(ventana_id, width=event.width)

    interior.bind("<Configure>", _on_interior_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.configure(yscrollcommand=scrollbar.set)

    def _rueda(event):
        delta = -1 * (event.delta // 120) if event.delta else (1 if event.num == 5 else -1)
        canvas.yview_scroll(delta, "units")

    canvas.bind_all("<MouseWheel>", _rueda, add="+")
    canvas.bind_all("<Button-4>", _rueda, add="+")
    canvas.bind_all("<Button-5>", _rueda, add="+")

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return canvas, interior
