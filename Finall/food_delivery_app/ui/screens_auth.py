import tkinter as tk
from tkinter import ttk, messagebox

from core.dtos import UserRegistrationDTO, ChefRegistrationDTO
from services.auth_service import AuthService, AuthError
from ui import theme
from ui.assets import logo_app


class _MarcoBase(ttk.Frame):
    """Layout compartido: panel rojo de marca a la izquierda + tarjeta blanca
    con el formulario a la derecha (look tipo app de delivery)."""

    def __init__(self, parent, controller, eslogan: str):
        super().__init__(parent)
        self.controller = controller

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        panel_marca = tk.Frame(self, bg=theme.ROJO)
        panel_marca.grid(row=0, column=0, sticky="nsew")
        panel_marca.columnconfigure(0, weight=1)

        contenedor_logo = tk.Frame(panel_marca, bg=theme.ROJO)
        contenedor_logo.place(relx=0.5, rely=0.42, anchor="center")
        tk.Label(contenedor_logo, image=logo_app(110), bg=theme.ROJO).pack()
        tk.Label(contenedor_logo, text="SaborLocal", bg=theme.ROJO, fg="white",
                 font=(theme.FUENTE, 26, "bold")).pack(pady=(10, 0))
        tk.Label(contenedor_logo, text=eslogan, bg=theme.ROJO, fg="#FFE3DC",
                 font=(theme.FUENTE, 11), wraplength=260, justify="center").pack(pady=(6, 0))

        self.panel_formulario = tk.Frame(self, bg=theme.CREMA)
        self.panel_formulario.grid(row=0, column=1, sticky="nsew")


