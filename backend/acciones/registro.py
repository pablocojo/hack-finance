"""
Registro cerrado de las seis acciones (modulos.md §6). Cada `AccionDef` trae sus parámetros
validados con pydantic, su texto legible, su efecto simulado sobre `banco_sim` y cómo deshacerlo.
Añadir una acción exige código, revisión de `experto-banca` y test.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..modulos.plantillas import formatear_eur, sanear_dato
from ..plataforma.tipos import ACCIONES
from .banco_sim import DIAS_CADUCIDAD_SOLICITUD
from .errores import ErrorAccion

TEXTO_BAJA = (
    "La baja la confirmas tú en {comercio}. Si lo eliges, rechazaremos sus cobros con tarjeta "
    "(según lo que permita tu banco emisor; no vale para recibos domiciliados). Bloquear no cancela "
    "el contrato: el comercio podría reclamarte lo que debas."
)
MAX_RECORDATORIO_DIAS = 90
# Reglas de Bizum entre particulares (docs/diseno/deudas-casos.md, «Cómo funciona Bizum hoy»).
BIZUM_IMPORTE_MIN = Decimal("0.50")
BIZUM_IMPORTE_MAX = Decimal("1000.00")
BIZUM_SOLICITUDES_MES = 60
CONCEPTO_MAX = 60


def normalizar(texto: Any) -> str:
    """Clave de comparación: sin mayúsculas, acentos ni espacios repetidos («La Tasca» == «LA TASCA»)."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().casefold()


def _dinero(v: Any) -> Decimal:
    if isinstance(v, bool):
        raise ValueError("importe no válido")
    d = v if isinstance(v, Decimal) else Decimal(str(v))
    if not d.is_finite() or d <= 0:
        raise ValueError("El importe debe ser positivo.")
    return d.quantize(Decimal("0.01"))


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)


class ParamsPedirBizum(_P):
    contraparte: str = Field(min_length=1, max_length=40)
    importe: Decimal
    concepto: str = Field(min_length=1, max_length=CONCEPTO_MAX)

    @field_validator("importe", mode="before")
    @classmethod
    def _importe(cls, v):
        return _dinero(v)

    @field_validator("concepto", mode="before")
    @classmethod
    def _concepto(cls, v):
        """Texto libre del usuario: se trata como dato (sin control, `{}<>` ni comillas; espacios limpios)."""
        if not isinstance(v, str):
            raise ValueError("El concepto debe ser texto.")
        return sanear_dato(v, maximo=10 * CONCEPTO_MAX)  # el tope se aplica después y rechaza, no recorta


class ParamsCancelar(_P):
    comercio: str = Field(min_length=1, max_length=60)
    bloquear_cobros: bool = False


class ParamsBloquear(_P):
    comercio: str = Field(min_length=1, max_length=60)


class ParamsReclamar(_P):
    movimiento_id: str = Field(min_length=1, max_length=80)
    motivo: str = Field(min_length=1, max_length=120)


class ParamsMover(_P):
    origen: Literal["ahorro"]
    destino: Literal["cuenta", "corriente"]
    importe: Decimal

    @field_validator("importe", mode="before")
    @classmethod
    def _importe(cls, v):
        return _dinero(v)


class ParamsRecordar(_P):
    cuando: str
    texto: str = Field(min_length=1, max_length=120)

    @field_validator("cuando")
    @classmethod
    def _cuando(cls, v: str) -> str:
        v = v.strip()
        m = re.fullmatch(r"\+(\d{1,3})d", v)
        if m:
            if not 0 <= int(m.group(1)) <= MAX_RECORDATORIO_DIAS:
                raise ValueError(f"Máximo {MAX_RECORDATORIO_DIAS} días.")
            return v
        try:
            date.fromisoformat(v[:10])
        except ValueError as e:
            raise ValueError("`cuando` es una fecha ISO o `+Nd`.") from e
        return v[:10]


def resolver_fecha(cuando: str, hoy: date) -> date:
    m = re.fullmatch(r"\+(\d+)d", cuando)
    f = hoy + timedelta(days=int(m.group(1))) if m else date.fromisoformat(cuando)
    if f > hoy + timedelta(days=MAX_RECORDATORIO_DIAS):
        raise ErrorAccion("parametros_invalidos", f"El recordatorio no puede pasar de {MAX_RECORDATORIO_DIAS} días.")
    return f


