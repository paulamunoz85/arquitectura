import hashlib
from PIL import Image, ImageDraw, ImageTk, ImageFont

_CACHE = {}

PALETA_AVATARES = [
    ("#E8452C", "#FFDCD3"),  # tomate
    ("#3AA655", "#DFF3E3"),  # verde
    ("#F4A340", "#FDEBD1"),  # naranja
    ("#3E7CB1", "#DCEBF7"),  # azul
    ("#8E5AC8", "#EBE0F7"),  # morado
    ("#D64580", "#FBDCE9"),  # rosa
]


def _color_para(texto: str):
    h = int(hashlib.md5(texto.encode("utf-8")).hexdigest(), 16)
    return PALETA_AVATARES[h % len(PALETA_AVATARES)]


def _fuente(tamano):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", tamano)
    except Exception:
        return ImageFont.load_default()


def _circulo(draw, box, fill):
    draw.ellipse(box, fill=fill)


def _dibujar_icono_categoria(draw, cx, cy, r, categoria, color_principal):
    """Dibuja un glifo simple según la categoría del platillo."""
    blanco = "#FFFFFF"
    if categoria == "pizza":
        draw.pieslice([cx - r, cy - r, cx + r, cy + r], -20, 100, fill=blanco)
        for ang, rr in [(20, 0.35), (55, 0.55), (80, 0.25)]:
            import math
            ax = cx + math.cos(math.radians(ang - 20)) * r * rr
            ay = cy + math.sin(math.radians(ang - 20)) * r * rr
            draw.ellipse([ax - r * 0.08, ay - r * 0.08, ax + r * 0.08, ay + r * 0.08], fill=color_principal)
    elif categoria == "hamburguesa":
        w = r * 1.5
        draw.rounded_rectangle([cx - w / 2, cy - r * 0.6, cx + w / 2, cy - r * 0.15], radius=r * 0.25, fill=blanco)
        draw.rectangle([cx - w / 2, cy - r * 0.1, cx + w / 2, cy + r * 0.1], fill=color_principal)
        draw.rounded_rectangle([cx - w / 2, cy + r * 0.15, cx + w / 2, cy + r * 0.55], radius=r * 0.2, fill=blanco)
    elif categoria == "ensalada":
        draw.arc([cx - r * 0.9, cy - r * 0.5, cx + r * 0.9, cy + r * 0.9], 200, 340, fill=blanco, width=int(r * 0.18))
        for dx, dy in [(-0.3, -0.2), (0.1, -0.35), (0.35, -0.05)]:
            draw.ellipse([cx + dx * r - r * 0.15, cy + dy * r - r * 0.15,
                          cx + dx * r + r * 0.15, cy + dy * r + r * 0.15], fill=blanco)
    elif categoria == "bebida":
        w = r * 0.9
        draw.polygon([(cx - w / 2, cy - r * 0.7), (cx + w / 2, cy - r * 0.7),
                      (cx + w * 0.35, cy + r * 0.7), (cx - w * 0.35, cy + r * 0.7)], fill=blanco)
        draw.rectangle([cx - w * 0.5, cy - r * 0.85, cx + w * 0.5, cy - r * 0.65], fill=blanco)
    elif categoria == "postre":
        draw.polygon([(cx, cy - r * 0.7), (cx + r * 0.65, cy + r * 0.6),
                      (cx - r * 0.65, cy + r * 0.6)], fill=blanco)
        draw.ellipse([cx - r * 0.12, cy - r * 0.9, cx + r * 0.12, cy - r * 0.66], fill=color_principal)
    else:  # plato genérico (tenedor y cuchillo)
        draw.line([cx - r * 0.35, cy - r * 0.6, cx - r * 0.35, cy + r * 0.6], fill=blanco, width=int(r * 0.14))
        draw.line([cx - r * 0.5, cy - r * 0.6, cx - r * 0.5, cy - r * 0.1], fill=blanco, width=int(r * 0.1))
        draw.line([cx - r * 0.2, cy - r * 0.6, cx - r * 0.2, cy - r * 0.1], fill=blanco, width=int(r * 0.1))
        draw.line([cx + r * 0.35, cy - r * 0.6, cx + r * 0.35, cy + r * 0.6], fill=blanco, width=int(r * 0.16))


