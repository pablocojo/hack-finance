"""
Enlaces y pasos de la baja guiada (modulos.md §6, «`cancelar_suscripcion` en detalle»).

Aquí solo se *valida y filtra* lo que ya está en la ficha del comercio (`InfoComercio`, de la caché: sin
red). Lo que llega de la web son datos, nunca instrucciones: la `url_baja` y los pasos pasan por estas
reglas antes de llegar a la tarjeta. **El servidor nunca hace una petición a la `url_baja`**: este módulo
no importa ninguna librería de red.

- `url_baja`: solo `https`, sin credenciales, sin IP, sin `xn--`, sin puerto raro, ≤ 200 caracteres.
  Con `origen: web` además su host debe coincidir con un dominio de las fuentes, y se muestra como texto
  («Compruébalo en la web oficial»), sin enlace. Con `origen: catalogo`, enlace normal.
- `pasos_baja`: como mucho 5 de 200 caracteres, texto plano. Se descartan los que tengan teléfonos, IBAN,
  correos, URL distintas de `url_baja` o verbos de pago.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

from ..modulos.plantillas import sanear_dato
from ..motor import conocimiento
from ..plataforma.tipos import DetalleBaja, InfoComercio

MAX_URL = 200
MAX_PASOS = 5
MAX_PASO = 200
TEXTO_URL_WEB = "Compruébalo en la web oficial"

_TLD = re.compile(r"[a-z]{2,24}")
_CONTROL = re.compile(r"[\s\x00-\x1f\x7f\\<>\"'`{}|^]")

# Patrones de los pasos: se aplican al texto sin tildes y en minúsculas.
_URL = re.compile(r"(?:https?:|ftp:|javascript:|data:|www\.)\S*|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|es|net|org|eu|io|app|co|info|example)\b\S*")
_CORREO = re.compile(r"\S+@\S+")
_IBAN = re.compile(r"\b[a-z]{2}\d{2}(?:[ -]?[a-z0-9]){10,30}\b")
_TELEFONO = re.compile(r"(?:\+|00)?\d(?:[ .\-]?\d){8,}")
_PAGO = re.compile(
    r"\b(?:transfier\w*|transfer\w*|pag(?:a|ar|ue|es|ando|o)|envi(?:a|ar|e|es|ando)|abon(?:a|ar|e|es)|ingres(?:a|ar|e|es)"
    r"|introduc\w*\s+(?:\w+\s+){0,6}tarjeta|numero\s+de\s+(?:tu\s+)?tarjeta|cvv|cvc|pin|bizum)\b")


def _sin_tildes(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).casefold()


def _host(url: str) -> str | None:
    """Host en minúsculas de una URL aceptable (https, sin credenciales ni puerto raro); si no, `None`."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL or _CONTROL.search(url):
        return None
    try:
        p = urlsplit(url)
        puerto = p.port
    except ValueError:
        return None
    if p.scheme != "https" or "@" in p.netloc or p.username is not None or p.password is not None:
        return None
    if puerto not in (None, 443):
        return None
    host = (p.hostname or "").rstrip(".").casefold()
    if not host or not host.isascii() or "[" in p.netloc or ":" in host:
        return None
    try:
        ipaddress.ip_address(host)
        return None                              # IP
    except ValueError:
        pass
    etiquetas = host.split(".")
    if len(etiquetas) < 2 or any(not e or e.startswith("-") or e.endswith("-") or not re.fullmatch(r"[a-z0-9-]+", e)
                                 for e in etiquetas):
        return None
    if any(e.startswith("xn--") for e in etiquetas):
        return None                              # IDN: posible homógrafo
    if not _TLD.fullmatch(etiquetas[-1]):
        return None                              # 127.1, 0x7f.1, 2130706433.es...
    return host


def _dominio(host: str) -> str:
    return host.removeprefix("www.")


def _hosts_fuentes(fuentes: list[str]) -> set[str]:
    salida = set()
    for f in fuentes or []:
        try:
            h = (urlsplit(str(f)).hostname or "").rstrip(".").casefold()
        except ValueError:
            continue
        if h and h.isascii():
            salida.add(_dominio(h))
    return salida


def validar_url_baja(url: str | None, origen: str = "catalogo", fuentes: list[str] | None = None) -> str | None:
    """La URL si es aceptable; si no, `None` (se omite en la tarjeta). Con `origen: web` su host debe ser un
    dominio de las fuentes (o subdominio suyo)."""
    if url is None:
        return None
    host = _host(url)
    if host is None:
        return None
    if origen == "web":
        d = _dominio(host)
        if not any(d == f or d.endswith("." + f) or f.endswith("." + d) for f in _hosts_fuentes(fuentes or [])):
            return None
    elif origen != "catalogo":
        return None                              # `desconocido` no trae enlace
    return url


def filtrar_pasos(pasos: list[str] | None, url_baja: str | None = None) -> list[str]:
    """Hasta 5 pasos de texto plano, de ≤ 200 caracteres; descarta los que no son seguros. Texto en claro:
    no pasa por plantillas ni por `dato`."""
    salida: list[str] = []
    for bruto in pasos or []:
        if len(salida) >= MAX_PASOS:
            break
        if not isinstance(bruto, str) or len(bruto) > MAX_PASO:
            continue
        paso = sanear_dato(bruto, maximo=MAX_PASO + 1)     # sin control, `{}<>` ni comillas
        if not paso or len(paso) > MAX_PASO:
            continue
        t = _sin_tildes(paso)
        if url_baja:
            t = t.replace(_sin_tildes(url_baja), " ")      # la URL de baja sí puede aparecer
        if _URL.search(t) or _CORREO.search(t) or _IBAN.search(t) or _TELEFONO.search(t) or _PAGO.search(t):
            continue
        salida.append(paso)
    return salida


def host_para_auditoria(detalle: DetalleBaja) -> str | None:
    """Solo el host (nunca la URL completa) para la auditoría."""
    return _host(detalle.url_baja) if detalle.url_baja else None


def detalle_desde_info(info: InfoComercio | None, comercio: str, bloquea_cobros: bool, canal: str = "tarjeta") -> DetalleBaja:
    url, pasos, origen = None, [], "desconocido"
    if info is not None and info.origen in ("catalogo", "web"):
        origen = info.origen
        url = validar_url_baja(info.url_baja, origen, info.fuentes)
        pasos = filtrar_pasos(info.pasos_baja, url)
    if not pasos:
        pasos = [f"Busca la baja en la web oficial de {sanear_dato(comercio)}."]
        if url is None:
            origen = "desconocido"
    return DetalleBaja(url_baja=url, url_es_enlace=bool(url) and origen == "catalogo", pasos=pasos,
                       bloquea_cobros=bloquea_cobros, canal=canal, fuente=origen)


def detalle_baja(comercio: str, bloquea_cobros: bool = False, canal: str = "tarjeta") -> DetalleBaja:
    """`DetalleBaja` del comercio a partir de la ficha en caché (catálogo o web). Sin red."""
    return detalle_desde_info(conocimiento.info_en_cache(comercio), comercio, bloquea_cobros, canal)
