from datetime import datetime

from core.database import get_db
from core.patterns import Sujeto


class ReviewError(Exception):
    pass


class ReviewService:
    def __init__(self):
        self.db = get_db()
        self._sujeto = Sujeto()
        self._sujeto.suscribir(self._recalcular_promedio)

    def calificar_pedido(self, pedido_id: int, cliente_id: int, puntuacion: int, comentario: str = ""):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise ReviewError("Pedido no encontrado.")
        if pedido["cliente_id"] != cliente_id:
            raise ReviewError("No autorizado para calificar este pedido.")
        if pedido["estado"] != "COMPLETADO":
            raise ReviewError("Solo se pueden calificar pedidos en estado 'Completado'.")
        if not (1 <= puntuacion <= 5):
            raise ReviewError("La puntuación debe estar entre 1 y 5 estrellas.")

        detalles = self.db.query("SELECT id FROM detalles_pedido WHERE pedido_id=?", (pedido_id,))
        if not detalles:
            raise ReviewError("El pedido no tiene detalle registrado; no se puede calificar.")

        existente = self.db.query_one("SELECT id FROM calificaciones WHERE pedido_id=?", (pedido_id,))
        if existente:
            raise ReviewError("Este pedido ya fue calificado (restricción única).")

        # Solo se guarda pedido_id: cliente y restaurante se derivan siempre por JOIN.
        self.db.execute(
            "INSERT INTO calificaciones (pedido_id, puntuacion, comentario, fecha_creacion) VALUES (?,?,?,?)",
            (pedido_id, puntuacion, comentario, datetime.now().isoformat()),
        )
        self._sujeto.notificar("NUEVA_CALIFICACION", {"restaurante_id": pedido["restaurante_id"]})
        return True

    def _recalcular_promedio(self, evento, datos):
        return self.promedio_restaurante(datos["restaurante_id"])

    def promedio_restaurante(self, restaurante_id: int):
        fila = self.db.query_one(
            "SELECT AVG(c.puntuacion) as promedio, COUNT(*) as total FROM calificaciones c "
            "JOIN pedidos p ON p.id = c.pedido_id WHERE p.restaurante_id=?",
            (restaurante_id,),
        )
        promedio = round(fila["promedio"], 2) if fila["promedio"] is not None else None
        return promedio, fila["total"]

    def listar_calificaciones_restaurante(self, restaurante_id: int):
        return self.db.query(
            "SELECT c.*, u.correo_electronico as cliente_correo FROM calificaciones c "
            "JOIN pedidos p ON p.id = c.pedido_id JOIN usuarios u ON u.id = p.cliente_id "
            "WHERE p.restaurante_id=? ORDER BY c.fecha_creacion DESC",
            (restaurante_id,),
        )


class DisputeService:
    ESTADOS_QUE_PERMITEN_DISPUTA = ("PAGADO", "EN_PREPARACION", "EN_TRANSITO", "LISTO_PARA_RECOGER", "COMPLETADO")

    def __init__(self):
        self.db = get_db()

    def abrir_disputa(self, pedido_id: int, motivo: str, creado_por_id: int, rol_creador: str):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise ReviewError("Pedido no encontrado.")
        if pedido["estado"] not in self.ESTADOS_QUE_PERMITEN_DISPUTA:
            raise ReviewError("Este pedido no está en un estado que permita abrir un reclamo.")
        if not motivo or not motivo.strip():
            raise ReviewError("Debes describir el motivo del reclamo.")

        if rol_creador == "CLIENTE" and pedido["cliente_id"] != creado_por_id:
            raise ReviewError("No autorizado: este pedido no pertenece al cliente autenticado.")

        ya_existe = self.db.query_one(
            "SELECT id FROM disputas WHERE pedido_id=? AND estado='PENDIENTE'", (pedido_id,)
        )
        if ya_existe:
            raise ReviewError("Ya existe un reclamo pendiente para este pedido.")

        self.db.transaction([
            ("INSERT INTO disputas (pedido_id, creado_por_id, motivo, estado, fecha_creacion) "
             "VALUES (?,?,?,?,?)",
             (pedido_id, creado_por_id, motivo.strip(), "PENDIENTE", datetime.now().isoformat())),
            ("UPDATE pedidos SET estado='EN_DISPUTA', fecha_actualizacion=? WHERE id=?",
             (datetime.now().isoformat(), pedido_id)),
        ])
        self.db.log_evento(pedido_id, creado_por_id, "DISPUTA_ABIERTA", f"Por {rol_creador}: {motivo.strip()}")
        return True

    def listar_disputas_pendientes(self):
        return self.db.query(
            "SELECT d.*, p.monto_total, u.nombre as creado_por_nombre, u.rol as creado_por_rol "
            "FROM disputas d JOIN pedidos p ON p.id = d.pedido_id "
            "LEFT JOIN usuarios u ON u.id = d.creado_por_id "
            "WHERE d.estado='PENDIENTE' ORDER BY d.fecha_creacion ASC"
        )

    def listar_disputas_de_pedido(self, pedido_id: int):
        return self.db.query(
            "SELECT * FROM disputas WHERE pedido_id=? ORDER BY fecha_creacion DESC", (pedido_id,)
        )

    def resolver_disputa(self, disputa_id: int, admin_id: int, aprobar_reembolso: bool, notas: str = ""):
        disputa = self.db.query_one("SELECT * FROM disputas WHERE id=?", (disputa_id,))
        if disputa is None:
            raise ReviewError("Disputa no encontrada.")
        estado_disputa = "RESUELTO_REEMBOLSO" if aprobar_reembolso else "RESUELTO_RECHAZADO"
        estado_pedido = "REEMBOLSADO" if aprobar_reembolso else "COMPLETADO"
        self.db.transaction([
            ("UPDATE disputas SET estado=?, administrador_id=?, notas_resolucion=? WHERE id=?",
             (estado_disputa, admin_id, notas, disputa_id)),
            ("UPDATE pedidos SET estado=?, fecha_actualizacion=? WHERE id=?",
             (estado_pedido, datetime.now().isoformat(), disputa["pedido_id"])),
        ])
        self.db.log_evento(disputa["pedido_id"], admin_id, "DISPUTA_RESUELTA",
                            f"{'A favor del cliente (reembolso)' if aprobar_reembolso else 'A favor del chef (rechazado)'}: {notas}")
        return True
