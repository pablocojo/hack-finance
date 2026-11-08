"""
Panel interno para probar el agente sin la web:  streamlit run panel/app.py

- Chat con el agente (streaming, traza y coste de cada respuesta).
- Carga de datos de ejemplo o de un CSV del banco.
- Prueba manual de cualquier herramienta con sus argumentos, sin gastar crédito.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from backend import config  # noqa: E402
from backend.agente import registro, servicio  # noqa: E402
from backend.agente.guardarrailes import AVISO_IA  # noqa: E402
from backend.agente.nucleo import Agente  # noqa: E402
from backend.datos.almacen import ALMACEN  # noqa: E402
from backend.datos.importar_csv import importar_csv  # noqa: E402
from backend.datos.sinteticos import PERFILES  # noqa: E402
from backend.herramientas.gastos import resumen_gastos  # noqa: E402

AJUSTES = config.ajustes()
st.set_page_config(page_title=f"Panel · {AJUSTES.nombre_producto}", layout="wide")

if "sesion_id" not in st.session_state:
    st.session_state.sesion_id = ALMACEN.crear(AJUSTES.perfil_demo).id
    st.session_state.chat = []
sesion = ALMACEN.obtener(st.session_state.sesion_id, perfil_demo=AJUSTES.perfil_demo)


def reiniciar_chat() -> None:
    sesion.mensajes = []
    st.session_state.chat = []


with st.sidebar:
    st.header("Datos")
    perfiles = list(PERFILES)
    perfil = st.selectbox("Perfil de ejemplo", perfiles,
                          index=perfiles.index(AJUSTES.perfil_demo) if AJUSTES.perfil_demo in perfiles else 0)
    if st.button("Cargar datos de ejemplo"):
        ALMACEN.cargar_ejemplo(sesion, perfil)
        reiniciar_chat()
    archivo = st.file_uploader("CSV del banco", type=["csv"])
    if archivo is not None and st.button("Importar CSV"):
        try:
            movimientos, informe = importar_csv(archivo.getvalue())
            ALMACEN.cargar_movimientos(sesion, movimientos, origen=f"CSV del usuario ({archivo.name})")
            reiniciar_chat()
            st.success(f"{informe['importadas']} movimientos importados")
        except ValueError as error:
            st.error(str(error))
    st.caption(json.dumps(sesion.resumen_datos(), ensure_ascii=False))

    st.header("Agente")
    preferencia = st.radio("Modelo", ["auto", "rapido", "normal", "profundo"], horizontal=True)
    revisor = st.toggle("Revisor de cumplimiento", value=AJUSTES.revisor_cumplimiento)
    estado = servicio.estado()
    if not estado["clave_configurada"]:
        st.warning("Sin clave: añade ANTHROPIC_API_KEY_PRODUCTO a .env")
    st.caption(f"Modo demo: {AJUSTES.modo_demo} · herramientas: {len(registro.disponibles())} · "
               f"coste de la sesión: {sesion.coste_usd:.4f} $")
    st.button("Nueva conversación", on_click=reiniciar_chat)

st.caption(AVISO_IA)
pestana_chat, pestana_datos, pestana_herramientas = st.tabs(["Chat", "Datos", "Herramientas"])

with pestana_chat:
    for mensaje in st.session_state.chat:
        with st.chat_message(mensaje["rol"]):
            st.markdown(mensaje["texto"])
            if mensaje.get("pie"):
                st.caption(mensaje["pie"])
            if mensaje.get("trazas"):
                with st.expander("Traza"):
                    st.json(mensaje["trazas"])

    pregunta = st.chat_input("Pregunta al agente")
    if pregunta:
        st.session_state.chat.append({"rol": "user", "texto": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            hueco = st.empty()
            partes: list[str] = []

            def al_evento(tipo: str, datos: dict) -> None:
                if tipo == "texto":
                    partes.append(datos["texto"])
                    hueco.markdown("".join(partes) + " ▌")
                elif tipo == "herramienta_inicio":
                    st.caption(f"Herramienta: {datos['nombre']} {json.dumps(datos['entrada'], ensure_ascii=False)}")
                elif tipo == "aviso":
                    st.info(datos["texto"])
                elif tipo == "revision" and not datos.get("aprobada", True):
                    st.warning("El revisor de cumplimiento ha corregido la respuesta: "
                               + "; ".join(datos.get("problemas", [])))

            try:
                resultado = servicio.conversar(sesion, pregunta, preferencia=preferencia,
                                               al_evento=al_evento, agente=Agente(revisor=revisor))
            except Exception as error:  # noqa: BLE001
                st.error(f"{type(error).__name__}: {error}")
                resultado = None
            if resultado:
                hueco.markdown(resultado["texto"])
                pie = (f"{resultado.get('modelo')} · {resultado.get('vueltas')} vueltas · "
                       f"{resultado.get('coste_usd', 0):.4f} $")
                st.caption(pie)
                st.session_state.chat.append({"rol": "assistant", "texto": resultado["texto"], "pie": pie,
                                              "trazas": resultado.get("trazas")})

with pestana_datos:
    if not sesion.movimientos:
        st.info("No hay movimientos cargados.")
    else:
        meses = st.slider("Meses", 1, 12, 3)
        resumen = resumen_gastos(meses=meses, ctx=sesion)
        columnas = st.columns(4)
        columnas[0].metric("Ingresos", f"{resumen['ingresos']:,.2f} €")
        columnas[1].metric("Gastos", f"{resumen['gastos']:,.2f} €")
        columnas[2].metric("Ahorro", f"{resumen['ahorro']:,.2f} €")
        columnas[3].metric("Tasa de ahorro", f"{resumen['tasa_ahorro_pct']} %")
        st.bar_chart(pd.DataFrame(resumen["por_categoria"]).set_index("categoria")["importe"])
        st.dataframe(pd.DataFrame(sesion.movimientos).iloc[::-1])

with pestana_herramientas:
    st.write("Ejecuta una herramienta tal y como la llamaría Claude. No gasta crédito "
             "(salvo categorizar_movimientos, que usa Haiku).")
    disponibles = {h.nombre: h for h in registro.disponibles()}
    nombre = st.selectbox("Herramienta", list(disponibles))
    st.code(json.dumps(disponibles[nombre].definicion(), ensure_ascii=False, indent=2), language="json")
    argumentos = st.text_area("Argumentos (JSON)", "{}")
    if st.button("Ejecutar"):
        try:
            entrada = json.loads(argumentos or "{}")
        except ValueError as error:
            st.error(f"JSON no válido: {error}")
        else:
            texto, es_error, ms = registro.ejecutar(nombre, entrada, ctx=sesion)
            (st.error if es_error else st.success)(f"{ms} ms")
            try:
                st.json(json.loads(texto))
            except ValueError:
                st.write(texto)
