"""
Frases del chat que enseñan sin crear un caso (docs/diseno/curva-amigos.md §4.2; CONTRATO.md, «Curva de amigos»):
herramienta `recordar_sobre_mi`. Todo PURO: no lee ni guarda nada (el candado, el disco y la auditoría son de
`plataforma/chat_casos.py`).

    aplicar_hecho(modelo, entrada, hoy, ...) -> ResultadoHecho      lista cerrada -> `HechoAprendido` (origen `chat`) + eventos
    deshacer_efecto(modelo, hecho, sitios)                          lo contrario, para apagar o borrar un hecho

Lista cerrada de tipos (`TipoHechoChat`) y qué hace cada uno:

| tipo              | qué dice el usuario                          | efecto                                                         |
|-------------------|----------------------------------------------|----------------------------------------------------------------|
| `va_solo`         | «en la cafetería siempre voy solo»           | eventos «fue solo» en el sitio (y tipo de sitio y franja)      |
| `nadie_debe_aqui` | «las comidas con clientes las paga la empresa»| eventos «acompañado, nadie me debe» en el sitio                |
| `grupo_habitual`  | «los sábados ceno con Laura y Marcos»        | eventos «acompañado, con esas personas» en el sitio            |
| `plan_recurrente` | «los jueves ceno con los del piso»           | igual que el anterior (suele llevar día de la semana)          |
| `paga_en_efectivo`| «Rodrigo me lo paga en efectivo»             | canal «efectivo» de esa persona, fijado por el usuario         |
| `no_recordar`     | «a Andrea no le recuerdes nada»              | silencio de ese contacto (como «no me avises de esta persona») |
| `paga_por_otro`   | «Rodrigo suele pagarme también lo de Marcos» | solo se guarda (visible y borrable); aún no cambia ningún aviso|
| `no_es_devolucion`| «los Bizums de Laura no son de las cenas»    | solo se guarda (visible y borrable); aún no cambia ningún aviso|

Reglas:
- Una declaración vale varias observaciones. Sobre un comercio de SUS cargos (`VECES`), ir solo y «nadie me debe» valen ~3
  (lo bastante para callar ese sitio) y un grupo ~2 (para sugerirlo). Sobre un tipo de sitio y franja («las cenas de los
  jueves»), que mezcla planes distintos, valen solo `VECES_TIPO` = 2: nunca callan por sí solas y la siguiente respuesta
  real manda. Todo se puede apagar, borrar o deshacer.
- Las personas se resuelven en la agenda; una desconocida se rechaza con `persona_desconocida` hasta que el usuario la
  confirme (`confirmar_personas_nuevas`), y entonces se añade a la agenda. Un nombre ambiguo se rechaza.
- La frase del usuario (`texto`, `pista`) es DATO: se filtra (sensibles, órdenes) y NUNCA se guarda tal cual; lo que se
  ve en «Lo que he aprendido» es una frase neutra y de hechos que escribe el código.
- `modo != "aprende"` (reglas o fijo): lo que enseña no se guarda («aprendizaje_apagado»); lo demás sí.
- Los hechos se refieren a una persona (`HechoAprendido.contraparte`) o a varias (`datos["personas"]`): al borrar el
  contacto, se borran con él (`amigos.borrar_contacto`, `edicion.olvidar_persona`).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable, get_args

from ..motor.normalizar import clave_contraparte
from ..plataforma.privacidad import enmascarar_nombre, enmascarar_texto
from ..plataforma.tipos import (
    Contacto,
    EventoAmigos,
    Franja,
    FormaReparto,
    HechoAprendido,
    HechoChatEntrada,
    ModeloUsuario,
    Silencio,
    TipoHechoChat,
)
from . import aprende_amigos as _ap
from .amigos import buscar_contacto
from .memoria import texto_permitido
from .politica import normalizar

TIPOS = get_args(TipoHechoChat)
VECES: dict[str, int] = {"va_solo": 3, "nadie_debe_aqui": 3, "grupo_habitual": 2, "plan_recurrente": 2}   # sobre un comercio
VECES_TIPO = 2                                           # sobre un tipo de sitio y franja (más amplio: pesa menos)
CON_SITIO = ("va_solo", "nadie_debe_aqui", "grupo_habitual", "plan_recurrente")
CON_PERSONAS = ("grupo_habitual",)                       # necesitan al menos una persona
CON_PERSONA = ("paga_en_efectivo", "no_recordar", "paga_por_otro", "no_es_devolucion")   # necesitan `persona`
APRENDEN = ("va_solo", "nadie_debe_aqui", "grupo_habitual", "plan_recurrente", "paga_en_efectivo")   # necesitan modo `aprende`
SOLO_GUARDAN = ("paga_por_otro", "no_es_devolucion")     # aún nadie los lee: se dice con claridad
DIAS = ("los lunes", "los martes", "los miércoles", "los jueves", "los viernes", "los sábados", "los domingos")
MAX_PISTA = 40

# Palabras que no distinguen un sitio de otro. Los días y «siempre/solo» tampoco.
_VACIAS = frozenset("""el la los las un una unos unas de del al en con y e o a por para que lo le mi mis siempre solo sola
solos lunes martes miercoles jueves viernes sabado sabados domingo domingos fin finde semana nunca cada uno""".split())
# Lo que se suele decir -> tipo de sitio del motor (`PagoIndividual.TIPOS_ELEGIBLES`), por las 4 primeras letras.
_TIPO_POR_RAIZ = {
    "pizz": "restaurante", "cena": "restaurante", "comi": "restaurante", "rest": "restaurante", "tapa": "restaurante",
    "sush": "restaurante", "rame": "restaurante", "hamb": "restaurante", "burg": "restaurante", "bruc": "restaurante",
    "menu": "restaurante", "bar": "bar", "bare": "bar", "tabe": "bar", "copa": "bar", "cana": "bar", "cerv": "bar", "birr": "bar", "pub": "bar",
    "verm": "bar", "coct": "bar", "cafe": "bar", "desa": "bar", "cine": "cine", "teat": "teatro", "conc": "concierto",
    "bole": "actividad", "esca": "actividad", "kart": "actividad", "kara": "actividad",
}


@dataclass(frozen=True)
class Sitio:
    visible: str                    # lo que dijo el usuario, saneado («la cafetería de la escuela»)
    comercio: str | None            # clave normalizada del comercio (como la del motor); None si el sitio es un tipo
    tipo: str | None                # tipo de sitio del motor
    ambito: str = "comercio"        # `comercio`: se aprende ese comercio · `tipo`: el tipo de sitio y la franja


@dataclass
class ResultadoHecho:
    ok: bool
    resultado: str                  # guardado | repetido | <código de rechazo>
    mensaje: str                    # español, para el agente (lo libre, entre <datos>)
    modelo: ModeloUsuario           # el nuevo (el mismo objeto si no cambia nada)
    hecho: HechoAprendido | None = None
    eventos: list[EventoAmigos] = field(default_factory=list)
    personas_sin_resolver: list[str] = field(default_factory=list)


# --- Texto y personas --------------------------------------------------------------------------------------------

def _limpio(texto: Any, maximo: int = MAX_PISTA) -> str:
    t = unicodedata.normalize("NFKC", str(texto or ""))
    t = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in t)
    t = re.sub(r"[{}<>\"`]", "", enmascarar_texto(t))
    return " ".join(t.split())[:maximo].strip()


def _dato(texto: Any, maximo: int = 160) -> str:
    return f"<datos>{_limpio(texto, maximo)}</datos>"


def _lista(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def resolver_persona(modelo: ModeloUsuario, texto: str, conocidas: Iterable[str] = ()) -> tuple[str, str | None]:
    """`("ok", clave)`, `("desconocida", clave|None)` (no está en la agenda: clave nueva si el nombre vale) o
    `("ambigua", None)` (encaja con varios contactos). Un nombre de pila solo encaja con quien lo tenga como primer
    nombre. `conocidas`: claves que no están en la agenda pero se conocen (p. ej. deudores de casos)."""
    clave = clave_contraparte(texto) if isinstance(texto, str) else None
    if clave is None:
        return "desconocida", None
    sabidas = set(modelo.contactos) | set(conocidas)
    if clave in sabidas:
        return "ok", clave
    por_nombre = buscar_contacto(modelo, texto)
    if por_nombre:
        return "ok", por_nombre
    if " " not in clave:
        coinciden = sorted(k for k in sabidas if k.split()[0] == clave)
        if len(coinciden) == 1:
            return "ok", coinciden[0]
        if len(coinciden) > 1:
            return "ambigua", None
    return "desconocida", clave


def _nombre(clave: str, contactos: dict[str, Contacto]) -> str:
    return _ap.nombre_persona(clave, contactos)


# --- Sitios --------------------------------------------------------------------------------------------------------

def _normal(texto: str) -> str:
    base = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", base.lower())


def _tokens(texto: str) -> list[str]:
    return [t for t in _normal(texto).split() if t not in _VACIAS and len(t) > 2]


def _raiz_igual(a: str, b: str) -> bool:
    return a == b or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4])


def _tipo_de_palabra(token: str) -> str | None:
    return _TIPO_POR_RAIZ.get(token[:4]) or _TIPO_POR_RAIZ.get(token)


def tipo_por_palabras(texto: str) -> str | None:
    for t in _tokens(texto):
        tipo = _tipo_de_palabra(t)
        if tipo:
            return tipo
    return None


def resolver_sitio(pista: str, comercios: Iterable[str] = (), tipo_de: Callable[[str], str | None] | None = None,
                   con_dia: bool = False) -> Sitio:
    """El sitio que dice el usuario, con lo que se sabe de su cuenta:
    - UN solo comercio de sus cargos encaja con todas las palabras de la pista -> ese comercio (`ambito = "comercio"`);
    - encajan varios («las pizzas»), o ninguno y la pista habla de un tipo de sitio («los bares», «las cenas del piso» si
      además dice un día) -> el tipo de sitio y la franja (`ambito = "tipo"`);
    - si no, la propia pista como nombre de comercio (un sitio con nombre que aún no está en sus cargos).
    `tipo_de(comercio)` se llama solo para los que encajan."""
    visible = _limpio(pista)
    palabras = _tokens(visible)
    encajan: dict[str, str] = {}
    if palabras:
        for crudo in comercios:
            clave = _ap.clave_comercio(crudo)
            if not clave or clave in encajan:
                continue
            toks = _tokens(crudo)
            if all(any(_raiz_igual(p, c) for c in toks) for p in palabras):
                encajan[clave] = crudo
    tipo = tipo_por_palabras(visible)
    if len(encajan) == 1:
        (clave, crudo), = encajan.items()
        return Sitio(visible, clave, (tipo_de(crudo) if tipo_de else None) or tipo)
    if encajan:
        tipos = {(tipo_de(c) if tipo_de else None) for c in encajan.values()} - {None}
        tipo = tipo or (tipos.pop() if len(tipos) == 1 else None)
        if tipo:
            return Sitio(visible, None, tipo, "tipo")
    elif tipo and (con_dia or (palabras and all(_tipo_de_palabra(t) for t in palabras))):
        return Sitio(visible, None, tipo, "tipo")
    return Sitio(visible, _ap.clave_comercio(visible), None)


def franja_de_dia(dia: int) -> Franja:
    return "finde" if dia >= 5 else "viernes" if dia == 4 else "laborable"


# --- Frases neutras --------------------------------------------------------------------------------------------------

def _donde(sitio: Sitio, dia: int | None) -> str:
    texto = sitio.visible[:1].upper() + sitio.visible[1:]
    return f"{texto}, {DIAS[dia]}" if dia is not None else texto


def _frase(tipo: str, persona: str | None, personas: list[str], sitio: Sitio | None, dia: int | None,
           contactos: dict[str, Contacto]) -> str:
    nombres = [_nombre(c, contactos) for c in personas]
    yo = _nombre(persona, contactos) if persona else ""
    donde = _donde(sitio, dia) if sitio else ""
    if tipo == "va_solo":
        return f"{donde}: sueles ir solo. No te pregunto."
    if tipo == "nadie_debe_aqui":
        return f"{donde}: nadie te debe nada. No te pregunto."
    if tipo == "grupo_habitual":
        return f"{donde}: sueles ir con {_lista(nombres)}."
    if tipo == "plan_recurrente":
        con = f", con {_lista(nombres)}" if nombres else ""
        return f"Plan habitual: {donde[:1].lower() + donde[1:]}{con}."
    if tipo == "paga_en_efectivo":
        return f"{yo} suele pagarte en efectivo (me lo has dicho tú)."
    if tipo == "no_recordar":
        return f"No te aviso de lo que te deba {yo} (me lo has dicho tú)."
    if tipo == "paga_por_otro":
        return f"{yo} suele pagar también la parte de {_lista(nombres)} (me lo has dicho tú)."
    return f"Los Bizums de {yo} no son devoluciones de gastos compartidos (me lo has dicho tú)."


# --- Aplicar ---------------------------------------------------------------------------------------------------------

def _id_hecho(tipo: str, persona: str | None, personas: list[str], sitio: Sitio | None, dia: int | None) -> str:
    base = "|".join([tipo, persona or "", ",".join(sorted(personas)), (sitio.comercio or "") if sitio else "",
                     (sitio.tipo or "") if sitio else "", "" if dia is None else str(dia)])
    return f"h-chat-{tipo}-{hashlib.sha1(base.encode()).hexdigest()[:10]}"


def _eventos(hecho_id: str, tipo: str, hoy: date, sitio: Sitio, dia: int | None, personas: list[str]) -> list[EventoAmigos]:
    """Observaciones de un hecho de sitio: `VECES[tipo]` sobre el comercio, o `VECES_TIPO` sobre el tipo de sitio en la franja
    del día que dice (sin día, en las tres franjas)."""
    acompanado = tipo != "va_solo"
    forma: FormaReparto | None = _ap.SIN_DEUDA if tipo == "nadie_debe_aqui" else None
    comunes = {"fuente": "chat", "fecha": hoy, "acompanado": acompanado, "personas": list(personas) if acompanado else [],
               "forma": forma}
    if sitio.ambito == "comercio":
        return [EventoAmigos(id=f"chat:{hecho_id}:{i}", comercio=sitio.comercio, **comunes) for i in range(VECES[tipo])]
    franjas: list[Franja] = [franja_de_dia(dia)] if dia is not None else list(get_args(Franja))
    return [EventoAmigos(id=f"chat:{hecho_id}:{i}:{franja}", tipo_comercio=sitio.tipo, franja=franja, **comunes)
            for i in range(VECES_TIPO) for franja in franjas]


def _ambitos(eventos: list[EventoAmigos]) -> list[str]:
    salida: list[str] = []
    for ev in eventos:
        c = _ap.clave_comercio(ev.comercio)
        t = _ap.clave_tipo_franja(ev.tipo_comercio, ev.franja)
        for a in ([f"comercio:{c}"] if c else []) + ([f"tipo:{t}"] if t else []):
            if a not in salida:
                salida.append(a)
    return salida


def _rechazo(modelo: ModeloUsuario, resultado: str, mensaje: str, sin_resolver: list[str] | None = None) -> ResultadoHecho:
    return ResultadoHecho(False, resultado, mensaje + " No he guardado nada.", modelo, personas_sin_resolver=sin_resolver or [])


def aplicar_hecho(modelo: ModeloUsuario, entrada: HechoChatEntrada, hoy: date, *, conocidas: Iterable[str] = (),
                  comercios: Iterable[str] = (), tipo_de: Callable[[str], str | None] | None = None,
                  confirmar_personas_nuevas: bool = False) -> ResultadoHecho:
    """Una frase de la lista cerrada -> `HechoAprendido` con origen `chat` y, si enseña, los `EventoAmigos` aplicados con
    `aprende_amigos.aprender_eventos`. Nunca lanza por lo que dice el usuario: devuelve `ok=False` con el motivo.

    `conocidas`: claves de personas que no están en la agenda pero se conocen (deudores de casos). `comercios`: nombres de
    los comercios de sus cargos (para reconocer el sitio) y `tipo_de` su tipo. Una persona desconocida se rechaza con
    `persona_desconocida` salvo con `confirmar_personas_nuevas`, y entonces se añade a la agenda."""
    tipo = entrada.tipo
    if tipo not in TIPOS:
        return _rechazo(modelo, "tipo_no_valido", f"Solo puedo recordar: {', '.join(TIPOS)}.")
    apr = modelo.aprendizaje
    if tipo in APRENDEN and apr.modo != "aprende":
        return _rechazo(modelo, "aprendizaje_apagado", "El aprendizaje está desactivado en esta cuenta.")
    try:
        texto_permitido(entrada.texto, 160)
        if entrada.pista:
            texto_permitido(entrada.pista, 60)
    except ValueError as error:
        return _rechazo(modelo, "texto_no_valido", str(error))

    # 1. Personas, en la agenda.
    nombres_dichos = ([entrada.persona] if entrada.persona else []) + [p for p in entrada.personas if p]
    claves: dict[str, str] = {}
    ambiguas: list[str] = []
    nuevas: list[str] = []
    for nombre in dict.fromkeys(nombres_dichos):
        estado, clave = resolver_persona(modelo, nombre, conocidas)
        if estado == "ambigua":
            ambiguas.append(nombre)
        elif clave is None:
            return _rechazo(modelo, "persona_desconocida", "No puedo usar ese nombre como persona: dime cómo se llama "
                            "(solo letras).", [nombre])
        else:
            claves[nombre] = clave
            if estado == "desconocida":
                nuevas.append(nombre)
    if ambiguas:
        return _rechazo(modelo, "persona_ambigua", f"{_lista([_dato(n, 40) for n in ambiguas])} encaja con varios contactos "
                        "de la agenda: pregunta cuál es (con su apellido o inicial).", ambiguas)
    if nuevas and not confirmar_personas_nuevas:
        return _rechazo(modelo, "persona_desconocida", f"No tengo a {_lista([_dato(n, 40) for n in nuevas])} en la agenda. "
                        "Pregunta al usuario si quiere añadirla y, si lo confirma, repite con confirmar_personas_nuevas.", nuevas)
    persona = claves.get(entrada.persona) if entrada.persona else None
    personas = list(dict.fromkeys(claves[n] for n in entrada.personas if n in claves))
    if tipo in CON_PERSONA:          # `persona` es de quien se habla; `personas`, los demás (solo `paga_por_otro` los pide)
        if persona is None and len(personas) == 1:
            persona = personas[0]
        personas = [p for p in personas if p != persona]
        if persona is None:
            return _rechazo(modelo, "falta_persona", "Dime de qué persona hablas (por su nombre).")
        if tipo == "paga_por_otro" and not personas:
            return _rechazo(modelo, "falta_persona", "Dime también por quién paga (por su nombre).")
    else:                            # de sitio: una `persona` suelta es un miembro más
        if persona is not None and persona not in personas:
            personas.append(persona)
        persona = None
        if tipo in CON_PERSONAS and not personas:
            return _rechazo(modelo, "falta_persona", "Dime con quién vas (por su nombre).")

    # 2. El sitio.
    sitio = None
    if tipo in CON_SITIO:
        if not (entrada.pista or "").strip() or not _limpio(entrada.pista):
            return _rechazo(modelo, "falta_sitio", "Dime a qué sitio o plan te refieres (por ejemplo, «la cafetería» o «las "
                            "cenas de los jueves»).")
        sitio = resolver_sitio(entrada.pista, comercios, tipo_de, con_dia=entrada.dia_semana is not None)
    dia = entrada.dia_semana

    # 3. El hecho; si ya estaba, no se duplica.
    todas = [persona, *personas] if persona else list(personas)
    hecho_id = _id_hecho(tipo, persona, personas, sitio, dia)
    contactos = {**modelo.contactos, **{c: Contacto(contraparte=c, nombre=enmascarar_nombre(c)) for c in todas
                                        if c not in modelo.contactos}}
    frase = _frase(tipo, persona, personas, sitio, dia, contactos)
    previo = next((h for h in modelo.hechos_aprendidos if h.id == hecho_id), None)
    silencio_valor = normalizar(persona) if tipo == "no_recordar" else None
    silencio_previo = silencio_valor is not None and any(
        s.ambito == "contacto" and normalizar(s.valor) == silencio_valor for s in modelo.preferencias.silencios)
    if (previo is not None and previo.activo) or (silencio_previo and previo is None):
        return ResultadoHecho(True, "repetido", f"Ya lo tenía apuntado: {_dato(frase)}.", modelo, hecho=previo)

    nuevo = modelo.model_copy(deep=True)
    nuevo.hechos_aprendidos = [h for h in nuevo.hechos_aprendidos if h.id != hecho_id]   # uno apagado se rehace
    contactos_nuevos = [c for c in todas if c not in nuevo.contactos]
    for c in contactos_nuevos:
        nuevo.contactos[c] = Contacto(contraparte=c, nombre=enmascarar_nombre(c))

    datos: dict[str, Any] = {"personas": todas}
    if sitio is not None:
        datos.update({"pista": sitio.visible, "comercio": sitio.comercio, "tipo_comercio": sitio.tipo, "ambito": sitio.ambito})
    if dia is not None:
        datos["dia_semana"] = dia
    if contactos_nuevos:
        datos["contactos_nuevos"] = contactos_nuevos
    clave_hecho: str | None = None
    eventos: list[EventoAmigos] = []

    # 4. El efecto.
    if sitio is not None:
        eventos = _eventos(hecho_id, tipo, hoy, sitio, dia, personas)
        datos["ambitos"] = _ambitos(eventos)
        datos["veces"] = VECES[tipo] if sitio.ambito == "comercio" else VECES_TIPO
        apr0 = nuevo.aprendizaje
        stale = f"chat:{hecho_id}:"
        if any(i.startswith(stale) for i in apr0.eventos_vistos):      # lo borró y lo repite: observaciones nuevas
            nuevo.aprendizaje = apr0.model_copy(update={"eventos_vistos": [i for i in apr0.eventos_vistos
                                                                           if not i.startswith(stale)]})
        nuevo = _ap.aprender_eventos(nuevo, eventos)
    elif tipo == "paga_en_efectivo":
        assert persona is not None
        antes = nuevo.aprendizaje.personas.get(persona)
        datos.update({"canales_antes": dict(antes.canales) if antes else {}, "habito_nuevo": antes is None,
                      "canal_fijado_antes": bool(antes and "canales" in antes.fijado_por_usuario)})
        nuevo.aprendizaje = _ap.editar_persona(nuevo.aprendizaje, persona, "canal", "efectivo")
    elif tipo == "no_recordar":
        assert persona is not None and silencio_valor is not None
        nuevo.preferencias.silencios.append(Silencio(ambito="contacto", valor=silencio_valor, desde=hoy, origen=hecho_id))
        clave_hecho = f"silencio:contacto:{silencio_valor}"

    contraparte = persona if persona else (todas[0] if len(todas) == 1 else None)
    hecho = HechoAprendido(id=hecho_id, texto=frase, creado=hoy, origen="chat", clave=clave_hecho, tipo=tipo,
                           contraparte=contraparte, datos=datos)
    nuevo.hechos_aprendidos.append(hecho)
    mensaje = f"Apuntado: {_dato(frase)}. Lo puede ver, cambiar o borrar en «Lo que he aprendido»."
    if tipo in SOLO_GUARDAN:
        mensaje += " De momento solo lo guardo: no cambia ningún aviso."
    return ResultadoHecho(True, "guardado", mensaje, nuevo, hecho=hecho, eventos=eventos)


# --- Deshacer ---------------------------------------------------------------------------------------------------------

def menciona(hecho: HechoAprendido, clave: str) -> bool:
    """¿El hecho habla de esa persona? Al olvidarla o borrar su contacto, el hecho se va con ella."""
    return hecho.contraparte == clave or clave in (hecho.datos.get("personas") or [])


def deshacer_efecto(modelo: ModeloUsuario, hecho: HechoAprendido, sitios: bool = True) -> None:
    """Quita lo que enseñó un hecho de `chat` (en el modelo ya copiado; lo llaman `edicion.apagar_hecho` y `borrar_hecho`).
    El silencio de `no_recordar` lo quita `edicion` por su `clave`. Con `sitios`, olvida también los ámbitos (sitio, o tipo
    de sitio y franja) que enseñó: sus observaciones no se pueden separar de las demás, así que se olvida el ámbito entero.
    Con `sitios=False` (borrar un contacto) solo se quita lo de la persona."""
    apr = modelo.aprendizaje
    if sitios:
        for ambito in hecho.datos.get("ambitos") or []:
            try:
                apr = _ap.borrar_sitio(apr, ambito)
            except KeyError:
                pass
    if hecho.tipo == "paga_en_efectivo" and hecho.contraparte and hecho.contraparte in apr.personas:
        habito = apr.personas[hecho.contraparte].model_copy(deep=True)
        habito.canales = {k: int(v) for k, v in (hecho.datos.get("canales_antes") or {}).items()}
        if not hecho.datos.get("canal_fijado_antes"):
            habito.fijado_por_usuario = [c for c in habito.fijado_por_usuario if c != "canales"]
        vacio = not (habito.canales or habito.retrasos_dias or habito.retrasos_tras_pedir or habito.paga_solo
                     or habito.paga_tras_pedir or habito.redondea or habito.fijado_por_usuario)
        personas = dict(apr.personas)
        if hecho.datos.get("habito_nuevo") and vacio:
            personas.pop(hecho.contraparte)
        else:
            personas[hecho.contraparte] = habito
        apr = apr.model_copy(update={"personas": personas})
    if apr is not modelo.aprendizaje:
        modelo.aprendizaje = apr