# --- Efectos simulados: reciben el estado del banco (dict mutable) y devuelven (mensaje, efecto) ---

def _mensaje_dinero(d: Decimal) -> str:
    return formatear_eur(d)


def _reglas_bizum(p: dict) -> None:
    """Reglas estáticas de Bizum: valen para lo que prepara Meisam y para lo que edita el usuario."""
    if not BIZUM_IMPORTE_MIN <= p["importe"] <= BIZUM_IMPORTE_MAX:
        raise ErrorAccion("importe_fuera_de_rango", "Un Bizum admite importes de 0,50 € a 1.000 €.")


def _pre_bizum(est: dict, p: dict, hoy: date, pid: str) -> None:
    """Reglas que dependen del estado del banco; se comprueban al preparar y otra vez al ejecutar."""
    k = normalizar(p["contraparte"])
    for s in est["solicitudes_bizum"]:
        if s["estado"] == "pendiente" and s.get("propuesta_id") == pid and normalizar(s["contraparte"]) == k:
            raise ErrorAccion("solicitud_abierta", f"Ya hay una solicitud pendiente a {sanear_dato(p['contraparte'])} "
                              "por esta deuda. Espera a que responda o cancélala antes de pedir otra.")
    este_mes = sum(1 for s in est["solicitudes_bizum"]
                   if (date.fromisoformat(s["fecha"]).year, date.fromisoformat(s["fecha"]).month) == (hoy.year, hoy.month))
    if este_mes >= BIZUM_SOLICITUDES_MES:
        raise ErrorAccion("limite_solicitudes_mes", f"Has llegado al máximo de {BIZUM_SOLICITUDES_MES} solicitudes de Bizum "
                          "este mes. Podrás pedir más el mes que viene.")
    if any(normalizar(c) == k for c in est.get("sin_bizum", [])):
        raise ErrorAccion("no_se_puede", f"{sanear_dato(p['contraparte'])} no tiene Bizum activo.")


def _vigente_bizum(est: dict, resultado: dict) -> bool:
    """Un resultado guardado solo vale como idempotente mientras su solicitud siga pendiente."""
    rid = (resultado.get("datos") or {}).get("resultado_id")
    return any(s["id"] == rid and s["estado"] == "pendiente" for s in est["solicitudes_bizum"])


def _sim_pedir_bizum(est: dict, p: dict, hoy: date, rid: str, pid: str = ""):
    _pre_bizum(est, p, hoy, pid)
    caduca = hoy + timedelta(days=DIAS_CADUCIDAD_SOLICITUD)
    est["solicitudes_bizum"].append({
        "id": rid, "contraparte": p["contraparte"], "importe": str(p["importe"]), "concepto": p["concepto"],
        "estado": "pendiente", "fecha": hoy.isoformat(), "caduca": caduca.isoformat(), "propuesta_id": pid,
    })
    return (f"Solicitud de Bizum de {_mensaje_dinero(p['importe'])} enviada a {sanear_dato(p['contraparte'])}. "
            f"Queda pendiente hasta que la acepte; caduca el {caduca.day}/{caduca.month} si no responde.",
            {"estado": "pendiente", "caduca": caduca.isoformat()})


def _des_pedir_bizum(est: dict, ef: dict, rid: str):
    for s in est["solicitudes_bizum"]:
        if s["id"] == rid:
            if s["estado"] != "pendiente":
                raise ErrorAccion("no_se_puede", "La solicitud ya no está pendiente; no se puede cancelar.")
            s["estado"] = "cancelada"
            return "Solicitud de Bizum cancelada."
    raise ErrorAccion("no_se_puede", "No se encuentra la solicitud.")


def _sim_cancelar(est: dict, p: dict, hoy: date, rid: str, pid: str = ""):
    com = p["comercio"]
    existe = any(b["comercio"] == com and b["estado"] == "guiada" for b in est["bajas"])
    if not existe:
        est["bajas"].append({"id": rid, "comercio": com, "estado": "guiada", "fecha": hoy.isoformat()})
    bloqueado, motivo = False, ""
    if p["bloquear_cobros"]:
        if com in est.get("recibos_domiciliados", []):
            motivo = " No se puede bloquear un recibo domiciliado: la baja la gestionas en el servicio."
        else:
            if not any(b["comercio"] == com and b.get("tipo") == "recurrente" for b in est["bloqueos"]):
                est["bloqueos"].append({"id": rid, "comercio": com, "tipo": "recurrente", "fecha": hoy.isoformat()})
            bloqueado = True
    msg = (f"Baja guiada de {sanear_dato(com)} registrada: la confirmas tú en el servicio."
           + (" Rechazaremos sus cobros con tarjeta." if bloqueado else "") + motivo)
    return msg, {"baja": "guiada", "bloqueado": bloqueado, "ya_registrada": existe}


