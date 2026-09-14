import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from services.restaurant_service import RestaurantService, RestaurantError
from services.order_service import OrderService, OrderError
from services.payment_service import PaymentService, PaymentError
from services.review_service import ReviewService, ReviewError, DisputeService
from core.patterns import get_canal_eventos
from core.dtos import TIPOS_PAGO_CON_TARJETA
from ui import theme
from ui.assets import avatar_restaurante, miniatura_producto, estrella, badge_circulo

BANCOS_PSE = ["Bancolombia", "Davivienda", "BBVA Colombia", "Banco de Bogotá", "Nequi",
              "Banco de Pruebas (rechaza)"]

ESTADOS_LEGIBLES = {
    "PENDIENTE_CHEF": ("Esperando confirmación del chef", theme.NARANJA),
    "RECHAZADO": ("Rechazado por el chef", "#D64545"),
    "PAGADO": ("Pagado · en cola de cocina", theme.NARANJA),
    "EN_PREPARACION": ("En preparación 👨‍🍳", theme.NARANJA),
    "EN_TRANSITO": ("En camino 🛵", theme.VERDE),
    "LISTO_PARA_RECOGER": ("Listo para recoger 🛍️", theme.VERDE),
    "COMPLETADO": ("Completado ✅", theme.VERDE),
    "EN_DISPUTA": ("En disputa ⚖️", "#D64545"),
    "REEMBOLSADO": ("Reembolsado", theme.GRIS),
}

ESTADOS_QUE_PERMITEN_RECLAMO = ("EN_TRANSITO", "LISTO_PARA_RECOGER", "COMPLETADO")


