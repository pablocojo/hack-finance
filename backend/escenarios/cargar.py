"""
Escenarios etiquetados (motor.md §5): YAML con movimientos sintéticos, la verdad (`esperado`) y
las trampas. Alimentan tests, `/medir motor`, `probar_en_seco` y la demo.

    esc = cargar("cena-lucia")             # Escenario: id, usuario_id, activacion, hasta, movimientos...
    momentos = reproducir(esc)             # motor en línea, día a día, en un usuario aislado
    resultado = evaluar(esc, momentos)     # aciertos, omitidos, falsos, trampas violadas y retrasos

Formato del YAML:
- `fondo` (opcional): `{perfil, meses, semilla, hasta, anomalias}` de `datos/sinteticos.py`.
- `activacion`: lo que tiene fecha <= activación entra con `cargar_historial` (sin emitir); después,
  `procesar` día a día hasta `hasta` (igual que el orquestador).
- `perfil`: `null` (sin perfil), `calcular` (`personalizacion.perfilar` al activar y cada 7 días) o un
  `PerfilUsuario` escrito a mano.
- `eventos`: `{fecha, tipo: registrar_prueba | cerrar_prueba, comercio, ...}` (lo que dice el cliente).
- `esperado`: `{tipo, fecha_detectable, ids, tolerancia_dias, datos?, candidatos?, solo_con_perfil?}`
  (`ids: []` = un momento sin movimientos que lo prueben, como una prueba que dijo el cliente).
- `trampas`: `{tipo, ids, motivo}`: ningún momento de ese tipo puede tocar esos ids.
- `contactos` (opcional): la agenda inventada del usuario, `[{contraparte: "MARCOS R", nombre: "Marcos R.",
  telefono: "+34 6** *** 123", relacion?}]` (`Escenario.contactos`, `Contacto` del contrato). La lee el orquestador al
  cargar el escenario; el motor no la usa.
- `amigos_pagan_tras_solicitud_dias` (opcional, solo demos; por defecto apagado): si el usuario pide un Bizum con el
  botón, N días después entra el Bizum de ese amigo por ese importe y la solicitud pasa a `aceptada` (lo guarda el
  orquestador en el estado del usuario; `banco_sim.pagos_de_solicitudes`). El motor no lo usa.
- Un `tipo` de etiqueta o trampa puede ser `pago_individual`: es un momento `gasto_compartido` con
  `datos.origen = pago_individual`, que se mide aparte (siempre `dudoso`). Ver `tipo_medido`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

import yaml

from .. import motor
from ..datos.sinteticos import generar_movimientos
from ..plataforma.tipos import Contacto, Momento, Movimiento, PerfilUsuario

DIRECTORIO = Path(__file__).resolve().parent
DIAS_PERFIL = 7
CAMPOS_FECHA_PREVISTA = ("fecha_prevista", "fecha_primer_cobro")   # se cruzan a ±1 día


@dataclass
class Escenario:
    id: str
    usuario_id: str
    activacion: date
    hasta: date
    movimientos: list[Movimiento]
    descripcion: str = ""
    perfil: Any = None
    eventos: list[dict] = field(default_factory=list)
    esperado: list[dict] = field(default_factory=list)
    trampas: list[dict] = field(default_factory=list)
    fondo: dict | None = None
    contactos: list[Contacto] = field(default_factory=list)
    amigos_pagan_tras_solicitud_dias: int | None = None    # solo demos: el amigo paga N días después de pedírselo
    crudo: dict = field(default_factory=dict, repr=False)

    def previos(self) -> list[Movimiento]:
        return [m for m in self.movimientos if m.fecha <= self.activacion]

    def del_dia(self, dia: date) -> list[Movimiento]:
        return [m for m in self.movimientos if m.fecha == dia]


# --- Leer ------------------------------------------------------------------------------------

def _fecha(valor: Any) -> date | None:
    if valor is None or isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def _movimiento(datos: dict) -> Movimiento:
    datos = dict(datos)
    datos["fecha"] = _fecha(datos["fecha"])
    datos["importe"] = Decimal(str(datos["importe"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if datos.get("saldo") is not None:
        datos["saldo"] = Decimal(str(datos["saldo"]))
    return Movimiento.model_validate(datos)


def _fondo(fondo: dict) -> list[Movimiento]:
    crudos = generar_movimientos(fondo.get("perfil", "estudiante"), meses=int(fondo.get("meses", 6)),
                                 semilla=int(fondo.get("semilla", 42)), hasta=_fecha(fondo["hasta"]),
                                 anomalias=bool(fondo.get("anomalias", False)))
    return [_movimiento(m) for m in crudos]


def _dias_pago_amigos(valor: Any) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 6:
        raise ValueError(f"amigos_pagan_tras_solicitud_dias debe ser un entero de 1 a 6 (la solicitud caduca a los 7 "
                         f"días): {valor!r}")
    return valor


def desde_dict(datos: dict) -> Escenario:
    fondo = datos.get("fondo")
    movimientos = (_fondo(fondo) if fondo else []) + [_movimiento(m) for m in datos.get("movimientos") or []]
    ids = [m.id for m in movimientos]
    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise ValueError(f"Ids repetidos en el escenario {datos.get('id')}: {sorted(repetidos)[:5]}")
    movimientos.sort(key=lambda m: m.fecha)          # estable: el orden del YAML dentro del día
    hasta = _fecha(datos.get("hasta")) or _fecha((fondo or {}).get("hasta")) or max(
        (m.fecha for m in movimientos), default=_fecha(datos["activacion"]))
    return Escenario(
        id=datos["id"],
        usuario_id=datos["usuario_id"],
        activacion=_fecha(datos["activacion"]),
        hasta=hasta,
        movimientos=[m for m in movimientos if m.fecha <= hasta],
        descripcion=datos.get("descripcion", "") or "",
        perfil=datos.get("perfil"),
        eventos=list(datos.get("eventos") or []),
        esperado=list(datos.get("esperado") or []),
        trampas=list(datos.get("trampas") or []),
        fondo=fondo,
        contactos=[Contacto.model_validate(c) for c in datos.get("contactos") or []],
        amigos_pagan_tras_solicitud_dias=_dias_pago_amigos(datos.get("amigos_pagan_tras_solicitud_dias")),
        crudo=dict(datos),
    )


def leer(escenario_id: str) -> dict:
    """YAML en crudo. `FileNotFoundError` si no existe."""
    if "/" in escenario_id or "\\" in escenario_id or escenario_id.startswith("."):
        raise FileNotFoundError(escenario_id)
    ruta = DIRECTORIO / f"{escenario_id}.yaml"
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el escenario {escenario_id!r}.")
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def cargar(escenario_id: str) -> Escenario:
    return desde_dict(leer(escenario_id))


def listar() -> list[dict]:
    """`[{id, usuario_id, descripcion}]` sin generar los movimientos."""
    salida = []
    for ruta in sorted(DIRECTORIO.glob("*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        if "id" in datos:
            salida.append({"id": datos["id"], "usuario_id": datos.get("usuario_id", ""),
                           "descripcion": datos.get("descripcion", "") or ""})
    return salida


# --- Reproducir ------------------------------------------------------------------------------

def perfil_para(escenario: Escenario, hoy: date, historial: list[Movimiento],
                anterior: PerfilUsuario | None = None) -> PerfilUsuario | None:
    """El perfil del escenario en `hoy`: ninguno, uno escrito a mano o `perfilar` sobre el historial."""
    spec = escenario.perfil
    if not spec:
        return None
    if isinstance(spec, dict):
        return PerfilUsuario.model_validate(spec)
    if spec == "calcular":
        from .. import personalizacion

        return personalizacion.perfilar(motor.enriquecer(historial), hoy, anterior)
    raise ValueError(f"Perfil de escenario no válido: {spec!r}")


def _aplicar_evento(uid: str, evento: dict, hoy: date) -> None:
    tipo = evento["tipo"]
    if tipo == "registrar_prueba":
        motor.registrar_prueba(uid, evento["comercio"], _fecha(evento.get("fecha_alta")) or hoy,
                               evento.get("dias"), hoy)
    elif tipo == "cerrar_prueba":
        motor.cerrar_prueba(uid, evento["comercio"], evento.get("motivo", "cancelada"), hoy)
    else:
        raise ValueError(f"Evento de escenario desconocido: {tipo!r}")


def reproducir(escenario: Escenario, con_perfil: bool | None = None,
               al_terminar: Callable[[str], None] | None = None) -> list[Momento]:
    """Motor en línea sobre el escenario, en un usuario aislado (no toca el estado del usuario real).
    `con_perfil=None` usa el perfil del escenario si lo tiene; `False` fuerza el arranque en frío."""
    usar_perfil = bool(escenario.perfil) if con_perfil is None else con_perfil
    uid = f"__escenario__:{escenario.id}:{uuid.uuid4().hex[:8]}"
    momentos: list[Momento] = []
    try:
        visto = escenario.previos()
        motor.cargar_historial(uid, visto, escenario.activacion)
        perfil = perfil_para(escenario, escenario.activacion, visto) if usar_perfil else None
        ultimo_perfil = escenario.activacion
        dia = escenario.activacion + timedelta(days=1)
        while dia <= escenario.hasta:
            nuevos = escenario.del_dia(dia)
            visto = visto + nuevos
            for evento in escenario.eventos:
                if _fecha(evento["fecha"]) == dia:
                    _aplicar_evento(uid, evento, dia)
            if usar_perfil and escenario.perfil == "calcular" and (dia - ultimo_perfil).days >= DIAS_PERFIL:
                perfil, ultimo_perfil = perfil_para(escenario, dia, visto, perfil), dia
            momentos += motor.procesar(uid, nuevos, dia, perfil)
            dia += timedelta(days=1)
        if al_terminar:
            al_terminar(uid)
    finally:
        motor.reiniciar(uid)
    return [m.model_copy(update={"usuario_id": escenario.usuario_id}) for m in momentos]


# --- Evaluar ---------------------------------------------------------------------------------

def _igual(esperado: Any, real: Any) -> bool:
    if isinstance(esperado, date) or isinstance(real, date):
        return str(esperado) == str(real)
    try:
        return Decimal(str(esperado)) == Decimal(str(real))
    except (InvalidOperation, ValueError):
        return esperado == real


def _fecha_cerca(esperado: Any, real: Any, dias: int = 1) -> bool:
    try:
        return abs((_fecha(esperado) - _fecha(real)).days) <= dias
    except (TypeError, ValueError):
        return False


ORIGEN_INDIVIDUAL = "pago_individual"


def tipo_medido(momento: Momento) -> str:
    """El tipo con el que se mide un momento: `pago_individual` (señal de lugar y día) es un `gasto_compartido` con
    `datos.origen = pago_individual` y tiene su propia dimensión; así `gasto_compartido` sigue midiendo solo las deudas."""
    if momento.tipo == "gasto_compartido" and momento.datos.get("origen") == ORIGEN_INDIVIDUAL:
        return ORIGEN_INDIVIDUAL
    return momento.tipo


def encaja(etiqueta: dict, momento: Momento) -> bool:
    """Acierto: mismo tipo, toca los ids, sale en [fecha_detectable, + tolerancia] y `datos` coinciden."""
    ids = etiqueta.get("ids") or []        # sin ids (una prueba que dijo el cliente): vale cualquiera del tipo
    if tipo_medido(momento) != etiqueta["tipo"] or (ids and not set(ids) & set(momento.movimientos)):
        return False
    if bool(momento.datos.get("dudoso")) != bool(etiqueta.get("dudoso", etiqueta["tipo"] == ORIGEN_INDIVIDUAL)):
        return False
    desde = _fecha(etiqueta["fecha_detectable"])
    if not desde <= momento.fecha <= desde + timedelta(days=int(etiqueta.get("tolerancia_dias", 0))):
        return False
    for campo, valor in (etiqueta.get("datos") or {}).items():
        real = momento.datos.get(campo)
        bien = _fecha_cerca(valor, real) if campo in CAMPOS_FECHA_PREVISTA else _igual(valor, real)
        if not bien:
            return False
    if "candidatos" in etiqueta:
        reales = [c.get("contraparte") for c in momento.datos.get("candidatos", [])]
        if reales != list(etiqueta["candidatos"]):
            return False
    return True


def evaluar(escenario: Escenario, momentos: list[Momento], con_perfil: bool = False) -> dict:
    """Compara los momentos con la verdad del escenario. `/medir motor` agrega estos resultados."""
    etiquetas = [e for e in escenario.esperado if con_perfil or not e.get("solo_con_perfil")]
    usados: set[str] = set()
    retrasos, omitidos = [], []
    por_tipo: dict[str, dict[str, int]] = {}

    def cuenta(tipo: str, campo: str) -> None:
        por_tipo.setdefault(tipo, {"aciertos": 0, "omitidos": 0, "falsos": 0, "dudosos": 0})[campo] += 1

    for etiqueta in etiquetas:
        momento = next((m for m in momentos if m.id not in usados and encaja(etiqueta, m)), None)
        if momento is None:
            omitidos.append(etiqueta)
            cuenta(etiqueta["tipo"], "omitidos")
            continue
        usados.add(momento.id)
        retrasos.append((momento.fecha - _fecha(etiqueta["fecha_detectable"])).days)
        cuenta(etiqueta["tipo"], "aciertos")
    sobrantes = [m for m in momentos if m.id not in usados]
    # Un `pago_individual` sin etiqueta es una pregunta legítima (dudoso) salvo en los escenarios que lo miden a propósito
    # (tienen etiquetas o trampas de ese tipo): ahí, uno de más es un falso positivo.
    mide_individual = any(e["tipo"] == ORIGEN_INDIVIDUAL for e in [*escenario.esperado, *escenario.trampas])
    dudoso = lambda m: bool(m.datos.get("dudoso")) and not (mide_individual and tipo_medido(m) == ORIGEN_INDIVIDUAL)  # noqa: E731
    dudosos = [m for m in sobrantes if dudoso(m)]
    falsos = [m for m in sobrantes if not dudoso(m)]
    for m in falsos:
        cuenta(tipo_medido(m), "falsos")
    for m in dudosos:
        cuenta(tipo_medido(m), "dudosos")
    violadas = [{"tipo": t["tipo"], "ids": list(t.get("ids", [])), "motivo": t.get("motivo", ""), "momento": m.id}
                for t in escenario.trampas for m in momentos
                if tipo_medido(m) == t["tipo"] and set(t.get("ids", [])) & set(m.movimientos)
                and (t.get("incluye_dudosos") or t["tipo"] == ORIGEN_INDIVIDUAL or not m.datos.get("dudoso"))]
    return {
        "escenario": escenario.id,
        "con_perfil": con_perfil,
        "aciertos": len(etiquetas) - len(omitidos),
        "omitidos": len(omitidos),
        "falsos_positivos": [m.id for m in falsos],
        "dudosos": [m.id for m in dudosos],
        "trampas_violadas": violadas,
        "retrasos": retrasos,
        "por_tipo": por_tipo,
        "detalle_omitidos": omitidos,
    }
