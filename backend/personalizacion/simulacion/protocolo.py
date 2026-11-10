"""
Protocolo de la curva de aprendizaje (personalizacion.md §8): 6 semanas × usuarios simulados × semillas,
con cinco políticas. Usa la política, el perfil y el aprendizaje reales (`backend.personalizacion`); no los
duplica. Solo datos sintéticos; sin Claude.

Políticas
- `reglas`: referencia, notifica todo lo que ahorra o protege (el «banco clásico»). Es la base de las
  «molestias evitadas».
- `fija`: la política sin perfil y sin aprender (arranque en frío, umbral de 20 €).
- `perfil`: con el perfil de vida del usuario, sin aprender.
- `aprendida`: sin perfil, aprendiendo de sus respuestas y de las acciones que elige.
- `personalizada`: perfil + aprendizaje (lo que hace Meisam).

Los avisos se responden con retraso (2 h; 48 h si se ignoran) y el aprendizaje solo ve lo ya ocurrido.
"""

from __future__ import annotations

import heapq
import time
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from ... import personalizacion
from ...plataforma.tipos import Feedback, ModeloUsuario, Propuesta, ResultadoAccion
from ..politica import silencio_que_coincide
from .generador import MODULO_DE, Sintetica, generar, mismo_duplicado
from .perfiles import PROTECCION, USUARIOS, Estado, UsuarioSimulado

POLITICAS = ("reglas", "fija", "perfil", "aprendida", "personalizada")
APRENDEN = frozenset({"aprendida", "personalizada"})
CON_PERFIL = frozenset({"perfil", "personalizada"})
SEMILLAS = tuple(range(10))
SEMANAS = 6
RETRASO_RESPUESTA = timedelta(hours=2)
RETRASO_IGNORADA = timedelta(hours=48)       # el orquestador cierra los avisos sin respuesta a las 48 h


def modelo_inicial(usuario: UsuarioSimulado, politica: str, modulos: dict[str, str] | None = None) -> ModeloUsuario:
    m = personalizacion.nuevo_modelo(usuario.nombre)
    m.modulos_activos = sorted(set((modulos or MODULO_DE).values()))
    m.consentimientos = {"copiloto": datetime(2026, 11, 1)}
    m.perfil = usuario.perfil.model_copy(deep=True) if politica in CON_PERFIL else None
    return m


def elige_accion(usuario: UsuarioSimulado, propuesta: Propuesta, azar: tuple[float, ...]) -> str:
    """Su favorita con p = 0,8; si no, otra de las ofrecidas."""
    ofrecidas = [a.accion_id for a in propuesta.acciones_ofrecidas]
    favorita = usuario.favorita[propuesta.tipo_momento]
    otras = [a for a in ofrecidas if a != favorita]
    if favorita in ofrecidas and (azar[2] < 0.8 or not otras):
        return favorita
    return otras[min(int(azar[3] * len(otras)), len(otras) - 1)]


def simular(politica: str, usuario: UsuarioSimulado, semilla: int, semanas: int = SEMANAS,
            modulos: dict[str, str] | None = None) -> list[dict]:
    """Una vida de `semanas` semanas bajo una política. Devuelve un registro por propuesta."""
    modelo = modelo_inicial(usuario, politica, modulos)
    estado = Estado()
    pendientes: list = []            # (cuando, orden, tipo, carga): respuestas aún no ocurridas
    orden = 0
    registros: list[dict] = []

    def aplicar_hasta(ahora: datetime) -> None:
        nonlocal modelo
        while pendientes and pendientes[0][0] <= ahora:
            _, _, tipo, carga = heapq.heappop(pendientes)
            modelo = (personalizacion.aprender(carga, modelo) if tipo == "feedback"
                      else personalizacion.registrar_accion(modelo, *carga))

    for s in generar(usuario, semilla, semanas, modulos):
        p, ahora = s.propuesta, s.propuesta.creada
        aplicar_hasta(ahora)
        valor = p.valor_estimado_eur or Decimal("0")
        proteccion = p.tipo_momento in PROTECCION or p.urgencia == "alta"
        if politica == "reglas":
            accion = "notificar_ahora" if (valor > 0 or proteccion) else "silenciar"
            ofrecida, motivos, ms, silencio = p, ["Ahorra o protege."], 0.0, False
        else:
            ofrecida = personalizacion.ordenar_acciones(p, modelo) if politica in APRENDEN else p
            silencio = silencio_que_coincide(p, modelo) is not None
            t0 = time.perf_counter()
            decision = personalizacion.decidir(ofrecida, modelo, ahora)
            ms = (time.perf_counter() - t0) * 1000
            accion, motivos = decision.accion, decision.motivos

        reg = {
            "politica": politica, "usuario": usuario.nombre, "semilla": semilla, "semana": s.semana,
            "id": p.id, "tipo": p.tipo_momento, "valor": float(valor), "util": s.util, "falsa": s.falsa,
            "proteccion": proteccion and not s.falsa, "accion": accion, "motivos": len(motivos),
            "ms": ms, "tras_silencio": silencio, "util_efectiva": False, "resultado": None,
            "primera": ofrecida.acciones_ofrecidas[0].accion_id, "elegida": None,
        }
        registros.append(reg)
        if accion == "silenciar":
            continue

        util_ahora = s.util
        resultado, fatiga = usuario.reacciona(
            accion=accion, tipo=p.tipo_momento, util=util_ahora, falsa=s.falsa, contraparte=p.contraparte,
            semana=s.semana, azar=s.azar, estado=estado)
        reg["resultado"] = resultado
        reg["util_efectiva"] = bool(s.util and not fatiga)
        reg["fatiga"] = fatiga
        if politica in APRENDEN:
            modelo = personalizacion.registrar_decision(modelo, ofrecida, decision)
            cuando = ahora + (RETRASO_IGNORADA if resultado == "ignorada" else RETRASO_RESPUESTA)
            fb = Feedback(propuesta_id=p.id, usuario_id=usuario.nombre, resultado=resultado, canal="app",
                          fecha=cuando)
            orden += 1
            heapq.heappush(pendientes, (cuando, orden, "feedback", fb))
        if resultado == "resuelta":
            elegida = elige_accion(usuario, ofrecida, s.azar)
            reg["elegida"] = elegida
            if politica in APRENDEN:
                orden += 1
                heapq.heappush(pendientes, (ahora + RETRASO_RESPUESTA, orden, "accion",
                                            (ofrecida, ResultadoAccion(accion_id=elegida, ok=True, mensaje="ok"))))
    return registros


