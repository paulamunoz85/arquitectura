import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from services.auth_service import AuthService, AuthError
from services.review_service import DisputeService, ReviewError
from ui import theme
from ui.assets import avatar_restaurante


class AdminPanel(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.auth = AuthService()
        self.dispute_service = DisputeService()
        self._procesando = set()

        self._construir_header()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(10, 16))

        self.tab_chefs = tk.Frame(self.notebook, bg=theme.CREMA)
        self.tab_disputas = tk.Frame(self.notebook, bg=theme.CREMA)
        self.notebook.add(self.tab_chefs, text="  👨‍🍳  Solicitudes de Chef  ")
        self.notebook.add(self.tab_disputas, text="  ⚖️  Disputas  ")

        self._construir_tab_chefs()
        self._construir_tab_disputas()

    def _construir_header(self):
        header = tk.Frame(self, bg=theme.ROJO, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🛠️  SaborLocal · Administración", bg=theme.ROJO, fg="white",
                 font=(theme.FUENTE, 15, "bold")).pack(side="left", padx=20)
        ttk.Button(header, text="Cerrar sesión", style="Secundario.TButton",
                   command=self.controller.cerrar_sesion).pack(side="right", padx=20, pady=12)

    # ---------------- HU-05 ----------------
    def _construir_tab_chefs(self):
        cont = self.tab_chefs
        ttk.Button(cont, text="🔄 Actualizar", style="Ghost.TButton", command=self._cargar_chefs).pack(
            anchor="w", pady=(0, 10))

        _, self.frame_chefs = theme.area_desplazable(cont)
        self._cargar_chefs()

    def _cargar_chefs(self):
        for w in self.frame_chefs.winfo_children():
            w.destroy()
        pendientes = self.auth.listar_chefs_pendientes()
        if not pendientes:
            tk.Label(self.frame_chefs, text="No hay solicitudes pendientes. 🎉",
                     bg=theme.CREMA, fg=theme.GRIS).pack(pady=30)
            return
        for r in pendientes:
            self._crear_tarjeta_chef(r)

    def _crear_tarjeta_chef(self, r):
        tarjeta = theme.tarjeta(self.frame_chefs)
        tarjeta.pack(fill="x", pady=6)
        fila = tk.Frame(tarjeta, bg=theme.BLANCO)
        fila.pack(fill="x", padx=14, pady=10)

        tk.Label(fila, image=avatar_restaurante(r["nombre_restaurante"], 48), bg=theme.BLANCO).pack(side="left")
        info = tk.Frame(fila, bg=theme.BLANCO)
        info.pack(side="left", padx=12, fill="x", expand=True)
        tk.Label(info, text=r["nombre_restaurante"], bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 11, "bold")).pack(anchor="w")
        tk.Label(info, text=r["correo_electronico"], bg=theme.BLANCO, fg=theme.GRIS,
                 font=(theme.FUENTE, 9)).pack(anchor="w")
        tk.Label(info, text=r["direccion"], bg=theme.BLANCO, fg=theme.GRIS, font=(theme.FUENTE, 9)).pack(anchor="w")

        ttk.Button(fila, text="✅ Aprobar", style="Exito.TButton",
                   command=lambda rid=r["id"]: self._aprobar(rid)).pack(side="right")

    def _aprobar(self, restaurante_id):
        if restaurante_id in self._procesando:
            return
        self._procesando.add(restaurante_id)
        try:
            self.auth.aprobar_chef(restaurante_id, self.controller.usuario["id"])
            messagebox.showinfo("Aprobado", "El chef fue notificado y su cuenta está activa.")
            self._cargar_chefs()
        except AuthError as e:
            messagebox.showerror("No se pudo aprobar", str(e))
        finally:
            self._procesando.discard(restaurante_id)

    # ---------------- Disputas ----------------
    def _construir_tab_disputas(self):
        cont = self.tab_disputas
        ttk.Button(cont, text="🔄 Actualizar", style="Ghost.TButton", command=self._cargar_disputas).pack(
            anchor="w", pady=(0, 10))

        _, self.frame_disputas = theme.area_desplazable(cont)
        self._cargar_disputas()

    def _cargar_disputas(self):
        for w in self.frame_disputas.winfo_children():
            w.destroy()
        disputas = self.dispute_service.listar_disputas_pendientes()
        if not disputas:
            tk.Label(self.frame_disputas, text="No hay disputas pendientes. 🎉",
                     bg=theme.CREMA, fg=theme.GRIS).pack(pady=30)
            return
        for d in disputas:
            self._crear_tarjeta_disputa(d)

    def _crear_tarjeta_disputa(self, d):
        tarjeta = theme.tarjeta(self.frame_disputas)
        tarjeta.pack(fill="x", pady=6)
        fila = tk.Frame(tarjeta, bg=theme.BLANCO)
        fila.pack(fill="x", padx=14, pady=10)

        info = tk.Frame(fila, bg=theme.BLANCO)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=f"Disputa #{d['id']} · Pedido #{d['pedido_id']}", bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 11, "bold")).pack(anchor="w")
        quien = {"CLIENTE": "el Cliente", "CHEF": "el Chef"}.get(d["creado_por_rol"], "un usuario")
        tk.Label(info, text=f"Reclamo abierto por {quien}" + (f" ({d['creado_por_nombre']})" if d["creado_por_nombre"] else ""),
                 bg=theme.BLANCO, fg=theme.NARANJA, font=(theme.FUENTE, 9, "bold")).pack(anchor="w", pady=(2, 0))
        tk.Label(info, text=d["motivo"], bg=theme.BLANCO, fg=theme.GRIS, font=(theme.FUENTE, 9),
                 wraplength=400, justify="left").pack(anchor="w", pady=(2, 0))
        tk.Label(info, text=f"Monto: ${d['monto_total']:,.0f}", bg=theme.BLANCO, fg=theme.ROJO_OSCURO,
                 font=(theme.FUENTE, 9, "bold")).pack(anchor="w", pady=(2, 0))

        acciones = tk.Frame(fila, bg=theme.BLANCO)
        acciones.pack(side="right")
        ttk.Button(acciones, text="💸 A favor del Cliente\n(reembolsar)", style="Exito.TButton",
                   command=lambda did=d["id"]: self._resolver(did, True)).pack(side="left", padx=3)
        ttk.Button(acciones, text="🚫 A favor del Chef\n(rechazar reclamo)", style="Peligro.TButton",
                   command=lambda did=d["id"]: self._resolver(did, False)).pack(side="left", padx=3)

    def _resolver(self, disputa_id, aprobar_reembolso):
        if disputa_id in self._procesando:
            return
        notas = simpledialog.askstring(
            "Notas de resolución",
            ("¿Por qué le das la razón al CLIENTE? (reembolso)" if aprobar_reembolso
             else "¿Por qué le das la razón al CHEF? (se rechaza el reclamo)"),
            parent=self) or ""
        self._procesando.add(disputa_id)
        try:
            self.dispute_service.resolver_disputa(disputa_id, self.controller.usuario["id"],
                                                   aprobar_reembolso, notas)
            mensaje = ("Se falló a favor del cliente: el pedido queda reembolsado." if aprobar_reembolso
                       else "Se falló a favor del chef: el reclamo fue rechazado.")
            messagebox.showinfo("Disputa resuelta", mensaje)
            self._cargar_disputas()
        except ReviewError as e:
            messagebox.showerror("No se pudo resolver", str(e))
        finally:
            self._procesando.discard(disputa_id)
