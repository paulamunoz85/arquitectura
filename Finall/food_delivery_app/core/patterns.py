from abc import ABC, abstractmethod

class UsuarioFactory:
    @staticmethod
    def crear_cliente(nombre, correo, contrasena_hash):
        return {
            "nombre": nombre,
            "correo_electronico": correo,
            "contrasena_hash": contrasena_hash,
            "rol": "CLIENTE",
            "esta_activo": True,
        }

    @staticmethod
    def crear_chef(nombre, correo, contrasena_hash):
        # El chef nace con esta_activo=False (equivalente a is_approved=false, HU-04)
        return {
            "nombre": nombre,
            "correo_electronico": correo,
            "contrasena_hash": contrasena_hash,
            "rol": "CHEF",
            "esta_activo": False,
        }

class RestauranteBuilder:
    def __init__(self):
        self._nombre = None
        self._direccion = None
        self._descripcion = ""
        self._hora_apertura = None
        self._hora_cierre = None
        self._platillos = []  # lista de dicts: nombre, descripcion, precio, inventario

    def con_datos_generales(self, nombre, direccion, descripcion=""):
        self._nombre = nombre
        self._direccion = direccion
        self._descripcion = descripcion
        return self

    def con_horario(self, hora_apertura, hora_cierre):
        self._hora_apertura = hora_apertura
        self._hora_cierre = hora_cierre
        return self

    def agregar_platillo(self, nombre, descripcion, precio, inventario):
        self._platillos.append({
            "nombre": nombre, "descripcion": descripcion,
            "precio": precio, "inventario": inventario,
        })
        return self

    def validar(self):
        errores = []
        if not self._nombre or not self._direccion:
            errores.append("Nombre y dirección del restaurante son obligatorios.")
        if not self._hora_apertura or not self._hora_cierre:
            errores.append("Debe definir al menos un rango de horario de atención.")
        if not self._platillos:
            errores.append("Debe registrar al menos un platillo.")
        for p in self._platillos:
            if not p["nombre"] or p["precio"] is None or p["precio"] <= 0:
                errores.append(f"El platillo '{p['nombre']}' requiere nombre y precio > $0.")
        return errores

    def build(self):
        return {
            "nombre_restaurante": self._nombre,
            "direccion": self._direccion,
            "descripcion": self._descripcion,
            "hora_apertura": self._hora_apertura,
            "hora_cierre": self._hora_cierre,
            "platillos": self._platillos,
        }

class EstrategiaRedireccion(ABC):
    @abstractmethod
    def pantalla_destino(self) -> str:
        ...


class RedireccionCliente(EstrategiaRedireccion):
    def pantalla_destino(self):
        return "PANEL_CLIENTE"


class RedireccionChef(EstrategiaRedireccion):
    def pantalla_destino(self):
        return "PANEL_CHEF"


class RedireccionAdmin(EstrategiaRedireccion):
    def pantalla_destino(self):
        return "PANEL_ADMIN"


def resolver_estrategia_redireccion(rol: str) -> EstrategiaRedireccion:
    return {
        "CLIENTE": RedireccionCliente(),
        "CHEF": RedireccionChef(),
        "ADMINISTRADOR": RedireccionAdmin(),
    }[rol]


class EstrategiaEntrega(ABC):
    @abstractmethod
    def requiere_direccion(self) -> bool:
        ...

    @abstractmethod
    def accion_despacho(self) -> str:
        ...


class EntregaDomicilio(EstrategiaEntrega):
    def requiere_direccion(self):
        return True

    def accion_despacho(self):
        return "Despachar pedido"


class EntregaRecoger(EstrategiaEntrega):
    def requiere_direccion(self):
        return False

    def accion_despacho(self):
        return "Marcar como listo"


def resolver_estrategia_entrega(tipo_entrega: str) -> EstrategiaEntrega:
    return {"DOMICILIO": EntregaDomicilio(), "RECOGER": EntregaRecoger()}[tipo_entrega]