def simular_todo(semillas: tuple[int, ...] = SEMILLAS, politicas: tuple[str, ...] = POLITICAS,
                 usuarios: tuple[str, ...] | None = None, semanas: int = SEMANAS,
                 modulos: dict[str, str] | None = None) -> list[dict]:
    nombres = usuarios or tuple(USUARIOS)
    return [r for pol in politicas for n in nombres for sem in semillas
            for r in simular(pol, USUARIOS[n], sem, semanas, modulos)]


# --- Métricas ---------------------------------------------------------------------------------------

def _div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def fila(regs: list[dict]) -> dict:
    """Métricas de un grupo de registros (una política, una semana, unos usuarios)."""
    ahora = [r for r in regs if r["accion"] == "notificar_ahora"]
    resumen = [r for r in regs if r["accion"] == "resumen"]
    silenciadas = [r for r in regs if r["accion"] == "silenciar"]
    utiles = [r for r in regs if r["util"]]
    utiles_ahora = [r for r in ahora if r["util_efectiva"]]
    eur_utiles = sum(r["valor"] for r in utiles)
    resueltas = [r for r in regs if r["elegida"]]
    return {
        "propuestas": len(regs), "ahora": len(ahora), "resumen": len(resumen), "silenciadas": len(silenciadas),
        "utiles": len(utiles),
        "precision_ahora": _div(len(utiles_ahora), len(ahora)),
        "molestias": len(ahora) - len(utiles_ahora),
        "cobertura_ahora": _div(sum(1 for r in utiles if r["accion"] == "notificar_ahora"), len(utiles)),
        "cobertura_total": _div(sum(1 for r in utiles if r["accion"] != "silenciar"), len(utiles)),
        "arrepentimiento": _div(sum(r["valor"] for r in utiles if r["accion"] == "silenciar"), eur_utiles),
        "primera_accion": _div(sum(1 for r in resueltas if r["elegida"] == r["primera"]), len(resueltas)),
        "acciones_elegidas": len(resueltas),
    }


def por_semana(regs: list[dict], semanas: int = SEMANAS) -> list[dict]:
    return [fila([r for r in regs if r["semana"] == w]) for w in range(semanas)]


def duplicado(modulos: dict[str, str] | None = None) -> dict[str, dict]:
    """El mismo duplicado (Netflix, 12,99 €) con cada vida, con la política `fija` y con `perfil`."""
    salida: dict[str, dict] = {}
    for nombre, u in USUARIOS.items():
        p = mismo_duplicado(u, modulos)
        fila_u = {}
        for pol in ("fija", "perfil"):
            d = personalizacion.decidir(p, modelo_inicial(u, pol, modulos), p.creada)
            fila_u[pol] = {"accion": d.accion, "U": d.puntuacion, "motivos": d.motivos}
        salida[nombre] = fila_u
    return salida


def verificar_aislamiento() -> list[str]:
    """Archivos de la política que importan algo de `simulacion` (debe salir vacío)."""
    import re
    from pathlib import Path

    patron = re.compile(r"^\s*(from|import)\s+[\w.]*simulacion", re.MULTILINE)
    base = Path(__file__).resolve().parent.parent
    return sorted(p.name for p in base.glob("*.py") if patron.search(p.read_text(encoding="utf-8")))


def _grupos(regs: list[dict], clave: str) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for r in regs:
        g[r[clave]].append(r)
    return g
