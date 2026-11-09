# Diario del hackathon

Memoria entre días. La escribe `/cierre-dia` cada noche y el hook de inicio enseña la última entrada al abrir Claude Code.

## 2026-11-07 (víspera)
- Preparación: kit v2 listo (ver `EMPIEZA_AQUI.md`).
- Mañana, lo primero: 1) pegar el enunciado en `reto/RETO.md` a las 9:00; 2) lluvia de ideas con los compañeros en `docs/IDEAS.md`; 3) `/kickoff` a las 10:00 y cerrar la idea antes de las 13:00.

## 2026-11-09 (mediodía)
- Cambio de idea: **Copiloto**, una plataforma para bancos que convierte los movimientos en momentos y lo resuelve por voz. La idea municipal queda descartada (ver `docs/DECISIONES.md`). La estrella de la demo es la cena compartida.
- Sistema de trabajo listo: contrato en `docs/diseno/CONTRATO.md`; cinco agentes nuevos (`ingeniero-deteccion`, `cientifico-personalizacion`, `ingeniero-modulos`, `ingeniero-voz` y `experto-banca`); skills nuevas (`/planificar`, `/esqueleto`, `/escenario`, `/detector`, `/modulo`, `/medir` y `copiloto`); `CLAUDE.md`, `ANALISIS.md`, `ARQUITECTURA.md` (objetivo) y `PLAN.md` actualizados.
- Borradores de diseño en `docs/diseno/` (motor, personalización, módulos y experiencia), escritos por subagentes. Son el punto de partida de `/planificar`.
- Aún no hay código nuevo. Tests del kit en verde (77 pasan y 1 se salta sin fastapi).
- Lo siguiente: 1) `git switch main && git pull`; 2) `claude` y `/planificar`; 3) `/esqueleto`; 4) crear el agente en ElevenLabs y poner `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID` en `.env`.
- Para los compañeros: marca (nombre provisional: Copiloto), historias reales de cenas compartidas para los escenarios y entrevistas.

## 2026-11-09 (día 2 de 4, noche)
- Hecho:
  - `/planificar`: contrato y diseños cerrados (nombre Meisam, perfil de vida, prueba gratuita, baja guiada, búsqueda web por nombre de comercio).
  - `/esqueleto`: E1-E8 de principio a fin (la cena de Lucía por HTTP), E9-E11 y despliegue en Vercel y Render. Puerta «esqueleto vivo y desplegado» cerrada un día antes de lo previsto.
  - Tanda del 10 adelantada: F1, F2, V1, V2, M1, M4, U1 y P3 y, tras quedarnos sin crédito y relanzar tres hilos, **M7, M8, U2 y F6**.
  - `main` subido a GitHub hasta `c777b9d` (voz y chat de ElevenLabs en el frontend desplegable). Quedan 3 commits locales sin subir: plan, agentes a Sonnet y este cierre.
- Decisiones:
  - `ingeniero-deteccion` y `cientifico-personalizacion` pasan a Sonnet para ahorrar crédito.
  - Hilos en el mismo árbol, con zonas de archivos disjuntas y sin commits de los agentes: integra el orquestador, un commit por zona y con `pytest` en verde.
  - El catálogo de comercios vive en `backend/datos/comercios_conocidos.json` (como dicen los diseños) y solo lleva cifras de comercios ficticios.
  - F6: pantalla previa «Meisam te llama» (el micrófono y el audio exigen un gesto del usuario) y caída por niveles: voz, chat de ElevenLabs y `/voz/texto`.
  - A revisar: `olvidar_todo` conserva `usar_perfil = False` si el cliente lo había apagado; un hecho aprendido por respuestas y apagado no se puede reactivar.
- Problemas abiertos:
  - Voz real sin probar. Antes: activar el override de «solo texto» en ElevenLabs (`experiencia.md` §6.1 paso 2 dice lo contrario) y comprobar `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID` en Render.
  - `_validar_contra_propuesta` (`backend/acciones/__init__.py`) compara los parámetros de forma estricta: un agente real que escriba «La Tasca» en vez de «LA TASCA» será rechazado.
  - Streamflix no genera propuesta hasta que exista el módulo `fin_de_prueba` (D1); `/app` carga `cena-lucia`, no `demo-lucia`.
  - `cargo_duplicado` con perfil baja a 0,67 de exhaustividad hasta M9 (xfail no estricto en `tests/test_demo_lucia.py`).
  - `experto-banca` debe revisar las marcas reales del catálogo de comercios; `next dev` regenera `frontend/AGENTS.md` (no commitearlo).
- Evals: las del agente (`/evals`) no se han ejecutado hoy (sin coste). `pytest`: 584 pasan y 1 xfail. `/medir motor`: `prueba_gratuita` 1,0/1,0 y 0 de 7 trampas.
- Saldo de las claves: Pablo se quedó sin crédito a media tanda y cambió a una clave de otra cuenta. Gasto de hoy y saldos: **pendientes de que Pablo los dé** (no los tengo).
- Mañana, lo primero: 1) a mano: override de «solo texto» y claves en Render, y probar la voz con el guion del informe de F6 (chat primero, ≤ 5 min de voz); 2) `/feature M9` (perfil en el motor: `parametros.ajustar`, `impacto_relativo`, `contexto_personal`); 3) `/feature D1` (catálogo `fin_de_prueba` y `cobro_duplicado`, baja guiada) junto con el arreglo de `_validar_contra_propuesta`.
