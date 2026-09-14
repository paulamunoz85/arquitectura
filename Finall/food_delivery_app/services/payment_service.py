from datetime import datetime

from core.database import get_db
from core.dtos import PaymentDTO
from core.patterns import (
    MockGatewayAdapter, PaymentErrorFacade, PedidoEstadoMachine, get_canal_eventos,
)


class PaymentError(Exception):
    def __init__(self, mensaje, codigo=None):
        super().__init__(mensaje)
        self.codigo = codigo


class PaymentService:
    def __init__(self, gateway_adapter=None):
        self.db = get_db()
        self.gateway: object = gateway_adapter or MockGatewayAdapter()
        self.canal = get_canal_eventos()

    # ---------------- HU-12: Ingresar Pago (validación DTO) ----------------
    def preparar_pago(self, pedido_id: int, tipo_pago: str, **campos_pago):
        """campos_pago acepta, según tipo_pago: numero_tarjeta, fecha_expiracion,
        cvv (tarjetas) | banco (PSE/transferencia) | numero_referencia (transferencia)."""
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise PaymentError("Pedido no encontrado.")
        if pedido["estado"] != "PENDIENTE_CHEF":
            raise PaymentError("Este pedido ya no está pendiente de pago.")

        from services.order_service import OrderService
        if not OrderService().pedido_fue_aceptado(pedido_id):
            raise PaymentError("El chef aún no ha aceptado este pedido.")

        dto = PaymentDTO(monto=pedido["monto_total"], tipo_pago=tipo_pago, **campos_pago)
        errores = dto.validar()
        if errores:
            raise PaymentError(" / ".join(errores))
        return dto

    # ---------------- HU-13: Procesar Pago ----------------
    def procesar_pago(self, pedido_id: int, dto: PaymentDTO):
        pedido = self.db.query_one("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if pedido is None:
            raise PaymentError("Pedido no encontrado.")

        # ---------------- HU-12: se guarda el DETALLE del pago ingresado ----------------
        detalle_pago_id = self.db.execute(
            "INSERT INTO detalle_pago (pedido_id, tipo_pago, monto, referencia_pago, fecha_registro) "
            "VALUES (?,?,?,?,?)",
            (pedido_id, dto.tipo_pago, dto.monto, dto.referencia(), datetime.now().isoformat()),
        ).lastrowid

        self.db.log_evento(
            pedido_id, pedido["cliente_id"], "INFO_FINANCIERA_ENVIADA_PASARELA",
            f"tipo_pago={dto.tipo_pago}, referencia={dto.referencia()}, monto={dto.monto}",
        )
        resultado = self.gateway.cobrar(dto, timeout_segundos=5.0)

        if not resultado["aprobado"]:
            # ---------------- HU-14: Notificar Error de Pago ----------------
            mensaje_amigable = PaymentErrorFacade.traducir(resultado["error"])
            self.db.execute(
                "INSERT INTO confirmacion_pago (detalle_pago_id, estado, id_transaccion, codigo_error, "
                "fecha_confirmacion) VALUES (?,?,?,?,?)",
                (detalle_pago_id, "FALLIDO", None, resultado["error"], datetime.now().isoformat()),
            )
            self.db.log_evento(pedido_id, pedido["cliente_id"], "PAGO_RECHAZADO", resultado["error"])
            raise PaymentError(mensaje_amigable, codigo=resultado["error"])

        # ---------------- HU-15: Cambiar Estado a Pagado (transacción ACID) ----------------
        nuevo_estado = PedidoEstadoMachine.transicionar(pedido["estado"], "PAGADO")
        self.db.transaction([
            ("INSERT INTO confirmacion_pago (detalle_pago_id, estado, id_transaccion, codigo_error, "
             "fecha_confirmacion) VALUES (?,?,?,?,?)",
             (detalle_pago_id, "APROBADO", resultado["id_transaccion"], None, datetime.now().isoformat())),
            ("UPDATE pedidos SET estado=?, fecha_actualizacion=? WHERE id=?",
             (nuevo_estado, datetime.now().isoformat(), pedido_id)),
        ])
        self.db.log_evento(pedido_id, pedido["cliente_id"], "PAGO_APROBADO", resultado["id_transaccion"])

        # ---------------- Generar y "enviar" el recibo/ticket digital ----------------
        recibo_texto = self._generar_texto_recibo(pedido_id, dto, resultado["id_transaccion"])
        existente = self.db.query_one("SELECT id FROM recibos WHERE pedido_id=?", (pedido_id,))
        if existente is None:
            self.db.execute(
                "INSERT INTO recibos (pedido_id, contenido, fecha_generacion) VALUES (?,?,?)",
                (pedido_id, recibo_texto, datetime.now().isoformat()),
            )
        self.db.log_evento(pedido_id, pedido["cliente_id"], "RECIBO_GENERADO_Y_ENVIADO", "")

        # Habilita el botón "Iniciar preparación" en el panel del chef
        self.canal.publicar("PEDIDO_PAGADO_CHEF", {
            "restaurante_id": pedido["restaurante_id"], "pedido_id": pedido_id,
        })
        return {"ok": True, "id_transaccion": resultado["id_transaccion"], "estado": nuevo_estado,
                "recibo": recibo_texto}

    def historial_pago(self, pedido_id: int):
        """JOIN detalle_pago + confirmacion_pago para mostrar el historial completo."""
        return self.db.query(
            "SELECT dp.*, cp.estado, cp.id_transaccion, cp.codigo_error, cp.fecha_confirmacion "
            "FROM detalle_pago dp LEFT JOIN confirmacion_pago cp ON cp.detalle_pago_id = dp.id "
            "WHERE dp.pedido_id=? ORDER BY dp.fecha_registro DESC", (pedido_id,)
        )

    def obtener_recibo(self, pedido_id: int):
        fila = self.db.query_one("SELECT * FROM recibos WHERE pedido_id=?", (pedido_id,))
        return fila["contenido"] if fila else None

    # ---------------- Recibo / ticket digital (RNF HU-13) ----------------
    def _generar_texto_recibo(self, pedido_id: int, dto: PaymentDTO, id_transaccion: str) -> str:
        pedido = self.db.query_one(
            "SELECT p.*, r.nombre_restaurante, u.nombre as cliente_nombre, u.correo_electronico "
            "FROM pedidos p JOIN restaurantes r ON r.id = p.restaurante_id "
            "JOIN usuarios u ON u.id = p.cliente_id WHERE p.id=?", (pedido_id,)
        )
        detalles = self.db.query(
            "SELECT d.*, pr.nombre FROM detalles_pedido d JOIN productos pr ON pr.id = d.producto_id "
            "WHERE d.pedido_id=?", (pedido_id,)
        )
        lineas = [
            "=" * 42,
            "        SABORLOCAL — RECIBO DE COMPRA",
            "=" * 42,
            f"Pedido:        #{pedido_id}",
            f"Restaurante:   {pedido['nombre_restaurante']}",
            f"Cliente:       {pedido['cliente_nombre'] or pedido['correo_electronico']}",
            f"Fecha:         {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "-" * 42,
        ]
        for d in detalles:
            lineas.append(f"{d['cantidad']} x {d['nombre']:<22} ${d['subtotal']:>10,.0f}")
        lineas += [
            "-" * 42,
            f"Subtotal:      ${pedido['subtotal']:>10,.0f}",
            f"Comisión:      ${pedido['monto_comision']:>10,.0f}",
            f"TOTAL:         ${pedido['monto_total']:>10,.0f}",
            "-" * 42,
            f"Medio de pago: {dto.tipo_pago} ({dto.referencia()})",
            f"Transacción:   {id_transaccion}",
            f"Entrega:       {'Domicilio' if pedido['tipo_entrega']=='DOMICILIO' else 'Recoger en el local'}",
            "=" * 42,
            "   ¡Gracias por tu compra en SaborLocal!",
            "=" * 42,
        ]
        return "\n".join(lineas)
