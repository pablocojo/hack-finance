"""
Plantillas de motivos y de hechos aprendidos (personalizacion.md §4.5 y §4.6).

Frases cortas en segunda persona. Nunca valoran a un tercero: los contactos salen enmascarados
(«Marcos R.») y solo como ámbito de una preferencia del propio usuario.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from ..plataforma.privacidad import enmascarar_nombre
from ..plataforma.tipos import PerfilUsuario, Propuesta, Silencio

if TYPE_CHECKING:  # pragma: no cover
    from ..plataforma.tipos import ModeloUsuario
    from .politica import Calculo

ETIQUETAS = {
    "cargo_duplicado": "cobros duplicados",
    "renovacion_proxima": "renovaciones",
    "subida_recibo": "subidas de recibos",
    "saldo_negativo_previsto": "saldo en negativo",
    "posible_estafa": "posibles estafas",
    "gasto_compartido": "gastos compartidos",
    "ingreso_extra": "ingresos extra",
    "viaje_detectado": "viajes",
    "prueba_gratuita": "pruebas gratuitas",
}

GENERICO = "Decido según lo que te puede ahorrar y cómo has respondido a avisos parecidos."
SIN_CONSENTIMIENTO = "No me has dado permiso para avisarte, así que no te molesto."
NO_AHORRA = "No te ahorra dinero ni te protege, así que no te interrumpo."
URGENTE_SIN_TOPE = "Es urgente: no cuenta para tu máximo de avisos al día."
AL_RESUMEN = "Merece la pena verlo, pero no tanto como para interrumpirte: lo dejo en el resumen."
EXPLORACION = "Aún sé poco de estos avisos; te lo dejo en el resumen por si te sirve."
NO_COMPENSA = "Por cómo has respondido a avisos parecidos, no compensa molestarte con esto."
DINERO_DEBIDO = "Es dinero que te deben: si no se reclama, se olvida."
PREGUNTA_UN_TOQUE = "Es solo una pregunta que se contesta con un toque: molesta menos que un aviso que pide hacer algo."
FRIO = "Aún no sé si estos avisos te interesan; decido por lo que te puede ahorrar."


def etiqueta(tipo: str) -> str:
    return ETIQUETAS.get(tipo, tipo.replace("_", " "))


def euros(valor: Decimal) -> str:
    """12.99 -> «12,99 €»; 24.00 -> «24 €»; 1850 -> «1.850 €»."""
    v = Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    entero = v == v.to_integral_value()
    texto = f"{v:,.0f}" if entero else f"{v:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def numero(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}".replace(".", ",")


def nombre_entidad(propuesta: Propuesta) -> str | None:
    if propuesta.contraparte:
        return f"con {enmascarar_nombre(propuesta.contraparte)}"
    if propuesta.comercio:
        return f"de {propuesta.comercio}"
    return None


# --- Reglas duras -----------------------------------------------------------------------------

def modulo_inactivo(modulo_id: str) -> str:
    return f"No tienes activado este tipo de aviso ({modulo_id}), así que no te molesto."


def silencio(s: Silencio, propuesta: Propuesta, estafa: bool = False) -> str:
    if s.ambito == "tipo":
        base = f"Me pediste no avisarte de {etiqueta(s.valor)}"
    elif s.ambito == "comercio":
        base = f"Me pediste no avisarte de {propuesta.comercio or s.valor}"
    else:
        base = f"Me pediste no avisarte de los gastos con {enmascarar_nombre(propuesta.contraparte or s.valor).rstrip('.')}"
    if estafa:
        return base + "; como puede ser una estafa, lo dejo en el resumen sin interrumpirte."
    return base + "."


def fuera_de_franja(modelo: "ModeloUsuario", ahora: datetime) -> str:
    p = modelo.preferencias
    return (f"Son las {ahora:%H:%M}, fuera de tu horario de avisos (de {p.hora_inicio} a {p.hora_fin} h); "
            "lo dejo en el resumen.")


def tope_diario(n: int) -> str:
    veces = "1 vez" if n == 1 else f"{n} veces"
    return f"Hoy ya te he avisado {veces}; lo dejo en el resumen."


def proteccion(propuesta: Propuesta) -> str:
    if propuesta.tipo_momento == "prueba_gratuita":
        quien = f"Tu prueba de {propuesta.comercio}" if propuesta.comercio else "Tu prueba gratuita"
        return f"{quien} pasará a cobrarse: siempre te lo enseño."
    return "Puede protegerte de un cobro o un fraude: siempre te lo enseño."


# --- Valor y contexto personal ----------------------------------------------------------------

def valor(propuesta: Propuesta, perfil: PerfilUsuario | None) -> str | None:
    if propuesta.contexto_personal:
        return propuesta.contexto_personal
    v = propuesta.valor_estimado_eur
    if v is None or v <= 0:
        if propuesta.tipo_momento in ("prueba_gratuita", "posible_estafa") or propuesta.urgencia == "alta":
            return proteccion(propuesta)
        return None
    if perfil and v > 2 * perfil.ticket_tipico:
        return f"Para ti, {euros(v)} es más del doble de una compra típica ({euros(perfil.ticket_tipico)})."
    donde = f" ({propuesta.comercio})" if propuesta.comercio else ""
    return f"Están en juego {euros(v)}{donde}."


# --- Lo aprendido -----------------------------------------------------------------------------

def _descripcion(clave: str, propuesta: Propuesta) -> str:
    if clave == "global":
        return "mis avisos"
    base = f"los avisos de {etiqueta(propuesta.tipo_momento)}"
    if "|b:" in clave:
        return f"{base} de este importe"
    if "|e:" in clave:
        ent = nombre_entidad(propuesta)
        return f"{base} {ent}" if ent else base
    return base


def aprendido(propuesta: Propuesta, cal: "Calculo") -> str:
    """El nivel que más se aleja del anterior (con n ≥ 1); en frío, la frase de arranque."""
    candidatos = [n for n in cal.niveles if n.celda.n >= 1]
    if not candidatos:
        texto = FRIO
    else:
        nivel = max(candidatos, key=lambda n: abs(n.media - n.previo))
        desc = _descripcion(nivel.clave, propuesta)
        cuenta = f"({numero(nivel.celda.utiles)} de {nivel.celda.n})"
        if nivel.media >= nivel.previo:
            texto = f"Sueles resolver {desc} {cuenta}."
        else:
            texto = f"Pocas veces te sirven {desc} {cuenta}."
    if cal.c < propuesta.confianza:
        texto = texto[:-1] + "; y me has marcado errores en avisos así."
    return texto


# --- Hechos derivados y de preferencias -------------------------------------------------------

def hecho_celda(clave: str, util: bool) -> str:
    """«Sueles resolver los avisos de gastos compartidos» / «… no suelen servirte»."""
    tipo = clave[2:].split("|", 1)[0]
    desc = f"los avisos de {etiqueta(tipo)}"
    if "|b:" in clave:
        desc += f" de importe {clave.split('|b:', 1)[1]}"
    if util:
        return f"Sueles resolver {desc}."
    return f"{desc[0].upper()}{desc[1:]} no suelen servirte."


def hecho_silencio(ambito: str, valor_txt: str, visible: str | None = None) -> str:
    if ambito == "tipo":
        return f"No quieres avisos de {etiqueta(valor_txt)}."
    if ambito == "comercio":
        return f"No quieres avisos de {visible or valor_txt}."
    return f"No quieres avisos de gastos con {enmascarar_nombre(visible or valor_txt).rstrip('.')}."
