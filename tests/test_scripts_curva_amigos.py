"""C9: la gráfica SVG de la curva de amigos y el diario de una vida (`scripts/grafica_amigos.py`,
`scripts/diario_amigos.py`). Sin Claude ni red; el diario corre una vida real del simulador (unos segundos)."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

import diario_amigos  # noqa: E402
import grafica_amigos  # noqa: E402

SEMANAS = [str(s) for s in range(1, 9)]


def celda(media, medio=0.05):
    return {"media": media, "ic95": None if media is None else [max(0.0, media - medio), media + medio], "n": 3}


def global_(**series):
    """`series`: medida -> lista de 8 medias (o None) + total. Las medidas que faltan se rellenan con ceros."""
    nombres = [m for m, _, _ in grafica_amigos.TOTALES]
    salida = {}
    for nombre in nombres:
        valores = series.get(nombre, [0.1] * 8)
        fila = {s: celda(v) for s, v in zip(SEMANAS, valores)}
        con_dato = [v for v in valores if v is not None]
        fila["total"] = celda(sum(con_dato) / len(con_dato) if con_dato else None)
        salida[nombre] = fila
    return salida


def json_ejemplo():
    reglas = global_(dinero_escapa=[None, None, None, 0.30, 0.28, 0.32, 0.31, 0.29],
                     preguntas_inutiles=[0.5, 0.6, 0.4, 0.5, 0.4, 0.5, 0.6, 0.5])
    personal = global_(dinero_escapa=[None, None, None, 0.30, 0.22, 0.18, 0.15, 0.12],
                       preguntas_inutiles=[0.5, 0.4, 0.3, 0.2, 0.2, 0.1, 0.1, 0.1])
    por_vida = lambda a, b: {"alvaro": {"dinero_escapa": {"total": celda(a)}, "preguntas_inutiles": {"total": celda(b)}},
                             "sergio": {"dinero_escapa": {"total": celda(0.3)}, "preguntas_inutiles": {"total": celda(0.5)}}}
    return {
        "parte": "amigos", "simulacion": True, "semillas": [0, 1, 2], "vidas": ["alvaro", "sergio"],
        "hash_vidas": "abcdef0123456789" * 4,
        "medidas": {m: {"debe": "bajar"} for m, _, _ in grafica_amigos.TOTALES},
        "resultados": {
            "reglas": {"ajuste": {"vidas": ["alvaro", "sergio"], "global": reglas}, "por_vida": por_vida(0.3, 0.5)},
            "personalizada": {"ajuste": {"vidas": ["alvaro", "sergio"], "global": personal},
                              "por_vida": por_vida(0.1, 0.2)},
        },
    }


def test_el_svg_es_xml_valido_y_dice_simulacion(tmp_path):
    ruta = tmp_path / "amigos-ejemplo.json"
    ruta.write_text(json.dumps(json_ejemplo()), encoding="utf-8")
    salida = tmp_path / "curva.svg"
    assert grafica_amigos.main([str(ruta), "--salida", str(salida)]) == 0
    raiz = ET.fromstring(salida.read_text(encoding="utf-8"))
    assert raiz.tag.endswith("svg") and raiz.attrib["viewBox"] == "0 0 1920 1080"
    textos = " ".join("".join(t.itertext()) for t in raiz.iter() if t.tag.endswith("text"))
    assert "Simulación: 2 vidas × 3 semillas" in textos and "abcdef01" in textos
    assert "reglas" in textos and "personalizada" in textos
    assert "baja" in textos                                     # la conclusión sale de las cifras
    assert "nan" not in salida.read_text(encoding="utf-8").lower().replace("personalizada", "")


def test_las_semanas_sin_dato_no_se_pintan_como_cero():
    svg = grafica_amigos.generar_svg(json_ejemplo())
    raiz = ET.fromstring(svg)
    lineas = [e for e in raiz.iter() if e.tag.endswith("polyline")]
    # el panel de dinero que se escapa empieza en la semana 4: sus líneas tienen 5 puntos, no 8
    assert any(len(e.attrib["points"].split()) == 5 for e in lineas)
    assert any(len(e.attrib["points"].split()) == 8 for e in lineas)        # el otro panel, completo
    assert "sin dato aún" in svg


def test_la_conclusion_dice_la_verdad_cuando_no_mejora():
    datos = json_ejemplo()
    datos["resultados"]["personalizada"]["ajuste"]["global"] = datos["resultados"]["reglas"]["ajuste"]["global"]
    frase = grafica_amigos.conclusion(datos)
    assert "no cambia" in frase and "no cambian" in frase
    malas = " ".join(grafica_amigos.sin_mejora(datos))
    assert "Sergio" in malas and "Alvaro" not in malas          # enseña dónde no mejora (§4.5)


def test_json_que_no_es_de_amigos_da_un_error_claro(tmp_path):
    ruta = tmp_path / "otro.json"
    ruta.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        grafica_amigos.main([str(ruta), "--salida", str(tmp_path / "x.svg")])


def test_el_diario_corre_una_vida_y_una_semilla(capsys):
    assert diario_amigos.main(["--vida", "alvaro", "--semana", "1", "--semilla", "0"]) == 0
    fuera = capsys.readouterr().out
    assert "SIMULACIÓN" in fuera and "Álvaro" in fuera
    assert "En realidad:" in fuera                              # la verdad oculta, al lado
    assert "Qué pasó con cada deuda" in fuera and "debía" in fuera
    assert "ERROR DEL SISTEMA" not in fuera


def test_el_diario_compara_reglas_y_personalizada(capsys):
    assert diario_amigos.main(["--vida", "diego", "--semana", "1", "--comparar"]) == 0
    fuera = capsys.readouterr().out
    assert "REGLAS" in fuera and "PERSONALIZADA" in fuera
    assert "MEISAM PREGUNTA" in fuera and "Motivos:" in fuera   # nivel y motivos de la escalera


def test_el_diario_rechaza_vida_y_semana_inexistentes():
    with pytest.raises(SystemExit):
        diario_amigos.main(["--vida", "nadie"])
    with pytest.raises(SystemExit):
        diario_amigos.main(["--semana", "9"])
