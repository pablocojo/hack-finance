"""
Casos de deuda (docs/diseno/deudas-casos.md): el objeto vivo detrás de un momento de `gasto_compartido`.

API pública (todo puro salvo `cargar` y `guardar`; solo el orquestador escribe en disco):

    crear_desde_momento(momento, hoy=None, ahora=None) -> Caso
    saldar_con_movimientos(caso, movimientos, hoy, ahora=None) -> Caso      (cierre.py)
    saldar_casos(casos, movimientos, hoy, ahora=None) -> list[Caso]
    posponer(caso, hoy, dias=2, origen="feedback", ahora=None) -> Caso
    descartar(caso, hoy, motivo, origen="feedback", ahora=None) -> Caso
    cerrar(caso, estado, hoy, motivo="", origen="codigo", ahora=None) -> Caso
    marcar_pedido(caso, contraparte, hoy, origen="usuario", ahora=None) -> Caso
    aplicar_feedback(caso, resultado, hoy, ahora=None) -> Caso
    aplicar_respuesta(caso, respuesta, hoy, ahora=None, origen="llamada") -> Caso    (pregunta pendiente de un caso dudoso)
    listo_para_avisar(caso, hoy) -> bool;  fecha_aviso(caso) -> date;  agrupar_por_contacto(casos) -> list[list[Caso]]
    Curva de amigos (11 nov): crear_desde_momento(..., pregunta=DecisionPregunta) aplica la escalera;
    fijar_plazos(caso, plazos, canales, hoy) (Deudor.avisar_desde y hechos["canal_probable"]);
    propuesta_pregunta(caso, ahora, nombres) (nivel 3, como prop-duda-*); pregunta_sin_respuesta(caso, hoy);
    abre_caso(lista, momento) (ningún pago_individual sobre un cargo que ya tiene caso)
    amigos_desde_casos(casos, hoy) -> list[Amigo];  sincronizar_amigos(modelo, casos, hoy) -> ModeloUsuario
    cargar(usuario_id) -> list[Caso];  guardar(usuario_id, casos) -> None

Escenarios y personas (transiciones.py):
    saldar_manual(caso, contraparte|None, via, motivo, hoy, ahora=None, origen="usuario") -> Caso
    cambiar_escenario(caso, nuevo, motivo, origen, hoy, ahora=None, deudores=None) -> Caso   (tabla TRANSICIONES)
    aplicar_recurrente(caso, momento, hoy, ahora=None) -> Caso;  momento_sintetico(caso, hoy) -> Momento | None
    caso_de_movimiento(...) / deudores_de_peticion(...) / buscar_de_movimiento(...): «X me debe esto»
    limitar_aviso(caso, decision) -> Decision;  sanear_motivo(texto) -> str

La herramienta `actualizar_caso` de la llamada (llamada.py, importar `backend.casos.llamada`):
    aplicar(caso, accion, hoy, ahora=None, *, persona, personas, importe, via, motivo, dias, escenario, respuesta, movimiento) -> Cambio
"""

from __future__ import annotations

from ..plataforma import almacenamiento as _alm
from ..plataforma.tipos import Caso
from .amigos import amigos_desde_casos, olvidar_contacto, purgar, sincronizar_amigos
from .ciclo import (
    ABIERTOS,
    CERRADOS,
    CLAVE_CANAL,
    CLAVE_SIN_DEUDA,
    DIAS_COLA,
    DIAS_POSPONER,
    DIAS_VIDA,
    MOTIVO_DUDOSO,
    MOTIVO_RESUMEN,
    TOLERANCIA,
    agrupar_por_contacto,
    aplicar_feedback,
    aplicar_respuesta,
    caducar,
    cerrar,
    crear_desde_momento,
    de_propuesta,
    decision_dudosa,
    descartar,
    es_dudoso,
    fecha_aviso,
    fijar_plazos,
    importe_pendiente,
    limitar_aviso,
    listo_para_avisar,
    marcar_avisado,
    marcar_ignorado,
    marcar_pedido,
    pendientes,
    posponer,
    pregunta_sin_respuesta,
    propuesta_pregunta,
    sanear_motivo,
    texto_pregunta,
    vincular_propuesta,
)
from .cierre import pagos_entrantes, saldar_casos, saldar_con_movimientos
from .transiciones import (
    DIAS_ESPERA_PAGO_POR_OTRO,
    TRANSICIONES,
    VIAS_MANUALES,
    abre_caso,
    aplicar_recurrente,
    buscar_de_movimiento,
    cambiar_escenario,
    caso_de_movimiento,
    clave_persona,
    comprobar_transicion,
    conciliar_con_historial,
    descartar_persona,
    deudores_de_peticion,
    escenario_por_defecto,
    momento_sintetico,
    saldar_manual,
)

NOMBRE_ARCHIVO = "casos"


def cargar(usuario_id: str) -> list[Caso]:
    """Lee `casos.json` del usuario (vacío si no existe)."""
    return _alm.cargar(usuario_id, NOMBRE_ARCHIVO, tipo=list[Caso], defecto=[])


def guardar(usuario_id: str, casos: list[Caso]) -> None:
    """Guarda `casos.json` (escritura atómica). Hay que llamarla dentro del candado del usuario."""
    _alm.guardar(usuario_id, NOMBRE_ARCHIVO, casos)
