"""
Política de interrupción `beta-jerarquica-v2` (docs/diseno/personalizacion.md §4).

En una frase: «estimo si este aviso te sirve por cómo respondiste a avisos parecidos y solo
interrumpo si lo que te ahorra, para alguien con tu vida, compensa la molestia».

- Reglas duras primero (consentimiento, solo si ahorra o protege, silencios, franja y tope diario).
- Después, Beta-Bernoulli jerárquica global → tipo → tramo → entidad (comercio o contacto),
  con tramos relativos a `umbral_relevante_eur` (20 € sin perfil), y utilidad U = q·B − (1 − q).
- Se aprende por `tipo_momento`, nunca por `modulo_id`: un módulo nuevo hereda lo aprendido.
- `decidir` es pura: no guarda nada (guarda el orquestador).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from ..plataforma.tipos import Celda, Decision, ModeloUsuario, PerfilUsuario, Propuesta, Silencio
from . import motivos as M

VERSION = "beta-jerarquica-v2"

PARAMETROS: dict = {
    "version": VERSION,
    "k": 4.0,                       # cuánto encoge cada nivel hacia el anterior
    "prior": (2.0, 2.0),            # Beta(2, 2) global
    "theta_ahora": 0.5,
    "theta_resumen": -0.3,
    "tope_B": 5.0,
    "factor_fp": 0.8,               # confianza · 0,8^falsos_positivos[tipo]
    "bonus_urgencia": {"alta": 2.0, "media": 0.5, "baja": 0.0},
    "bonus_nomina": 0.5,
    "impacto_nomina": Decimal("0.05"),
    "dias_nomina": 10,
    "umbral_sin_perfil": Decimal("20"),
    "n_exploracion": 3,             # celda del tipo con n < 3: exploración prudente
    "E_max_dinero_debido": Decimal("10"),   # el dinero que te deben no se diluye con el umbral personal
    "factor_E_pregunta": Decimal("0.25"),   # 11 nov (Pablo): una pregunta de un toque (sin acción ni dinero) molesta
                                            # una cuarta parte que un aviso que pide hacer algo
}

TIPOS_PROTECCION = frozenset({"prueba_gratuita", "posible_estafa"})
TIPOS_DINERO_DEBIDO = frozenset({"gasto_compartido"})   # dinero tuyo pendiente de recuperar, no un gasto
CONSENTIMIENTOS_AVISOS = ("copiloto", "avisos")   # personalizacion.md usa «copiloto»; la API, «avisos»


# --- Claves -----------------------------------------------------------------------------------

def normalizar(valor: str | None) -> str | None:
    if not valor:
        return None
    limpio = " ".join(valor.strip().upper().split())
    return limpio or None


def perfil_efectivo(modelo: ModeloUsuario) -> PerfilUsuario | None:
    """El perfil solo cuenta si existe y el usuario no lo ha apagado."""
    return modelo.perfil if modelo.preferencias.usar_perfil else None


def umbral(modelo: ModeloUsuario) -> Decimal:
    perfil = perfil_efectivo(modelo)
    return perfil.umbral_relevante_eur if perfil else PARAMETROS["umbral_sin_perfil"]


def euros_por_molestia(modelo: ModeloUsuario, tipo: str | None = None) -> Decimal:
    """E: lo que elijas en ajustes o, si no, umbral_relevante_eur / 2. El dinero que te deben
    (`gasto_compartido`) no se mide igual que un gasto: su E nunca pasa de 10 € (el de sin perfil)."""
    if modelo.preferencias.euros_por_molestia is not None and modelo.preferencias.euros_por_molestia > 0:
        return modelo.preferencias.euros_por_molestia
    e = umbral(modelo) / 2
    if tipo in TIPOS_DINERO_DEBIDO:
        e = min(e, PARAMETROS["E_max_dinero_debido"])
    return e


def valor_de(propuesta: Propuesta) -> Decimal:
    return propuesta.valor_estimado_eur if propuesta.valor_estimado_eur is not None else Decimal("0")


def tramo(valor: Decimal, umbral_eur: Decimal) -> str:
    if valor < umbral_eur / 2:
        return "bajo"
    if valor < umbral_eur:
        return "medio"
    return "alto"


def entidad(propuesta: Propuesta) -> tuple[str | None, str | None]:
    """(ámbito, valor normalizado): el contacto manda sobre el comercio."""
    contacto = normalizar(propuesta.contraparte)
    if contacto:
        return "contacto", contacto
    comercio = normalizar(propuesta.comercio)
    if comercio:
        return "comercio", comercio
    return None, None


def claves(propuesta: Propuesta, modelo: ModeloUsuario) -> list[str]:
    """Claves de celda de lo general a lo concreto (personalizacion.md §4.1)."""
    t = f"t:{propuesta.tipo_momento}"
    lista = ["global", t, f"{t}|b:{tramo(valor_de(propuesta), umbral(modelo))}"]
    _, ent = entidad(propuesta)
    if ent:
        lista.append(f"{t}|e:{ent}")
    return lista


def es_clave_celda(clave: str) -> bool:
    return clave == "global" or clave.startswith("t:")


def es_proteccion(propuesta: Propuesta) -> bool:
    return propuesta.urgencia == "alta" or propuesta.tipo_momento in TIPOS_PROTECCION


# --- Cálculo ----------------------------------------------------------------------------------

@dataclass
class Nivel:
    clave: str
    previo: float          # media del nivel anterior (prior 0,5 para el global)
    media: float
    celda: Celda


@dataclass
class Calculo:
    claves: list[str]
    niveles: list[Nivel] = field(default_factory=list)
    p: float = 0.5
    c: float = 1.0
    q: float = 0.5
    E: Decimal = Decimal("10")
    umbral: Decimal = Decimal("20")
    tramo: str = "bajo"
    bonus_urgencia: float = 0.0
    bonus_nomina: float = 0.0
    B: float = 0.0
    U: float = 0.0
    dias_hasta_nomina: int | None = None
    sd_tipo: float = 0.0
    n_tipo: int = 0


def dias_hasta_dia_del_mes(dia: int, hoy: date) -> int:
    """Días desde `hoy` hasta el próximo día `dia` del mes (0 si es hoy)."""
    def ultimo_dia(anio: int, mes: int) -> int:
        siguiente = date(anio + (mes == 12), mes % 12 + 1, 1)
        return (siguiente - date(anio, mes, 1)).days

    d = min(dia, ultimo_dia(hoy.year, hoy.month))
    if hoy.day <= d:
        return d - hoy.day
    anio, mes = hoy.year + (hoy.month == 12), hoy.month % 12 + 1
    return (date(anio, mes, min(dia, ultimo_dia(anio, mes))) - hoy).days


def evaluar(propuesta: Propuesta, modelo: ModeloUsuario, ahora: datetime) -> Calculo:
    k = PARAMETROS["k"]
    a0, b0 = PARAMETROS["prior"]
    cal = Calculo(claves=claves(propuesta, modelo))
    cal.umbral = umbral(modelo)
    cal.E = euros_por_molestia(modelo, propuesta.tipo_momento)
    if propuesta.solo_pregunta:
        cal.E = cal.E * PARAMETROS["factor_E_pregunta"]
    valor = valor_de(propuesta)
    cal.tramo = tramo(valor, cal.umbral)

    # 4.1 Beta jerárquica: cada nivel con celda encoge hacia el anterior.
    previo = a0 / (a0 + b0)
    media = previo
    for i, clave in enumerate(cal.claves):
        celda = modelo.estadisticas.get(clave)
        if i == 0:
            celda_g = celda or Celda()
            media = (a0 + celda_g.utiles) / (a0 + b0 + celda_g.utiles + celda_g.molestias)
            if celda:
                cal.niveles.append(Nivel(clave, previo, media, celda))
        elif celda:
            media = (k * previo + celda.utiles) / (k + celda.utiles + celda.molestias)
            cal.niveles.append(Nivel(clave, previo, media, celda))
        if i == 1:   # desviación de la Beta del tipo, para la exploración prudente
            celda_t = celda or Celda()
            alfa = k * previo + celda_t.utiles
            beta = k * (1 - previo) + celda_t.molestias
            s = alfa + beta
            cal.sd_tipo = math.sqrt(alfa * beta / (s * s * (s + 1)))
            cal.n_tipo = celda_t.n
        previo = media
    cal.p = media

    fp = modelo.falsos_positivos.get(propuesta.tipo_momento, 0)
    cal.c = propuesta.confianza * PARAMETROS["factor_fp"] ** fp
    cal.q = min(1.0, max(0.0, cal.p * cal.c))

    # 4.2 Utilidad esperada en euros relativos al perfil.
    cal.bonus_urgencia = PARAMETROS["bonus_urgencia"].get(propuesta.urgencia, 0.0)
    perfil = perfil_efectivo(modelo)
    if perfil and perfil.dia_cobro_nomina:
        cal.dias_hasta_nomina = dias_hasta_dia_del_mes(perfil.dia_cobro_nomina, ahora.date())
        if (
            propuesta.impacto_relativo is not None
            and propuesta.impacto_relativo >= PARAMETROS["impacto_nomina"]
            and cal.dias_hasta_nomina <= PARAMETROS["dias_nomina"]
        ):
            cal.bonus_nomina = PARAMETROS["bonus_nomina"]
    cal.B = min(PARAMETROS["tope_B"], float(valor / cal.E) + cal.bonus_urgencia + cal.bonus_nomina)
    cal.U = cal.q * cal.B - (1 - cal.q)
    return cal


def utilidad_optimista(cal: Calculo) -> float:
    """U con p + una desviación de la Beta del tipo (beneficio de la duda mientras sé poco)."""
    q = min(1.0, (cal.p + cal.sd_tipo)) * cal.c
    return q * cal.B - (1 - q)


# --- Reglas duras -----------------------------------------------------------------------------

def silencio_que_coincide(propuesta: Propuesta, modelo: ModeloUsuario) -> Silencio | None:
    comercio = normalizar(propuesta.comercio)
    contacto = normalizar(propuesta.contraparte)
    for s in modelo.preferencias.silencios:
        valor = normalizar(s.valor)
        if s.ambito == "tipo" and s.valor == propuesta.tipo_momento:
            return s
        if s.ambito == "comercio" and comercio and valor == comercio:
            return s
        if s.ambito == "contacto" and contacto and valor == contacto:
            return s
    return None


def avisos_hoy(modelo: ModeloUsuario, ahora: datetime) -> int:
    return sum(1 for f in modelo.ultimos_avisos if f.date() == ahora.date())


def en_franja(modelo: ModeloUsuario, ahora: datetime) -> bool:
    p = modelo.preferencias
    return p.hora_inicio <= ahora.hour < p.hora_fin


def _decision(propuesta: Propuesta, accion: str, cal: Calculo, motivos: list[str]) -> Decision:
    limpios = [m for m in motivos if m][:3]
    return Decision(
        propuesta_id=propuesta.id,
        accion=accion,
        puntuacion=round(cal.U, 4),
        probabilidad_util=round(cal.q, 4),
        motivos=limpios or [M.GENERICO],
        politica=VERSION,
    )


def decidir(propuesta: Propuesta, modelo: ModeloUsuario, ahora: datetime) -> Decision:
    """Pura. La primera regla que aplica, gana (personalizacion.md §4.3)."""
    cal = evaluar(propuesta, modelo, ahora)
    proteccion = es_proteccion(propuesta)

    # 1. Módulo no activo o sin consentimiento.
    if propuesta.modulo_id not in modelo.modulos_activos:
        return _decision(propuesta, "silenciar", cal, [M.modulo_inactivo(propuesta.modulo_id)])
    if not any(c in modelo.consentimientos for c in CONSENTIMIENTOS_AVISOS):
        return _decision(propuesta, "silenciar", cal, [M.SIN_CONSENTIMIENTO])

    # 2. Solo si ahorra o protege.
    if valor_de(propuesta) <= 0 and not proteccion:
        return _decision(propuesta, "silenciar", cal, [M.NO_AHORRA])

    valor_txt = M.valor(propuesta, perfil_efectivo(modelo))
    aprendido_txt = M.aprendido(propuesta, cal)

    # 3. Silencio explícito (la posible estafa urgente baja al resumen, no se calla).
    silencio = silencio_que_coincide(propuesta, modelo)
    if silencio:
        if propuesta.tipo_momento == "posible_estafa" and propuesta.urgencia == "alta":
            return _decision(propuesta, "resumen", cal, [M.silencio(silencio, propuesta, estafa=True), valor_txt])
        return _decision(propuesta, "silenciar", cal, [M.silencio(silencio, propuesta)])

    # 4. Compensa interrumpir: salvo fuera de franja o con el tope diario (la urgencia alta no cuenta).
    if cal.U >= PARAMETROS["theta_ahora"]:
        if not en_franja(modelo, ahora):
            return _decision(propuesta, "resumen", cal, [M.fuera_de_franja(modelo, ahora), valor_txt, aprendido_txt])
        n_hoy = avisos_hoy(modelo, ahora)
        tope = n_hoy >= modelo.preferencias.max_avisos_dia
        if tope and propuesta.urgencia != "alta":
            return _decision(propuesta, "resumen", cal, [M.tope_diario(n_hoy), valor_txt, aprendido_txt])
        primero = M.URGENTE_SIN_TOPE if tope else None
        if primero is None and propuesta.solo_pregunta:
            primero = M.PREGUNTA_UN_TOQUE
        if primero is None and propuesta.tipo_momento in TIPOS_DINERO_DEBIDO:
            primero = M.DINERO_DEBIDO
        return _decision(propuesta, "notificar_ahora", cal, [primero, valor_txt, aprendido_txt])

    # 5. Vale la pena, pero no tanto como para interrumpir.
    if cal.U >= PARAMETROS["theta_resumen"]:
        return _decision(propuesta, "resumen", cal, [M.AL_RESUMEN, valor_txt, aprendido_txt])

    # 6. No compensa: se calla, salvo protección o exploración prudente.
    if proteccion:
        return _decision(propuesta, "resumen", cal, [M.proteccion(propuesta), valor_txt, aprendido_txt])
    if cal.n_tipo < PARAMETROS["n_exploracion"] and utilidad_optimista(cal) >= PARAMETROS["theta_resumen"]:
        return _decision(propuesta, "resumen", cal, [M.EXPLORACION, valor_txt])
    return _decision(propuesta, "silenciar", cal, [M.NO_COMPENSA, valor_txt, aprendido_txt])