class LoginFrame(_MarcoBase):
    """HU-02 - Iniciar Sesión.
    Flujo: se llenan los campos de correo/contraseña y, al enviar, el sistema
    valida las credenciales y RESUELVE automáticamente el rol (Cliente, Chef
    o Administrador) -- el usuario nunca elige su rol manualmente. Si las
    credenciales son inválidas, se muestra el error y la persona se queda en
    esta misma pantalla de inicio de sesión."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Pide comida casera\nde los mejores cocineros locales")
        self.auth = AuthService()
        self._enviado = False

        tarjeta = tk.Frame(self.panel_formulario, bg=theme.CREMA)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(tarjeta, text="¡Bienvenido de nuevo! 👋", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 18, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4), sticky="w")
        tk.Label(tarjeta, text="Inicia sesión para continuar", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 10)).grid(row=1, column=0, columnspan=2, pady=(0, 20), sticky="w")

        tk.Label(tarjeta, text="Correo electrónico", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).grid(row=2, column=0, columnspan=2, sticky="w")
        self.correo_var = tk.StringVar()
        ttk.Entry(tarjeta, textvariable=self.correo_var, width=34, font=(theme.FUENTE, 11)).grid(
            row=3, column=0, columnspan=2, pady=(2, 12), ipady=4)

        tk.Label(tarjeta, text="Contraseña", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).grid(row=4, column=0, columnspan=2, sticky="w")
        self.pass_var = tk.StringVar()
        entry_pass = ttk.Entry(tarjeta, textvariable=self.pass_var, show="•", width=34, font=(theme.FUENTE, 11))
        entry_pass.grid(row=5, column=0, columnspan=2, pady=(2, 20), ipady=4)
        entry_pass.bind("<Return>", lambda e: self._login())

        self.btn_login = ttk.Button(tarjeta, text="Iniciar sesión", style="Primario.TButton",
                                     command=self._login)
        self.btn_login.grid(row=6, column=0, columnspan=2, sticky="ew", ipady=4)

        ttk.Separator(tarjeta).grid(row=7, column=0, columnspan=2, sticky="ew", pady=18)

        ttk.Button(tarjeta, text="🧑 Crear cuenta de Cliente", style="Secundario.TButton",
                   command=lambda: controller.mostrar("RegistroCliente")).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=4, ipady=2)
        ttk.Button(tarjeta, text="👨‍🍳 Quiero vender mi comida (Chef)", style="Secundario.TButton",
                   command=lambda: controller.mostrar("RegistroChef")).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=4, ipady=2)

        tk.Label(tarjeta, text="Admin de prueba: admin@marketplace.com / admin123",
                 bg=theme.CREMA, fg=theme.GRIS, font=(theme.FUENTE, 8)).grid(
            row=10, column=0, columnspan=2, pady=(16, 0))

    def _login(self):
        # RNF: el botón se deshabilita tras el primer clic para evitar múltiples peticiones.
        if self._enviado:
            return
        self._enviado = True
        self.btn_login.config(state="disabled")
        try:
            if not self.correo_var.get() or not self.pass_var.get():
                messagebox.showwarning("Campos vacíos", "Correo y contraseña son obligatorios.")
                return
            # 1) Primero se validan las credenciales ingresadas...
            resultado = self.auth.iniciar_sesion(self.correo_var.get().strip(), self.pass_var.get())
            # 2) ...y SOLO si son válidas, el sistema resuelve el rol y redirige.
            self.controller.iniciar_sesion(resultado)
        except AuthError as e:
            # Credenciales inválidas -> se queda en esta misma pantalla de login, con el error.
            messagebox.showerror("Error de acceso", str(e))
        finally:
            self.btn_login.config(state="normal")
            self._enviado = False
            self.pass_var.set("")


class RegistroClienteFrame(_MarcoBase):
    """HU-01 - Registrar Cliente (incluye nombre completo)."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Miles de platillos caseros\na un clic de distancia")
        self.auth = AuthService()
        self._enviado = False

        tarjeta = tk.Frame(self.panel_formulario, bg=theme.CREMA)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(tarjeta, text="Crear cuenta de Cliente 🍽️", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 18, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

        tk.Label(tarjeta, text="Nombre completo", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).grid(row=1, column=0, sticky="w")
        self.nombre_var = tk.StringVar()
        ttk.Entry(tarjeta, textvariable=self.nombre_var, width=34, font=(theme.FUENTE, 11)).grid(
            row=2, column=0, columnspan=2, pady=(2, 12), ipady=4)

        tk.Label(tarjeta, text="Correo electrónico", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).grid(row=3, column=0, sticky="w")
        self.correo_var = tk.StringVar()
        entry_correo = ttk.Entry(tarjeta, textvariable=self.correo_var, width=34, font=(theme.FUENTE, 11))
        entry_correo.grid(row=4, column=0, columnspan=2, pady=(2, 12), ipady=4)
        entry_correo.bind("<FocusOut>", self._validar_correo_visual)

        tk.Label(tarjeta, text="Contraseña", bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                 font=(theme.FUENTE, 9)).grid(row=5, column=0, sticky="w")
        self.pass_var = tk.StringVar()
        ttk.Entry(tarjeta, textvariable=self.pass_var, show="•", width=34, font=(theme.FUENTE, 11)).grid(
            row=6, column=0, columnspan=2, pady=(2, 6), ipady=4)

        self.lbl_estado = tk.Label(tarjeta, text="", bg=theme.CREMA, fg="#C0392B", font=(theme.FUENTE, 9))
        self.lbl_estado.grid(row=7, column=0, columnspan=2, sticky="w")

        self.btn_registrar = ttk.Button(tarjeta, text="Registrarme", style="Primario.TButton",
                                         command=self._registrar)
        self.btn_registrar.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(14, 6), ipady=4)
        ttk.Button(tarjeta, text="⬅ Volver a inicio de sesión", style="Ghost.TButton",
                   command=lambda: controller.mostrar("Login")).grid(row=9, column=0, columnspan=2, sticky="ew")

    def _validar_correo_visual(self, event):
        from core.dtos import EMAIL_REGEX
        correo = self.correo_var.get()
        self.lbl_estado.config(text="Formato de correo inválido." if correo and not EMAIL_REGEX.match(correo) else "")

    def _registrar(self):
        if self._enviado:
            return
        self._enviado = True
        self.btn_registrar.config(state="disabled")
        try:
            dto = UserRegistrationDTO(nombre=self.nombre_var.get().strip(),
                                       correo_electronico=self.correo_var.get().strip(),
                                       contrasena=self.pass_var.get())
            self.auth.registrar_cliente(dto)
            messagebox.showinfo("Registro exitoso", "Cuenta creada. Ahora inicia sesión.")
            self.controller.mostrar("Login")
        except AuthError as e:
            messagebox.showerror("Error de registro", str(e))
        finally:
            self.btn_registrar.config(state="normal")
            self._enviado = False