class Comando(ABC):
    @abstractmethod
    def ejecutar(self):
        ...


class ComandoAprobarChef(Comando):
    def __init__(self, chef_service, restaurante_id, admin_id):
        self.chef_service = chef_service
        self.restaurante_id = restaurante_id
        self.admin_id = admin_id
        self._ejecutado = False

    def ejecutar(self):
        if self._ejecutado:
            return  # idempotencia
        self.chef_service.aprobar(self.restaurante_id, self.admin_id)
        self._ejecutado = True


class ComandoIniciarPreparacion(Comando):
    """HU-16: Comando idempotente -- doble clic no debe romper el estado."""
    def __init__(self, order_service, pedido_id, chef_id):
        self.order_service = order_service
        self.pedido_id = pedido_id
        self.chef_id = chef_id
        self._ejecutado = False

    def ejecutar(self):
        if self._ejecutado:
            return {"ok": True, "info": "Comando ya ejecutado (ignorado por idempotencia)."}
        resultado = self.order_service.iniciar_preparacion(self.pedido_id, self.chef_id)
        self._ejecutado = True
        return resultado

class OrderValidatorFacade:
    def __init__(self, db):
        self.db = db

    def validate(self, carrito: list, restaurante_id: int):
        """carrito: lista de dicts {producto_id, cantidad}
        Retorna (es_valido: bool, items_fallidos: list[dict])"""
        fallidos = []
        restaurante = self.db.query_one(
            "SELECT * FROM restaurantes WHERE id=? AND estado='PUBLICADO'", (restaurante_id,)
        )
        if restaurante is None:
            return False, [{"error": "El restaurante no está publicado."}]

        for item in carrito:
            producto = self.db.query_one(
                "SELECT * FROM productos WHERE id=? AND esta_activo=1", (item["producto_id"],)
            )
            if producto is None or producto["inventario"] < item["cantidad"]:
                fallidos.append({
                    "producto_id": item["producto_id"],
                    "nombre": producto["nombre"] if producto else "Desconocido",
                    "disponible": producto["inventario"] if producto else 0,
                    "solicitado": item["cantidad"],
                })
        return (len(fallidos) == 0), fallidos


class PaymentErrorFacade:
    """HU-14: traduce respuestas técnicas de la pasarela a mensajes simples."""
    MENSAJES = {
        "INSUFFICIENT_FUNDS": "Tu tarjeta no tiene fondos suficientes.",
        "EXPIRED_CARD": "Tu tarjeta está vencida.",
        "INVALID_CARD": "Los datos de la tarjeta no son válidos.",
        "TIMEOUT": "La pasarela de pagos no respondió a tiempo. Intenta de nuevo.",
        "GENERIC_DECLINE": "El banco rechazó la transacción. Intenta con otro método de pago.",
    }

    @classmethod
    def traducir(cls, codigo_error: str) -> str:
        return cls.MENSAJES.get(codigo_error, cls.MENSAJES["GENERIC_DECLINE"])

class Sujeto:
    def __init__(self):
        self._observadores = []

    def suscribir(self, observador_callable):
        self._observadores.append(observador_callable)

    def desuscribir(self, observador_callable):
        if observador_callable in self._observadores:
            self._observadores.remove(observador_callable)

    def notificar(self, evento: str, datos: dict):
        for obs in list(self._observadores):
            try:
                obs(evento, datos)
            except Exception:
                pass  # un observador roto no debe tumbar la publicación


class CanalEventos:
    """Implementa un mini Pub/Sub global en memoria (simula WebSockets/colas
    de mensajería mencionadas en HU-11 y HU-18: canales por restaurante_id
    y por cliente_id)."""
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia.sujeto = Sujeto()
        return cls._instancia

    def publicar(self, evento: str, datos: dict):
        self.sujeto.notificar(evento, datos)

    def suscribir(self, callback):
        self.sujeto.suscribir(callback)


