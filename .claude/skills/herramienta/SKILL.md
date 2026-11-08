---
name: herramienta
description: Crea una herramienta nueva para el agente del producto con esquema, función, test, caso de eval y validación financiera. Úsala cuando el agente necesite calcular o consultar algo que hoy no puede.
argument-hint: "<qué debe hacer la herramienta>"
disable-model-invocation: true
---

# /herramienta $ARGUMENTS

## 1. Diseño (5 minutos)
- Nombre en `snake_case` con verbo o sustantivo claro (`simular_hipoteca`, `impuesto_iva`).
- Primera línea del docstring: qué hace **y cuándo debe usarla Claude**. Es lo que decide si la elige.
- Argumentos con tipos, unidades y rangos en la sección `Args:`. Opcionales con valor por defecto.
- Salida: dict con cifras redondeadas, los supuestos usados y una `nota` si hay limitaciones.
- ¿Necesita los datos de la sesión? Entonces lleva el parámetro `ctx`.

## 2. Implementación (`programador`)
En el módulo que corresponda de `backend/herramientas/` (o uno nuevo, importado en `backend/herramientas/__init__.py`):

```python
from ..agente.registro import herramienta

@herramienta
def nombre_herramienta(importe: float, meses: int = 12, ctx=None) -> dict:
    """Qué hace y cuándo usarla, en una frase.

    Úsala para "pregunta típica del usuario".

    Args:
        importe: Importe en euros (mayor que cero).
        meses: Plazo en meses (1-360).
    """
    if importe <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    ...
    return {"resultado": ..., "supuestos": {...}, "nota": "Cálculo orientativo."}
```
- Dinero exacto con `Decimal`; análisis con pandas y `eur()` de `_analisis.py`.
- Errores con `ValueError` y un mensaje que diga qué falta: Claude lo lee y corrige la llamada.
- Si llama a una API externa: `obtener_json()` con timeout, caché y mensaje claro si no hay red (ver `mercados.py`).
- Si llama a Claude (por ejemplo, para clasificar): `claude_client.preguntar_json_con_coste(...)` con Haiku y suma el coste a `ctx.coste_usd`.

## 3. Test (`tester`)
En `tests/test_<modulo>.py`: caso normal con valores calculados a mano, caso límite y error esperado. Sin API real.

## 4. Validación financiera
Si hay una fórmula, `experto-finanzas` la revisa con un cálculo independiente.

## 5. Eval
Añade un caso en `evals/casos.yaml` con `herramientas: [nombre_herramienta]` y, si hay cifra, `cifras: [{herramienta, argumentos, campo}]`. Lánzalo: `python evals/ejecutar.py --casos <id>`.

## 6. Cerrar
- Nombre legible en `frontend/lib/formato.ts` (diccionario `HERRAMIENTAS`).
- Pruébala a mano en el panel (`streamlit run panel/app.py`, pestaña Herramientas).
- `pytest -q` en verde y commit `feat: herramienta <nombre>`.
