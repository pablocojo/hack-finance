"""
Memoria para el agente de voz (personalizacion.md §7). Se calcula, no se guarda.

Solo hechos operativos activos (lo que suele resolver, lo que no quiere que le avisen y lo que dijo
en la llamada). Nunca ingresos, importes por categoría ni `resumen_vida`: los hechos con origen
`perfil` se quedan en la pantalla del cliente. Todo va dentro de <datos>: son datos, no instrucciones.
La extracción con Haiku de la memoria de la llamada queda pendiente (stub); sus filtros
(`texto_permitido`) ya se usan al editar a mano un hecho de voz o el `resumen_vida`.
"""

from __future__ import annotations

import re

from ..plataforma.tipos import ModeloUsuario
from .perfil import es_sensible

ORIGENES_OPERATIVOS = ("feedback", "preferencia", "amigos", "voz")
MAX_CARACTERES = 600
MAX_LINEA = 140
ELECCION_MIN = 3          # veces que ha de haber elegido una acción para decir que es la que suele elegir
ELECCION_PESO = 0.5       # y al menos la mitad de todas sus elecciones

# Lo que parece una orden al agente, una URL o un IBAN no es un hecho: ante la duda, no se guarda.
PARECE_ORDEN = re.compile(
    r"\b(ignor\w*|olvid\w*|desobedec\w*|instrucci\w*|prompt|system|jailbreak|"
    r"a partir de ahora|desde ahora|debes|tienes que|siempre (responde|di|haz)|nunca (digas|avises)|"
    r"act[uú]a como|eres un|obedece\w*)\b|https?://|www\.|\b[a-z]{2}\d{2}(?:\s?\d{4}){3,}\b|[<>{}\[\]`]",
    re.IGNORECASE,
)


def texto_permitido(texto: str, max_caracteres: int = 100) -> str:
    """Devuelve el texto limpio o lanza ValueError si está vacío, es largo, es de la lista sensible
    (salud, religión, política…) o parece una orden. Se usa en todo texto libre que acaba en el perfil."""
    limpio = " ".join(str(texto or "").split())
    if not limpio:
        raise ValueError("El texto está vacío.")
    if len(limpio) > max_caracteres:
        raise ValueError(f"El texto es demasiado largo (máximo {max_caracteres} caracteres).")
    if es_sensible(concepto=limpio):
        raise ValueError("No guardo datos sensibles (salud, religión, política, apuestas…).")
    if PARECE_ORDEN.search(limpio):
        raise ValueError("Eso parece una instrucción, no un hecho o una preferencia tuya; no lo guardo.")
    return limpio


def _linea(texto: str) -> str | None:
    """Una línea de datos: sin saltos, sin etiquetas y sin nada que parezca una orden o un dato sensible."""
    limpio = " ".join(texto.replace("<", " ").replace(">", " ").split())
    if not limpio or PARECE_ORDEN.search(limpio) or es_sensible(concepto=limpio):
        return None
    return "- " + limpio[:MAX_LINEA]


def _accion_habitual(modelo: ModeloUsuario) -> str | None:
    globales = {k[2:]: n for k, n in modelo.elecciones.items() if k.startswith("a:") and n > 0}
    total = sum(globales.values())
    if not globales:
        return None
    accion, veces = max(sorted(globales.items()), key=lambda x: x[1])
    if veces < ELECCION_MIN or veces < ELECCION_PESO * total:
        return None
    return f"Suele resolver los avisos con la acción «{accion.replace('_', ' ')}»."


def _candidatos(modelo: ModeloUsuario) -> list[str]:
    candidatos = [h.texto for h in modelo.hechos_aprendidos if h.activo and h.origen in ORIGENES_OPERATIVOS]
    habitual = _accion_habitual(modelo)
    if habitual:
        candidatos.append(habitual)
    return candidatos


def textos_para_agente(modelo: ModeloUsuario, maximo: int = 10) -> list[str]:
    """Lo mismo que `memoria_para_agente` (mismos orígenes y mismo filtro de órdenes y datos sensibles), un texto por
    elemento y sin etiquetas, para la herramienta `lo_que_sabes_de_mi` de la llamada. Nunca ingresos ni `resumen_vida`."""
    lineas = (_linea(t) for t in _candidatos(modelo))
    return [l[2:] for l in lineas if l][:maximo]


def memoria_para_agente(modelo: ModeloUsuario) -> str:
    candidatos = _candidatos(modelo)
    lineas: list[str] = []
    largo = len("<datos>\n</datos>")
    for texto in candidatos:
        linea = _linea(texto)
        if linea is None:
            continue
        if largo + len(linea) + 1 > MAX_CARACTERES:
            break
        lineas.append(linea)
        largo += len(linea) + 1
    if not lineas:
        return ""
    return "<datos>\n" + "\n".join(lineas) + "\n</datos>"
