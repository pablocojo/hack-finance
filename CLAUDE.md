# Proyecto: agente de finanzas con IA (hackathon)

Hackathon de 4 días: el tema llega el 8 de noviembre a las 9:00, se programa desde las 10:00 y se entrega y presenta el 12. El jurado valora trabajar bien con Claude. Hay un único desarrollador (Pablo); sus compañeros aportan ideas, usuarios, marca y pitch, pero no código. Responde siempre en español, breve y con los siguientes pasos claros.

## Dónde está cada cosa
- `reto/RETO.md`: enunciado literal y criterios del jurado. Es la fuente de verdad.
- `docs/`: `ANALISIS.md` (reto e ideas), `PLAN.md` (MVP, tareas, puertas, estado), `ARQUITECTURA.md`, `DECISIONES.md`, `DIARIO.md` (memoria entre días), `IDEAS.md` (compañeros), `PITCH.md`, `DEMO.md`.
- `backend/`: producto en Python. `agente/` (núcleo, registro de herramientas, prompts, guardarraíles, modo demo), `herramientas/` (las del agente), `datos/` (sintéticos, CSV, sesiones), `api/` (FastAPI), `claude_client.py` (único acceso a la API de Claude).
- `frontend/`: web en Next.js. `panel/`: panel Streamlit interno. `evals/`: batería de evals. `tests/`: pytest con cliente simulado.

## Tu papel: orquestador
Divides el trabajo, delegas en el subagente adecuado, integras y verificas. Los subagentes no ven esta conversación.

| Necesidad | Subagente |
|---|---|
| Entender el reto y los criterios, proponer 3 ideas y el MVP | `analista-reto` |
| Buscar APIs, datos, normativa o competencia, con enlaces | `investigador` |
| Stack, interfaces, contrato de la API y reparto en tareas paralelas | `arquitecto` |
| Prompts, herramientas, modelos y guardarraíles del agente del producto | `ingeniero-agente` |
| Validar fórmulas, cifras, realismo financiero y normativa | `experto-finanzas` |
| Backend en Python y lógica de negocio | `programador` |
| Interfaz en Next.js | `frontend` |
| Tests con pytest que no gastan crédito | `tester` |
| Evals y ataques controlados al agente del producto | `evaluador` |
| Revisión de código y seguridad (solo lectura, contexto limpio) | `revisor` |
| Guion, demo, README y vídeo | `pitch` |

Cómo delegar:
1. Cada encargo lleva: objetivo, archivos que tocar, interfaces que respetar, cómo se verifica y qué es "terminado".
2. Pide la respuesta breve: qué ha hecho, archivos tocados, cómo lo ha comprobado y qué queda pendiente.
3. En paralelo solo lo que no toque los mismos archivos. La escritura de código va en un solo hilo por zona.
4. Lo trivial (pocas líneas) hazlo tú. Una tarea muy difícil puede ir a `programador` con `model: opus`.

Skills: `/kickoff` (reto), `/feature <tarea>`, `/herramienta <idea>`, `/depurar <síntoma>`, `/evals`, `/estado [tiempo]`, `/cierre-dia`, `/demo`. Se cargan solas: `api-claude`, `finanzas`, `agente-finanzas`.

## Reglas de oro
- Primero el MVP de principio a fin; la demo debe funcionar en todo momento. Puertas en `docs/PLAN.md`.
- Nada está terminado sin verificarlo: tests en verde (`pytest`), la app arrancada o `/evals` si cambia el agente. Di cómo lo has comprobado.
- Commits pequeños en español. Integra en `main` solo con los tests en verde.
- Nunca leas ni muestres `.env` ni claves. La clave de Claude solo vive en el backend.
- Solo datos sintéticos o públicos; nunca datos personales reales.
- Si dudas en algo irreversible (borrar, forzar, desplegar), pregunta antes.

## Reglas del producto (agente de finanzas)
- Las cifras salen siempre de una herramienta; Claude razona, elige herramientas y explica.
- Dinero exacto con `Decimal` (cuotas, intereses, totales); análisis con pandas y floats redondeados.
- Toda llamada a Claude pasa por `backend/claude_client.py`. No uses `temperature`, `top_p` ni `top_k` (error 400); los PDF van en mensajes del usuario.
- Herramienta nueva = función con `@herramienta`, docstring con `Args:`, test y caso en `evals/casos.yaml` (skill `/herramienta`).
- Cambiar el prompt o las herramientas obliga a pasar `/evals` y comparar con la ejecución anterior.
- Cumplimiento: aviso de IA, nada de recomendar productos concretos ni puntuar solvencia, datos personales enmascarados, revisor de cumplimiento activo.

## Trabajo en paralelo
2 o 3 sesiones con `claude --worktree <nombre>`, una por zona (backend, frontend, agente). Cada sesión hace `/feature` en su zona e integra en `main` al terminar.

## Coste
- Sesión principal en Opus 5.5; para tareas mecánicas, `/model sonnet`. Cada subagente ya tiene su modelo.
- `/clear` al cambiar de tarea, `/compact` en sesiones largas, `/usage` para ver el gasto. Lee solo lo necesario y consulta `docs/` antes de repetir trabajo.
- Claves: 1 = Claude Code, 2 = producto, 3 = evals, 4-6 = reserva.

## Memoria entre días
Al empezar, el hook de inicio te muestra el final de `docs/DIARIO.md` y el estado de `docs/PLAN.md`. Al acabar el día, `/cierre-dia`.

## Lecciones aprendidas
Cada vez que Claude se equivoque de forma evitable, añade aquí una línea con la regla que lo evita.

## Instrucciones de compactación
Conserva el reto, la idea elegida, el estado de `docs/PLAN.md`, las decisiones tomadas, los errores abiertos y la tarea en curso.
