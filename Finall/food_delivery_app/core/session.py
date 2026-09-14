class SessionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.usuario = None   # dict con id, correo, rol
            cls._instance.token = None
        return cls._instance

    def iniciar_sesion(self, usuario: dict, token: str):
        self.usuario = usuario
        self.token = token

    def cerrar_sesion(self):
        self.usuario = None
        self.token = None

    @property
    def esta_autenticado(self) -> bool:
        return self.usuario is not None

    @property
    def rol(self):
        return self.usuario["rol"] if self.usuario else None

    @property
    def usuario_id(self):
        return self.usuario["id"] if self.usuario else None
    
    def get_session() -> SessionManager:
        return SessionManager()
