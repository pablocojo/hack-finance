"""
`observar` (O7): contactos y saldo con cada amigo. Puro: no guarda nada (guarda el orquestador).

- `observar(modelo, movimientos, hoy)` (firma fija del contrato): por cada Bizum o transferencia del día suma
  una vez a `contactos` (clave de contraparte `MARCOS R`). Nunca guarda conceptos ni notas.
- `saldo_amigos(modelo, casos, hoy)`: el saldo con cada amigo se CALCULA a partir de los `Caso`
  (`backend/casos/amigos.py`); `Amigo` no se estira ni se guarda aparte. Lo llama el orquestador tras `observar`.
"""

from __future__ import annotations

from datetime import date

from ..motor.normalizar import normalizar
from ..plataforma.tipos import Caso, Contacto, ModeloUsuario, Movimiento


def observar(modelo: ModeloUsuario, movimientos: list[Movimiento], hoy: date) -> ModeloUsuario:
    nuevo = modelo
    for m in movimientos:
        e = normalizar(m)
        if e.canal not in ("bizum", "transferencia") or not e.contraparte_normalizada or e.fecha > hoy:
            continue
        if nuevo is modelo:
            nuevo = modelo.model_copy(deep=True)
        previo = nuevo.contactos.get(e.contraparte_normalizada)
        nuevo.contactos[e.contraparte_normalizada] = Contacto(
            contraparte=e.contraparte_normalizada, veces=(previo.veces if previo else 0) + 1,
            ultima=max(e.fecha, previo.ultima) if previo else e.fecha)
    return nuevo


def saldo_amigos(modelo: ModeloUsuario, casos: list[Caso], hoy: date) -> ModeloUsuario:
    from ..casos import sincronizar_amigos
    return sincronizar_amigos(modelo, casos, hoy)
