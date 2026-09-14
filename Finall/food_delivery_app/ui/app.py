import tkinter as tk
from tkinter import ttk

from ui import theme
from ui.assets import logo_app
from ui.screens_auth import LoginFrame, RegistroClienteFrame, RegistroChefFrame
from ui.screens_cliente import ClientePanel
from ui.screens_chef import ChefPanel
from ui.screens_admin import AdminPanel


class App(tk.Tk):
    """Ventana principal de SaborLocal. Actúa como enrutador simple entre
    pantallas, equivalente al 'Sistema Web' del diagrama BPMN visto desde
    el frontend."""

    def __init__(self):
        super().__init__()
        self.title("SaborLocal — Marketplace de Domicilios de Comida")
        self.geometry("1150x720")
        self.minsize(1000, 650)

        theme.aplicar_tema(self)
        self._icono = logo_app(32)
        try:
            self.iconphoto(True, self._icono)
        except tk.TclError:
            pass

        self.usuario = None
        self.token = None

        self.contenedor = tk.Frame(self, bg=theme.CREMA)
        self.contenedor.pack(fill="both", expand=True)

        self.frames = {}
        for Clase, nombre in [
            (LoginFrame, "Login"),
            (RegistroClienteFrame, "RegistroCliente"),
            (RegistroChefFrame, "RegistroChef"),
        ]:
            frame = Clase(self.contenedor, self)
            self.frames[nombre] = frame
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.panel_actual = None
        self.mostrar("Login")

        # Bucle de refresco reactivo (simula recepción de eventos push, HU-11/HU-18)
        self.after(1000, self._tick_refresco)

    def mostrar(self, nombre_frame):
        for f in self.frames.values():
            f.place_forget()
        self.frames[nombre_frame].place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frames[nombre_frame].tkraise()

    # ---------------- HU-02/03: sesión ----------------
    def iniciar_sesion(self, resultado_login: dict):
        self.usuario = resultado_login["usuario"]
        self.token = resultado_login["token"]
        destino = resultado_login["pantalla_destino"]

        if self.panel_actual is not None:
            self.panel_actual.destroy()

        if destino == "PANEL_CLIENTE":
            self.panel_actual = ClientePanel(self.contenedor, self)
        elif destino == "PANEL_CHEF":
            self.panel_actual = ChefPanel(self.contenedor, self)
        else:
            self.panel_actual = AdminPanel(self.contenedor, self)

        self.panel_actual.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panel_actual.tkraise()

    def cerrar_sesion(self):
        self.usuario = None
        self.token = None
        if self.panel_actual is not None:
            self.panel_actual.destroy()
            self.panel_actual = None
        self.mostrar("Login")

    def _tick_refresco(self):
        # Los paneles de Cliente y Chef exponen 'revisar_refresco_pendiente'
        # para reflejar notificaciones Observer/Pub-Sub sin recargar (HU-11/HU-18).
        if self.panel_actual is not None and hasattr(self.panel_actual, "revisar_refresco_pendiente"):
            try:
                self.panel_actual.revisar_refresco_pendiente()
            except tk.TclError:
                pass
        self.after(1000, self._tick_refresco)


def run():
    app = App()
    app.mainloop()
