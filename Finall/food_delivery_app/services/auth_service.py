from datetime import datetime

from core.database import get_db
from core.security import hash_password, verify_password, generar_token
from core.dtos import UserRegistrationDTO, ChefRegistrationDTO
from core.patterns import UsuarioFactory, resolver_estrategia_redireccion, ComandoAprobarChef


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self):
        self.db = get_db()

    # ---------------- HU-01: Registrar Cliente ----------------
    def registrar_cliente(self, dto: UserRegistrationDTO):
        errores = dto.validar()
        if errores:
            raise AuthError(" / ".join(errores))

        existente = self.db.query_one(
            "SELECT id FROM usuarios WHERE correo_electronico = ?", (dto.correo_electronico,)
        )
        if existente:
            raise AuthError("El correo electrónico ya se encuentra registrado.")

        datos = UsuarioFactory.crear_cliente(dto.nombre.strip(), dto.correo_electronico, hash_password(dto.contrasena))
        self.db.execute(
            "INSERT INTO usuarios (nombre, correo_electronico, contrasena_hash, rol, esta_activo, fecha_creacion) "
            "VALUES (?,?,?,?,?,?)",
            (datos["nombre"], datos["correo_electronico"], datos["contrasena_hash"], datos["rol"],
             datos["esta_activo"], datetime.now().isoformat()),
        )
        return True  # el frontend debe redirigir manualmente al login (HU-01, punto 7)

    # ---------------- HU-04: Registrar Chef (solicitud) ----------------
    def registrar_chef(self, dto: ChefRegistrationDTO):
        errores = dto.validar()
        if errores:
            raise AuthError(" / ".join(errores))

        existente = self.db.query_one(
            "SELECT id FROM usuarios WHERE correo_electronico = ?", (dto.correo_electronico,)
        )
        if existente:
            raise AuthError("El correo electrónico ya se encuentra registrado.")

        datos_usuario = UsuarioFactory.crear_chef(dto.nombre.strip(), dto.correo_electronico, hash_password(dto.contrasena))
        usuario_id = self.db.transaction([
            ("INSERT INTO usuarios (nombre, correo_electronico, contrasena_hash, rol, esta_activo, fecha_creacion) "
             "VALUES (?,?,?,?,?,?)",
             (datos_usuario["nombre"], datos_usuario["correo_electronico"], datos_usuario["contrasena_hash"],
              datos_usuario["rol"], datos_usuario["esta_activo"], datetime.now().isoformat())),
        ])
        self.db.execute(
            "INSERT INTO restaurantes (usuario_id, nombre_restaurante, direccion, descripcion, estado, fecha_creacion) "
            "VALUES (?,?,?,?, 'PENDIENTE', ?)",
            (usuario_id, dto.nombre_restaurante, dto.direccion, dto.descripcion, datetime.now().isoformat()),
        )
        # "Alerta interna" simple: se registra en el log de eventos (HU-04 punto 3)
        self.db.log_evento(None, usuario_id, "SOLICITUD_CHEF_CREADA",
                            f"Restaurante '{dto.nombre_restaurante}' pendiente de revisión.")
        return True

    # ---------------- HU-05: Aprobar Chef ----------------
    def listar_chefs_pendientes(self):
        return self.db.query(
            "SELECT r.*, u.correo_electronico FROM restaurantes r "
            "JOIN usuarios u ON u.id = r.usuario_id WHERE r.estado = 'PENDIENTE' "
            "ORDER BY r.fecha_creacion ASC"
        )

    def aprobar_chef(self, restaurante_id: int, admin_id: int):
        comando = ComandoAprobarChef(self, restaurante_id, admin_id)
        comando.ejecutar()

    def aprobar(self, restaurante_id: int, admin_id: int):
        """Lógica real invocada por el ComandoAprobarChef (Patrón Command)."""
        restaurante = self.db.query_one("SELECT * FROM restaurantes WHERE id=?", (restaurante_id,))
        if restaurante is None:
            raise AuthError("Restaurante no encontrado.")
        self.db.transaction([
            ("UPDATE restaurantes SET estado='APROBADO' WHERE id=?", (restaurante_id,)),
            ("UPDATE usuarios SET esta_activo=1 WHERE id=?", (restaurante["usuario_id"],)),
        ])
        self.db.log_evento(None, admin_id, "CHEF_APROBADO",
                            f"Restaurante id={restaurante_id} aprobado por admin id={admin_id}.")
        return True

    # ---------------- HU-02 / HU-03: Iniciar sesión + validar credenciales ----------------
    def iniciar_sesion(self, correo: str, contrasena: str):
        if not correo or not contrasena:
            raise AuthError("Correo y contraseña son obligatorios.")

        usuario = self.db.query_one("SELECT * FROM usuarios WHERE correo_electronico = ?", (correo,))
        if usuario is None or not verify_password(contrasena, usuario["contrasena_hash"]):
            self.db.log_evento(None, None, "LOGIN_FALLIDO", f"Intento fallido para correo {correo}.")
            # Mensaje genérico: no revela si falló correo o contraseña (HU-03)
            raise AuthError("Credenciales inválidas.")

        if not usuario["esta_activo"]:
            raise AuthError("La cuenta aún no ha sido activada/aprobada.")

        estrategia = resolver_estrategia_redireccion(usuario["rol"])
        payload = {"id": usuario["id"], "nombre": usuario["nombre"] or "",
                   "correo": usuario["correo_electronico"], "rol": usuario["rol"]}
        token = generar_token(payload)
        self.db.log_evento(None, usuario["id"], "LOGIN_EXITOSO", "")
        return {
            "usuario": payload,
            "token": token,
            "pantalla_destino": estrategia.pantalla_destino(),
        }
