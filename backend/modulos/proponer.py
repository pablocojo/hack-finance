"""Momento + modelo -> propuestas de los módulos que lo escuchan (el orquestador llama luego a `ordenar_acciones`)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import AccionOfrecida, Limites, ModeloUsuario, Momento, Propuesta
from . import condiciones, plantillas, registro
from .esquema import MAX_ACCIONES, MAX_REPETIR, AccionSpec, ModuloSpec


def modulo_activo_para(spec: ModuloSpec, modelo: ModeloUsuario | None) -> bool:
    """`activo` en el estado del módulo; si el cliente ya eligió módulos (`modulos_activos` no vacío),
    los opcionales solo salen si están en la lista. Un módulo con producto exige activación explícita."""
    if spec.estado != "activo":
        return False
    elegidos = list(modelo.modulos_activos) if modelo is not None else []
    if spec.ficha_informacion:
        return spec.id in elegidos
    if spec.opcional and elegidos:
        return spec.id in elegidos
    return True


def _dec_o_none(x: Any) -> Decimal | None:
    try:
        return None if x is None or isinstance(x, bool) else Decimal(str(x))
    except InvalidOperation:
        return None


def _expandir(a: AccionSpec, datos: dict, cupo: int) -> list[AccionOfrecida]:
    items: list[dict | None] = [None]
    if a.repetir_por:
        lista = datos.get(a.repetir_por.split(".")[1]) or []
        items = [i for i in lista if isinstance(i, dict)][: min(MAX_REPETIR, cupo)]
    from ..acciones.registro import REGISTRO  # import tardío: evita el ciclo modulos <-> acciones

    defn = REGISTRO[a.accion_id]
    salida = []
    for item in items:
        try:
            crudos = {k: plantillas.valor_parametro(v, datos, item) for k, v in a.parametros.items()}
            params = defn.validar(crudos)
            imp = a.limites.importe_max
            importe_max = None
            if imp is not None:
                importe_max = _dec_o_none(plantillas.valor_parametro(imp, datos, item))
                if importe_max is None:
                    continue
            contrapartes = None
            if a.limites.contrapartes is not None:
                contrapartes = [str(plantillas.valor_parametro(c, datos, item)) for c in a.limites.contrapartes]
        except (plantillas.ErrorPlantilla, ValueError):
            continue  # un dato ausente o inválido: esa acción no se ofrece
        legibles = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in params.items()}
        salida.append(AccionOfrecida(accion_id=a.accion_id, parametros=legibles,
                                     limites=Limites(importe_max=importe_max, contrapartes=contrapartes)))
    return salida


def construir(spec: ModuloSpec, momento: Momento, modelo: ModeloUsuario | None,
              informe: list[str] | None = None) -> Propuesta | None:
    """Evalúa `cuando` y rellena la propuesta. `None` si no cumple o si no queda ninguna acción."""
    if momento.tipo not in spec.escucha:
        return None
    ctx = condiciones.contexto(momento, modelo)
    if spec.cuando and not condiciones.evaluar(condiciones.compilar(spec.cuando), ctx, informe):
        return None
    datos = momento.datos
    p = spec.propuesta
    titulo, notif, llamada = p.titulo, p.mensaje_notificacion, p.contexto_llamada
    if p.alternativa and datos.get(p.alternativa.falta.split(".")[1]) is None:
        alt = p.alternativa
        titulo, notif, llamada = alt.titulo or titulo, alt.mensaje_notificacion or notif, alt.contexto_llamada or llamada
    try:
        titulo = plantillas.renderizar(titulo, datos)
        notif = plantillas.renderizar(notif, datos)
        llamada = plantillas.renderizar_llamada(llamada, datos)
    except plantillas.ErrorPlantilla as e:
        if informe is not None:
            informe.append(f"plantilla no renderiza: {e}")
        return None

    fijas = sum(1 for a in spec.acciones if not a.repetir_por)
    acciones: list[AccionOfrecida] = []
    for a in spec.acciones:
        acciones += _expandir(a, datos, MAX_ACCIONES - fijas) if a.repetir_por else _expandir(a, datos, 1)
    acciones = acciones[:MAX_ACCIONES]
    if not acciones:
        return None

    valor = None
    if p.valor_estimado_eur:
        valor = _dec_o_none(condiciones.evaluar_valor(condiciones.compilar(p.valor_estimado_eur), ctx))
    if valor is None:
        valor = momento.impacto_eur if momento.impacto_eur is not None else Decimal("0")
    candidatos = datos.get("candidatos") if isinstance(datos.get("candidatos"), list) else []
    contraparte = datos.get("contraparte") or (
        candidatos[0].get("contraparte") if candidatos and isinstance(candidatos[0], dict) else None)
    return Propuesta(
        id=f"prop-{momento.id}-{spec.id}", modulo_id=spec.id, momento_id=momento.id, usuario_id=momento.usuario_id,
        titulo=titulo, mensaje_notificacion=notif, contexto_llamada=llamada, acciones_ofrecidas=acciones,
        valor_estimado_eur=valor, urgencia=p.urgencia, tipo_momento=momento.tipo,
        comercio=datos.get("comercio") if isinstance(datos.get("comercio"), str) else None,
        contraparte=contraparte if isinstance(contraparte, str) else None, confianza=momento.confianza,
        impacto_relativo=momento.impacto_relativo, contexto_personal=momento.contexto_personal,
        creada=ahora_por_defecto(momento.fecha),
    )


def proponer(momento: Momento, modelo: ModeloUsuario | None) -> list[Propuesta]:
    salida = []
    for spec in registro.todos().values():
        if modulo_activo_para(spec, modelo):
            prop = construir(spec, momento, modelo)
            if prop is not None:
                salida.append(prop)
    return salida
