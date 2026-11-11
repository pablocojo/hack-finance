"""
Crear casos desde el chat (docs/diseno/curva-amigos.md §4.2; CONTRATO.md, «Curva de amigos»): herramienta `apuntar_gasto`.

El usuario dice «las pizzas de ayer, con Marcos y Rodrigo» y el SERVIDOR hace el trabajo: busca el cargo en la cuenta
(`casos/apuntar.py`, puro), resuelve a las personas en la agenda, calcula las cuotas con `Decimal` y crea (o convierte, si
ya había un `pago_individual`) el caso con `orquestador.crear_caso_usuario`. Reglas:

- Solo pagos que están en la cuenta. Una deuda sin cargo («le pagué en efectivo») es `no_soportado` (hoja de ruta).
- Si hay varios cargos que encajan, o la persona no está en la agenda, o el importe no vale, NO se crea nada y se dice por qué.
- Nunca mueve dinero ni pide ningún Bizum: solo abre el caso (el Bizum sale del aviso, con botón y token).
- Todo con el candado del usuario; rastro `caso_chat` en la auditoría y origen `chat` en el caso. «Deshacer» como en
  `actualizar_caso` (`apuntar_gasto_con_rastro` devuelve el caso antes y después para que la sesión lo guarde).
- Todo texto libre que vuelve al modelo va entre `<datos>`: la pista, los comercios y los nombres son DATOS.

`recordar_sobre_mi_usuario` (herramienta `recordar_sobre_mi`) es lo mismo para las frases que enseñan sin crear un caso:
con el candado, auditoría `hecho_chat` y «Deshacer» (`recordar_con_rastro` / `deshacer_hecho`). La lógica pura vive en
`personalizacion/hechos_chat.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .. import casos
from ..casos import apuntar as _apuntar
from ..modulos.plantillas import sanear_dato
from ..personalizacion import amigos as _contactos
from ..personalizacion import edicion, hechos_chat
from ..personalizacion.perfil import es_sensible
from . import almacenamiento as alm
from . import orquestador
from .privacidad import enmascarar_texto
from .reloj import ahora_por_defecto
from .tipos import (
    ApuntarGastoEntrada,
    ApuntarGastoSalida,
    AprendizajeAmigos,
    Caso,
    CargoCandidato,
    Contacto,
    CuotaPersona,
    HechoChatEntrada,
    Movimiento,
    ResultadoApuntar,
)

MSG_EFECTIVO = ("Todavía no puedo apuntar una deuda que no sale de un pago de tu cuenta (como lo pagado en efectivo): "
                "está en la hoja de ruta. No he creado nada. Si el pago fue con tarjeta, dime cuál era y lo apunto.")


def _dato(texto: object, maximo: int = 60) -> str:
    return f"<datos>{sanear_dato(enmascarar_texto(str(texto or '')), maximo)}</datos>"


def _eur(valor: Decimal) -> str:
    return casos.ciclo.eur_texto(valor).replace(".", ",") + " €"


def _fecha(d: date) -> str:
    return f"{d.day}/{d.month}"


def _salida(resultado: ResultadoApuntar, mensaje: str, *, ok: bool = False, **campos) -> ApuntarGastoSalida:
    return ApuntarGastoSalida(ok=ok, resultado=resultado, mensaje=mensaje, **campos)


def _lista(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _resolver(modelo, lista: list[Caso], texto: str) -> tuple[str, str | None]:
    """`("ok", clave)`, `("desconocida", clave|None)` (no está en la agenda: clave nueva si el nombre vale) o
    `("ambigua", None)` (encaja con varios contactos). Un nombre de pila solo encaja con quien lo tenga como primer nombre."""
    clave = casos.clave_persona(texto)
    if clave is None:
        return "desconocida", None
    conocidas = set(modelo.contactos if modelo is not None else ()) | {d.contraparte for c in lista for d in c.deudores}
    if clave in conocidas:
        return "ok", clave
    por_nombre = _contactos.buscar_contacto(modelo, texto) if modelo is not None else None
    if por_nombre:
        return "ok", por_nombre
    if " " not in clave:
        coinciden = sorted(k for k in conocidas if k.split()[0] == clave)
        if len(coinciden) == 1:
            return "ok", coinciden[0]
        if len(coinciden) > 1:
            return "ambigua", None
    return "desconocida", clave   # (la misma regla que `hechos_chat.resolver_persona`, que usa `recordar_sobre_mi`)


def _movimiento_elegido(historial: list[Movimiento], movimiento_id: str, hoy: date) -> Movimiento | None:
    m = next((x for x in historial if x.id == movimiento_id), None)
    if m is None or m.fecha > hoy or m.importe >= 0 or m.canal in ("bizum", "transferencia", "cajero"):
        return None
    return None if es_sensible(m.categoria, m.comercio, m.concepto) else m


def _lineas_candidatos(candidatos: list[CargoCandidato]) -> str:
    return "; ".join(f"{i}) {_dato(c.comercio, 40)} del {_fecha(c.fecha)}, {_eur(c.importe)}" for i, c in enumerate(candidatos, 1))


RASTRO_APUNTADO = "rastro_apuntado"      # {caso_id: {aprendizaje y contactos antes/después}} de los casos creados por el chat


def _huella_modelo(modelo) -> dict:
    """Lo que aprende crear un caso desde el chat: el aprendizaje de amigos y la agenda de contactos, en JSON."""
    return {"aprendizaje": modelo.aprendizaje.model_dump(mode="json"),
            "contactos": {k: c.model_dump(mode="json") for k, c in modelo.contactos.items()}}


def _guardar_rastro_aprendizaje(usuario_id: str, caso_id: str, antes, despues) -> None:
    """Guarda (con el candado ya tomado) el aprendizaje y los contactos de antes y de después de crear el caso, para que
    «Deshacer» los devuelva a como estaban. Si no cambiaron (o no hay modelo) no guarda nada."""
    if antes is None or despues is None:
        return
    a, d = _huella_modelo(antes), _huella_modelo(despues)
    if a == d:
        return
    rastros = alm.cargar(usuario_id, RASTRO_APUNTADO, defecto={}) or {}
    rastros[caso_id] = {"antes": a, "despues": d}
    alm.guardar(usuario_id, RASTRO_APUNTADO, rastros)


def apuntar_gasto_con_rastro(usuario_id: str, entrada: ApuntarGastoEntrada) -> tuple[ApuntarGastoSalida, Caso | None, Caso | None]:
    """Como `apuntar_gasto_usuario`, pero devuelve también `(antes, despues)`: el caso previo (None si es nuevo) y el caso
    resultante (None si no se creó nada). La sesión de la llamada los guarda para «Deshacer». Con el candado del usuario.
    Si crea un caso nuevo, guarda también el aprendizaje y los contactos de antes y de después (`RASTRO_APUNTADO`)."""
    with alm.candado(usuario_id):
        estado = orquestador._estado(usuario_id)
        hoy = orquestador._hoy(estado)
        pista = _dato(entrada.pista)

        if entrada.efectivo:
            return _salida("no_soportado", MSG_EFECTIVO), None, None
        if not entrada.personas:
            return _salida("sin_personas", "Dime con quién fue (por su nombre) para apuntar quién te debe parte de ese pago."), None, None

        historial = orquestador._leer(usuario_id, "movimientos", [])
        modelo = orquestador._leer(usuario_id, "modelo")
        lista = casos.cargar(usuario_id)

        # 1. El cargo, por código.
        if entrada.movimiento_id:
            elegido = _movimiento_elegido(historial, entrada.movimiento_id, hoy)
            if elegido is None:
                return _salida("sin_cargo", "Ese cargo no está entre tus movimientos (o no se puede repartir). No he creado nada."), None, None
        else:
            candidatos = _apuntar.buscar_cargos(historial, entrada, hoy)
            if not candidatos:
                return _salida("sin_cargo", f"No encuentro en tu cuenta ningún pago que encaje con {pista}. No he creado nada: "
                                            "dime el comercio o la fecha, o el importe, y lo busco de nuevo."), None, None
            if len(candidatos) > 1:
                return _salida("varios_candidatos", "Hay varios pagos que podrían ser: " + _lineas_candidatos(candidatos) +
                               ". Pregunta cuál es y repite con su movimiento_id. No he creado nada.",
                               candidatos=candidatos), None, None
            elegido = next(m for m in historial if m.id == candidatos[0].movimiento_id)

        # 2. Las personas, en la agenda.
        claves: list[str] = []
        ambiguas: list[str] = []
        nuevas: list[str] = []
        for p in entrada.personas:
            tipo, clave = _resolver(modelo, lista, p.nombre)
            if tipo == "ambigua":
                ambiguas.append(p.nombre)
            elif tipo == "desconocida":
                nuevas.append(p.nombre)
                if clave is not None:
                    claves.append(clave)
            else:
                claves.append(clave)  # type: ignore[arg-type]
        if ambiguas:
            return _salida("persona_ambigua", f"{_lista([_dato(n, 40) for n in ambiguas])} encaja con varios contactos de tu "
                           "agenda: pregunta cuál es (con su apellido o inicial). No he creado nada.",
                           personas_sin_resolver=ambiguas), None, None
        if nuevas and not entrada.confirmar_personas_nuevas:
            return _salida("persona_desconocida", f"No tengo a {_lista([_dato(n, 40) for n in nuevas])} en tu agenda. "
                           "Pregunta al usuario si quiere añadirla y, si lo confirma, repite con confirmar_personas_nuevas. "
                           "No he creado nada.", personas_sin_resolver=nuevas), None, None
        if len(claves) != len(entrada.personas):   # un nombre que no se puede convertir en persona ni confirmándolo
            return _salida("persona_desconocida", "No puedo usar ese nombre como persona: dime cómo se llama (solo letras). "
                           "No he creado nada.", personas_sin_resolver=nuevas), None, None

        # 3. Las cuotas, del código.
        try:
            cuotas = _apuntar.cuotas_de(elegido, entrada, claves)
        except ValueError as error:
            return _salida("importe_invalido", f"{error} No he creado nada."), None, None

        # 4. Crear o convertir con las reglas de siempre.
        previo = casos.buscar_de_movimiento(lista, elegido.id)
        try:
            resumen = orquestador.crear_caso_usuario(
                usuario_id, elegido.id, [{"contraparte": c, "importe": format(q, "f")} for c, q in cuotas.items()],
                origen="chat")
        except ValueError as error:   # p. ej. ya hay un caso abierto del mismo tipo o la transición no existe
            return _salida("no_soportado", f"No puedo apuntarlo así: {error} No he cambiado nada."), None, None
        despues = next(c for c in casos.cargar(usuario_id) if c.id == resumen["id"])
        convertido = previo is not None
        if not convertido:
            _guardar_rastro_aprendizaje(usuario_id, despues.id, modelo, orquestador._leer(usuario_id, "modelo"))
        orquestador._auditar(usuario_id, "caso_chat", caso_id=despues.id, resultado="convertido" if convertido else "creado",
                             escenario=despues.escenario, personas=len(cuotas), movimiento=elegido.id)
        deudores = [CuotaPersona(contraparte=c, nombre=casos.ciclo.nombre_visible(c), cuota=q) for c, q in cuotas.items()]
        quienes = _lista([f"{_dato(d.nombre, 30)} ({_eur(d.cuota)})" for d in deudores])
        aviso = (f"te avisaré en {(despues.avisar_desde - hoy).days} días si aún no te han hecho el Bizum"
                 if despues.avisar_desde and despues.avisar_desde > hoy else "te avisaré si no te hacen el Bizum")
        mensaje = (f"{'Caso actualizado' if convertido else 'Apuntado'}: {_dato(_apuntar._visible(elegido), 40)} del "
                   f"{_fecha(elegido.fecha)}, {_eur(abs(elegido.importe))}. Te deben: {quienes}. "
                   f"No he movido dinero ni pedido ningún Bizum; {aviso} y lo pedirás con un botón.")
        return (_salida("convertido" if convertido else "creado", mensaje, ok=True, caso_id=despues.id, deudores=deudores),
                previo, despues)


def apuntar_gasto_usuario(usuario_id: str, entrada: ApuntarGastoEntrada) -> ApuntarGastoSalida:
    """Herramienta `apuntar_gasto` (y simulador de amigos): `ApuntarGastoSalida` y nunca lanza por datos del usuario.
    Lanza `orquestador.NoEncontrado` solo si el usuario no existe."""
    return apuntar_gasto_con_rastro(usuario_id, entrada)[0]


MSG_APRENDIZAJE_CAMBIADO = ("He descartado el caso, pero no he quitado lo que Meisam aprendió al apuntarlo porque ha cambiado "
                            "desde entonces; puedes revisarlo en «Lo que Meisam sabe de ti».")


def deshacer_apuntado_con_aviso(usuario_id: str, despues: Caso) -> tuple[Caso, str | None]:
    """«Deshacer» un caso que acaba de crear el chat: se descarta (queda en el historial, nada se borra), solo si no ha
    cambiado desde entonces. Además, el aprendizaje y los contactos vuelven a como estaban antes de apuntarlo, solo si no
    han cambiado desde entonces (misma regla que el caso); si han cambiado se deja lo que hay y el segundo valor es el
    aviso para el usuario (`None` si todo volvió a su sitio o no se había aprendido nada).
    Para uno convertido se usa `orquestador.restaurar_caso_llamada`. `ValueError` si no se puede."""
    with alm.candado(usuario_id):
        hoy = orquestador._hoy(orquestador._estado(usuario_id))
        lista = casos.cargar(usuario_id)
        actual = orquestador._caso_de(lista, despues.id)
        if actual.model_dump(mode="json") != despues.model_dump(mode="json"):
            raise ValueError("El caso ha cambiado después de apuntarlo: ya no se puede deshacer.")
        nuevo = casos.descartar(actual, hoy, "lo deshiciste justo después de apuntarlo.", "usuario", ahora_por_defecto(hoy))
        orquestador._guardar_caso(usuario_id, hoy, lista, nuevo, actual)
        restaurado, aviso = False, None
        rastros = alm.cargar(usuario_id, RASTRO_APUNTADO, defecto={}) or {}
        rastro = rastros.pop(despues.id, None)
        if rastro is not None:
            modelo = orquestador._leer(usuario_id, "modelo")
            if modelo is not None and _huella_modelo(modelo) == rastro["despues"]:
                antes = rastro["antes"]
                alm.guardar(usuario_id, "modelo", modelo.model_copy(update={
                    "aprendizaje": AprendizajeAmigos.model_validate(antes["aprendizaje"]),
                    "contactos": {k: Contacto.model_validate(c) for k, c in antes["contactos"].items()},
                    "actualizado": ahora_por_defecto(hoy)}))
                restaurado = True
            else:
                aviso = MSG_APRENDIZAJE_CAMBIADO
            alm.guardar(usuario_id, RASTRO_APUNTADO, rastros)
        orquestador._auditar(usuario_id, "caso_chat_deshecho", caso_id=despues.id, aprendizaje_restaurado=restaurado)
        return nuevo, aviso


def deshacer_apuntado(usuario_id: str, despues: Caso) -> Caso:
    """Como `deshacer_apuntado_con_aviso`, devolviendo solo el caso descartado."""
    return deshacer_apuntado_con_aviso(usuario_id, despues)[0]


# --- `recordar_sobre_mi`: frases que enseñan sin crear un caso (personalizacion/hechos_chat.py) -------------------------

def recordar_con_rastro(usuario_id: str, entrada: HechoChatEntrada,
                        confirmar_personas_nuevas: bool = False) -> tuple[dict, dict | None]:
    """Como `recordar_sobre_mi_usuario`, pero devuelve también el rastro para «Deshacer» (`None` si no cambió nada): el
    hecho y el aprendizaje antes y después. Con el candado del usuario y rastro `hecho_chat` en la auditoría."""
    with alm.candado(usuario_id):
        estado = orquestador._estado(usuario_id)
        hoy = orquestador._hoy(estado)
        modelo = orquestador._leer(usuario_id, "modelo")
        if modelo is None:
            raise orquestador.NoEncontrado(f"El usuario {usuario_id!r} aún no tiene modelo.")
        historial = [m for m in orquestador._leer(usuario_id, "movimientos", [])
                     if m.fecha <= hoy and m.importe < 0 and m.canal not in ("bizum", "transferencia", "cajero") and m.comercio
                     and not es_sensible(m.categoria, m.comercio, m.concepto)]
        por_comercio: dict[str, Movimiento] = {}
        for m in historial:
            por_comercio.setdefault(m.comercio, m)
        r = hechos_chat.aplicar_hecho(
            modelo, entrada, hoy, conocidas={d.contraparte for c in casos.cargar(usuario_id) for d in c.deudores},
            comercios=list(por_comercio), tipo_de=lambda c: orquestador._tipo_comercio(por_comercio[c]),
            confirmar_personas_nuevas=confirmar_personas_nuevas)
        if not r.ok:
            salida = {"ok": False, "resultado": r.resultado, "error": r.mensaje}
            if r.personas_sin_resolver:
                salida["personas_sin_resolver"] = r.personas_sin_resolver
            return salida, None
        salida = {"ok": True, "resultado": r.resultado, "mensaje": r.mensaje}
        if r.hecho is None or r.modelo is modelo:      # ya lo sabía: nada que guardar ni deshacer
            return salida, None
        alm.guardar(usuario_id, "modelo", r.modelo.model_copy(update={"actualizado": ahora_por_defecto(hoy)}))
        orquestador._auditar(usuario_id, "hecho_chat", hecho_id=r.hecho.id, tipo=r.hecho.tipo, eventos=len(r.eventos),
                             personas=len(r.hecho.datos.get("personas") or []))
        salida.update({"hecho": r.hecho.texto, "hecho_id": r.hecho.id})
        rastro = {"hecho_id": r.hecho.id, "antes": modelo.aprendizaje.model_dump(mode="json"),
                  "despues": r.modelo.aprendizaje.model_dump(mode="json")}
        return salida, rastro


def recordar_sobre_mi_usuario(usuario_id: str, entrada: HechoChatEntrada, confirmar_personas_nuevas: bool = False) -> dict:
    """Herramienta `recordar_sobre_mi` (y simulador de amigos): `{ok, resultado, mensaje, hecho, hecho_id}` o
    `{ok: False, resultado, error}` (`persona_desconocida`, `persona_ambigua`, `falta_persona`, `falta_sitio`,
    `texto_no_valido`, `aprendizaje_apagado`, `tipo_no_valido`). Nunca lanza por lo que dice el usuario; lanza
    `orquestador.NoEncontrado` solo si el usuario no existe. Una persona desconocida se confirma repitiendo con
    `confirmar_personas_nuevas=True`."""
    return recordar_con_rastro(usuario_id, entrada, confirmar_personas_nuevas)[0]


def deshacer_hecho(usuario_id: str, rastro: dict) -> None:
    """«Deshacer» un hecho que acaba de guardar el chat: se borra con su efecto (silencio, canal, sitios). Si el aprendizaje
    no ha cambiado desde entonces, vuelve exactamente a como estaba. `ValueError` si el hecho ya no está."""
    with alm.candado(usuario_id):
        hoy = orquestador._hoy(orquestador._estado(usuario_id))
        modelo = orquestador._leer(usuario_id, "modelo")
        hecho = next((h for h in modelo.hechos_aprendidos if h.id == rastro["hecho_id"]), None) if modelo else None
        if hecho is None:
            raise ValueError("Ese dato ya no está guardado: no hay nada que deshacer.")
        nuevo = edicion.borrar_hecho(modelo, hecho.id)
        if modelo.aprendizaje.model_dump(mode="json") == rastro["despues"]:
            nuevo = nuevo.model_copy(update={"aprendizaje": AprendizajeAmigos.model_validate(rastro["antes"])})
        for clave in hecho.datos.get("contactos_nuevos") or []:      # la agenda vuelve a como estaba si nadie más la usó
            c = nuevo.contactos.get(clave)
            if c is not None and c.veces == 0 and not any(clave in (h.datos.get("personas") or []) for h in nuevo.hechos_aprendidos):
                del nuevo.contactos[clave]
        alm.guardar(usuario_id, "modelo", nuevo.model_copy(update={"actualizado": ahora_por_defecto(hoy)}))
        orquestador._auditar(usuario_id, "hecho_chat_deshecho", hecho_id=hecho.id)
