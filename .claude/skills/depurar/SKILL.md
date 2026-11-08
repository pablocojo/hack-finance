---
name: depurar
description: Depuración sistemática de un fallo. Reproducir con un test, aislar, formular una hipótesis, arreglo mínimo en la causa y test de regresión. Úsala cuando algo falle dos veces seguidas o el error no sea evidente.
argument-hint: "<síntoma o mensaje de error>"
---

# /depurar $ARGUMENTS

Nada de cambios a ciegas: sin reproducción no hay arreglo.

1. **Reproducir**: el comando exacto o un test que falle (`tester`). Anota la salida literal.
2. **Aislar**: lee el traceback de abajo arriba y localiza la primera línea de nuestro código. Mira qué cambió hace poco: `git log --oneline -5` y `git diff`.
3. **Hipótesis**: escribe una sola hipótesis y cómo comprobarla. Compruébala con un test o un print temporal.
4. **Arreglo mínimo** en la causa, no en el síntoma.
5. **Regresión**: el test que reproducía el fallo pasa y `pytest -q` sigue en verde. Quita los prints temporales.
6. **Lección**: si el fallo vino de un error evitable de Claude, añade una línea en "Lecciones aprendidas" de `CLAUDE.md`.

Tras 3 hipótesis fallidas, para y cuenta al usuario lo que sabes, lo que has descartado y qué probarías.

## Causas típicas en este proyecto
| Síntoma | Causa probable |
|---|---|
| `SinClaveError` o 503 en `/chat` | Falta `ANTHROPIC_API_KEY_PRODUCTO` en `.env` (en un worktree, revisa `.worktreeinclude`) |
| 400 de la API de Claude | `temperature`/`top_p`/`top_k` en la petición, un PDF en un mensaje del asistente o un esquema JSON no válido |
| 429 | Límite de velocidad de la organización: baja la concurrencia y espera |
| "credit balance too low" | Saldo agotado: cambia a la clave de reserva |
| El navegador no conecta | Backend parado, `NEXT_PUBLIC_API_URL` mal (hay que reiniciar `npm run dev`) o CORS (`ORIGENES_CORS`) |
| El streaming llega de golpe | Un proxy guarda la respuesta: revisa la cabecera `X-Accel-Buffering: no` |
| Herramienta con error en la traza | Mira el `resumen` del paso: es el `ValueError` que lee Claude |
| Cifras raras | Prueba la herramienta en el panel (pestaña Herramientas) con los mismos argumentos |
