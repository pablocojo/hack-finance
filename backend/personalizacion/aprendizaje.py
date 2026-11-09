"""
Qué hace cada `Feedback` (personalizacion.md §4.6). Todo puro: devuelve un modelo nuevo.

- `abrir_aviso`: al decidir `notificar_ahora` o `resumen`, guarda el `AvisoAbierto` con las claves
  usadas (para aprender después) y cuenta el aviso para el tope diario (la urgencia alta no cuenta).
- `aprender`: suma la respuesta a todas las claves del aviso y lo cierra (una respuesta por aviso).
  Después regenera los hechos derivados que se ven en «Lo que he aprendido de ti».
"""

from __future__ import annotations

from datetime import date

from ..plataforma.tipos import (
    AvisoAbierto,
    Celda,
    Decision,
    Feedback,
    HechoAprendido,
    ModeloUsuario,
    Propuesta,
    Silencio,
)
from . import motivos as M
from .politica import claves, es_clave_celda, normalizar

# Entradas informativas de `AvisoAbierto.claves` que no son celdas (para crear silencios).
INFO_COMERCIO = "comercio="
INFO_CONTACTO = "contacto="

# (útiles, molestias) que suma cada respuesta.
DELTAS: dict[str, tuple[float, float]] = {
    "resuelta": (1.0, 0.0),
    "vista_sin_accion": (0.5, 0.5),
    "rechazada": (0.0, 1.0),
    "no_avisar_tipo": (0.0, 1.0),
    "no_avisar_comercio": (0.0, 1.0),
    "no_avisar_contacto": (0.0, 1.0),
}
IGNORADA = {"notificar_ahora": 1.0, "resumen": 0.25}

HECHO_N_MIN = 3
HECHO_MEDIA_BAJA = 0.3
HECHO_MEDIA_ALTA = 0.75


def abrir_aviso(modelo: ModeloUsuario, propuesta: Propuesta, decision: Decision) -> ModeloUsuario:
    if decision.accion == "silenciar":
        return modelo
    nuevo = modelo.model_copy(deep=True)
    lista = claves(propuesta, modelo)
    if propuesta.comercio:
        lista.append(INFO_COMERCIO + propuesta.comercio)
    if propuesta.contraparte:
        lista.append(INFO_CONTACTO + propuesta.contraparte)
    nuevo.avisos_abiertos[propuesta.id] = AvisoAbierto(
        propuesta_id=propuesta.id, claves=lista, tipo_momento=propuesta.tipo_momento,
        accion=decision.accion, fecha=propuesta.creada,
    )
    if decision.accion == "notificar_ahora" and propuesta.urgencia != "alta":
        nuevo.ultimos_avisos = [*nuevo.ultimos_avisos, propuesta.creada][-50:]
    return nuevo


def _sumar(modelo: ModeloUsuario, lista: list[str], utiles: float, molestias: float, dia: date) -> None:
    for clave in lista:
        if not es_clave_celda(clave):
            continue
        celda = modelo.estadisticas.get(clave) or Celda()
        modelo.estadisticas[clave] = Celda(
            utiles=celda.utiles + utiles, molestias=celda.molestias + molestias, n=celda.n + 1, ultima=dia,
        )


def _info(aviso: AvisoAbierto, prefijo: str) -> str | None:
    for c in aviso.claves:
        if c.startswith(prefijo):
            return c[len(prefijo):]
    return None


def _silenciar(modelo: ModeloUsuario, aviso: AvisoAbierto, resultado: str, dia: date) -> None:
    ambito = resultado.removeprefix("no_avisar_")
    visible = None
    if ambito == "tipo":
        valor = aviso.tipo_momento
    else:
        visible = _info(aviso, INFO_COMERCIO if ambito == "comercio" else INFO_CONTACTO)
        valor = normalizar(visible)
        if not valor:
            return
    if any(s.ambito == ambito and normalizar(s.valor) == normalizar(valor) for s in modelo.preferencias.silencios):
        return
    modelo.preferencias.silencios.append(Silencio(ambito=ambito, valor=valor, desde=dia, origen=aviso.propuesta_id))
    clave = f"silencio:{ambito}:{valor}"
    modelo.hechos_aprendidos.append(HechoAprendido(
        id=f"h-{clave}", texto=M.hecho_silencio(ambito, valor, visible), creado=dia,
        origen="preferencia", clave=clave,
    ))


def hechos_derivados(modelo: ModeloUsuario, dia: date) -> None:
    """Tipo o tramo con n ≥ 3 y media ≤ 0,3 o ≥ 0,75. Conserva `activo` y `creado` de los que siguen."""
    previos = {h.id: h for h in modelo.hechos_aprendidos if h.origen == "feedback"}
    nuevos: list[HechoAprendido] = []
    for clave, celda in sorted(modelo.estadisticas.items()):
        if not clave.startswith("t:") or "|e:" in clave or celda.n < HECHO_N_MIN:
            continue
        total = celda.utiles + celda.molestias
        if total <= 0:
            continue
        media = celda.utiles / total
        if HECHO_MEDIA_BAJA < media < HECHO_MEDIA_ALTA:
            continue
        hid = f"h-{clave}"
        texto = M.hecho_celda(clave, util=media >= HECHO_MEDIA_ALTA)
        previo = previos.get(hid)
        # Un hecho apagado por el usuario reinició su celda: si vuelve a salir, es aprendizaje nuevo.
        nuevos.append(HechoAprendido(
            id=hid, texto=texto,
            creado=previo.creado if previo and previo.activo and previo.texto == texto else dia,
            origen="feedback", clave=clave,
        ))
    # Los apagados que no han vuelto a salir siguen a la vista (inactivos) hasta que los borre.
    apagados = [h for h in previos.values() if not h.activo and h.id not in {n.id for n in nuevos}]
    otros = [h for h in modelo.hechos_aprendidos if h.origen != "feedback"]
    modelo.hechos_aprendidos = otros + apagados + nuevos


def aprender(feedback: Feedback, modelo: ModeloUsuario) -> ModeloUsuario:
    """Pura: no guarda. Sin aviso abierto para esa propuesta, devuelve el modelo igual."""
    aviso = modelo.avisos_abiertos.get(feedback.propuesta_id)
    if aviso is None or feedback.usuario_id != modelo.usuario_id:
        return modelo
    nuevo = modelo.model_copy(deep=True)
    dia = feedback.fecha.date()
    r = feedback.resultado
    if r == "falso_positivo":
        nuevo.falsos_positivos[aviso.tipo_momento] = nuevo.falsos_positivos.get(aviso.tipo_momento, 0) + 1
    elif r == "ignorada":
        molestia = IGNORADA.get(aviso.accion, 0.0)
        if molestia:
            _sumar(nuevo, aviso.claves, 0.0, molestia, dia)
    else:
        utiles, molestias = DELTAS[r]
        _sumar(nuevo, aviso.claves, utiles, molestias, dia)
        if r.startswith("no_avisar_"):
            _silenciar(nuevo, aviso, r, dia)
    del nuevo.avisos_abiertos[feedback.propuesta_id]
    hechos_derivados(nuevo, dia)
    nuevo.actualizado = feedback.fecha
    return nuevo
