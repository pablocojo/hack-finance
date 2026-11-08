---
name: cierre-dia
description: Cierre de la jornada. Tests, commit, entrada en el diario con avances, decisiones, problemas y saldo de las claves, siguientes pasos para mañana y lecciones añadidas a CLAUDE.md.
disable-model-invocation: true
---

# /cierre-dia

1. `pytest -q`. Si algo falla, apúntalo como problema abierto (no lo arregles ahora salvo que sea trivial).
2. `git status`: haz commit de lo pendiente con un mensaje claro. Si hay worktrees sin integrar, dilo.
3. Pregunta al usuario el gasto de hoy por clave (lo ve con `/usage` y en la Console). No inventes cifras.
4. Añade al final de `docs/DIARIO.md`:
   ```
   ## AAAA-MM-DD (día N de 5)
   - Hecho:
   - Decisiones:
   - Problemas abiertos:
   - Evals: aprobados/total (coste)
   - Saldo de las claves: 1 …, 2 …, 3 …
   - Mañana, lo primero: 1) … 2) … 3) …
   ```
5. Actualiza "Estado" y las puertas en `docs/PLAN.md`.
6. Lecciones: por cada error evitable de hoy, una línea en "Lecciones aprendidas" de `CLAUDE.md`.
7. Commit `docs: cierre del día` y muestra al usuario las 3 primeras tareas de mañana con sus comandos.
