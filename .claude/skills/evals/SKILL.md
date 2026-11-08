---
name: evals
description: Lanza la batería de evals del agente del producto, la compara con la ejecución anterior y resume regresiones y arreglos. Úsala tras cambiar el prompt, las herramientas o el modelo, cada noche y antes de la demo.
argument-hint: "[ids de casos separados por comas]"
---

# /evals $ARGUMENTS

1. Delega en `evaluador`:
   - Todos los casos: `python evals/ejecutar.py`
   - Algunos: `python evals/ejecutar.py --casos $ARGUMENTS`
   - Otro modelo: añade `--modelo opus` (o `haiku`, `sonnet`).
   Usa la clave de evals (`ANTHROPIC_API_KEY_EVALS`). Cada pasada completa cuesta céntimos.
2. Pide el resumen: aprobados/total, casos que empeoran respecto a la ejecución anterior, los 3 fallos más importantes con su arreglo propuesto y el coste.
3. Si algo empeora, crea la tarea en `docs/PLAN.md` y arréglalo con `/feature` antes de seguir con otra cosa.
4. Si todo pasa, apunta el resultado en `docs/DIARIO.md` (lo usa el pitch).

Sin crédito o sin red, `python evals/ejecutar.py --simulado` comprueba que el arnés funciona (los casos fallan, es normal).