def get_canal_eventos() -> CanalEventos:
    return CanalEventos()

TRANSICIONES_VALIDAS = {
    "PENDIENTE_CHEF": {"PAGADO", "RECHAZADO"},
    "PAGADO": {"EN_PREPARACION", "EN_DISPUTA"},
    "EN_PREPARACION": {"EN_TRANSITO", "LISTO_PARA_RECOGER", "EN_DISPUTA"},
    "EN_TRANSITO": {"COMPLETADO", "EN_DISPUTA"},
    "LISTO_PARA_RECOGER": {"COMPLETADO", "EN_DISPUTA"},
    "COMPLETADO": {"EN_DISPUTA"},
    "EN_DISPUTA": {"RESUELTO_REEMBOLSO", "REEMBOLSADO", "RESUELTO_RECHAZADO", "COMPLETADO"},
    "RECHAZADO": set(),
    "REEMBOLSADO": set(),
}


class TransicionInvalidaError(Exception):
    pass


class PedidoEstadoMachine:
    """Valida que un pedido (Orden) solo se mueva a estados alcanzables desde
    su estado actual, según la máquina de estados definida en el BPMN."""

    @staticmethod
    def puede_transicionar(estado_actual: str, estado_nuevo: str) -> bool:
        return estado_nuevo in TRANSICIONES_VALIDAS.get(estado_actual, set())

    @staticmethod
    def transicionar(estado_actual: str, estado_nuevo: str) -> str:
        if not PedidoEstadoMachine.puede_transicionar(estado_actual, estado_nuevo):
            raise TransicionInvalidaError(
                f"No se puede pasar de '{estado_actual}' a '{estado_nuevo}'."
            )
        return estado_nuevo

class IPaymentAdapter(ABC):
    @abstractmethod
    def cobrar(self, payment_dto, timeout_segundos: float = 5.0) -> dict:
        """Retorna dict: {aprobado: bool, id_transaccion: str|None, error: str|None}"""
        ...


class MockGatewayAdapter(IPaymentAdapter):

    def cobrar(self, payment_dto, timeout_segundos: float = 5.0) -> dict:
        import time as _time
        import uuid

        if payment_dto.tipo_pago in ("TARJETA_CREDITO", "TARJETA_DEBITO"):
            numero = payment_dto.numero_tarjeta.replace(" ", "")
            # Reglas determinísticas para pruebas:
            if numero.endswith("0000"):
                return {"aprobado": False, "id_transaccion": None, "error": "INSUFFICIENT_FUNDS"}
            if numero.endswith("9999"):
                _time.sleep(min(timeout_segundos, 1.0))
                return {"aprobado": False, "id_transaccion": None, "error": "TIMEOUT"}
            if payment_dto.fecha_expiracion and payment_dto.fecha_expiracion.startswith("00"):
                return {"aprobado": False, "id_transaccion": None, "error": "EXPIRED_CARD"}

        elif payment_dto.tipo_pago == "PSE":
            # Simula un banco caído si el usuario selecciona "Banco de Pruebas (rechaza)"
            if "rechaza" in (payment_dto.banco or "").lower():
                return {"aprobado": False, "id_transaccion": None, "error": "GENERIC_DECLINE"}

        elif payment_dto.tipo_pago == "TRANSFERENCIA":
            # Simula comprobante inválido si termina en "000"
            if (payment_dto.numero_referencia or "").endswith("000"):
                return {"aprobado": False, "id_transaccion": None, "error": "INVALID_CARD"}

        # Camino feliz
        return {
            "aprobado": True,
            "id_transaccion": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "error": None,
        }

class CatalogoIterator:
    def __init__(self, productos: list):
        self._productos = productos
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self._productos):
            raise StopIteration
        item = self._productos[self._index]
        self._index += 1
        return item

    def hay_siguiente(self):
        return self._index < len(self._productos)