def _des_cancelar(est: dict, ef: dict, rid: str):
    est["bloqueos"] = [b for b in est["bloqueos"] if b["id"] != rid]
    return "Bloqueo de cobros retirado. La baja en el servicio no se deshace desde aquí."


def _sim_bloquear(est: dict, p: dict, hoy: date, rid: str, pid: str = ""):
    if not any(b["comercio"] == p["comercio"] for b in est["bloqueos"]):
        est["bloqueos"].append({"id": rid, "comercio": p["comercio"], "tipo": "comercio", "fecha": hoy.isoformat()})
    return (f"Cobros nuevos de {sanear_dato(p['comercio'])} rechazados. Esto no cancela el contrato: "
            "seguirás debiendo el servicio."), {"bloqueado": True}


def _sim_reclamar(est: dict, p: dict, hoy: date, rid: str, pid: str = ""):
    canal = est.get("canal_movimientos", {}).get(p["movimiento_id"], "tarjeta")
    if canal == "recibo":
        plazo = (hoy + timedelta(weeks=8)).isoformat()
        tipo, msg = "devolucion_sepa", f"Devolución SEPA solicitada (plazo hasta el {plazo})."
    else:
        tipo, msg = "reclamacion_tarjeta", "Reclamación enviada. No hay plazo garantizado de respuesta."
    est["reclamaciones"].append({"id": rid, "movimiento_id": p["movimiento_id"], "tipo": tipo,
                                 "motivo": p["motivo"], "estado": "abierta", "fecha": hoy.isoformat()})
    return msg, {"tipo": tipo}


def _des_reclamar(est: dict, ef: dict, rid: str):
    for r in est["reclamaciones"]:
        if r["id"] == rid:
            r["estado"] = "retirada"
            return "Reclamación retirada."
    raise ErrorAccion("no_se_puede", "No se encuentra la reclamación.")


def _sim_mover(est: dict, p: dict, hoy: date, rid: str, pid: str = ""):
    ahorro = Decimal(est["cuentas"]["ahorro"])
    if ahorro < p["importe"]:
        raise ErrorAccion("no_se_puede", "No hay saldo suficiente en ahorro.")
    est["cuentas"]["ahorro"] = str(ahorro - p["importe"])
    est["cuentas"]["corriente"] = str(Decimal(est["cuentas"]["corriente"]) + p["importe"])
    return f"Traspaso simulado de {_mensaje_dinero(p['importe'])} de ahorro a tu cuenta.", {"importe": str(p["importe"])}


def _des_mover(est: dict, ef: dict, rid: str):
    imp = Decimal(ef["importe"])
    est["cuentas"]["ahorro"] = str(Decimal(est["cuentas"]["ahorro"]) + imp)
    est["cuentas"]["corriente"] = str(Decimal(est["cuentas"]["corriente"]) - imp)
    return "Traspaso revertido."


def _sim_recordar(est: dict, p: dict, hoy: date, rid: str, pid: str = ""):
    f = resolver_fecha(p["cuando"], hoy)
    est["recordatorios"].append({"id": rid, "fecha": f.isoformat(), "texto": p["texto"]})
    return f"Recordatorio creado para el {f.day}/{f.month}.", {"fecha": f.isoformat()}


def _des_recordar(est: dict, ef: dict, rid: str):
    est["recordatorios"] = [r for r in est["recordatorios"] if r["id"] != rid]
    return "Recordatorio borrado."


def _des_bloquear(est: dict, ef: dict, rid: str):
    est["bloqueos"] = [b for b in est["bloqueos"] if b["id"] != rid]
    return "Bloqueo retirado."


