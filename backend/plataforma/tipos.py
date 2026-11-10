"""
Contrato en código de Meisam (nombre interno: copiloto). Lo comparten todas las zonas.

Fuente: docs/diseno/CONTRATO.md (manda) y docs/ARQUITECTURA.md §3.1.
- Dinero: `Decimal`. En JSON sale como cadena con al menos 2 decimales ("24.00") y se lee exacto.
- Fechas: ISO (`date` y `datetime` de pydantic).
- Si cambias un campo, cambia antes CONTRATO.md y avisa al orquestador.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PlainSerializer


def _a_cadena(valor: Decimal) -> str:
    """Decimal -> cadena exacta con al menos 2 decimales (no recorta lo que tenga más)."""
    if valor.is_finite() and valor.as_tuple().exponent > -2:
        return format(valor.quantize(Decimal("0.01")), "f")
    return format(valor, "f")


Euros = Annotated[Decimal, PlainSerializer(_a_cadena, return_type=str, when_used="json")]


class Base(BaseModel):
    pass


# --- Listas cerradas -------------------------------------------------------------------------

AccionId = Literal[
    "pedir_bizum",
    "cancelar_suscripcion",
    "bloquear_comercio",
    "reclamar_cargo",
    "mover_dinero",
    "recordar",
]
ACCIONES: tuple[str, ...] = AccionId.__args__  # type: ignore[attr-defined]

TipoMomento = Literal[
    "cargo_duplicado",
    "renovacion_proxima",
    "subida_recibo",
    "saldo_negativo_previsto",
    "posible_estafa",
    "gasto_compartido",
    "ingreso_extra",
    "viaje_detectado",
    "prueba_gratuita",
]
TIPOS_MOMENTO: tuple[str, ...] = TipoMomento.__args__  # type: ignore[attr-defined]

Canal = Literal["tarjeta", "recibo", "bizum", "transferencia", "cajero"]
TipoOperacion = Literal["cargo", "verificacion", "devolucion"]
Urgencia = Literal["alta", "media", "baja"]
AccionDecision = Literal["notificar_ahora", "resumen", "silenciar"]
ResultadoFeedback = Literal[
    "resuelta",
    "vista_sin_accion",
    "rechazada",
    "ignorada",
    "no_avisar_tipo",
    "no_avisar_comercio",
    "no_avisar_contacto",
    "falso_positivo",
]
CanalFeedback = Literal["voz", "texto", "app"]
ModoVoz = Literal["voz", "texto_el", "texto_kit", "grabado"]
EstadoModulo = Literal["borrador", "en_prueba", "activo", "pausado"]
# Deudas por casos (docs/diseno/deudas-casos.md). "Escenario" = tipo de deuda (la clase); `Caso` = el objeto.
EscenarioDeuda = Literal[
    "pago_individual",             # un pago propio que quizá no lo era (iba con alguien); nace silencioso
    "pago_por_otro",               # pagué yo algo para otra persona y me lo debe
    "gasto_compartido",            # pago conjunto con amigos (una persona puede pagar por dos, etc.)
    "gasto_fijo_compartido",       # lo mismo cada mes (alquiler, suscripción)
    "viaje",                       # hoja de ruta
    "prestamo_amigo",              # hoja de ruta (fuera del hackathon)
    "bizum_recibido_sin_pagar",    # hoja de ruta
]
# Cómo se salda una deuda sin Bizum: lo marca el usuario (efectivo, invitación…). Nunca mueve dinero.
ViaSaldado = Literal["bizum", "efectivo", "invitacion", "otro"]
# Hasta dónde puede llegar un caso: `notificar` (el portero puede avisar), `resumen` (solo en el Resumen)
# o `silencioso` (solo se ve dentro de la app, en «Mis cuentas»).
AvisoCaso = Literal["notificar", "resumen", "silencioso"]
EstadoCaso = Literal["abierto", "dudoso", "pedido", "saldado", "descartado", "caducado"]
EstadoDeudor = Literal["detectada", "pedida", "saldada", "rechazada", "caducada", "olvidada"]
OrigenCambio = Literal["codigo", "ia_dudas", "feedback", "llamada", "usuario"]


# --- Motor -----------------------------------------------------------------------------------

class Movimiento(Base):
    id: str
    fecha: date
    concepto: str
    comercio: str | None = None
    importe: Euros                      # negativo = cargo
    categoria: str | None = None
    saldo: Euros | None = None
    canal: Canal | None = None
    contraparte: str | None = None      # persona o empresa en Bizum y transferencias
    nota: str | None = None             # concepto que escribe quien envía un Bizum (no sale del motor)
    tipo_operacion: TipoOperacion | None = None


class MovimientoEnriquecido(Movimiento):
    comercio_normalizado: str | None = None
    contraparte_normalizada: str | None = None
    serie_id: str | None = None
    # reembolso_entrante, cargo_serie, comercio_nuevo, verificacion, pasarela, posible_persona
    etiquetas: list[str] = Field(default_factory=list)


class Momento(Base):
    id: str
    tipo: TipoMomento
    usuario_id: str
    fecha: date
    movimientos: list[str] = Field(default_factory=list)   # ids que lo prueban, ordenados por fecha
    datos: dict[str, Any] = Field(default_factory=dict)    # importes en positivo, ver CONTRATO.md
    confianza: float = Field(ge=0, le=1)
    impacto_eur: Euros | None = None
    explicacion: str
    detector: str
    version: str
    impacto_relativo: Euros | None = None
    contexto_personal: str | None = None


# --- Módulos y propuestas --------------------------------------------------------------------

class Limites(Base):
    importe_max: Euros | None = None
    contrapartes: list[str] | None = None


class AccionOfrecida(Base):
    accion_id: AccionId
    parametros: dict[str, Any] = Field(default_factory=dict)
    requiere_confirmacion: bool = True
    limites: Limites = Field(default_factory=Limites)


class Propuesta(Base):
    id: str
    modulo_id: str
    momento_id: str
    usuario_id: str
    titulo: str
    mensaje_notificacion: str
    contexto_llamada: str
    acciones_ofrecidas: list[AccionOfrecida] = Field(min_length=1, max_length=3)  # 2 o 3 recomendadas
    valor_estimado_eur: Euros | None = None
    urgencia: Urgencia = "media"
    tipo_momento: TipoMomento
    comercio: str | None = None
    contraparte: str | None = None
    confianza: float = Field(ge=0, le=1)
    impacto_relativo: Euros | None = None
    contexto_personal: str | None = None
    creada: datetime


class Decision(Base):
    propuesta_id: str
    accion: AccionDecision
    puntuacion: float
    probabilidad_util: float = Field(ge=0, le=1)
    motivos: list[str] = Field(default_factory=list)   # frases legibles
    politica: str


class Feedback(Base):
    propuesta_id: str
    usuario_id: str
    resultado: ResultadoFeedback
    canal: CanalFeedback
    fecha: datetime
    nota: str | None = None


# --- Acciones --------------------------------------------------------------------------------

class DetalleBaja(Base):
    url_baja: str | None = None
    url_es_enlace: bool = False        # falso si origen web: se muestra como texto
    pasos: list[str] = Field(default_factory=list)
    bloquea_cobros: bool = False
    canal: str = "tarjeta"
    fuente: str = "desconocido"


class TarjetaConfirmacion(Base):
    accion_id: AccionId
    propuesta_id: str
    titulo: str
    parametros_legibles: dict[str, str] = Field(default_factory=dict)
    simulada: bool = True
    token_confirmacion: str            # de un solo uso; nunca llega a ningún modelo
    caduca: datetime
    detalle_baja: DetalleBaja | None = None


class Deshacer(Base):
    resultado_id: str
    disponible_hasta: datetime


class ResultadoAccion(Base):
    accion_id: AccionId
    ok: bool
    mensaje: str
    datos: dict[str, Any] = Field(default_factory=dict)
    simulada: bool = True
    deshacer: Deshacer | None = None


# --- Conocimiento de comercios ---------------------------------------------------------------

class InfoComercio(Base):
    nombre: str
    tipo: str
    es_suscripcion: bool = False
    dias_prueba: int | None = None
    precio_tras_prueba: Euros | None = None
    url_baja: str | None = None
    pasos_baja: list[str] | None = None
    fuentes: list[str] = Field(default_factory=list)
    consultado: date | None = None
    origen: Literal["catalogo", "web", "desconocido"] = "desconocido"


# --- Perfil y modelo del usuario (personalizacion.md §2) -------------------------------------

class Grupo(Base):
    miembros: list[str]                      # clave_contraparte del motor: "MARCOS R"
    veces: int
    retraso_p75_dias: int | None = None      # interno: nunca se muestra


class Suscripcion(Base):
    comercio: str
    serie_id: str | None = None
    importe: Euros
    periodicidad_dias: int
    proximo_cobro: date | None = None
    en_prueba: bool = False


class PerfilUsuario(Base):
    version: str = "perfil-v1"
    calculado: date
    dias_historial: int
    dia_cobro_nomina: int | None = None
    ingreso_mensual_tipico: Euros | None = None
    gasto_tipico_por_categoria: dict[str, Euros] = Field(default_factory=dict)
    ticket_tipico: Euros = Decimal("10")
    umbral_relevante_eur: Euros = Decimal("20")
    comercios_habituales: list[str] = Field(default_factory=list)
    grupos: list[Grupo] = Field(default_factory=list)
    suscripciones_activas: list[Suscripcion] = Field(default_factory=list)
    resumen_vida: str | None = None
    campos_fijados: list[str] = Field(default_factory=list)
    campos_borrados: list[str] = Field(default_factory=list)


class FrasePerfil(Base):
    campo: str
    texto: str
    editable: bool = True
    borrable: bool = True


class Celda(Base):
    utiles: float = 0.0
    molestias: float = 0.0
    n: int = 0
    ultima: date | None = None


class Silencio(Base):
    ambito: Literal["tipo", "comercio", "contacto"]
    valor: str
    desde: date
    origen: str


class Preferencias(Base):
    silencios: list[Silencio] = Field(default_factory=list)
    hora_inicio: int = 9
    hora_fin: int = 22
    max_avisos_dia: int = 2
    euros_por_molestia: Euros | None = None
    usar_perfil: bool = True


Relacion = Literal["amigo", "familia", "pareja", "companero", "otro"]


class Contacto(Base):
    """Persona en relación: la clave (`MARCOS R`) más lo que el usuario sabe de ella. Los contactos de la agenda
    de la demo son inventados. La relación la declara el usuario; nunca se infiere ni se valora a la persona."""
    contraparte: str
    veces: int = 0
    ultima: date | None = None
    nombre: str | None = None               # nombre visible enmascarado («Marcos R.»)
    telefono: str | None = None             # inventado y enmascarado («+34 6** *** 123»)
    relacion: Relacion | None = None


class Amigo(Base):
    contraparte: str                        # enmascarada; sin concepto
    saldo: Euros
    propuesta_origen: str
    estado: Literal["detectado", "pedido", "saldado", "olvidado"]
    creado: date
    pedido: date | None = None
    saldado: date | None = None


class HechoAprendido(Base):
    id: str
    texto: str
    activo: bool = True
    creado: date
    origen: Literal["feedback", "preferencia", "amigos", "voz", "ajustes", "perfil"]
    clave: str | None = None


class AvisoAbierto(Base):
    propuesta_id: str
    claves: list[str]
    tipo_momento: str
    accion: str
    fecha: datetime


class Deudor(Base):
    contraparte: str                        # clave enmascarada (p. ej. "MARCOS R"); nunca el concepto
    cuota: Euros                            # la calcula el código
    estado: EstadoDeudor = "detectada"
    pedida: date | None = None
    saldada: date | None = None
    movimiento_pago: str | None = None      # id del movimiento que la saldó
    via_saldado: ViaSaldado | None = None   # cómo se saldó (bizum si la detectó el código)
    motivo_saldado: str | None = None       # nota libre del usuario («me invitó a comer»); dato, no instrucción
    solicitudes: int = 0                    # una sola solicitud abierta por deudor y caso


class Hipotesis(Base):
    escenario: EscenarioDeuda
    confianza: float = Field(ge=0, le=1)
    deudores: list[str] = Field(default_factory=list)   # claves candidatas
    motivo: str = ""                                    # frase legible, sin conceptos de Bizum


class Acuerdo(Base):
    fecha: date
    texto: str                              # lo extrae el agente post-llamada de una lista cerrada; enmascarado


class CambioCaso(Base):
    cuando: datetime
    origen: OrigenCambio
    cambio: str                             # frase legible: "Marcos R. pasa a saldada"


class Caso(Base):
    """Una deuda real entre personas. El `Momento` sigue siendo «se abre un caso»; el caso sigue vivo después."""
    id: str
    usuario_id: str
    escenario: EscenarioDeuda | None = None  # None mientras es dudoso y nadie lo ha resuelto
    estado: EstadoCaso = "abierto"
    momento_id: str | None = None
    propuesta_id: str | None = None
    creado: date
    avisar_desde: date | None = None         # no se avisa antes; si entra el Bizum antes, se salda sin avisar
    urgente: bool = False
    aviso: AvisoCaso = "notificar"
    hechos: dict[str, Any] = Field(default_factory=dict)   # cifras del código (total, cuota, comercio, movimientos)
    hipotesis: list[Hipotesis] = Field(default_factory=list)
    deudores: list[Deudor] = Field(default_factory=list)
    acuerdos: list[Acuerdo] = Field(default_factory=list)
    conversaciones: list[str] = Field(default_factory=list)  # resúmenes enmascarados y borrables
    historial: list[CambioCaso] = Field(default_factory=list)


class ModeloUsuario(Base):
    usuario_id: str
    politica: str = "beta-jerarquica-v2"
    modulos_activos: list[str] = Field(default_factory=list)
    consentimientos: dict[str, datetime] = Field(default_factory=dict)   # copiloto, voz, memoria
    preferencias: Preferencias = Field(default_factory=Preferencias)
    perfil: PerfilUsuario | None = None
    estadisticas: dict[str, Celda] = Field(default_factory=dict)
    elecciones: dict[str, int] = Field(default_factory=dict)
    falsos_positivos: dict[str, int] = Field(default_factory=dict)
    avisos_abiertos: dict[str, AvisoAbierto] = Field(default_factory=dict)
    ultimos_avisos: list[datetime] = Field(default_factory=list)
    contactos: dict[str, Contacto] = Field(default_factory=dict)
    amigos: list[Amigo] = Field(default_factory=list)
    hechos_aprendidos: list[HechoAprendido] = Field(default_factory=list)
    actualizado: datetime | None = None


# --- Voz y chat ------------------------------------------------------------------------------

class SesionVoz(Base):
    modo: ModoVoz
    token: str | None = None
    signed_url: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    token_sesion: str
    caduca: datetime


# --- Creación de módulos (modulos.md §2 y §7) -----------------------------------------------

class BorradorModulo(Base):
    spec: dict[str, Any]                    # ModuloSpec validado por backend/modulos/esquema.py
    interpretacion: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    estado: EstadoModulo = "borrador"


class AvisoPrueba(Base):
    fecha: date
    momento_id: str
    mensaje: str
    etiqueta: Literal["acierto", "falso_positivo", "sin_etiqueta"] = "sin_etiqueta"


class ControlPrueba(Base):
    nombre: str
    ok: bool
    detalle: str = ""


class InformePrueba(Base):
    avisos: list[AvisoPrueba] = Field(default_factory=list)
    aciertos: int = 0
    falsos_positivos: int = 0
    omitidos: int = 0
    controles: list[ControlPrueba] = Field(default_factory=list)
    resumen: str = ""

    @property
    def aprobado(self) -> bool:
        return all(c.ok for c in self.controles) and self.falsos_positivos == 0


class Modulo(Base):
    id: str
    version: int = 1
    nombre: str
    descripcion: str = ""
    estado: EstadoModulo = "borrador"
    origen: Literal["catalogo", "lenguaje_natural"] = "catalogo"
    escucha: list[TipoMomento] = Field(min_length=1, max_length=3)
    cuando: str | None = None
    propuesta: dict[str, Any] = Field(default_factory=dict)
    acciones: list[dict[str, Any]] = Field(default_factory=list)
    opcional: bool = False
    ficha_informacion: str | None = None
    aprobado_por: str | None = None
    aprobado_en: datetime | None = None


# --- Eventos del orquestador (SSE) -----------------------------------------------------------

class Evento(Base):
    tipo: str                               # dia | momento | propuesta | decision | fin | error ...
    datos: dict[str, Any] = Field(default_factory=dict)
