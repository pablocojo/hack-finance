# Finanzas IA

Asistente de finanzas personales con IA: entiende en qué se va tu dinero, detecta cargos raros, prevé si llegas a fin de mes y hace cálculos exactos de préstamos y ahorro. Las cifras las calcula el código; Claude razona, elige las herramientas y lo explica.

> Este README es la base del kit. El subagente `pitch` lo reescribe para el jurado en `/demo`.

## Qué hace
- Chat en streaming que enseña qué herramientas ha usado y cuánto ha costado cada respuesta.
- Panel de gastos por categoría y por mes.
- Detección de cobros duplicados, importes inusuales y comercios nuevos.
- Recibos y suscripciones con su coste anual, y previsión del saldo.
- Préstamos (cuota, TAE con comisiones), interés compuesto, plan de ahorro y regla 50/30/20.
- Tipos de cambio de referencia y, con clave, cotizaciones.
- Lectura de tickets, facturas y extractos en imagen o PDF.

## Cómo funciona
```
Web (Next.js) → API (FastAPI, SSE) → agente (bucle de herramientas sobre la API de Claude)
                                       ├─ 14 herramientas en Python (pandas, Decimal)
                                       ├─ guardarraíles: datos personales ocultos y revisor de cumplimiento
                                       └─ datos: sintéticos, CSV del banco, Frankfurter, Alpha Vantage
```
Modelos: Haiku para clasificar y revisar, Sonnet para conversar y Opus para análisis complejos. Caché de prompts y esfuerzo ajustado en cada llamada. Detalle en `docs/ARQUITECTURA.md`.

## Arrancar en local
```bash
pip install -r requirements.txt && cp .env.example .env    # pon ANTHROPIC_API_KEY_PRODUCTO
uvicorn backend.api.main:app --reload
cd frontend && npm install && npm run dev                   # http://localhost:3000
```
Tests sin gastar crédito: `pytest`. Evals del agente: `python evals/ejecutar.py`.

## Cómo hemos trabajado con Claude
- Claude Code como orquestador con 11 subagentes especializados (análisis, investigación, arquitectura, agente, finanzas, backend, frontend, tests, evals, revisión y pitch) y 11 skills con nuestro flujo de trabajo.
- Sesiones en paralelo con worktrees, memoria entre días en `docs/DIARIO.md` y un hook que registra cada subagente.
- Evals con cifras esperadas, ataques de inyección y preguntas trampa de cumplimiento.
- Cifras reales: `python scripts/informe_agentes.py`.

## Confianza y cumplimiento
- Aviso permanente de que es una IA y de que la información es orientativa, no asesoramiento.
- No recomienda productos financieros concretos ni puntúa la solvencia de nadie.
- IBAN, tarjetas, DNI, emails y teléfonos se ocultan antes de llegar a la IA. La demo usa datos sintéticos.
- La clave de la API solo vive en el backend.

## Limitaciones
- Las sesiones viven en memoria: si el servidor se reinicia, se pierde la conversación.
- La detección de anomalías da señales para revisar, no pruebas de fraude.
