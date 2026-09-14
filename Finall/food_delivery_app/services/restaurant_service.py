from datetime import datetime, time as dtime

from core.database import get_db
from core.patterns import RestauranteBuilder, CatalogoIterator, resolver_estrategia_entrega


class RestaurantError(Exception):
    pass


class RestaurantService:
    def __init__(self):
        self.db = get_db()

    # ---------------- HU-06 ----------------
    def obtener_restaurante_por_usuario(self, usuario_id: int):
        return self.db.query_one("SELECT * FROM restaurantes WHERE usuario_id=?", (usuario_id,))

    def configurar_perfil_y_menu(self, usuario_id: int, nombre, direccion, descripcion,
                                  hora_apertura, hora_cierre, platillos: list):
        builder = RestauranteBuilder().con_datos_generales(nombre, direccion, descripcion) \
                                       .con_horario(hora_apertura, hora_cierre)
        for p in platillos:
            builder.agregar_platillo(p["nombre"], p.get("descripcion", ""), p["precio"], p["inventario"])

        errores = builder.validar()
        if errores:
            raise RestaurantError(" / ".join(errores))

        datos = builder.build()
        restaurante = self.obtener_restaurante_por_usuario(usuario_id)
        if restaurante is None:
            raise RestaurantError("No existe un restaurante asociado a este usuario.")

        statements = [
            ("UPDATE restaurantes SET nombre_restaurante=?, direccion=?, descripcion=?, "
             "hora_apertura=?, hora_cierre=?, estado='PUBLICADO' WHERE id=?",
             (datos["nombre_restaurante"], datos["direccion"], datos["descripcion"],
              datos["hora_apertura"], datos["hora_cierre"], restaurante["id"])),
        ]
        for plato in datos["platillos"]:
            statements.append((
                "INSERT INTO productos (restaurante_id, nombre, descripcion, precio, inventario, "
                "esta_activo, fecha_creacion) VALUES (?,?,?,?,?,1,?)",
                (restaurante["id"], plato["nombre"], plato["descripcion"], plato["precio"],
                 plato["inventario"], datetime.now().isoformat())
            ))
        self.db.transaction(statements)
        return True

    # ---------------- HU-07 ----------------
    def listar_restaurantes_publicados(self):
        """Solo restaurantes 'Publicado' y (opcionalmente) en horario de atención."""
        ahora = datetime.now().time()
        filas = self.db.query("SELECT * FROM restaurantes WHERE estado='PUBLICADO'")
        resultado = []
        for r in filas:
            en_horario = True
            if r["hora_apertura"] and r["hora_cierre"]:
                try:
                    apertura = dtime.fromisoformat(r["hora_apertura"])
                    cierre = dtime.fromisoformat(r["hora_cierre"])
                    en_horario = apertura <= ahora <= cierre
                except ValueError:
                    en_horario = True
            resultado.append(dict(r) | {"en_horario": en_horario})
        return resultado

    def listar_productos(self, restaurante_id: int):
        productos = self.db.query(
            "SELECT * FROM productos WHERE restaurante_id=? AND esta_activo=1", (restaurante_id,)
        )
        # Uso explícito del Patrón Iterator para recorrer el catálogo (HU-07)
        return list(CatalogoIterator([dict(p) for p in productos]))

    @staticmethod
    def calcular_subtotal(carrito_con_precios: list) -> float:
        return round(sum(item["precio"] * item["cantidad"] for item in carrito_con_precios), 2)

    # ---------------- HU-08 ----------------
    @staticmethod
    def validar_tipo_entrega(tipo_entrega: str, direccion_entrega: str):
        estrategia = resolver_estrategia_entrega(tipo_entrega)
        if estrategia.requiere_direccion() and not (direccion_entrega or "").strip():
            raise RestaurantError("Debe ingresar la dirección de entrega para la modalidad Domicilio.")
        return True
