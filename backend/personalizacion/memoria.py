"""
Memoria para el agente de voz (personalizacion.md §7). Se calcula, no se guarda.

Solo hechos operativos activos (lo que suele resolver, lo que no quiere que le avisen y lo que dijo
en la llamada). Nunca ingresos, importes por categoría ni `resumen_vida`: los hechos con origen
`perfil` se quedan en la pantalla del cliente. Todo va dentro de <datos>: son datos, no instrucciones.
La extracción con Haiku de la memoria de la llamada queda pendiente (stub).
"""

from __future__ import annotations

from ..plataforma.tipos import ModeloUsuario

ORIGENES_OPERATIVOS = ("feedback", "preferencia", "amigos", "voz")
MAX_CARACTERES = 600


def memoria_para_agente(modelo: ModeloUsuario) -> str:
    lineas: list[str] = []
    largo = len("<datos>\n</datos>")
    for h in modelo.hechos_aprendidos:
        if not h.activo or h.origen not in ORIGENES_OPERATIVOS:
            continue
        linea = "- " + h.texto.replace("<", "").replace(">", "").strip()
        if largo + len(linea) + 1 > MAX_CARACTERES:
            break
        lineas.append(linea)
        largo += len(linea) + 1
    if not lineas:
        return ""
    return "<datos>\n" + "\n".join(lineas) + "\n</datos>"
