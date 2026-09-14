import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from services.restaurant_service import RestaurantService, RestaurantError
from services.order_service import OrderService, OrderError
from core.patterns import get_canal_eventos
from ui import theme
from ui.assets import avatar_restaurante, miniatura_producto, badge_circulo

ESTADOS_LEGIBLES = {
    "PENDIENTE_CHEF": ("Esperando tu confirmación", theme.NARANJA),
    "PAGADO": ("Pagado · listo para preparar", theme.NARANJA),
    "EN_PREPARACION": ("En preparación 👨‍🍳", theme.NARANJA),
    "EN_TRANSITO": ("En camino 🛵", theme.VERDE),
    "LISTO_PARA_RECOGER": ("Listo para recoger 🛍️", theme.VERDE),
    "COMPLETADO": ("Completado ✅", theme.VERDE),
}


class ChefPanel(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.restaurant_service = RestaurantService()
        self.order_service = OrderService()
        self._pendiente_refresco = False
        self._platillos_temporales = []
        self._restaurante = None
        self._procesando = set()  # pedido_ids con una acción en curso (evita doble clic / doble petición)

        self._construir_header()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(10, 16))

        self.tab_pedidos = tk.Frame(self.notebook, bg=theme.CREMA)
        self.tab_menu = tk.Frame(self.notebook, bg=theme.CREMA)
        self.notebook.add(self.tab_pedidos, text="  📋  Pedidos  ")
        self.notebook.add(self.tab_menu, text="  🍳  Mi restaurante  ")

        self._construir_tab_pedidos()
        self._construir_tab_menu()

        get_canal_eventos().suscribir(self._observador_eventos)

    def _construir_header(self):
        header = tk.Frame(self, bg=theme.ROJO, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        restaurante = self._obtener_restaurante()
        tk.Label(header, image=avatar_restaurante(restaurante["nombre_restaurante"] if restaurante else "Chef", 40),
                 bg=theme.ROJO).pack(side="left", padx=16)
        info = tk.Frame(header, bg=theme.ROJO)
        info.pack(side="left")
        tk.Label(info, text=restaurante["nombre_restaurante"] if restaurante else "Panel del Chef",
                 bg=theme.ROJO, fg="white", font=(theme.FUENTE, 13, "bold")).pack(anchor="w", pady=(10, 0))
        tk.Label(info, text="SaborLocal · Panel del Chef", bg=theme.ROJO, fg="#FFE3DC",
                 font=(theme.FUENTE, 9)).pack(anchor="w")
        ttk.Button(header, text="Cerrar sesión", style="Secundario.TButton",
                   command=self.controller.cerrar_sesion).pack(side="right", padx=20, pady=12)

    # ==================================================================
    # TAB PEDIDOS
    # ==================================================================
    def _construir_tab_pedidos(self):
        cont = self.tab_pedidos
        barra = tk.Frame(cont, bg=theme.CREMA)
        barra.pack(fill="x", pady=(0, 10))
        ttk.Button(barra, text="🔄 Actualizar", style="Ghost.TButton", command=self._cargar_pedidos).pack(side="left")

        _, self.frame_pedidos = theme.area_desplazable(cont)
        self._cargar_pedidos()

    def _obtener_restaurante(self):
        if self._restaurante is None:
            self._restaurante = self.restaurant_service.obtener_restaurante_por_usuario(
                self.controller.usuario["id"])
        return self._restaurante

    def _cargar_pedidos(self):
        restaurante = self._obtener_restaurante()
        for w in self.frame_pedidos.winfo_children():
            w.destroy()
        if restaurante is None:
            return
        pedidos = [p for p in self.order_service.listar_pedidos_de_chef(restaurante["id"])
                   if p["estado"] in ESTADOS_LEGIBLES]
        if not pedidos:
            tk.Label(self.frame_pedidos, text="No tienes pedidos activos por ahora.",
                     bg=theme.CREMA, fg=theme.GRIS).pack(pady=30)
            return
        for p in pedidos:
            self._crear_tarjeta_pedido(p)

    def _crear_tarjeta_pedido(self, p):
        texto_estado, color_estado = ESTADOS_LEGIBLES.get(p["estado"], (p["estado"], theme.GRIS))
        tarjeta = theme.tarjeta(self.frame_pedidos)
        tarjeta.pack(fill="x", pady=6, padx=2)
        fila = tk.Frame(tarjeta, bg=theme.BLANCO)
        fila.pack(fill="x", padx=14, pady=10)

        izquierda = tk.Frame(fila, bg=theme.BLANCO)
        izquierda.pack(side="left", fill="x", expand=True)
        tipo_txt = "🛵 Domicilio" if p["tipo_entrega"] == "DOMICILIO" else "🏠 Recoger en el local"
        tk.Label(izquierda, text=f"Pedido #{p['id']}  ·  {tipo_txt}", bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 11, "bold")).pack(anchor="w")
        badge = tk.Frame(izquierda, bg=theme.BLANCO)
        badge.pack(anchor="w", pady=(4, 0))
        tk.Label(badge, image=badge_circulo(color_estado, 10), bg=theme.BLANCO).pack(side="left")
        tk.Label(badge, text=" " + texto_estado, bg=theme.BLANCO, fg=color_estado,
                 font=(theme.FUENTE, 9, "bold")).pack(side="left")
        tk.Label(izquierda, text=f"Total: ${p['monto_total']:,.0f}", bg=theme.BLANCO, fg=theme.GRIS,
                 font=(theme.FUENTE, 9)).pack(anchor="w", pady=(2, 0))

        acciones = tk.Frame(fila, bg=theme.BLANCO)
        acciones.pack(side="right")
        if p["estado"] == "PENDIENTE_CHEF":
            ttk.Button(acciones, text="✅ Aceptar", style="Exito.TButton",
                       command=lambda pid=p["id"]: self._aceptar(pid)).pack(side="left", padx=3)
            ttk.Button(acciones, text="❌ Rechazar", style="Peligro.TButton",
                       command=lambda pid=p["id"]: self._rechazar(pid)).pack(side="left", padx=3)
        elif p["estado"] == "PAGADO":
            ttk.Button(acciones, text="🍳 Iniciar preparación", style="Primario.TButton",
                       command=lambda pid=p["id"]: self._iniciar_preparacion(pid)).pack(side="left", padx=3)
        elif p["estado"] == "EN_PREPARACION":
            texto_boton = "🛵 Despachar" if p["tipo_entrega"] == "DOMICILIO" else "🛍️ Marcar listo"
            ttk.Button(acciones, text=texto_boton, style="Primario.TButton",
                       command=lambda pid=p["id"]: self._despachar(pid)).pack(side="left", padx=3)
        else:
            tk.Label(acciones, text="Sin acciones pendientes", bg=theme.BLANCO, fg=theme.GRIS,
                      font=(theme.FUENTE, 9)).pack(side="left", padx=3)

    def _aceptar(self, pedido_id):
        if pedido_id in self._procesando:
            return
        self._procesando.add(pedido_id)
        try:
            self.order_service.aceptar_pedido(pedido_id, self.controller.usuario["id"])
            messagebox.showinfo("Pedido aceptado", "El cliente ya puede proceder con el pago.")
            self._cargar_pedidos()
        except OrderError as e:
            messagebox.showerror("No se pudo aceptar", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _rechazar(self, pedido_id):
        if pedido_id in self._procesando:
            return
        motivo = simpledialog.askstring("Motivo", "Motivo del rechazo (opcional):", parent=self) or ""
        self._procesando.add(pedido_id)
        try:
            self.order_service.rechazar_pedido(pedido_id, self.controller.usuario["id"], motivo)
            messagebox.showinfo("Pedido rechazado", "El stock reservado fue devuelto al inventario.")
            self._cargar_pedidos()
        except OrderError as e:
            messagebox.showerror("No se pudo rechazar", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _iniciar_preparacion(self, pedido_id):
        if pedido_id in self._procesando:
            return
        self._procesando.add(pedido_id)
        try:
            self.order_service.iniciar_preparacion_comando(pedido_id, self.controller.usuario["id"])
            self._cargar_pedidos()
        except OrderError as e:
            messagebox.showerror("No se pudo iniciar preparación", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _despachar(self, pedido_id):
        if pedido_id in self._procesando:
            return
        self._procesando.add(pedido_id)
        try:
            resultado = self.order_service.despachar_o_marcar_listo(pedido_id, self.controller.usuario["id"])
            messagebox.showinfo("Actualizado", resultado["mensaje"])
            self._cargar_pedidos()
        except OrderError as e:
            messagebox.showerror("No se pudo despachar", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _observador_eventos(self, evento, datos):
        if evento in ("NUEVO_PEDIDO_CHEF", "PEDIDO_PAGADO_CHEF"):
            restaurante = self._obtener_restaurante()
            if restaurante and datos.get("restaurante_id") == restaurante["id"]:
                self._pendiente_refresco = True

    def revisar_refresco_pendiente(self):
        if self._pendiente_refresco:
            self._pendiente_refresco = False
            try:
                self._cargar_pedidos()
            except tk.TclError:
                pass

    # ==================================================================
    # TAB MI RESTAURANTE (HU-06)
    # ==================================================================
    def _construir_tab_menu(self):
        cont = self.tab_menu
        restaurante = self._obtener_restaurante()

        _, interior = theme.area_desplazable(cont)

        marco_datos = theme.tarjeta(interior)
        marco_datos.pack(fill="x", pady=(0, 12), ipady=8)
        tk.Label(marco_datos, text="Datos generales del restaurante", bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 12, "bold")).pack(anchor="w", padx=16, pady=(12, 8))

        cuerpo = tk.Frame(marco_datos, bg=theme.BLANCO)
        cuerpo.pack(fill="x", padx=16, pady=(0, 12))

        self.nombre_var = tk.StringVar(value=restaurante["nombre_restaurante"] if restaurante else "")
        self.direccion_var = tk.StringVar(value=restaurante["direccion"] if restaurante else "")
        self.desc_var = tk.StringVar(value=(restaurante["descripcion"] or "") if restaurante else "")
        self.apertura_var = tk.StringVar(value=restaurante["hora_apertura"] if restaurante and restaurante["hora_apertura"] else "08:00")
        self.cierre_var = tk.StringVar(value=restaurante["hora_cierre"] if restaurante and restaurante["hora_cierre"] else "20:00")

        for i, (etiqueta, var) in enumerate([
            ("Nombre", self.nombre_var), ("Dirección", self.direccion_var), ("Descripción", self.desc_var),
        ]):
            tk.Label(cuerpo, text=etiqueta, bg=theme.BLANCO, fg=theme.CARBON_SUAVE, font=(theme.FUENTE, 9)).grid(
                row=i, column=0, sticky="w", pady=4)
            ttk.Entry(cuerpo, textvariable=var, width=45, font=(theme.FUENTE, 10)).grid(
                row=i, column=1, pady=4, padx=(10, 0), ipady=3)

        tk.Label(cuerpo, text="Horario (HH:MM)", bg=theme.BLANCO, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).grid(row=3, column=0, sticky="w", pady=4)
        frame_horario = tk.Frame(cuerpo, bg=theme.BLANCO)
        frame_horario.grid(row=3, column=1, sticky="w", padx=(10, 0))
        entry_apertura = ttk.Entry(frame_horario, textvariable=self.apertura_var, width=8)
        entry_apertura.pack(side="left", ipady=3)
        tk.Label(frame_horario, text=" a ", bg=theme.BLANCO).pack(side="left")
        entry_cierre = ttk.Entry(frame_horario, textvariable=self.cierre_var, width=8)
        entry_cierre.pack(side="left", ipady=3)

        # Vista previa en vivo: así el chef entiende cómo el sistema decide
        # si el restaurante aparece "Abierto ahora" o "Cerrado" en el catálogo
        # del cliente (se compara la hora actual contra este rango, HU-07).
        self.lbl_preview_horario = tk.Label(cuerpo, text="", bg=theme.BLANCO, font=(theme.FUENTE, 8, "bold"))
        self.lbl_preview_horario.grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(2, 0))
        self.apertura_var.trace_add("write", lambda *a: self._actualizar_preview_horario())
        self.cierre_var.trace_add("write", lambda *a: self._actualizar_preview_horario())
        self._actualizar_preview_horario()

        marco_platos = theme.tarjeta(interior)
        marco_platos.pack(fill="both", expand=True, ipady=8)
        tk.Label(marco_platos, text="Agregar platillos al menú", bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 12, "bold")).pack(anchor="w", padx=16, pady=(12, 8))

        fila = tk.Frame(marco_platos, bg=theme.BLANCO)
        fila.pack(fill="x", padx=16)
        self.plato_nombre = tk.StringVar()
        self.plato_desc = tk.StringVar()
        self.plato_precio = tk.DoubleVar(value=0.0)
        self.plato_stock = tk.IntVar(value=1)
        ttk.Entry(fila, textvariable=self.plato_nombre, width=16, font=(theme.FUENTE, 9)).pack(side="left", padx=2, ipady=3)
        ttk.Entry(fila, textvariable=self.plato_desc, width=18, font=(theme.FUENTE, 9)).pack(side="left", padx=2, ipady=3)
        ttk.Entry(fila, textvariable=self.plato_precio, width=8, font=(theme.FUENTE, 9)).pack(side="left", padx=2, ipady=3)
        ttk.Entry(fila, textvariable=self.plato_stock, width=6, font=(theme.FUENTE, 9)).pack(side="left", padx=2, ipady=3)
        ttk.Button(fila, text="+ Agregar", style="Secundario.TButton", command=self._agregar_plato_temporal).pack(
            side="left", padx=6)
        tk.Label(marco_platos, text="Nombre · Descripción · Precio · Stock", bg=theme.BLANCO, fg=theme.GRIS,
                 font=(theme.FUENTE, 8)).pack(anchor="w", padx=16, pady=(2, 8))

        self.frame_platos_temp = tk.Frame(marco_platos, bg=theme.BLANCO)
        self.frame_platos_temp.pack(fill="x", padx=16)

        ttk.Button(interior, text="Guardar y Publicar restaurante", style="Primario.TButton",
                   command=self._guardar_menu).pack(fill="x", pady=14, ipady=5)

    def _actualizar_preview_horario(self):
        from datetime import time as _time, datetime as _dt
        try:
            apertura = _dt.strptime(self.apertura_var.get(), "%H:%M").time()
            cierre = _dt.strptime(self.cierre_var.get(), "%H:%M").time()
            ahora = _dt.now().time()
            abierto = apertura <= ahora <= cierre
            texto = f"Ahora mismo (según la hora del sistema, {ahora.strftime('%H:%M')}) tu restaurante " \
                    + ("se mostraría ABIERTO ✅" if abierto else "se mostraría CERRADO ⛔")
            self.lbl_preview_horario.config(text=texto, fg=theme.VERDE if abierto else theme.GRIS)
        except ValueError:
            self.lbl_preview_horario.config(text="Formato de hora inválido (usa HH:MM, ej. 08:00).",
                                             fg="#D64545")

    def _agregar_plato_temporal(self):
        nombre = self.plato_nombre.get().strip()
        precio = self.plato_precio.get()
        stock = self.plato_stock.get()

        errores = []
        if not nombre:
            errores.append("El platillo necesita un nombre.")
        if precio is None or precio <= 0:
            errores.append("El precio debe ser mayor a $0.")
        if stock is None or stock < 0:
            errores.append("El stock no puede ser negativo.")
        if errores:
            messagebox.showwarning("Revisa los datos del platillo", " / ".join(errores))
            return

        plato = {"nombre": nombre, "descripcion": self.plato_desc.get(), "precio": precio, "inventario": stock}
        self._platillos_temporales.append(plato)
        self._renderizar_platillos_temporales()

        self.plato_nombre.set(""); self.plato_desc.set(""); self.plato_precio.set(0.0); self.plato_stock.set(1)

    def _renderizar_platillos_temporales(self):
        for w in self.frame_platos_temp.winfo_children():
            w.destroy()
        for idx, plato in enumerate(self._platillos_temporales):
            fila = tk.Frame(self.frame_platos_temp, bg=theme.BLANCO)
            fila.pack(fill="x", pady=3)
            tk.Label(fila, image=miniatura_producto(plato["nombre"], 32), bg=theme.BLANCO).pack(side="left")
            tk.Label(fila, text=f"{plato['nombre']} · ${plato['precio']:,.0f} · stock {plato['inventario']}",
                     bg=theme.BLANCO, fg=theme.CARBON, font=(theme.FUENTE, 9)).pack(side="left", padx=8)
            # Permite quitar/corregir un platillo ya agregado ANTES de publicar.
            ttk.Button(fila, text="🗑️ Quitar", style="Ghost.TButton",
                       command=lambda i=idx: self._quitar_plato_temporal(i)).pack(side="right")

    def _quitar_plato_temporal(self, indice):
        if 0 <= indice < len(self._platillos_temporales):
            del self._platillos_temporales[indice]
            self._renderizar_platillos_temporales()

    def _guardar_menu(self):
        if not self._platillos_temporales:
            messagebox.showwarning("Sin platillos", "Agrega al menos un platillo a la lista antes de guardar.")
            return
        try:
            self.restaurant_service.configurar_perfil_y_menu(
                usuario_id=self.controller.usuario["id"],
                nombre=self.nombre_var.get(), direccion=self.direccion_var.get(),
                descripcion=self.desc_var.get(),
                hora_apertura=self.apertura_var.get(), hora_cierre=self.cierre_var.get(),
                platillos=self._platillos_temporales,
            )
            messagebox.showinfo("Publicado 🎉", "Tu restaurante quedó publicado en el catálogo.")
            self._platillos_temporales = []
            self._renderizar_platillos_temporales()
            self._restaurante = None
        except RestaurantError as e:
            messagebox.showerror("No se pudo guardar", str(e))
