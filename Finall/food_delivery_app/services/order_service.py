from datetime import datetime

from core.database import get_db
from core.patterns import (
    OrderValidatorFacade, get_canal_eventos, PedidoEstadoMachine,
    TransicionInvalidaError, ComandoIniciarPreparacion, resolver_estrategia_entrega,
)


class OrderError(Exception):
    pass


COMISION_PORCENTAJE = 0.10  


class OrderService:
    def __init__(self):
        self.db = get_db()
        self.canal = get_canal_eventos()

    # ---------------- HU-09: Validar Stock (Facade) ----------------
    def validar_carrito(self, carrito: list, restaurante_id: int):
        facade = OrderValidatorFacade(self.db)
        return facade.validate(carrito, restaurante_id)

    # ---------------- HU-09/10/11: crear pedido tras validar ----------------
    def crear_pedido(self, cliente_id: int, restaurante_id: int, carrito: list,
                      tipo_entrega: str, direccion_entrega: str = None):
        es_valido, fallidos = self.validar_carrito(carrito, restaurante_id)
        if not es_valido:
            # HU-10: notificar qué productos fallaron, sin crear el pedido
            raise OrderError("Stock insuficiente: " + "; ".join(
                f"{f.get('nombre','?')} (disponible {f.get('disponible','?')}, "
                f"solicitado {f.get('solicitado','?')})" for f in fallidos
            ))

        productos = {p["id"]: p for p in self.db.query(
            "SELECT * FROM productos WHERE restaurante_id=?", (restaurante_id,)
        )}
        items = []
        subtotal = 0.0
        for item in carrito:
            producto = productos[item["producto_id"]]
            sub = round(producto["precio"] * item["cantidad"], 2)
            subtotal += sub
            items.append({
                "producto_id": producto["id"], "precio_unitario": producto["precio"],
                "cantidad": item["cantidad"], "subtotal": sub,
            })
        subtotal = round(subtotal, 2)
        comision = round(subtotal * COMISION_PORCENTAJE, 2)
        total = round(subtotal + comision, 2)

        now = datetime.now().isoformat()
        statements = [
            ("INSERT INTO pedidos (cliente_id, restaurante_id, tipo_entrega, direccion_entrega, "
             "subtotal, monto_comision, monto_total, estado, fecha_creacion, fecha_actualizacion) "
             "VALUES (?,?,?,?,?,?,?, 'PENDIENTE_CHEF', ?, ?)",
             (cliente_id, restaurante_id, tipo_entrega, direccion_entrega, subtotal, comision,
              total, now, now)),
        ]
        pedido_id = self.db.transaction(statements)
        for it in items:
            self.db.execute(
                "INSERT INTO detalles_pedido (pedido_id, producto_id, precio_unitario, cantidad, subtotal) "
                "VALUES (?,?,?,?,?)",
                (pedido_id, it["producto_id"], it["precio_unitario"], it["cantidad"], it["subtotal"]),
            )
            # Descuenta stock reservado de forma optimista
            self.db.execute(
                "UPDATE productos SET inventario = inventario - ? WHERE id=?",
                (it["cantidad"], it["producto_id"]),
            )
        self.db.log_evento(pedido_id, cliente_id, "PEDIDO_CREADO", f"Total: {total}")

        # HU-11: notificación push (Observer/Pub-Sub) al panel del chef
        self.canal.publicar("NUEVO_PEDIDO_CHEF", {
            "restaurante_id": restaurante_id, "pedido_id": pedido_id, "monto_total": total,
        })
        return pedido_id

    def aceptar_pedido(self, pedido_id: int, chef_id: int):
        """El chef decide si puede preparar el pedido (ver notas de HU-11 y HU-12:
        'Cliente al que ya le aceptaron el pedido'). No cambia el estado en la BD
        (sigue 'PENDIENTE_CHEF', que ya significa 'Esperando confirmación del Chef'),
        pero deja constancia y habilita al cliente a proceder con el pago."""
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise OrderError("Pedido no encontrado.")
        if pedido["estado"] != "PENDIENTE_CHEF":
            raise OrderError("Solo se pueden aceptar pedidos en estado 'Esperando confirmación del Chef'.")
        self.db.log_evento(pedido_id, chef_id, "PEDIDO_ACEPTADO_CHEF", "")
        self.canal.publicar("PEDIDO_ACEPTADO_CLIENTE", {"pedido_id": pedido_id})
        return {"ok": True}

    def rechazar_pedido(self, pedido_id: int, chef_id: int, motivo: str = ""):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise OrderError("Pedido no encontrado.")
        nuevo_estado = PedidoEstadoMachine.transicionar(pedido["estado"], "RECHAZADO")
        # Devuelve el stock reservado al rechazar el pedido
        detalles = self.db.query("SELECT * FROM detalles_pedido WHERE pedido_id=?", (pedido_id,))
        for d in detalles:
            self.db.execute("UPDATE productos SET inventario = inventario + ? WHERE id=?",
                             (d["cantidad"], d["producto_id"]))
        self._actualizar_estado(pedido_id, nuevo_estado)
        self.db.log_evento(pedido_id, chef_id, "PEDIDO_RECHAZADO_CHEF", motivo)
        self.canal.publicar("ACTUALIZACION_PEDIDO_CLIENTE", {"pedido_id": pedido_id, "estado": nuevo_estado})
        return {"ok": True}

    def pedido_fue_aceptado(self, pedido_id: int) -> bool:
        fila = self.db.query_one(
            "SELECT id FROM historial_estados WHERE pedido_id=? AND evento='PEDIDO_ACEPTADO_CHEF'", (pedido_id,)
        )
        return fila is not None

    # ---------------- HU-16: Preparar Pedido ----------------
    def iniciar_preparacion_comando(self, pedido_id: int, chef_id: int):
        """Punto de entrada que usa el Patrón Command (idempotente ante doble clic)."""
        comando = ComandoIniciarPreparacion(self, pedido_id, chef_id)
        return comando.ejecutar()

    def iniciar_preparacion(self, pedido_id: int, chef_id: int):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise OrderError("Pedido no encontrado.")
        if pedido["estado"] == "EN_PREPARACION":
            return {"ok": True, "estado": "EN_PREPARACION", "info": "Ya estaba en preparación."}
        if pedido["estado"] != "PAGADO":
            raise OrderError("Solo se puede iniciar preparación de pedidos en estado 'PAGADO'.")

        nuevo_estado = PedidoEstadoMachine.transicionar(pedido["estado"], "EN_PREPARACION")
        self._actualizar_estado(pedido_id, nuevo_estado)
        self.db.log_evento(pedido_id, chef_id, "PREPARACION_INICIADA", "")
        # Refleja el cambio en la vista de tracking del cliente sin recargar (HU-16)
        self.canal.publicar("ACTUALIZACION_PEDIDO_CLIENTE", {
            "pedido_id": pedido_id, "estado": nuevo_estado,
        })
        return {"ok": True, "estado": nuevo_estado}

    # ---------------- HU-17: Despachar / Recoger ----------------
    def despachar_o_marcar_listo(self, pedido_id: int, chef_id: int):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise OrderError("Pedido no encontrado.")
        if pedido["estado"] != "EN_PREPARACION":
            raise OrderError("El pedido debe estar 'En preparación' para despachar/marcar listo.")

        estrategia = resolver_estrategia_entrega(pedido["tipo_entrega"])
        nuevo_estado = "EN_TRANSITO" if pedido["tipo_entrega"] == "DOMICILIO" else "LISTO_PARA_RECOGER"
        nuevo_estado = PedidoEstadoMachine.transicionar(pedido["estado"], nuevo_estado)
        self._actualizar_estado(pedido_id, nuevo_estado)
        self.db.log_evento(pedido_id, chef_id, "DESPACHO_EJECUTADO", estrategia.accion_despacho())

        # ---------------- HU-18: Notificar Avance ----------------
        mensaje = (f"En camino a {pedido['direccion_entrega']}" if nuevo_estado == "EN_TRANSITO"
                   else "Listo para retiro en el local")
        self.canal.publicar("ACTUALIZACION_PEDIDO_CLIENTE", {
            "pedido_id": pedido_id, "estado": nuevo_estado, "mensaje": mensaje,
        })
        return {"ok": True, "estado": nuevo_estado, "mensaje": mensaje}

    # ---------------- HU-19: Confirmar Recepción ----------------
    def confirmar_recepcion(self, pedido_id: int, cliente_id: int):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise OrderError("Pedido no encontrado.")
        if pedido["cliente_id"] != cliente_id:
            raise OrderError("No autorizado: este pedido no pertenece al usuario autenticado.")
        if pedido["estado"] not in ("EN_TRANSITO", "LISTO_PARA_RECOGER"):
            raise OrderError("El pedido no está en un estado válido para confirmar recepción.")

        nuevo_estado = PedidoEstadoMachine.transicionar(pedido["estado"], "COMPLETADO")
        self._actualizar_estado(pedido_id, nuevo_estado)
        self.db.log_evento(pedido_id, cliente_id, "RECEPCION_CONFIRMADA", "")
        self.canal.publicar("PEDIDO_COMPLETADO", {"pedido_id": pedido_id})
        return {"ok": True, "estado": nuevo_estado}

    # ---------------- utilidades ----------------
    def _actualizar_estado(self, pedido_id: int, nuevo_estado: str):
        self.db.execute(
            "UPDATE pedidos SET estado=?, fecha_actualizacion=? WHERE id=?",
            (nuevo_estado, datetime.now().isoformat(), pedido_id),
        )

    def listar_pedidos_de_chef(self, restaurante_id: int, estados=None):
        if estados:
            placeholders = ",".join("?" * len(estados))
            return self.db.query(
                f"SELECT * FROM pedidos WHERE restaurante_id=? AND estado IN ({placeholders}) "
                "ORDER BY fecha_creacion DESC",
                (restaurante_id, *estados),
            )
        return self.db.query(
            "SELECT * FROM pedidos WHERE restaurante_id=? ORDER BY fecha_creacion DESC", (restaurante_id,)
        )

    def listar_pedidos_de_cliente(self, cliente_id: int):
        return self.db.query(
            "SELECT p.*, r.nombre_restaurante FROM pedidos p "
            "JOIN restaurantes r ON r.id = p.restaurante_id "
            "WHERE p.cliente_id=? ORDER BY p.fecha_creacion DESC", (cliente_id,)
        )

    def detalle_pedido(self, pedido_id: int):
        cabecera = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        detalles = self.db.query(
            "SELECT d.*, pr.nombre FROM detalles_pedido d "
            "JOIN productos pr ON pr.id = d.producto_id WHERE d.pedido_id=?", (pedido_id,)
        )
        return cabecera, detalles
