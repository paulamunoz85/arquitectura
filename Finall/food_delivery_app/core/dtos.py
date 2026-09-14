from dataclasses import dataclass
import re

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TIPOS_PAGO_CON_TARJETA = ("TARJETA_CREDITO", "TARJETA_DEBITO")
TIPOS_PAGO_VALIDOS = ("TARJETA_CREDITO", "TARJETA_DEBITO", "PSE", "TRANSFERENCIA")


@dataclass
class UserRegistrationDTO:
    nombre: str
    correo_electronico: str
    contrasena: str

    def validar(self):
        errores = []
        if not self.nombre or len(self.nombre.strip()) < 2:
            errores.append("El nombre es obligatorio (mínimo 2 caracteres).")
        if not self.correo_electronico or not EMAIL_REGEX.match(self.correo_electronico):
            errores.append("Correo electrónico inválido u obligatorio.")
        if not self.contrasena or len(self.contrasena) < 4:
            errores.append("La contraseña es obligatoria (mínimo 4 caracteres).")
        return errores


@dataclass
class ChefRegistrationDTO:
    nombre: str
    correo_electronico: str
    contrasena: str
    nombre_restaurante: str
    direccion: str
    descripcion: str = ""

    def validar(self):
        errores = []
        if not self.nombre or len(self.nombre.strip()) < 2:
            errores.append("El nombre es obligatorio (mínimo 2 caracteres).")
        if not self.correo_electronico or not EMAIL_REGEX.match(self.correo_electronico):
            errores.append("Correo electrónico inválido u obligatorio.")
        if not self.contrasena or len(self.contrasena) < 4:
            errores.append("La contraseña es obligatoria (mínimo 4 caracteres).")
        if not self.nombre_restaurante:
            errores.append("El nombre del restaurante es obligatorio.")
        if not self.direccion:
            errores.append("La dirección es obligatoria.")
        return errores


@dataclass
class PaymentDTO:
    monto: float
    tipo_pago: str = "TARJETA_CREDITO"
    numero_tarjeta: str = ""
    fecha_expiracion: str = ""
    cvv: str = ""
    banco: str = ""
    numero_referencia: str = ""

    def validar(self):
        errores = []
        if self.tipo_pago not in TIPOS_PAGO_VALIDOS:
            errores.append("Tipo de pago inválido.")
            return errores

        if self.monto is None or self.monto <= 0:
            errores.append("Monto inválido.")

        if self.tipo_pago in TIPOS_PAGO_CON_TARJETA:
            numero = (self.numero_tarjeta or "").replace(" ", "")
            if not numero.isdigit() or len(numero) not in (15, 16):
                errores.append("Número de tarjeta inválido (15-16 dígitos).")
            if not re.match(r"^\d{2}/\d{2}$", self.fecha_expiracion or ""):
                errores.append("Fecha de expiración inválida (MM/AA).")
            if not (self.cvv or "").isdigit() or len(self.cvv) not in (3, 4):
                errores.append("CVV inválido.")
        elif self.tipo_pago == "PSE":
            if not self.banco:
                errores.append("Debes seleccionar el banco para pagar con PSE.")
        elif self.tipo_pago == "TRANSFERENCIA":
            if not self.banco:
                errores.append("Debes indicar el banco de origen de la transferencia.")
            if not self.numero_referencia or len(self.numero_referencia.strip()) < 4:
                errores.append("Debes ingresar el número de comprobante de la transferencia.")
        return errores

    def referencia(self) -> str:
        """Dato corto que identifica el medio de pago para 'detalle_pago.referencia_pago'."""
        if self.tipo_pago in TIPOS_PAGO_CON_TARJETA:
            numero = (self.numero_tarjeta or "").replace(" ", "")
            return f"Tarjeta terminada en {numero[-4:]}" if numero else "Tarjeta"
        if self.tipo_pago == "PSE":
            return f"PSE - {self.banco}"
        if self.tipo_pago == "TRANSFERENCIA":
            return f"{self.banco} - comprobante {self.numero_referencia}"
        return ""
