"""
Esquema de las vidas ocultas y del corpus del chat (`ESQUEMA.md` §1 y §3). Solo datos sintéticos.

Modelos Pydantic con `extra="forbid"` (una errata en un YAML falla en voz alta), `cargar_vidas()`,
`cargar_corpus()` y las reglas de validación de §1.9. Los errores son `ValueError` (también lo es
`pydantic.ValidationError`) con lo que hay que corregir.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....plataforma.tipos import Euros

RAIZ = Path(__file__).resolve().parents[4]
DIR_VIDAS = Path(__file__).resolve().parent / "vidas"
RUTA_CORPUS = RAIZ / "evals" / "datos" / "chat_amigos.yaml"

TOPE_BIZUM = Decimal("1000")
Categoria = Literal["restaurantes", "ocio", "compras", "supermercado", "transporte", "suministros",
                    "suscripciones", "vivienda", "ingresos", "otros"]
Franja = Literal["comida", "tarde", "cena", "noche"]
TipoEsperado = Literal["restaurante", "bar", "ocio", "comida_domicilio", "supermercado", "otro"]
Relacion = Literal["amigo", "familia", "pareja", "companero", "otro"]
TipoPlan = Literal["rutina", "cumpleanos", "cena_clase", "viaje", "concierto", "deporte", "trabajo", "familia", "otro"]
Reparto = Literal["iguales", "por_consumo", "invita"]
PAGA_ESPECIALES = ("usuario", "cada_uno", "efectivo")
CLAVE_PERSONA = re.compile(r"^[A-Z]+( [A-Z]+)?$")


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Piezas comunes --------------------------------------------------------------------------

def _validar_distribucion(d: dict, nombre: str, minimo: float | None = None, maximo: float | None = None) -> dict:
    if not d:
        raise ValueError(f"{nombre}: la distribución está vacía")
    if any(p < 0 for p in d.values()):
        raise ValueError(f"{nombre}: los pesos no pueden ser negativos")
    if sum(d.values()) <= 0:
        raise ValueError(f"{nombre}: los pesos deben sumar más de 0")
    for valor in d:
        if isinstance(valor, int | float) and ((minimo is not None and valor < minimo)
                                               or (maximo is not None and valor > maximo)):
            raise ValueError(f"{nombre}: el valor {valor} está fuera de [{minimo}, {maximo}]")
    return d


class RangoEuros(_Modelo):
    min: Euros
    max: Euros

    @model_validator(mode="after")
    def _orden(self):
        if self.min > self.max:
            raise ValueError(f"rango de dinero con min {self.min} > max {self.max}")
        if self.min < 0:
            raise ValueError("rango de dinero negativo: los importes van en positivo")
        return self


class RangoInt(_Modelo):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _orden(self):
        if self.min > self.max:
            raise ValueError(f"rango con min {self.min} > max {self.max}")
        return self


# --- Visible ---------------------------------------------------------------------------------

class Ingreso(_Modelo):
    tipo: Literal["beca", "paga", "sueldo", "pension", "otro"]
    concepto: str = Field(min_length=1)
    contraparte: str | None = None
    canal: Literal["transferencia", "bizum"]
    importe: Euros = Field(gt=0)
    dia_mes: int = Field(ge=1, le=28)
    variacion: Euros = Field(default=Decimal("0.00"), ge=0)


class Fondo(_Modelo):
    comercio: str = Field(min_length=1)
    categoria: Categoria
    canal: Literal["tarjeta", "recibo"]
    veces_semana: float | None = Field(default=None, ge=0, le=14)
    dias: list[int] | None = None
    dia_mes: int | None = Field(default=None, ge=1, le=28)
    importe: Euros | None = Field(default=None, gt=0)
    rango: RangoEuros | None = None

    @model_validator(mode="after")
    def _forma(self):
        if (self.veces_semana is None) == (self.dia_mes is None):
            raise ValueError(f"fondo «{self.comercio}»: usa `veces_semana` o `dia_mes`, uno de los dos")
        if (self.importe is None) == (self.rango is None):
            raise ValueError(f"fondo «{self.comercio}»: usa `importe` o `rango`, uno de los dos")
        if self.dias is not None and any(not 0 <= d <= 6 for d in self.dias):
            raise ValueError(f"fondo «{self.comercio}»: `dias` van de 0 a 6")
        return self


class Visible(_Modelo):
    saldo_inicial: Euros = Field(ge=0, le=20000)
    ingresos: list[Ingreso] = Field(default_factory=list)
    comercios_habituales: list[str] = Field(default_factory=list)
    fondo: list[Fondo] = Field(default_factory=list)


# --- Amigos ----------------------------------------------------------------------------------

class Redondea(_Modelo):
    prob: float = Field(ge=0, le=1)
    a: Euros = Field(gt=0)


class PagaPorDos(_Modelo):
    prob: float = Field(ge=0, le=1)
    con: str


class Amigo(_Modelo):
    nombre: str = Field(min_length=1)
    nombre_pila: str = Field(min_length=1)
    relacion: Relacion
    en_agenda: bool
    retraso_dias: dict[int, float]
    prob_paga_solo: float = Field(ge=0, le=1)
    retraso_tras_pedir_dias: dict[int, float]
    canal: dict[Literal["bizum", "efectivo", "transferencia"], float]
    redondea: Redondea | None = None
    paga_por_dos: PagaPorDos | None = None
    no_paga: float = Field(default=0.0, ge=0, le=0.3)
    notas_bizum: list[str] = Field(default_factory=lambda: [""])

    @field_validator("retraso_dias")
    @classmethod
    def _retraso(cls, d):
        return _validar_distribucion(d, "retraso_dias", 0, 30)

    @field_validator("retraso_tras_pedir_dias")
    @classmethod
    def _retraso_pedir(cls, d):
        return _validar_distribucion(d, "retraso_tras_pedir_dias", 0, 7)

    @field_validator("canal")
    @classmethod
    def _canal(cls, d):
        return _validar_distribucion(d, "canal")

    @field_validator("notas_bizum")
    @classmethod
    def _notas(cls, v):
        return v or [""]


# --- Planes ----------------------------------------------------------------------------------

class Sitio(_Modelo):
    comercio: str = Field(min_length=1)
    categoria: Categoria
    peso: float = Field(default=1.0, gt=0)
    coloquial: list[str] = Field(default_factory=list)
    tipo_esperado: TipoEsperado = "otro"


class OpcionalGrupo(_Modelo):
    amigo: str
    prob: float = Field(ge=0, le=1)


class Grupo(_Modelo):
    fijos: list[str] = Field(default_factory=list)
    opcionales: list[OpcionalGrupo] = Field(default_factory=list)
    desconocidos: RangoInt = RangoInt(min=0, max=0)


class CuandoPlan(_Modelo):
    semana: int = Field(ge=-3, le=8)
    dia: int = Field(ge=0, le=6)


class _PlanBase(_Modelo):
    id: str = Field(pattern=r"^[a-z_0-9]+$")
    descripcion: str
    tipo: TipoPlan
    franja: Franja
    sitios: list[Sitio] = Field(min_length=1)
    grupo: Grupo
    paga: dict[str, float]
    reparto: Reparto
    variacion_pct: float = Field(default=0.0, ge=0, le=0.5)
    importe_por_persona: RangoEuros
    meisam_rutina_4: bool = False

    @field_validator("paga")
    @classmethod
    def _paga(cls, d):
        return _validar_distribucion(d, "paga")


class PlanRecurrente(_PlanBase):
    dias: list[int] = Field(min_length=1)
    prob_semanal: float = Field(ge=0, le=1)

    @field_validator("dias")
    @classmethod
    def _dias(cls, v):
        if any(not 0 <= d <= 6 for d in v):
            raise ValueError("`dias` van de 0 (lunes) a 6 (domingo)")
        return v


class PlanEsporadico(_PlanBase):
    cuando: list[CuandoPlan] = Field(min_length=1)


class GastoSolo(_Modelo):
    id: str = Field(pattern=r"^[a-z_0-9]+$")
    comercio: str = Field(min_length=1)
    categoria: Categoria
    coloquial: list[str] = Field(default_factory=list)
    tipo_esperado: TipoEsperado = "otro"
    dias: list[int] = Field(min_length=1)
    prob_dia: float = Field(ge=0, le=1)
    importe: RangoEuros

    @field_validator("dias")
    @classmethod
    def _dias(cls, v):
        if any(not 0 <= d <= 6 for d in v):
            raise ValueError("`dias` van de 0 (lunes) a 6 (domingo)")
        return v


class CambioRutina(_Modelo):
    id: str
    semanas: list[int]
    planes: dict[str, float] = Field(default_factory=dict)
    gastos_solo: dict[str, float] = Field(default_factory=dict)
    nota: str = ""

    @field_validator("semanas")
    @classmethod
    def _semanas(cls, v):
        if any(not 1 <= s <= 8 for s in v):
            raise ValueError("`semanas` de un cambio de rutina van de 1 a 8")
        return v

    @field_validator("planes", "gastos_solo")
    @classmethod
    def _mult(cls, d):
        if any(m < 0 for m in d.values()):
            raise ValueError("los multiplicadores no pueden ser negativos")
        return d


class ConfigMeisam(_Modelo):
    contesta_resumen: float = Field(ge=0, le=1)
    contesta_notificacion: float = Field(ge=0, le=1)
    retraso_respuesta_horas: dict[int, float]
    acierta_respuesta: float = Field(ge=0, le=1)
    acepta_sugerencia_correcta: float = Field(ge=0, le=1)
    usa_chat: float = Field(ge=0, le=1)
    chat_hechos: float = Field(ge=0, le=1)
    tolerancia_avisos_semana: int = Field(ge=0, le=20)
    silencia_tras_inutiles: int = Field(ge=0)
    no_recordar: list[str] = Field(default_factory=list)
    si_no_pagan: dict[Literal["pide_bizum", "se_lo_dice_en_persona", "lo_deja"], float]
    declara_efectivo: float = Field(ge=0, le=1)
    acepta_nivel_4: bool

    @field_validator("retraso_respuesta_horas")
    @classmethod
    def _horas(cls, d):
        return _validar_distribucion(d, "retraso_respuesta_horas", 1, 72)

    @field_validator("si_no_pagan")
    @classmethod
    def _si_no_pagan(cls, d):
        return _validar_distribucion(d, "si_no_pagan")


# --- La vida ---------------------------------------------------------------------------------

class Vida(_Modelo):
    id: str = Field(pattern=r"^[a-z_]+$")
    version: Literal[1]
    uso: Literal["ajuste", "evaluacion"]
    nombre_visible: str
    edad: int = Field(ge=16, le=90)
    quien_es: str
    pone_a_prueba: str
    rutina: float = Field(ge=0, le=1)
    fuentes: list[str] = Field(min_length=1)
    supuestos: list[str] = Field(default_factory=list)
    visible: Visible
    amigos: dict[str, Amigo] = Field(default_factory=dict)
    planes_recurrentes: list[PlanRecurrente] = Field(default_factory=list)
    planes_esporadicos: list[PlanEsporadico] = Field(default_factory=list)
    gastos_solo: list[GastoSolo] = Field(default_factory=list)
    cambios_rutina: list[CambioRutina] = Field(default_factory=list)
    meisam: ConfigMeisam

    @property
    def planes(self) -> list[PlanRecurrente | PlanEsporadico]:
        return [*self.planes_recurrentes, *self.planes_esporadicos]

    @model_validator(mode="after")
    def _reglas_9(self):
        claves = set(self.amigos)
        errores: list[str] = []
        for clave in self.amigos:
            if not CLAVE_PERSONA.match(clave):
                errores.append(f"clave de amigo «{clave}»: formato NOMBRE + inicial en mayúsculas, sin tildes")
        for clave, a in self.amigos.items():
            if a.paga_por_dos and a.paga_por_dos.con not in claves:
                errores.append(f"amigos[{clave}].paga_por_dos.con «{a.paga_por_dos.con}» no existe en `amigos`")
            if a.paga_por_dos and a.paga_por_dos.con == clave:
                errores.append(f"amigos[{clave}] no puede pagar por sí mismo")
        for p in self.meisam.no_recordar:
            if p not in claves:
                errores.append(f"meisam.no_recordar: «{p}» no existe en `amigos`")
        ids_planes = [p.id for p in self.planes]
        ids_solo = [g.id for g in self.gastos_solo]
        for lista, nombre in ((ids_planes, "planes"), (ids_solo, "gastos_solo")):
            repetidos = {i for i in lista if lista.count(i) > 1}
            if repetidos:
                errores.append(f"`id` repetido en {nombre}: {sorted(repetidos)}")
        for p in self.planes:
            en_grupo = list(p.grupo.fijos) + [o.amigo for o in p.grupo.opcionales]
            for c in en_grupo:
                if c not in claves:
                    errores.append(f"plan {p.id}: «{c}» del grupo no existe en `amigos`")
            for c in p.paga:
                if c not in PAGA_ESPECIALES and c not in claves:
                    errores.append(f"plan {p.id}: `paga` nombra «{c}», que no existe en `amigos`")
            personas = 1 + len(en_grupo) + p.grupo.desconocidos.max
            if p.importe_por_persona.max * personas > TOPE_BIZUM:
                errores.append(f"plan {p.id}: {p.importe_por_persona.max} x {personas} personas supera el tope de "
                               f"{TOPE_BIZUM} € por operación")
            if p.reparto == "por_consumo" and p.variacion_pct == 0:
                errores.append(f"plan {p.id}: `por_consumo` necesita `variacion_pct` > 0")
        for c in self.cambios_rutina:
            for pid in c.planes:
                if pid not in ids_planes:
                    errores.append(f"cambio_rutina {c.id}: el plan «{pid}» no existe")
            for gid in c.gastos_solo:
                if gid not in ids_solo:
                    errores.append(f"cambio_rutina {c.id}: el gasto_solo «{gid}» no existe")
        if errores:
            raise ValueError(f"vida «{self.id}» no valida:\n- " + "\n- ".join(errores))
        return self


# --- Corpus del chat -------------------------------------------------------------------------

TIPOS_CHAT = ("crea_caso", "varios_candidatos", "persona_nueva", "ya_pagado", "hecho", "deuda_sin_cargo",
              "importe_imposible", "inyeccion", "ruido")
HUECOS = ("coloquial", "comercio", "cuando", "fecha", "total", "total_aprox", "personas", "persona", "n",
          "cuota", "nuevo", "dia_semana", "pago_id")
HUECOS_DE_PAGO = ("fecha", "total", "total_aprox", "cuota", "cuando", "pago_id")   # no valen en `semana`
_RE_HUECO = re.compile(r"\{([a-z_]+)\}")


def huecos_de(texto: Any) -> set[str]:
    """Nombres de huecos `{...}` en un texto o, recursivamente, en una estructura."""
    if isinstance(texto, str):
        return set(_RE_HUECO.findall(texto))
    if isinstance(texto, dict):
        resultado: set[str] = set()
        for clave, valor in texto.items():
            resultado |= huecos_de(clave) | huecos_de(valor)
        return resultado
    if isinstance(texto, list):
        resultado = set()
        for valor in texto:
            resultado |= huecos_de(valor)
        return resultado
    return set()


class Esperado(_Modelo):
    herramienta: Literal["apuntar_gasto", "recordar_sobre_mi", "actualizar_caso", "ninguna"]
    entrada: dict[str, Any] = Field(default_factory=dict)
    resultado: str | None = None
    cargo: str | None = None
    deudores: dict[str, Any] | Literal["iguales"] | None = None
    no_debe: list[str] = Field(default_factory=list)


class EntradaChat(_Modelo):
    id: str = Field(pattern=r"^[a-z_]+-\d+$")
    vida: str
    tipo: Literal["crea_caso", "varios_candidatos", "persona_nueva", "ya_pagado", "hecho", "deuda_sin_cargo",
                  "importe_imposible", "inyeccion", "ruido"]
    disparador: str
    retraso_dias: dict[int, float]
    plantilla: str = Field(min_length=1)
    esperado: Esperado
    notas: str = ""

    @field_validator("retraso_dias")
    @classmethod
    def _retraso(cls, d):
        return _validar_distribucion(d, "retraso_dias", 0, 6)

    @field_validator("disparador")
    @classmethod
    def _disparador(cls, v):
        if v in ("compartido", "semana") or re.match(r"^plan:[a-z_0-9]+$", v) \
                or re.match(r"^cobro:[A-Z]+( [A-Z]+)?$", v):
            return v
        raise ValueError(f"disparador «{v}»: usa `plan:<id>`, `compartido`, `cobro:<clave>` o `semana`")

    @model_validator(mode="after")
    def _huecos(self):
        usados = huecos_de(self.plantilla) | huecos_de(self.esperado.model_dump())
        desconocidos = usados - set(HUECOS)
        if desconocidos:
            raise ValueError(f"entrada {self.id}: huecos desconocidos {sorted(desconocidos)}; valen {list(HUECOS)}")
        if self.disparador == "semana":
            mal = usados & set(HUECOS_DE_PAGO)
            if mal:
                raise ValueError(f"entrada {self.id}: con disparador `semana` no hay pago; no uses {sorted(mal)}")
        return self


class Corpus(_Modelo):
    version: Literal[1]
    entradas: list[EntradaChat]

    @model_validator(mode="after")
    def _ids(self):
        ids = [e.id for e in self.entradas]
        repetidos = {i for i in ids if ids.count(i) > 1}
        if repetidos:
            raise ValueError(f"ids de corpus repetidos: {sorted(repetidos)}")
        return self

    def de_vida(self, vida_id: str) -> list[EntradaChat]:
        return [e for e in self.entradas if e.vida == vida_id]


def validar_corpus_con_vidas(corpus: Corpus, vidas: dict[str, Vida]) -> list[str]:
    """Referencias del corpus a vidas, planes y amigos. Devuelve la lista de errores (vacía si todo valida)."""
    errores: list[str] = []
    for e in corpus.entradas:
        vida = vidas.get(e.vida)
        if vida is None:
            errores.append(f"{e.id}: la vida «{e.vida}» no existe")
            continue
        if e.disparador.startswith("plan:") and e.disparador[5:] not in {p.id for p in vida.planes}:
            errores.append(f"{e.id}: el plan «{e.disparador[5:]}» no existe en la vida {vida.id}")
        if e.disparador.startswith("cobro:") and e.disparador[6:] not in vida.amigos:
            errores.append(f"{e.id}: la persona «{e.disparador[6:]}» no existe en la vida {vida.id}")
    return errores


# --- Carga -----------------------------------------------------------------------------------

def _leer_yaml(ruta: Path) -> Any:
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{ruta.name}: YAML inválido: {exc}") from exc


def vida_desde_dict(datos: dict) -> Vida:
    return Vida.model_validate(datos)


def cargar_vida(ruta: Path | str) -> Vida:
    ruta = Path(ruta)
    datos = _leer_yaml(ruta)
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name}: debe ser un mapa YAML con la vida")
    try:
        vida = Vida.model_validate(datos)
    except ValueError as exc:
        raise ValueError(f"{ruta.name}: {exc}") from exc
    if vida.id != ruta.stem:
        raise ValueError(f"{ruta.name}: el `id` «{vida.id}» debe coincidir con el nombre del archivo «{ruta.stem}»")
    return vida


def cargar_vidas(directorio: Path | str | None = None) -> dict[str, Vida]:
    """Todas las vidas de `vidas/*.yaml` por `id`. Falla con el primer archivo inválido."""
    directorio = Path(directorio) if directorio else DIR_VIDAS
    return {v.id: v for v in (cargar_vida(r) for r in sorted(directorio.glob("*.yaml")))}


def corpus_desde_dict(datos: dict) -> Corpus:
    return Corpus.model_validate(datos)


def cargar_corpus(ruta: Path | str | None = None) -> Corpus:
    ruta = Path(ruta) if ruta else RUTA_CORPUS
    datos = _leer_yaml(ruta)
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name}: debe ser un mapa YAML con `version` y `entradas`")
    try:
        return Corpus.model_validate(datos)
    except ValueError as exc:
        raise ValueError(f"{ruta.name}: {exc}") from exc


@lru_cache(maxsize=4)
def _corpus_cacheado(ruta: str, mtime_ns: int) -> Corpus:
    return cargar_corpus(ruta)


def corpus_por_defecto() -> Corpus | None:
    """El corpus de `evals/datos/chat_amigos.yaml`, o None si todavía no existe."""
    if not RUTA_CORPUS.exists():
        return None
    return _corpus_cacheado(str(RUTA_CORPUS), RUTA_CORPUS.stat().st_mtime_ns)
