"""
Ciclo de vida de las pruebas gratuitas (motor.md §3.5). Aquí vive lo que cambia el estado del motor;
el detector `prueba_gratuita` solo lee el resultado (`ctx.pruebas`) y decide cuándo avisar.

`sincronizar` se llama desde `procesar`, una vez por día y solo con el pasado (`historial` tiene fecha <= hoy):
1. **Alta por verificación**: una autorización de 0 €, o de <= 1 € que se devuelve en <= 5 días, de un comercio
   de suscripciones, sin cargos suyos > 1 € en 365 días (si no, es un cambio de tarjeta), que no esté en
   `perfil.suscripciones_activas` con `en_prueba = false` y sin una prueba ya abierta o cerrada.
   Si la ficha del comercio no está en la caché se pide (`comercios_pendientes`) y se reevalúa cada día;
   sin ficha vale la categoría `suscripciones` por reglas (con confianza máxima 0,55 en el detector).
2. **Fusión**: una verificación a +-3 días de una prueba que dijo el cliente es la misma (rellena `verificacion_id`).
3. **Cierre**: `cobrada` (entra un cargo > 1 € del comercio entre el alta y el primer cobro + 7 días) y
   `caducada` (pasa ese plazo sin cargo). `cancelada` y `baja_guiada` las pone `cerrar_prueba`.

Una prueba es un `dict` JSON puro (se guarda con `exportar_estado`):
`{comercio, fecha_alta, dias, fuente: verificacion|usuario, estado, registrada, cerrada, verificacion_id, evidencias}`.
Los nombres de comercio son datos: solo se comparan y se usan como clave.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from ..plataforma.tipos import InfoComercio, MovimientoEnriquecido, PerfilUsuario
from .normalizar import PASARELAS_OPACAS
from .parametros import PruebaGratuita

ABIERTAS = ("abierta", "baja_guiada")


# --- Duración y fechas -----------------------------------------------------------------------

def ficha_util(info: InfoComercio | None) -> InfoComercio | None:
    """Una ficha que sirve para decidir: la que no es `desconocido`."""
    return info if info is not None and info.origen != "desconocido" else None


def duracion(prueba: dict, info: InfoComercio | None, p: PruebaGratuita) -> tuple[int, str]:
    """(`dias_prueba`, `fuente_duracion`): lo que dijo el cliente > la ficha (`catalogo` o `web`) > 30 días."""
    if prueba.get("dias"):
        return int(prueba["dias"]), "usuario"
    ficha = ficha_util(info)
    if ficha is not None and ficha.dias_prueba and ficha.dias_prueba > 0:
        return int(ficha.dias_prueba), ficha.origen
    return p.DIAS_PRUEBA_POR_DEFECTO, "por_defecto"


def fecha_primer_cobro(prueba: dict, info: InfoComercio | None, p: PruebaGratuita) -> date:
    dias, _ = duracion(prueba, info, p)
    return date.fromisoformat(prueba["fecha_alta"]) + timedelta(days=dias)


def buscable(nombre: str | None, etiquetas: list[str] | tuple[str, ...], p: PruebaGratuita) -> bool:
    """Solo se busca en la web el nombre de un comercio: corto, sin dígitos, sin ser una persona ni una
    pasarela que oculta el comercio (`APPLE`, `GOOGLE`, `PAYPAL`)."""
    if not nombre or len(nombre) > p.MAX_CARACTERES_BUSQUEDA or any(c.isdigit() for c in nombre):
        return False
    if "posible_persona" in etiquetas or nombre in PASARELAS_OPACAS or nombre == "PAYPAL":
        return False
    return True


# --- Altas por verificación ------------------------------------------------------------------

def _es_cobro(m: MovimientoEnriquecido, p: PruebaGratuita) -> bool:
    return m.tipo_operacion == "cargo" and m.importe < 0 and abs(m.importe) > p.IMPORTE_MAX_VERIF


def verificaciones(historial: list[MovimientoEnriquecido], p: PruebaGratuita
                   ) -> list[tuple[MovimientoEnriquecido, MovimientoEnriquecido | None]]:
    """(verificación, su devolución) de lo que ya se ve: 0 €, o <= 1 € con una devolución del mismo comercio e
    importe en <= `VENTANA_DEVOLUCION_VERIF` días. Una de 1 € sin devolución no cuenta."""
    salida = []
    for v in historial:
        if v.tipo_operacion != "verificacion" or not v.comercio_normalizado or v.canal not in ("tarjeta", None):
            continue
        if v.importe == 0:
            salida.append((v, None))
        elif v.importe < 0 and abs(v.importe) <= p.IMPORTE_MAX_VERIF:
            limite = v.fecha + timedelta(days=p.VENTANA_DEVOLUCION_VERIF)
            dev = next((d for d in historial if d.importe == -v.importe and v.fecha <= d.fecha <= limite
                        and d.comercio_normalizado == v.comercio_normalizado and d.id != v.id), None)
            if dev is not None:
                salida.append((v, dev))
    return salida


def _prueba_cercana(pruebas: list[dict], comercio: str, dia: date, p: PruebaGratuita) -> dict | None:
    """La prueba del comercio (en cualquier estado) cuyo alta está a menos de `DIAS_SIN_SERIE` días de `dia`."""
    for prueba in pruebas:
        if prueba["comercio"] == comercio and abs((date.fromisoformat(prueba["fecha_alta"]) - dia).days) < p.DIAS_SIN_SERIE:
            return prueba
    return None


def _en_suscripciones_activas(perfil: PerfilUsuario | None, comercio: str) -> bool:
    """«Ya se paga»: en la lista del perfil y fuera de prueba (las entradas `en_prueba` se ignoran)."""
    return perfil is not None and any(s.comercio == comercio and not s.en_prueba for s in perfil.suscripciones_activas)


def _alta(v: MovimientoEnriquecido, dev: MovimientoEnriquecido | None, hoy: date) -> dict:
    return {
        "comercio": v.comercio_normalizado, "fecha_alta": v.fecha.isoformat(), "dias": None, "fuente": "verificacion",
        "estado": "abierta", "registrada": hoy.isoformat(), "cerrada": None, "verificacion_id": v.id,
        "evidencias": [v.id] + ([dev.id] if dev is not None else []),
    }


def sincronizar(
    estado,
    historial: list[MovimientoEnriquecido],
    hoy: date,
    perfil: PerfilUsuario | None,
    p: PruebaGratuita,
    conocimiento: Callable[[str], InfoComercio | None],
) -> None:
    """Pone al día `estado.pruebas` y `estado.comercios_pendientes` con lo que se ve hasta `hoy`."""
    pendientes: list[str] = []

    def pedir(nombre: str, etiquetas) -> None:
        if nombre not in pendientes and buscable(nombre, etiquetas, p):
            pendientes.append(nombre)

    # 1 y 2. Altas por verificación y fusión con lo que dijo el cliente.
    for v, dev in verificaciones(historial, p):
        comercio = v.comercio_normalizado
        if (hoy - v.fecha).days > p.DIAS_ALTA_MAX:
            continue
        existente = _prueba_cercana(estado.pruebas, comercio, v.fecha, p)
        if existente is not None:
            if (existente["fuente"] == "usuario" and not existente.get("verificacion_id")
                    and abs((date.fromisoformat(existente["fecha_alta"]) - v.fecha).days) <= p.DIAS_FUSION_USUARIO):
                existente["verificacion_id"] = v.id
                existente["evidencias"] = [v.id] + ([dev.id] if dev is not None else [])
            continue
        if "posible_persona" in v.etiquetas or comercio in PASARELAS_OPACAS:
            continue
        desde = v.fecha - timedelta(days=p.DIAS_SIN_SERIE)
        if any(m.comercio_normalizado == comercio and _es_cobro(m, p) and desde <= m.fecha < v.fecha for m in historial):
            continue                                            # ya lo pagaba: cambio de tarjeta
        if _en_suscripciones_activas(perfil, comercio):
            continue
        info = conocimiento(comercio)
        ficha = ficha_util(info)
        if ficha is not None and not ficha.es_suscripcion:
            continue                                            # una tienda que guarda la tarjeta
        if info is None:
            pedir(comercio, v.etiquetas)
        if ficha is None and (v.categoria or "") != "suscripciones":
            continue                                            # sin ficha, solo vale la categoría por reglas
        estado.pruebas.append(_alta(v, dev, hoy))

    # 3. Cierres: cobrada (también desde baja guiada) o caducada.
    for prueba in estado.pruebas:
        if prueba["estado"] not in ABIERTAS:
            continue
        info = conocimiento(prueba["comercio"])
        alta = date.fromisoformat(prueba["fecha_alta"])
        limite = fecha_primer_cobro(prueba, info, p) + timedelta(days=p.DIAS_GRACIA_COBRO)
        if any(m.comercio_normalizado == prueba["comercio"] and _es_cobro(m, p) and alta <= m.fecha <= limite
               for m in historial):
            prueba.update(estado="cobrada", cerrada=hoy.isoformat())
        elif prueba["estado"] == "abierta" and hoy > limite:
            prueba.update(estado="caducada", cerrada=hoy.isoformat())
        elif prueba["estado"] == "abierta" and info is None:
            pedir(prueba["comercio"], ())                       # el cliente la dijo: se busca solo el nombre

    estado.comercios_pendientes = pendientes


# --- Lo que lee el detector ------------------------------------------------------------------

def confianza(prueba: dict, info: InfoComercio | None, fuente_duracion: str, p: PruebaGratuita) -> float:
    """0,60 + 0,20 (verificación explícita) + 0,10 (duración de catálogo o web) - 0,15 (por defecto);
    el cliente, 0,90; sin ficha del comercio, como mucho 0,55."""
    if prueba["fuente"] == "usuario":
        valor = p.CONFIANZA_USUARIO
    else:
        valor = p.CONFIANZA_BASE + p.CONFIANZA_VERIFICACION
        if fuente_duracion in ("catalogo", "web", "usuario"):
            valor += p.CONFIANZA_DURACION_CONOCIDA
        elif fuente_duracion == "por_defecto":
            valor += p.CONFIANZA_DURACION_SUPUESTA
    if ficha_util(info) is None and prueba["fuente"] != "usuario":
        valor = min(valor, p.CONFIANZA_SIN_CATALOGO_MAX)
    return min(round(valor, 2), p.CONFIANZA_MAX)


def importe_previsto(info: InfoComercio | None) -> Decimal | None:
    ficha = ficha_util(info)
    return ficha.precio_tras_prueba if ficha is not None else None