@dataclass(frozen=True)
class AccionDef:
    id: str
    modelo: type[BaseModel]
    limites: tuple[str, ...]                    # admitidos: importe_max, contrapartes
    titulo: str
    legible: Callable[[dict], dict[str, str]]
    simular: Callable[..., tuple[str, dict]]    # (estado, params, hoy, resultado_id, propuesta_id)
    deshacer: Callable[[dict, dict, str], str]
    variables: tuple[str, ...] = ()             # parámetros que el cliente puede cambiar en la tarjeta
    # Campos que el usuario puede editar en la tarjeta (solo con `preparar_editada`): se validan con las
    # reglas de la acción, no con los `limites` de la propuesta, que frenan lo que prepara Meisam.
    editables: tuple[str, ...] = ()
    reglas: Callable[[dict], None] | None = None                            # reglas estáticas de la acción
    precondiciones: Callable[[dict, dict, date, str], None] | None = None   # reglas con el estado del banco
    vigente: Callable[[dict, dict], bool] | None = None   # ¿un resultado guardado sigue valiendo como idempotente?

    def validar(self, parametros: dict) -> dict:
        """Valida y normaliza (dinero a Decimal con 2 decimales). Lanza `ErrorAccion`."""
        if not isinstance(parametros, dict):
            raise ErrorAccion("parametros_invalidos", "Los parámetros deben ser un objeto.")
        try:
            params = self.modelo.model_validate(parametros).model_dump()
        except Exception as e:  # pydantic.ValidationError y errores de conversión
            detalle = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg'].removeprefix('Value error, ')}"
                                for x in getattr(e, "errors", lambda: [])()) or str(e)
            raise ErrorAccion("parametros_invalidos", f"Parámetros no válidos para {self.id}: {detalle}") from e
        if self.reglas is not None:
            self.reglas(params)
        return params


def _leg_bizum(p):
    return {"Para": sanear_dato(p["contraparte"]), "Importe": formatear_eur(p["importe"]),
            "Concepto": sanear_dato(p["concepto"], CONCEPTO_MAX),
            "Aviso": f"Si no responde en {DIAS_CADUCIDAD_SOLICITUD} días, la solicitud caduca."}


def _leg_cancelar(p):
    d = {"Comercio": sanear_dato(p["comercio"]),
         "Bloquear cobros con tarjeta": "Sí" if p["bloquear_cobros"] else "No",
         "Aviso": TEXTO_BAJA.format(comercio=sanear_dato(p["comercio"]))}
    return d


REGISTRO: dict[str, AccionDef] = {
    "pedir_bizum": AccionDef("pedir_bizum", ParamsPedirBizum, ("importe_max", "contrapartes"),
                             "Pedir un Bizum", _leg_bizum, _sim_pedir_bizum, _des_pedir_bizum,
                             editables=("importe", "concepto"), reglas=_reglas_bizum, precondiciones=_pre_bizum, vigente=_vigente_bizum),
    "cancelar_suscripcion": AccionDef("cancelar_suscripcion", ParamsCancelar, (), "Guiarte para darte de baja",
                                      _leg_cancelar, _sim_cancelar, _des_cancelar, variables=("bloquear_cobros",)),
    "bloquear_comercio": AccionDef("bloquear_comercio", ParamsBloquear, (), "Bloquear los cobros de un comercio",
                                   lambda p: {"Comercio": sanear_dato(p["comercio"]),
                                              "Aviso": "No cancela el contrato: seguirás debiendo el servicio."},
                                   _sim_bloquear, _des_bloquear),
    "reclamar_cargo": AccionDef("reclamar_cargo", ParamsReclamar, (), "Reclamar un cargo",
                                lambda p: {"Movimiento": sanear_dato(p["movimiento_id"]), "Motivo": sanear_dato(p["motivo"])},
                                _sim_reclamar, _des_reclamar),
    "mover_dinero": AccionDef("mover_dinero", ParamsMover, ("importe_max",), "Mover dinero desde ahorro",
                              lambda p: {"De": "Ahorro", "A": "Cuenta", "Importe": formatear_eur(p["importe"])},
                              _sim_mover, _des_mover),
    "recordar": AccionDef("recordar", ParamsRecordar, (), "Crear un recordatorio",
                          lambda p: {"Cuándo": p["cuando"], "Texto": sanear_dato(p["texto"])},
                          _sim_recordar, _des_recordar),
}

assert set(REGISTRO) == set(ACCIONES), "El registro debe tener exactamente las acciones del contrato."


def obtener(accion_id: str) -> AccionDef:
    if accion_id not in REGISTRO:
        raise ErrorAccion("accion_no_ofrecida", f"Acción no permitida: {accion_id!r}. Las válidas son: {', '.join(REGISTRO)}.")
    return REGISTRO[accion_id]