def categoria_por_nombre(nombre: str) -> str:
    n = (nombre or "").lower()
    if any(k in n for k in ("pizza",)):
        return "pizza"
    if any(k in n for k in ("hamburguesa", "burger")):
        return "hamburguesa"
    if any(k in n for k in ("ensalada", "salad", "vegetal", "vegano")):
        return "ensalada"
    if any(k in n for k in ("jugo", "gaseosa", "bebida", "limonada", "malteada", "cerveza", "café", "cafe")):
        return "bebida"
    if any(k in n for k in ("postre", "torta", "pastel", "helado", "dulce", "flan")):
        return "postre"
    return "plato"


def miniatura_producto(nombre: str, size: int = 64):
    clave = ("producto", nombre, size)
    if clave in _CACHE:
        return _CACHE[clave]
    categoria = categoria_por_nombre(nombre)
    principal, suave = _color_para(nombre)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = int(size * 0.06)
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=int(size * 0.28), fill=principal)
    _dibujar_icono_categoria(draw, size / 2, size / 2, size * 0.30, categoria, principal)
    foto = ImageTk.PhotoImage(img)
    _CACHE[clave] = foto
    return foto


def avatar_restaurante(nombre: str, size: int = 72):
    clave = ("restaurante", nombre, size)
    if clave in _CACHE:
        return _CACHE[clave]
    principal, suave = _color_para(nombre)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _circulo(draw, [0, 0, size - 1, size - 1], suave)
    _circulo(draw, [size * 0.08, size * 0.08, size * 0.92, size * 0.92], principal)
    iniciales = "".join([p[0] for p in (nombre or "R").split()[:2]]).upper() or "R"
    fuente = _fuente(int(size * 0.34))
    bbox = draw.textbbox((0, 0), iniciales, font=fuente)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((size / 2 - tw / 2 - bbox[0], size / 2 - th / 2 - bbox[1]), iniciales, fill="#FFFFFF", font=fuente)
    foto = ImageTk.PhotoImage(img)
    _CACHE[clave] = foto
    return foto


def logo_app(size: int = 96):
    clave = ("logo", size)
    if clave in _CACHE:
        return _CACHE[clave]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _circulo(draw, [0, 0, size - 1, size - 1], "#E8452C")
    r = size * 0.30
    cx, cy = size / 2, size / 2
    blanco = "#FFFFFF"
    draw.line([cx - r * 0.35, cy - r * 0.9, cx - r * 0.35, cy + r * 0.9], fill=blanco, width=max(2, int(r * 0.16)))
    draw.line([cx - r * 0.55, cy - r * 0.9, cx - r * 0.55, cy - r * 0.15], fill=blanco, width=max(2, int(r * 0.12)))
    draw.line([cx - r * 0.15, cy - r * 0.9, cx - r * 0.15, cy - r * 0.15], fill=blanco, width=max(2, int(r * 0.12)))
    draw.line([cx + r * 0.45, cy - r * 0.9, cx + r * 0.45, cy + r * 0.9], fill=blanco, width=max(2, int(r * 0.2)))
    draw.pieslice([cx + r * 0.15, cy - r * 0.9, cx + r * 0.75, cy - r * 0.3], 0, 360, fill=blanco)
    foto = ImageTk.PhotoImage(img)
    _CACHE[clave] = foto
    return foto


def estrella(size: int = 16, llena: bool = True):
    clave = ("estrella", size, llena)
    if clave in _CACHE:
        return _CACHE[clave]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    import math
    cx, cy, r_ext, r_int = size / 2, size / 2, size * 0.48, size * 0.20
    puntos = []
    for i in range(10):
        ang = math.radians(-90 + i * 36)
        r = r_ext if i % 2 == 0 else r_int
        puntos.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    color = "#F2C230" if llena else "#E4DDD3"
    draw.polygon(puntos, fill=color)
    foto = ImageTk.PhotoImage(img)
    _CACHE[clave] = foto
    return foto


def badge_circulo(color_hex: str, size: int = 12):
    clave = ("badge", color_hex, size)
    if clave in _CACHE:
        return _CACHE[clave]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _circulo(draw, [1, 1, size - 2, size - 2], color_hex)
    foto = ImageTk.PhotoImage(img)
    _CACHE[clave] = foto
    return foto
