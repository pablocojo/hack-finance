---
name: estado
description: Revisa el avance frente al plan y las puertas, los riesgos y el tiempo restante, y recomienda las 2 o 3 tareas siguientes sin conflictos entre sesiones. Úsala por la mañana, a media tarde o cuando haya dudas sobre prioridades.
argument-hint: "[tiempo restante o próximo hito]"
---

# /estado $ARGUMENTS

1. Recoge datos sin gastar de más: `date`, `docs/PLAN.md`, la última entrada de `docs/DIARIO.md`, `git log --oneline -15` y `pytest -q`.
2. Calcula para la próxima puerta: tareas hechas y pendientes, horas que quedan y horas estimadas.
3. Da un veredicto: **vamos bien**, **justo** o **no llegamos**. Si es "justo" o "no llegamos", propón qué recortar (lo que menos puntos da al jurado).
4. Recomienda 2 o 3 tareas siguientes que no toquen los mismos archivos, con su zona y el comando para lanzarlas (`claude --worktree <zona>` y `/feature <id>`).
5. Lista los 3 riesgos principales con su plan B (tabla de riesgos de `docs/PLAN.md`).
6. Actualiza la sección "Estado" de `docs/PLAN.md` con la fecha y el veredicto.

Respuesta al usuario: 20 líneas como mucho.
