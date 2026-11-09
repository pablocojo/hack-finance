"""
Orden de las acciones (personalizacion.md §5): primero la que sueles elegir en ese tipo de momento.

En una frase: «cuento qué acción eliges en cada tipo de aviso y pongo arriba la que más eliges;
si aún sé poco, me fío de lo que eliges en general y, sin datos, del orden del módulo».

    g_a = (n_a + 1) / (N + K)               # global con Laplace; K = acciones ofrecidas
    s_a = (n_{t,a} + 2·g_a) / (n_t + 2)     # por tipo, encogida hacia la global

Solo reordena `acciones_ofrecidas`: nunca añade, quita ni cambia una acción ni sus `limites`.
Se aprende por tipo de momento, no por módulo: un módulo nuevo hereda lo aprendido.
"""

from __future__ import annotations

from ..plataforma.tipos import ModeloUsuario, Propuesta, ResultadoAccion
from .motivos import etiqueta

PRIOR_TIPO = 2          # peso de la global dentro de cada tipo
MIN_VECES_FRASE = 2     # desde aquí se le dice al agente que la proponga primero

NOMBRES_ACCION = {
    "pedir_bizum": "pedir un Bizum",
    "cancelar_suscripcion": "cancelar la suscripción",
    "bloquear_comercio": "bloquear el comercio",
    "reclamar_cargo": "reclamar el cargo",
    "mover_dinero": "mover dinero",
    "recordar": "recordar",
}
_FEMENINO = {"renovaciones", "subidas de recibos", "posibles estafas", "pruebas gratuitas"}


def clave_tipo(tipo: str, accion: str) -> str:
    return f"t:{tipo}|a:{accion}"


def clave_global(accion: str) -> str:
    return f"a:{accion}"


def _en_los(tipo: str) -> str:
    nombre = etiqueta(tipo)
    if nombre == "saldo en negativo":
        return "los avisos de saldo en negativo"
    return f"{'las' if nombre in _FEMENINO else 'los'} {nombre}"


def puntuaciones(propuesta: Propuesta, modelo: ModeloUsuario) -> dict[str, float]:
    """`s_a` de cada acción ofrecida (para tests y explicaciones)."""
    elecciones = modelo.elecciones
    ofrecidas = [a.accion_id for a in propuesta.acciones_ofrecidas]
    total = sum(v for k, v in elecciones.items() if k.startswith("a:"))
    prefijo = f"t:{propuesta.tipo_momento}|a:"
    total_tipo = sum(v for k, v in elecciones.items() if k.startswith(prefijo))
    salida = {}
    for accion in ofrecidas:
        g = (elecciones.get(clave_global(accion), 0) + 1) / (total + len(ofrecidas))
        salida[accion] = (elecciones.get(clave_tipo(propuesta.tipo_momento, accion), 0) + PRIOR_TIPO * g) / (
            total_tipo + PRIOR_TIPO)
    return salida


def frase_preferida(propuesta: Propuesta, modelo: ModeloUsuario) -> str | None:
    """«Sueles elegir recordar en las renovaciones (3 de 4).» si la primera se eligió >= 2 veces."""
    if not propuesta.acciones_ofrecidas:
        return None
    primera = propuesta.acciones_ofrecidas[0].accion_id
    veces = modelo.elecciones.get(clave_tipo(propuesta.tipo_momento, primera), 0)
    if veces < MIN_VECES_FRASE:
        return None
    prefijo = f"t:{propuesta.tipo_momento}|a:"
    total_tipo = sum(v for k, v in modelo.elecciones.items() if k.startswith(prefijo))
    return (f"Sueles elegir {NOMBRES_ACCION.get(primera, primera)} en {_en_los(propuesta.tipo_momento)} "
            f"({veces} de {total_tipo}).")


def ordenar_acciones(propuesta: Propuesta, modelo: ModeloUsuario) -> Propuesta:
    """Pura. Orden por `s_a` descendente; empates y arranque en frío, el orden del módulo."""
    s = puntuaciones(propuesta, modelo)
    indices = sorted(range(len(propuesta.acciones_ofrecidas)),
                     key=lambda i: (-s[propuesta.acciones_ofrecidas[i].accion_id], i))
    ordenada = propuesta.model_copy(deep=True)
    ordenada.acciones_ofrecidas = [ordenada.acciones_ofrecidas[i] for i in indices]
    frase = frase_preferida(ordenada, modelo)
    if frase and frase not in ordenada.contexto_llamada:
        ordenada.contexto_llamada = f"{ordenada.contexto_llamada.rstrip()} {frase}".strip()
    return ordenada


def registrar_accion(modelo: ModeloUsuario, propuesta: Propuesta, resultado: ResultadoAccion) -> ModeloUsuario:
    """Pura. Con `ok`, suma 1 a `t:<tipo>|a:<accion>` y a `a:<accion>`. Sin `ok`, no cambia nada."""
    if not resultado.ok:
        return modelo
    nuevo = modelo.model_copy(deep=True)
    for clave in (clave_tipo(propuesta.tipo_momento, resultado.accion_id), clave_global(resultado.accion_id)):
        nuevo.elecciones[clave] = nuevo.elecciones.get(clave, 0) + 1
    return nuevo
