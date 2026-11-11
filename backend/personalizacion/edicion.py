"""
«Lo que he aprendido de ti»: ver, editar y borrar (personalizacion.md §6). Todo puro: devuelve un
modelo nuevo y no guarda nada (guarda el orquestador).

- Perfil: `frases_perfil` lo cuenta en frases; `editar_perfil` lo cambia (el campo pasa a `campos_fijados`
  y `perfilar` ya no lo pisa); `borrar_campo_perfil` lo deja en su valor por defecto (`campos_borrados`);
  `borrar_perfil` apaga el perfil entero (motor y política vuelven al arranque en frío).
- Hechos aprendidos: se apagan o se borran (deshacen su efecto: reinician la celda o quitan el silencio);
  solo los de voz se editan, y con los mismos filtros que el resumen.
- `olvidar_todo` deja solo `consentimientos` y `modulos_activos`.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ..motor.normalizar import clave_contraparte
from ..plataforma.tipos import FrasePerfil, HechoAprendido, ModeloUsuario, PerfilUsuario, Preferencias, Silencio
from . import aprende_amigos
from .amigos import buscar_contacto
from .memoria import texto_permitido
from .motivos import euros
from .perfil import CAMPOS_CALCULADOS, nombre_visible, resumen_plantilla
from .politica import normalizar

# Campos que el cliente puede reescribir; el resto solo se puede borrar.
CAMPOS_EDITABLES = (
    "dia_cobro_nomina", "ingreso_mensual_tipico", "umbral_relevante_eur", "resumen_vida",
    "comercios_habituales", "grupos", "suscripciones_activas",
)
CAMPOS_LISTA = ("comercios_habituales", "grupos", "suscripciones_activas")
MAX_RESUMEN = 300
UMBRAL_MIN, UMBRAL_MAX = Decimal("1"), Decimal("1000")
INGRESO_MAX = Decimal("100000")
MAX_HECHO_VOZ = 100


class NoExiste(ValueError):
    """El hecho o el campo que se pide no existe (el orquestador lo convierte en 404)."""


# --- Ver ---------------------------------------------------------------------------------------

def frases_perfil(perfil: PerfilUsuario | None) -> list[FrasePerfil]:
    """El perfil, campo a campo, en lenguaje claro. Los campos vacíos o borrados no salen."""
    if perfil is None:
        return []
    f: list[FrasePerfil] = []

    def anadir(campo: str, texto: str) -> None:
        f.append(FrasePerfil(campo=campo, texto=texto, editable=campo in CAMPOS_EDITABLES, borrable=True))

    if perfil.dia_cobro_nomina:
        anadir("dia_cobro_nomina", f"Tu nómina suele llegar el día {perfil.dia_cobro_nomina}.")
    if perfil.ingreso_mensual_tipico:
        anadir("ingreso_mensual_tipico", f"Te entran unos {euros(perfil.ingreso_mensual_tipico)} al mes.")
    if perfil.gasto_tipico_por_categoria:
        partes = ", ".join(f"{c} {euros(v)}" for c, v in perfil.gasto_tipico_por_categoria.items())
        anadir("gasto_tipico_por_categoria", f"Gastas al mes, más o menos: {partes}.")
    if "ticket_tipico" not in perfil.campos_borrados:
        anadir("ticket_tipico", f"Tu compra típica ronda {euros(perfil.ticket_tipico)}.")
    if "umbral_relevante_eur" not in perfil.campos_borrados:
        anadir("umbral_relevante_eur", f"Para ti, algo es relevante a partir de unos {euros(perfil.umbral_relevante_eur)}: "
                                       "por debajo no te interrumpo.")
    if perfil.comercios_habituales:
        anadir("comercios_habituales",
               "Tus comercios de siempre: " + ", ".join(nombre_visible(c) for c in perfil.comercios_habituales) + ".")
    if len(perfil.grupos) == 1:
        anadir("grupos", f"Divides gastos con un grupo de {len(perfil.grupos[0].miembros)} personas.")
    elif perfil.grupos:
        anadir("grupos", f"Divides gastos con {len(perfil.grupos)} grupos de personas.")
    if perfil.suscripciones_activas:
        lista = ", ".join(f"{nombre_visible(s.comercio)} ({euros(s.importe)})" for s in perfil.suscripciones_activas)
        anadir("suscripciones_activas", f"Tus suscripciones: {lista}.")
    if perfil.resumen_vida:
        anadir("resumen_vida", perfil.resumen_vida)
    return f


# --- Perfil: editar y borrar -------------------------------------------------------------------

def _con_perfil(modelo: ModeloUsuario) -> tuple[ModeloUsuario, PerfilUsuario]:
    if modelo.perfil is None:
        raise ValueError("Todavía no hay perfil: hacen falta al menos 28 días de movimientos (o está apagado).")
    nuevo = modelo.model_copy(deep=True)
    return nuevo, nuevo.perfil


def _decimal(valor: Any, minimo: Decimal, maximo: Decimal, que: str) -> Decimal:
    if isinstance(valor, bool):
        raise ValueError(f"{que}: tiene que ser un importe en euros.")
    try:
        d = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{que}: tiene que ser un importe en euros.") from None
    if not minimo <= d <= maximo:
        raise ValueError(f"{que}: tiene que estar entre {euros(minimo)} y {euros(maximo)}.")
    return d


def _quedan(valor: Any, actuales: list[str], que: str) -> list[str]:
    """Quitar elementos: `valor` es lo que se queda y debe salir de lo que hay (no se puede inventar)."""
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        raise ValueError(f"{que}: envía la lista de lo que se queda.")
    ajenos = [v for v in valor if v not in actuales]
    if ajenos:
        raise ValueError(f"{que}: solo se puede quitar, no añadir ({', '.join(ajenos)}).")
    return [a for a in actuales if a in valor]


def _regenerar_resumen(perfil: PerfilUsuario) -> None:
    """El resumen redactado por plantilla se rehace con lo que queda (el escrito a mano no se toca)."""
    if "resumen_vida" in perfil.campos_fijados or "resumen_vida" in perfil.campos_borrados:
        return
    perfil.resumen_vida = resumen_plantilla(perfil, cenas="dividir cenas" in (perfil.resumen_vida or ""))


def editar_perfil(modelo: ModeloUsuario, campo: str, valor: Any) -> ModeloUsuario:
    """Cambia un campo del perfil y lo fija (va a `campos_fijados`). Quitar de una lista: `valor` es lo
    que se queda (comercios por nombre, suscripciones por `serie_id`, grupos por posición «0», «1»…)."""
    if campo not in CAMPOS_CALCULADOS:
        raise NoExiste(f"El perfil no tiene el campo {campo!r}.")
    if campo not in CAMPOS_EDITABLES:
        raise ValueError(f"El campo {campo!r} no se edita, solo se puede borrar.")
    nuevo, perfil = _con_perfil(modelo)
    if campo == "dia_cobro_nomina":
        if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 31:
            raise ValueError("El día de cobro tiene que ser un número del 1 al 31.")
        perfil.dia_cobro_nomina = valor
    elif campo == "ingreso_mensual_tipico":
        perfil.ingreso_mensual_tipico = _decimal(valor, Decimal("1"), INGRESO_MAX, "El ingreso mensual")
    elif campo == "umbral_relevante_eur":
        perfil.umbral_relevante_eur = _decimal(valor, UMBRAL_MIN, UMBRAL_MAX, "El umbral")
    elif campo == "resumen_vida":
        perfil.resumen_vida = texto_permitido(valor, MAX_RESUMEN)
    elif campo == "comercios_habituales":
        perfil.comercios_habituales = _quedan(valor, perfil.comercios_habituales, "Comercios")
    elif campo == "suscripciones_activas":
        quedan = _quedan(valor, [s.serie_id for s in perfil.suscripciones_activas], "Suscripciones")
        perfil.suscripciones_activas = [s for s in perfil.suscripciones_activas if s.serie_id in quedan]
    else:  # grupos
        quedan = _quedan(valor, [str(i) for i in range(len(perfil.grupos))], "Grupos")
        perfil.grupos = [g for i, g in enumerate(perfil.grupos) if str(i) in quedan]
    perfil.campos_borrados = [c for c in perfil.campos_borrados if c != campo]
    if campo not in perfil.campos_fijados:
        perfil.campos_fijados.append(campo)
    if campo != "resumen_vida":
        _regenerar_resumen(perfil)
    return nuevo


def borrar_campo_perfil(modelo: ModeloUsuario, campo: str) -> ModeloUsuario:
    """Deja el campo en su valor por defecto y en `campos_borrados`: `perfilar` ya no lo recalcula."""
    if campo not in CAMPOS_CALCULADOS:
        raise NoExiste(f"El perfil no tiene el campo {campo!r}.")
    nuevo, perfil = _con_perfil(modelo)
    setattr(perfil, campo, PerfilUsuario.model_fields[campo].get_default(call_default_factory=True))
    perfil.campos_fijados = [c for c in perfil.campos_fijados if c != campo]
    if campo not in perfil.campos_borrados:
        perfil.campos_borrados.append(campo)
    if campo != "resumen_vida":
        _regenerar_resumen(perfil)
    return nuevo


def borrar_perfil(modelo: ModeloUsuario) -> ModeloUsuario:
    """`perfil = None` y `usar_perfil = False`: motor y política vuelven al arranque en frío."""
    modelo = modelo.model_copy(deep=True)
    modelo.perfil = None
    modelo.preferencias.usar_perfil = False
    modelo.hechos_aprendidos = [h for h in modelo.hechos_aprendidos if h.origen != "perfil"]
    return modelo


def usar_perfil(modelo: ModeloUsuario, activo: bool) -> ModeloUsuario:
    """Apagar equivale a borrar el perfil. Encender solo quita el freno: el orquestador lo recalcula."""
    if not activo:
        return borrar_perfil(modelo)
    nuevo = modelo.model_copy(deep=True)
    nuevo.preferencias.usar_perfil = True
    return nuevo


# --- Hechos aprendidos --------------------------------------------------------------------------

def _hecho(modelo: ModeloUsuario, hecho_id: str) -> HechoAprendido:
    for h in modelo.hechos_aprendidos:
        if h.id == hecho_id:
            return h
    raise NoExiste(f"No hay nada aprendido con el identificador {hecho_id!r}.")


def _silencio_de(clave: str | None) -> tuple[str, str] | None:
    if clave and clave.startswith("silencio:"):
        partes = clave.split(":", 2)
        if len(partes) == 3:
            return partes[1], partes[2]
    return None


def _deshacer_efecto(modelo: ModeloUsuario, h: HechoAprendido) -> None:
    """Quita el silencio o reinicia la celda de la que salió el hecho (en el modelo ya copiado)."""
    silencio = _silencio_de(h.clave)
    if silencio:
        ambito, valor = silencio
        modelo.preferencias.silencios = [
            s for s in modelo.preferencias.silencios
            if not (s.ambito == ambito and normalizar(s.valor) == normalizar(valor))]
    elif h.clave and h.clave.startswith("t:"):
        sin_tramo = "|" not in h.clave      # el hecho del tipo arrastra también sus tramos y entidades
        for k in [k for k in modelo.estadisticas if k == h.clave or (sin_tramo and k.startswith(h.clave + "|"))]:
            del modelo.estadisticas[k]
        if sin_tramo:   # y los hechos de sus tramos, que se quedarían sin celda
            modelo.hechos_aprendidos = [x for x in modelo.hechos_aprendidos
                                        if not (x.origen == "feedback" and (x.clave or "").startswith(h.clave + "|"))]


def apagar_hecho(modelo: ModeloUsuario, hecho_id: str) -> ModeloUsuario:
    """El hecho queda a la vista pero inactivo, y su efecto se deshace (§4.6)."""
    nuevo = modelo.model_copy(deep=True)
    h = _hecho(nuevo, hecho_id)
    if h.activo:
        _deshacer_efecto(nuevo, h)
        h.activo = False
    return nuevo


def activar_hecho(modelo: ModeloUsuario, hecho_id: str) -> ModeloUsuario:
    """Reactiva un hecho apagado. Un silencio vuelve a regir; lo aprendido por tus respuestas no vuelve
    solo (se reinició): reaparecerá si repites esas respuestas."""
    nuevo = modelo.model_copy(deep=True)
    h = _hecho(nuevo, hecho_id)
    if h.activo:
        return nuevo
    silencio = _silencio_de(h.clave)
    if silencio:
        ambito, valor = silencio
        nuevo.preferencias.silencios.append(Silencio(ambito=ambito, valor=valor, desde=h.creado, origen=h.id))
    elif h.origen == "feedback":
        raise ValueError("Esto lo aprendí de tus respuestas y al apagarlo lo olvidé; volverá a aparecer si lo repites.")
    h.activo = True
    return nuevo


def editar_hecho(modelo: ModeloUsuario, hecho_id: str, texto: str) -> ModeloUsuario:
    """Solo los hechos de voz se editan (los demás se apagan o se borran), con los mismos filtros."""
    nuevo = modelo.model_copy(deep=True)
    h = _hecho(nuevo, hecho_id)
    if h.origen != "voz":
        raise ValueError("Este hecho no se edita: se puede apagar o borrar.")
    h.texto = texto_permitido(texto, MAX_HECHO_VOZ)
    return nuevo


def borrar_hecho(modelo: ModeloUsuario, hecho_id: str) -> ModeloUsuario:
    nuevo = modelo.model_copy(deep=True)
    h = _hecho(nuevo, hecho_id)
    if h.activo:
        _deshacer_efecto(nuevo, h)
    nuevo.hechos_aprendidos = [x for x in nuevo.hechos_aprendidos if x.id != hecho_id]
    return nuevo


def borrar_amigo(modelo: ModeloUsuario, contraparte: str, propuesta_origen: str | None = None) -> ModeloUsuario:
    """Quita a un amigo pendiente (por su nombre enmascarado y, si hace falta, su propuesta)."""
    nuevo = modelo.model_copy(deep=True)
    antes = len(nuevo.amigos)
    nuevo.amigos = [a for a in nuevo.amigos if not (
        a.contraparte == contraparte and (propuesta_origen is None or a.propuesta_origen == propuesta_origen))]
    if len(nuevo.amigos) == antes:
        raise NoExiste("No hay ningún amigo pendiente con ese nombre.")
    return nuevo


# --- Lo aprendido de amigos y sitios (curva de amigos, A5) ----------------------------------------------------
# Lo puro vive en `aprende_amigos`; aquí se resuelve la persona (por clave o por nombre visible), se comprueba que
# existe y se limpian también sus hechos. Nunca hay juicios: las frases son de `aprende_amigos.frases_amigos`.

def frases_aprendido_amigos(modelo: ModeloUsuario) -> list[dict]:
    """Las frases de amigos y sitios, listas para la API: `FrasePerfil` más su `clave` (persona o ámbito) para editar o
    borrar. Solo sirven para los recordatorios del propio usuario."""
    salida = []
    for f in aprende_amigos.frases_amigos(modelo.aprendizaje, modelo.contactos):
        tipo, _, clave = f.campo.partition(":")
        salida.append({**f.model_dump(mode="json"), "tipo": "persona" if tipo == "amigos" else "sitio",
                       "clave": clave})
    return salida


def _clave_persona(modelo: ModeloUsuario, texto: str) -> str:
    apr = modelo.aprendizaje
    if texto in apr.personas or texto in modelo.contactos:
        return texto
    return buscar_contacto(modelo, texto) or clave_contraparte(texto) or texto


def _persona_conocida(modelo: ModeloUsuario, clave: str) -> bool:
    apr = modelo.aprendizaje
    return (clave in apr.personas or clave in modelo.contactos
            or any(clave in g.miembros for a in (*apr.por_comercio.values(), *apr.por_tipo_franja.values())
                   for g in a.grupos)
            or any(h.contraparte == clave for h in modelo.hechos_aprendidos))


def olvidar_persona(modelo: ModeloUsuario, contraparte: str) -> ModeloUsuario:
    """Quita lo aprendido de una persona (su hábito, su sitio en los grupos y los hechos que se refieren a ella). El
    contacto y los casos no se tocan. `NoExiste` si no se sabe nada de ella."""
    clave = _clave_persona(modelo, contraparte)
    if not _persona_conocida(modelo, clave):
        raise NoExiste("No he aprendido nada de esa persona.")
    nuevo = modelo.model_copy(deep=True)
    nuevo.aprendizaje = aprende_amigos.borrar_persona(nuevo.aprendizaje, clave)
    for h in [h for h in nuevo.hechos_aprendidos if h.contraparte == clave and h.activo]:
        _deshacer_efecto(nuevo, h)
    nuevo.hechos_aprendidos = [h for h in nuevo.hechos_aprendidos if h.contraparte != clave]
    return nuevo


def olvidar_sitio(modelo: ModeloUsuario, clave: str) -> ModeloUsuario:
    """Quita lo aprendido de un sitio (`comercio:<X>` o `tipo:<tipo>|<franja>`). `NoExiste` si no hay nada."""
    try:
        aprendizaje = aprende_amigos.borrar_sitio(modelo.aprendizaje, clave)
    except KeyError as error:
        raise NoExiste("No he aprendido nada de ese sitio.") from error
    return modelo.model_copy(update={"aprendizaje": aprendizaje})


def corregir_persona(modelo: ModeloUsuario, contraparte: str, campo: str, valor: Any) -> ModeloUsuario:
    """Corrige a mano `retraso_dias` o `canal` de una persona; el código ya no lo pisa. `NoExiste` si no la conoce;
    `ValueError` (en español) si el campo o el valor no valen."""
    clave = _clave_persona(modelo, contraparte)
    if not _persona_conocida(modelo, clave):
        raise NoExiste("No conozco a esa persona.")
    return modelo.model_copy(update={"aprendizaje": aprende_amigos.editar_persona(modelo.aprendizaje, clave, campo, valor)})


def olvidar_todo(modelo: ModeloUsuario) -> ModeloUsuario:
    """Deja solo `consentimientos` y `modulos_activos` (y la decisión de no usar perfil, si la tomó)."""
    preferencias = Preferencias(usar_perfil=modelo.preferencias.usar_perfil)
    return ModeloUsuario(usuario_id=modelo.usuario_id, politica=modelo.politica,
                         modulos_activos=list(modelo.modulos_activos), consentimientos=dict(modelo.consentimientos),
                         preferencias=preferencias, actualizado=modelo.actualizado)