class RegistroChefFrame(_MarcoBase):
    """HU-04 - Registrar Chef (solicitud de vinculación), incluye nombre del chef."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Convierte tu cocina\nen tu propio negocio")
        self.auth = AuthService()
        self._enviado = False

        tarjeta = tk.Frame(self.panel_formulario, bg=theme.CREMA)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(tarjeta, text="Solicitud como Chef 👨‍🍳", bg=theme.CREMA, fg=theme.CARBON,
                 font=(theme.FUENTE, 18, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 18), sticky="w")

        campos = [
            ("Tu nombre completo", "nombre_persona", None),
            ("Correo electrónico", "correo", None),
            ("Contraseña", "pass", "•"),
            ("Nombre del restaurante", "nombre_restaurante", None),
            ("Dirección", "direccion", None),
            ("Descripción (opcional)", "descripcion", None),
        ]
        self.vars = {}
        for i, (etiqueta, clave, show) in enumerate(campos):
            tk.Label(tarjeta, text=etiqueta, bg=theme.CREMA, fg=theme.CARBON_SUAVE,
                     font=(theme.FUENTE, 9)).grid(row=i * 2 + 1, column=0, columnspan=2, sticky="w")
            var = tk.StringVar()
            ttk.Entry(tarjeta, textvariable=var, width=34, show=show, font=(theme.FUENTE, 11)).grid(
                row=i * 2 + 2, column=0, columnspan=2, pady=(2, 10), ipady=4)
            self.vars[clave] = var

        fila_final = len(campos) * 2 + 1
        self.btn_registrar = ttk.Button(tarjeta, text="Enviar solicitud", style="Primario.TButton",
                                         command=self._registrar)
        self.btn_registrar.grid(row=fila_final, column=0, columnspan=2, sticky="ew", pady=(10, 6), ipady=4)
        ttk.Button(tarjeta, text="⬅ Volver a inicio de sesión", style="Ghost.TButton",
                   command=lambda: controller.mostrar("Login")).grid(row=fila_final + 1, column=0, columnspan=2, sticky="ew")

    def _registrar(self):
        if self._enviado:
            return
        self._enviado = True
        self.btn_registrar.config(state="disabled")
        try:
            dto = ChefRegistrationDTO(
                nombre=self.vars["nombre_persona"].get().strip(),
                correo_electronico=self.vars["correo"].get().strip(),
                contrasena=self.vars["pass"].get(),
                nombre_restaurante=self.vars["nombre_restaurante"].get().strip(),
                direccion=self.vars["direccion"].get().strip(),
                descripcion=self.vars["descripcion"].get().strip(),
            )
            self.auth.registrar_chef(dto)
            messagebox.showinfo(
                "Solicitud enviada",
                "Tu solicitud fue enviada y quedó en estado 'Pendiente de revisión'.\n"
                "Un administrador debe aprobarla antes de que puedas iniciar sesión."
            )
            self.controller.mostrar("Login")
        except AuthError as e:
            messagebox.showerror("Error de registro", str(e))
        finally:
            self.btn_registrar.config(state="normal")
            self._enviado = False