class ClientePanel(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.restaurant_service = RestaurantService()
        self.order_service = OrderService()
        self.payment_service = PaymentService()
        self.review_service = ReviewService()
        self.dispute_service = DisputeService()

        self.restaurante_actual = None
        self.carrito = []
        self._pendiente_refresco = False
        self._tarjetas_restaurante = []
        self._procesando = set()  # pedido_ids con una acción en curso (evita doble clic)

        self._construir_header()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(10, 16))

        self.tab_catalogo = tk.Frame(self.notebook, bg=theme.CREMA)
        self.tab_pedidos = tk.Frame(self.notebook, bg=theme.CREMA)
        self.notebook.add(self.tab_catalogo, text="  🍽  Explorar  ")
        self.notebook.add(self.tab_pedidos, text="  📦  Mis pedidos  ")

        self._construir_tab_catalogo()
        self._construir_tab_pedidos()

        get_canal_eventos().suscribir(self._observador_eventos)

    # ==================================================================
    def _construir_header(self):
        header = tk.Frame(self, bg=theme.ROJO, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🍅  SaborLocal", bg=theme.ROJO, fg="white",
                 font=(theme.FUENTE, 16, "bold")).pack(side="left", padx=20)
        correo = self.controller.usuario.get("correo", "") if self.controller.usuario else ""
        nombre = (self.controller.usuario.get("nombre") or "").strip() if self.controller.usuario else ""
        saludo = nombre.split(" ")[0] if nombre else correo.split("@")[0]
        tk.Label(header, text=f"Hola, {saludo} 👋", bg=theme.ROJO, fg="#FFE3DC",
                 font=(theme.FUENTE, 10)).pack(side="left", padx=6)
        ttk.Button(header, text="Cerrar sesión", style="Secundario.TButton",
                   command=self.controller.cerrar_sesion).pack(side="right", padx=20, pady=12)

    # ==================================================================
    # TAB CATÁLOGO (HU-07, HU-08) -- estilo tarjetas
    # ==================================================================
    def _construir_tab_catalogo(self):
        cont = self.tab_catalogo
        cont.columnconfigure(0, weight=0, minsize=280)
        cont.columnconfigure(1, weight=1)
        cont.columnconfigure(2, weight=0, minsize=280)
        cont.rowconfigure(0, weight=1)

        # ---------- Columna restaurantes ----------
        col_rest = tk.Frame(cont, bg=theme.CREMA)
        col_rest.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(col_rest, text="Restaurantes cerca de ti", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 13, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Button(col_rest, text="🔄 Actualizar", style="Ghost.TButton", command=self._cargar_restaurantes).pack(
            fill="x", pady=(0, 8))
        _, self.frame_restaurantes = theme.area_desplazable(col_rest)

        # ---------- Columna menú ----------
        col_menu = tk.Frame(cont, bg=theme.CREMA)
        col_menu.grid(row=0, column=1, sticky="nsew")
        self.lbl_restaurante_actual = tk.Label(col_menu, text="Selecciona un restaurante",
                                                bg=theme.CREMA, fg=theme.CARBON, font=(theme.FUENTE, 14, "bold"))
        self.lbl_restaurante_actual.pack(anchor="w", pady=(0, 8))

        _, self.frame_menu = theme.area_desplazable(col_menu)

        # ---------- Columna carrito ----------
        col_carrito = theme.tarjeta(cont, width=280)
        col_carrito.grid(row=0, column=2, sticky="nsew")
        col_carrito.pack_propagate(False)
        tk.Label(col_carrito, text="🛒 Tu pedido", bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 13, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        self.frame_carrito_items = tk.Frame(col_carrito, bg=theme.BLANCO)
        self.frame_carrito_items.pack(fill="both", expand=True, padx=16)

        self.lbl_carrito_vacio = tk.Label(self.frame_carrito_items, text="Aún no has agregado nada 🍔",
                                           bg=theme.BLANCO, fg=theme.GRIS, font=(theme.FUENTE, 9),
                                           wraplength=200, justify="left")
        self.lbl_carrito_vacio.pack(pady=20)

        pie_carrito = tk.Frame(col_carrito, bg=theme.BLANCO)
        pie_carrito.pack(fill="x", padx=16, pady=16, side="bottom")
        ttk.Separator(pie_carrito).pack(fill="x", pady=(0, 10))
        self.lbl_subtotal = tk.Label(pie_carrito, text="Subtotal: $0", bg=theme.BLANCO, fg=theme.CARBON,
                                      font=(theme.FUENTE, 12, "bold"))
        self.lbl_subtotal.pack(anchor="w")
        ttk.Button(pie_carrito, text="Vaciar carrito", style="Ghost.TButton", command=self._vaciar_carrito).pack(
            fill="x", pady=(8, 4))
        ttk.Button(pie_carrito, text="Continuar pedido  ➜", style="Primario.TButton",
                   command=self._abrir_checkout).pack(fill="x", ipady=4)

        self._cargar_restaurantes()

    def _cargar_restaurantes(self):
        for w in self.frame_restaurantes.winfo_children():
            w.destroy()
        self._restaurantes = self.restaurant_service.listar_restaurantes_publicados()
        if not self._restaurantes:
            tk.Label(self.frame_restaurantes, text="Aún no hay restaurantes publicados.",
                     bg=theme.CREMA, fg=theme.GRIS, wraplength=240).pack(pady=20)
            return
        for r in self._restaurantes:
            self._crear_tarjeta_restaurante(r)

    def _crear_tarjeta_restaurante(self, r):
        promedio, total = self.review_service.promedio_restaurante(r["id"])
        tarjeta = theme.tarjeta(self.frame_restaurantes, cursor="hand2")
        tarjeta.pack(fill="x", pady=6, ipady=6)

        fila = tk.Frame(tarjeta, bg=theme.BLANCO)
        fila.pack(fill="x", padx=10, pady=8)
        tk.Label(fila, image=avatar_restaurante(r["nombre_restaurante"], 56), bg=theme.BLANCO).pack(side="left")

        info = tk.Frame(fila, bg=theme.BLANCO)
        info.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(info, text=r["nombre_restaurante"], bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 11, "bold")).pack(anchor="w")

        fila_estrellas = tk.Frame(info, bg=theme.BLANCO)
        fila_estrellas.pack(anchor="w", pady=2)
        if promedio:
            for i in range(5):
                tk.Label(fila_estrellas, image=estrella(12, i < round(promedio)), bg=theme.BLANCO).pack(side="left")
            tk.Label(fila_estrellas, text=f" {promedio}  ({total})", bg=theme.BLANCO, fg=theme.GRIS,
                     font=(theme.FUENTE, 8)).pack(side="left")
        else:
            tk.Label(fila_estrellas, text="Sin calificaciones aún", bg=theme.BLANCO, fg=theme.GRIS,
                     font=(theme.FUENTE, 8)).pack(side="left")

        color_estado = theme.VERDE if r["en_horario"] else theme.GRIS
        texto_estado = "Abierto ahora" if r["en_horario"] else "Cerrado"
        fila_badge = tk.Frame(info, bg=theme.BLANCO)
        fila_badge.pack(anchor="w", pady=(2, 0))
        tk.Label(fila_badge, image=badge_circulo(color_estado, 10), bg=theme.BLANCO).pack(side="left")
        tk.Label(fila_badge, text=" " + texto_estado, bg=theme.BLANCO, fg=color_estado,
                 font=(theme.FUENTE, 8, "bold")).pack(side="left")
        if r["hora_apertura"] and r["hora_cierre"]:
            tk.Label(info, text=f"Horario: {r['hora_apertura']} – {r['hora_cierre']}", bg=theme.BLANCO,
                     fg=theme.GRIS, font=(theme.FUENTE, 8)).pack(anchor="w")

        widgets_click = [tarjeta, fila, info] + list(fila.winfo_children()) + list(info.winfo_children())
        for w in [tarjeta, fila, info]:
            w.bind("<Button-1>", lambda e, rr=r: self._seleccionar_restaurante(rr))
        for hijo in info.winfo_children():
            hijo.bind("<Button-1>", lambda e, rr=r: self._seleccionar_restaurante(rr))

    def _seleccionar_restaurante(self, restaurante):
        if not restaurante["en_horario"]:
            messagebox.showwarning("Fuera de horario", "Este restaurante no está en horario de atención.")
        self.restaurante_actual = restaurante
        self.lbl_restaurante_actual.config(text=f"🍽  Menú de {restaurante['nombre_restaurante']}")
        self._cargar_productos(restaurante["id"])
        if self.carrito and self.carrito[0].get("restaurante_id") != restaurante["id"]:
            self._vaciar_carrito()

    def _cargar_productos(self, restaurante_id):
        for w in self.frame_menu.winfo_children():
            w.destroy()
        self._productos = self.restaurant_service.listar_productos(restaurante_id)
        if not self._productos:
            tk.Label(self.frame_menu, text="Este restaurante aún no tiene platillos.",
                     bg=theme.CREMA, fg=theme.GRIS).pack(pady=20)
            return
        for p in self._productos:
            self._crear_tarjeta_producto(p)

    def _crear_tarjeta_producto(self, p):
        tarjeta = theme.tarjeta(self.frame_menu)
        tarjeta.pack(fill="x", pady=6)
        fila = tk.Frame(tarjeta, bg=theme.BLANCO)
        fila.pack(fill="x", padx=12, pady=10)

        tk.Label(fila, image=miniatura_producto(p["nombre"], 56), bg=theme.BLANCO).pack(side="left")

        info = tk.Frame(fila, bg=theme.BLANCO)
        info.pack(side="left", padx=12, fill="x", expand=True)
        tk.Label(info, text=p["nombre"], bg=theme.BLANCO, fg=theme.CARBON,
                 font=(theme.FUENTE, 11, "bold")).pack(anchor="w")
        if p["descripcion"]:
            tk.Label(info, text=p["descripcion"], bg=theme.BLANCO, fg=theme.GRIS, font=(theme.FUENTE, 8),
                     wraplength=220, justify="left").pack(anchor="w")
        stock_txt = f"Stock: {p['inventario']}" if p["inventario"] > 0 else "Agotado"
        color_stock = theme.GRIS if p["inventario"] > 0 else "#D64545"
        tk.Label(info, text=stock_txt, bg=theme.BLANCO, fg=color_stock, font=(theme.FUENTE, 8, "bold")).pack(anchor="w")

        control = tk.Frame(fila, bg=theme.BLANCO)
        control.pack(side="right")
        tk.Label(control, text=f"${p['precio']:,.0f}", bg=theme.BLANCO, fg=theme.ROJO_OSCURO,
                 font=(theme.FUENTE, 12, "bold")).pack(anchor="e")
        estado_btn = "normal" if p["inventario"] > 0 else "disabled"
        ttk.Button(control, text="+ Agregar", style="Primario.TButton", state=estado_btn,
                   command=lambda prod=p: self._agregar_al_carrito(prod)).pack(pady=(6, 0))

    def _agregar_al_carrito(self, producto):
        for item in self.carrito:
            if item["producto_id"] == producto["id"]:
                if item["cantidad"] + 1 > producto["inventario"]:
                    messagebox.showwarning("Sin stock", f"Solo hay {producto['inventario']} unidades disponibles.")
                    return
                item["cantidad"] += 1
                break
        else:
            self.carrito.append({
                "producto_id": producto["id"], "nombre": producto["nombre"],
                "precio": producto["precio"], "cantidad": 1,
                "restaurante_id": self.restaurante_actual["id"],
            })
        self._refrescar_carrito()

    def _refrescar_carrito(self):
        for w in self.frame_carrito_items.winfo_children():
            w.destroy()
        if not self.carrito:
            tk.Label(self.frame_carrito_items, text="Aún no has agregado nada 🍔", bg=theme.BLANCO,
                      fg=theme.GRIS, font=(theme.FUENTE, 9), wraplength=200, justify="left").pack(pady=20)
        for item in self.carrito:
            fila = tk.Frame(self.frame_carrito_items, bg=theme.BLANCO)
            fila.pack(fill="x", pady=4)
            tk.Label(fila, image=miniatura_producto(item["nombre"], 32), bg=theme.BLANCO).pack(side="left")
            texto = f"{item['cantidad']} × {item['nombre']}"
            tk.Label(fila, text=texto, bg=theme.BLANCO, fg=theme.CARBON, font=(theme.FUENTE, 9),
                     wraplength=110, justify="left").pack(side="left", padx=4)
            tk.Label(fila, text=f"${item['precio']*item['cantidad']:,.0f}", bg=theme.BLANCO,
                     fg=theme.ROJO_OSCURO, font=(theme.FUENTE, 9, "bold")).pack(side="left")
        subtotal = RestaurantService.calcular_subtotal(self.carrito)
        self.lbl_subtotal.config(text=f"Subtotal: ${subtotal:,.0f}")

    def _vaciar_carrito(self):
        self.carrito = []
        self._refrescar_carrito()

    def _abrir_checkout(self):
        if not self.carrito:
            messagebox.showinfo("Carrito vacío", "Agrega al menos un producto antes de continuar.")
            return
        CheckoutDialog(self, self.carrito, self.restaurante_actual, self._procesar_checkout)

    def _procesar_checkout(self, tipo_entrega, direccion):
        try:
            RestaurantService.validar_tipo_entrega(tipo_entrega, direccion)
            pedido_id = self.order_service.crear_pedido(
                cliente_id=self.controller.usuario["id"],
                restaurante_id=self.restaurante_actual["id"],
                carrito=[{"producto_id": i["producto_id"], "cantidad": i["cantidad"]} for i in self.carrito],
                tipo_entrega=tipo_entrega, direccion_entrega=direccion,
            )
        except (OrderError, RestaurantError) as e:
            messagebox.showerror("No se pudo crear el pedido", str(e))
            self._cargar_productos(self.restaurante_actual["id"])
            return

        messagebox.showinfo("Pedido enviado 🎉",
                             f"Pedido #{pedido_id} enviado al chef. Te avisaremos cuando sea aceptado.")
        self._vaciar_carrito()
        self.notebook.select(self.tab_pedidos)
        self._cargar_pedidos()

    # ==================================================================
    # TAB MIS PEDIDOS
    # ==================================================================
    def _construir_tab_pedidos(self):
        cont = self.tab_pedidos
        barra = tk.Frame(cont, bg=theme.CREMA)
        barra.pack(fill="x", pady=(0, 10))
        ttk.Button(barra, text="🔄 Actualizar", style="Ghost.TButton", command=self._cargar_pedidos).pack(side="left")

        _, self.frame_pedidos = theme.area_desplazable(cont)

        self._cargar_pedidos()

    def _cargar_pedidos(self):
        for w in self.frame_pedidos.winfo_children():
            w.destroy()
        pedidos = self.order_service.listar_pedidos_de_cliente(self.controller.usuario["id"])
        if not pedidos:
            tk.Label(self.frame_pedidos, text="Aún no tienes pedidos. ¡Ve a Explorar! 🍽️",
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
        tk.Label(izquierda, text=f"Pedido #{p['id']}  ·  {p['nombre_restaurante']}", bg=theme.BLANCO,
                 fg=theme.CARBON, font=(theme.FUENTE, 11, "bold")).pack(anchor="w")
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
            ttk.Button(acciones, text="💳 Pagar", style="Primario.TButton",
                       command=lambda pid=p["id"]: self._pagar_pedido(pid)).pack(side="left", padx=3)
        if p["estado"] in ("EN_TRANSITO", "LISTO_PARA_RECOGER"):
            ttk.Button(acciones, text="✅ Confirmar recibido", style="Exito.TButton",
                       command=lambda pid=p["id"]: self._confirmar_recepcion(pid)).pack(side="left", padx=3)
        if p["estado"] == "COMPLETADO":
            ya_calificado = self.review_service.db.query_one(
                "SELECT id FROM calificaciones WHERE pedido_id=?", (p["id"],))
            if not ya_calificado:
                ttk.Button(acciones, text="⭐ Calificar", style="Secundario.TButton",
                           command=lambda pid=p["id"]: self._calificar_pedido(pid)).pack(side="left", padx=3)
            else:
                tk.Label(acciones, text="¡Ya calificado! ⭐", bg=theme.BLANCO, fg=theme.GRIS,
                         font=(theme.FUENTE, 9)).pack(side="left", padx=3)
        if p["estado"] in ESTADOS_QUE_PERMITEN_RECLAMO:
            ttk.Button(acciones, text="⚠️ ¿Algún problema?", style="Ghost.TButton",
                       command=lambda pid=p["id"]: self._reportar_reclamo(pid)).pack(side="left", padx=3)
        if p["estado"] == "EN_DISPUTA":
            tk.Label(acciones, text="Tu reclamo está en revisión por el equipo de SaborLocal.",
                     bg=theme.BLANCO, fg="#D64545", font=(theme.FUENTE, 9), wraplength=220,
                     justify="left").pack(side="left", padx=3)

    def _pagar_pedido(self, pedido_id):
        if pedido_id in self._procesando:
            return
        PagoDialog(self, pedido_id, self.payment_service, lambda: self._on_pago_exitoso(pedido_id))

    def _on_pago_exitoso(self, pedido_id):
        self._cargar_pedidos()
        recibo = self.payment_service.obtener_recibo(pedido_id)
        if recibo:
            ReciboDialog(self, pedido_id, recibo)

    def _confirmar_recepcion(self, pedido_id):
        if pedido_id in self._procesando:
            return
        self._procesando.add(pedido_id)
        try:
            self.order_service.confirmar_recepcion(pedido_id, self.controller.usuario["id"])
            messagebox.showinfo("¡Listo!", "Recepción confirmada. ¡Buen provecho!")
            self._cargar_pedidos()
        except OrderError as e:
            messagebox.showerror("No se pudo confirmar", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _reportar_reclamo(self, pedido_id):
        if pedido_id in self._procesando:
            return
        motivo = simpledialog.askstring(
            "¿Qué pasó con tu pedido?",
            "Cuéntanos el problema (ej. llegó incompleto, muy tarde, en mal estado...):",
            parent=self)
        if not motivo or not motivo.strip():
            return
        self._procesando.add(pedido_id)
        try:
            self.dispute_service.abrir_disputa(pedido_id, motivo, self.controller.usuario["id"], "CLIENTE")
            messagebox.showinfo("Reclamo enviado",
                                 "Tu reclamo fue enviado al equipo de SaborLocal. Te avisaremos con la resolución.")
            self._cargar_pedidos()
        except ReviewError as e:
            messagebox.showerror("No se pudo enviar el reclamo", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _calificar_pedido(self, pedido_id):
        if pedido_id in self._procesando:
            return
        puntuacion = simpledialog.askinteger("Calificar", "Puntuación (1 a 5 estrellas):", minvalue=1, maxvalue=5,
                                              parent=self)
        if puntuacion is None:
            return
        comentario = simpledialog.askstring("Comentario", "Comentario (opcional):", parent=self) or ""
        self._procesando.add(pedido_id)
        try:
            self.review_service.calificar_pedido(pedido_id, self.controller.usuario["id"], puntuacion, comentario)
            messagebox.showinfo("¡Gracias!", "Tu calificación fue registrada.")
            self._cargar_pedidos()
        except ReviewError as e:
            messagebox.showerror("No se pudo calificar", str(e))
        finally:
            self._procesando.discard(pedido_id)

    def _observador_eventos(self, evento, datos):
        if evento in ("ACTUALIZACION_PEDIDO_CLIENTE", "PEDIDO_COMPLETADO", "PEDIDO_ACEPTADO_CLIENTE"):
            self._pendiente_refresco = True

    def revisar_refresco_pendiente(self):
        if self._pendiente_refresco:
            self._pendiente_refresco = False
            try:
                self._cargar_pedidos()
            except tk.TclError:
                pass


class CheckoutDialog(tk.Toplevel):
    """HU-08 - Elegir Tipo de Entrega."""

    def __init__(self, parent, carrito, restaurante, on_confirmar):
        super().__init__(parent)
        self.title("Tipo de entrega · SaborLocal")
        self.configure(bg=theme.CREMA)
        self.resizable(False, False)
        self.on_confirmar = on_confirmar
        self._enviado = False
        self.grab_set()

        subtotal = RestaurantService.calcular_subtotal(carrito)
        comision = round(subtotal * 0.10, 2)

        tk.Label(self, text=f"🧾 {restaurante['nombre_restaurante']}", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 13, "bold")).pack(padx=24, pady=(20, 4), anchor="w")
        tk.Label(self, text=f"Subtotal: ${subtotal:,.0f}   +   Comisión (10%): ${comision:,.0f}",
                 bg=theme.CREMA, fg=theme.CARBON_SUAVE, font=(theme.FUENTE, 9)).pack(padx=24, anchor="w")
        tk.Label(self, text=f"Total: ${subtotal + comision:,.0f}", bg=theme.CREMA, fg=theme.ROJO_OSCURO,
                 font=(theme.FUENTE, 13, "bold")).pack(padx=24, pady=(4, 16), anchor="w")

        self.tipo_var = tk.StringVar(value="RECOGER")
        frame_radio = tk.Frame(self, bg=theme.CREMA)
        frame_radio.pack(padx=24, pady=4, anchor="w")
        ttk.Radiobutton(frame_radio, text="🏠  Recoger en el local", value="RECOGER",
                         variable=self.tipo_var, command=self._toggle_direccion).pack(anchor="w", pady=3)
        ttk.Radiobutton(frame_radio, text="🛵  Domicilio", value="DOMICILIO",
                         variable=self.tipo_var, command=self._toggle_direccion).pack(anchor="w", pady=3)

        self.lbl_direccion = tk.Label(self, text="Dirección de entrega:", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                                       font=(theme.FUENTE, 9))
        self.entry_direccion = ttk.Entry(self, width=40, font=(theme.FUENTE, 10))
        self.lbl_direccion.pack(padx=24, pady=(10, 0), anchor="w")
        self.entry_direccion.pack(padx=24, pady=(2, 10), ipady=3)
        self._toggle_direccion()

        self.btn_confirmar = ttk.Button(self, text="Confirmar y enviar al chef", style="Primario.TButton",
                                         command=self._confirmar)
        self.btn_confirmar.pack(pady=18, padx=24, fill="x", ipady=4)

    def _toggle_direccion(self):
        if self.tipo_var.get() == "DOMICILIO":
            self.lbl_direccion.pack(padx=24, pady=(10, 0), anchor="w")
            self.entry_direccion.pack(padx=24, pady=(2, 10), ipady=3)
        else:
            self.lbl_direccion.pack_forget()
            self.entry_direccion.pack_forget()

    def _confirmar(self):
        # RNF: el botón se deshabilita tras el primer clic para evitar doble envío del pedido.
        if self._enviado:
            return
        self._enviado = True
        self.btn_confirmar.config(state="disabled")
        tipo = self.tipo_var.get()
        direccion = self.entry_direccion.get().strip() if tipo == "DOMICILIO" else None
        if tipo == "DOMICILIO" and not direccion:
            messagebox.showwarning("Falta la dirección", "Debes ingresar la dirección de entrega.")
            self.btn_confirmar.config(state="normal")
            self._enviado = False
            return
        self.destroy()
        self.on_confirmar(tipo, direccion)


class PagoDialog(tk.Toplevel):
    """HU-12/13/14 - Ingresar y Procesar Pago.
    Soporta 4 medios de pago: Tarjeta de crédito, Tarjeta de débito, PSE y
    Transferencia bancaria -- los campos del formulario cambian dinámicamente
    según el medio elegido."""

    def __init__(self, parent, pedido_id, payment_service: PaymentService, on_exito):
        super().__init__(parent)
        self.title(f"Pagar pedido #{pedido_id} · SaborLocal")
        self.configure(bg=theme.CREMA)
        self.resizable(False, False)
        self.pedido_id = pedido_id
        self.payment_service = payment_service
        self.on_exito = on_exito
        self._enviado = False
        self.grab_set()

        pedido = payment_service.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        self.monto_total = pedido["monto_total"] if pedido else 0.0

        tk.Label(self, text=f"💳 Monto a pagar: ${self.monto_total:,.0f}", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 13, "bold")).pack(padx=24, pady=(20, 14))

        tk.Label(self, text="Medio de pago", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).pack(padx=24, anchor="w")
        self.tipo_pago_var = tk.StringVar(value="TARJETA_CREDITO")
        frame_tipo = tk.Frame(self, bg=theme.CREMA)
        frame_tipo.pack(padx=24, anchor="w", pady=(2, 10))
        opciones = [
            ("Tarjeta de crédito", "TARJETA_CREDITO"), ("Tarjeta de débito", "TARJETA_DEBITO"),
            ("PSE", "PSE"), ("Transferencia bancaria", "TRANSFERENCIA"),
        ]
        for i, (texto, valor) in enumerate(opciones):
            ttk.Radiobutton(frame_tipo, text=texto, value=valor, variable=self.tipo_pago_var,
                             command=self._actualizar_campos).grid(row=i // 2, column=i % 2, sticky="w",
                                                                     padx=(0, 14), pady=2)

        # ---- Contenedor de campos dinámicos según el medio de pago ----
        self.frame_campos = tk.Frame(self, bg=theme.CREMA)
        self.frame_campos.pack(padx=24, pady=(4, 4), fill="x")

        # Campos de tarjeta
        self.numero_var = tk.StringVar()
        self.fecha_var = tk.StringVar()
        self.cvv_var = tk.StringVar()
        # Campos PSE / Transferencia
        self.banco_var = tk.StringVar(value=BANCOS_PSE[0])
        self.referencia_var = tk.StringVar()

        self.lbl_ayuda = tk.Label(self, text="", bg=theme.CREMA, fg=theme.GRIS, font=(theme.FUENTE, 8),
                                   wraplength=300, justify="left")
        self.lbl_ayuda.pack(padx=24, pady=(2, 10))

        self.btn_pagar = ttk.Button(self, text="Pagar ahora", style="Primario.TButton", command=self._pagar)
        self.btn_pagar.pack(padx=24, pady=(4, 20), fill="x", ipady=5)

        self._actualizar_campos()

    def _actualizar_campos(self):
        for w in self.frame_campos.winfo_children():
            w.destroy()
        tipo = self.tipo_pago_var.get()

        if tipo in TIPOS_PAGO_CON_TARJETA:
            tk.Label(self.frame_campos, text="Número de tarjeta", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                     font=(theme.FUENTE, 9)).pack(anchor="w")
            ttk.Entry(self.frame_campos, textvariable=self.numero_var, width=30, font=(theme.FUENTE, 10)).pack(
                pady=(2, 10), ipady=3, fill="x")

            fila_fecha_cvv = tk.Frame(self.frame_campos, bg=theme.CREMA)
            fila_fecha_cvv.pack(anchor="w", pady=(0, 4))
            col1 = tk.Frame(fila_fecha_cvv, bg=theme.CREMA)
            col1.pack(side="left", padx=(0, 16))
            tk.Label(col1, text="Fecha (MM/AA)", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                     font=(theme.FUENTE, 9)).pack(anchor="w")
            ttk.Entry(col1, textvariable=self.fecha_var, width=10, font=(theme.FUENTE, 10)).pack(ipady=3)
            col2 = tk.Frame(fila_fecha_cvv, bg=theme.CREMA)
            col2.pack(side="left")
            tk.Label(col2, text="CVV", bg=theme.CREMA, fg=theme.CARBON_SUAVE, font=(theme.FUENTE, 9)).pack(anchor="w")
            ttk.Entry(col2, textvariable=self.cvv_var, show="•", width=8, font=(theme.FUENTE, 10)).pack(ipady=3)
            self.lbl_ayuda.config(
                text="Prueba: termina en 0000 = fondos insuficientes · 9999 = timeout · otro = aprobado")

        elif tipo == "PSE":
            tk.Label(self.frame_campos, text="Banco", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                     font=(theme.FUENTE, 9)).pack(anchor="w")
            ttk.Combobox(self.frame_campos, textvariable=self.banco_var, values=BANCOS_PSE,
                         state="readonly", font=(theme.FUENTE, 10)).pack(pady=(2, 10), fill="x")
            self.lbl_ayuda.config(text="Serás redirigido al portal de tu banco para autorizar el pago "
                                        "(simulado). Prueba: 'Banco de Pruebas (rechaza)' simula un rechazo.")

        elif tipo == "TRANSFERENCIA":
            tk.Label(self.frame_campos, text="Banco de origen", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                     font=(theme.FUENTE, 9)).pack(anchor="w")
            ttk.Combobox(self.frame_campos, textvariable=self.banco_var, values=BANCOS_PSE[:-1],
                         state="readonly", font=(theme.FUENTE, 10)).pack(pady=(2, 10), fill="x")
            tk.Label(self.frame_campos, text="Número de comprobante", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                     font=(theme.FUENTE, 9)).pack(anchor="w")
            ttk.Entry(self.frame_campos, textvariable=self.referencia_var, width=30, font=(theme.FUENTE, 10)).pack(
                pady=(2, 10), ipady=3, fill="x")
            self.lbl_ayuda.config(text="Prueba: un comprobante que termine en '000' simula un comprobante "
                                        "inválido/rechazado.")

    def _pagar(self):
        if self._enviado:
            return
        self._enviado = True
        self.btn_pagar.config(state="disabled")
        try:
            tipo = self.tipo_pago_var.get()
            if tipo in TIPOS_PAGO_CON_TARJETA:
                campos = dict(numero_tarjeta=self.numero_var.get(), fecha_expiracion=self.fecha_var.get(),
                              cvv=self.cvv_var.get())
            elif tipo == "PSE":
                campos = dict(banco=self.banco_var.get())
            else:  # TRANSFERENCIA
                campos = dict(banco=self.banco_var.get(), numero_referencia=self.referencia_var.get())

            dto = self.payment_service.preparar_pago(self.pedido_id, tipo, **campos)
            resultado = self.payment_service.procesar_pago(self.pedido_id, dto)
            messagebox.showinfo("Pago aprobado ✅",
                                 f"Transacción: {resultado['id_transaccion']}\nSe generó tu recibo digital.")
            self.destroy()
            self.on_exito()
        except PaymentError as e:
            messagebox.showerror("Pago rechazado", str(e))
            self.numero_var.set("")
            self.cvv_var.set("")
        finally:
            if self.winfo_exists():
                self.btn_pagar.config(state="normal")
            self._enviado = False


class ReciboDialog(tk.Toplevel):

    def __init__(self, parent, pedido_id, contenido: str):
        super().__init__(parent)
        self.title(f"Recibo · Pedido #{pedido_id}")
        self.configure(bg=theme.CREMA)
        self.resizable(False, False)
        self.contenido = contenido
        self.pedido_id = pedido_id
        self.grab_set()

        tk.Label(self, text="🧾 Recibo digital de tu compra", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 13, "bold")).pack(padx=20, pady=(16, 8))

        marco = tk.Frame(self, bg="#FFFFFF", highlightbackground=theme.GRIS_CLARO, highlightthickness=1)
        marco.pack(padx=20, pady=(0, 12))
        texto = tk.Text(marco, width=46, height=18, font=("Courier New", 9), bg="#FFFFFF",
                        fg=theme.CARBON, relief="flat", wrap="none")
        texto.insert("1.0", contenido)
        texto.config(state="disabled")
        texto.pack(padx=10, pady=10)

        botones = tk.Frame(self, bg=theme.CREMA)
        botones.pack(fill="x", padx=20, pady=(0, 18))
        ttk.Button(botones, text="💾 Guardar como archivo", style="Secundario.TButton",
                   command=self._guardar_archivo).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(botones, text="Cerrar", style="Primario.TButton", command=self.destroy).pack(
            side="left", expand=True, fill="x", padx=(6, 0))

    def _guardar_archivo(self):
        import os
        carpeta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "recibos")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, f"recibo_pedido_{self.pedido_id}.txt")
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(self.contenido)
            messagebox.showinfo("Recibo guardado", f"Se guardó en:\n{ruta}")
        except OSError as e:
            messagebox.showerror("No se pudo guardar", str(e))
