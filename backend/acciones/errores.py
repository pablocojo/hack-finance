"""Errores controlados de las acciones. `codigo` permite a la API elegir el estado HTTP."""

from __future__ import annotations

HTTP_POR_CODIGO = {
    "parametros_invalidos": 400,
    "token_desconocido": 404,
    "propuesta_desconocida": 404,
    "accion_no_ofrecida": 403,
    "fuera_de_limites": 403,
    "token_otro_usuario": 403,
    "token_otra_propuesta": 403,
    "parametros_alterados": 403,
    "token_usado": 409,
    "token_caducado": 410,
    "no_se_puede": 409,
    "importe_fuera_de_rango": 400,
    "limite_solicitudes_mes": 409,
    "solicitud_abierta": 409,
}


class ErrorAccion(ValueError):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje

    @property
    def http(self) -> int:
        return HTTP_POR_CODIGO.get(self.codigo, 400)
