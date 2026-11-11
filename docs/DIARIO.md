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

## 2026-11-11 (día 4 de 4, tarde; parada a las 17:52 por saldo de la clave)
- Hecho (14:35-17:50, en `main`, sin `push`; 40 commits desde `7fcfafc`):
  - Encargo `docs/diseno/curva-amigos.md`: fase 0 (tipos, `CONTRATO.md` «Curva de amigos», `amigos/ESQUEMA.md`, decisiones), 10 vidas congeladas (`3fc7f63`, con `FICHAS.md` y `FUENTES.md`), generador, bucle de 8 semanas sobre el sistema real, 7 medidas con sensibilidad, aislamiento y tanda de ajuste en 22 s, gráfica (`evals/resultados/curva-amigos.svg`) y diario (`scripts/diario_amigos.py --vida alvaro --semana 1 --comparar`).
  - Aprendizaje por usuario (`personalizacion/aprende_amigos.py`, `escalera.py`): compañía por comercio y por tipo y franja, grupo habitual, retraso y canal por persona, «Nadie me debe», aprende también de los Bizums que llegan (`casos/observar.py`), escalera 0-3 y grupo habitual en el motor (`motor/detectores/grupo_habitual.py`). Ajuste I2 en `registro/ajuste-amigos.md`.
  - Chat: `apuntar_gasto` y `recordar_sobre_mi` (llamada, conversación sin aviso y plan B), con Deshacer que también desaprende. Pablo ya los dio de alta en ElevenLabs con el prompt nuevo.
  - App: resumen semanal, preguntas con respuestas fijas y «Otra respuesta» (K4), «Tus amigos y tus planes» en `/app/aprendido`, y la pregunta del Bizum que no encaja.
  - Motor: todo el ocio y precio por persona (K1 c, d); Bizum que no encaja con la deuda (K1 a).
- Verificado: `pytest` completo en verde; `/medir todo` sin regresiones; evals de la llamada 35/35 (0,77 US$ con la clave del producto); `revisor` sin bloqueantes (arreglados el 500 con importes absurdos, los hechos del chat fuera de los módulos y el Deshacer que no desaprendía).
- Curva final (simulación, semillas 100-119, total de 8 semanas, `reglas` → `personalizada`): preguntas inútiles 1,11 → 0,78; recordatorios a destiempo 38,9 % → 31,3 %; dinero que se escapa 19,1 % → 19,1 % (no mejora). Nerea y Pilar (vidas nuevas) no mejoran. Frases válidas para el pitch y las que no: `docs/revisiones/necesidad-2026-11-11.md`.
- Tiempos: lo estimado (~20 h) tardó ~5 h reales; ver la columna «h real» de `PLAN.md` y `registro/agentes.jsonl`.
- Problemas abiertos:
  - En la simulación, ~47 % de las personas nombradas en los avisos no debían ese pago o ya lo habían devuelto (igual con `reglas`): planes grandes y cambiantes. No enseñar diarios de Álvaro ni de Pilar sin revisarlos; la demo, con `demo-lucia`.
  - El motor abre a veces un segundo caso sobre un pago que ya tiene uno del chat. Falta una política «sin Meisam» para hablar de dinero recuperado.
  - Menores del `revisor`: `borrar_persona` deja ids en `eventos_vistos`; `confirmar_personas_nuevas` lo decide el modelo, no un clic; `GET /aprendido` sin clave de demo.
  - C8 (extracción del chat con Haiku) preparado y sin ejecutar; la curva usa las etiquetas del corpus.
  - Gráfica a medias (`d2da55b`): faltan del crítico «igual» cuando la diferencia cae dentro del IC95, la fila de Nerea y Pilar y dos supuestos al pie (chat por etiquetas e IA de dudas apagada).
  - `docs/diseno/personalizacion.md` sin el apartado nuevo (A7). El worktree `.claude/worktrees/agent-a9ee61c38c255df23` ya está integrado y se puede borrar.
- Claves: la del producto (2) casi sin saldo; la 3 (evals) no está definida y todo cae en la del producto. **Antes de seguir y antes de la demo, poner una clave de reserva (4-6) como `ANTHROPIC_API_KEY_PRODUCTO` en `.env` y en Render**, y si se quiere, la 3 para evals.
- Para continuar (por orden):
  1. Cambiar la clave del producto (`.env` y Render) por una de reserva.
  2. Terminar la gráfica (`scripts/grafica_amigos.py`, lista de arriba) y regenerarla: `python scripts/grafica_amigos.py evals/resultados/amigos-final-2026-11-11.json`.
  3. Prueba a mano con `demo-lucia` en la app: chat con «Daniel me suele pagar en efectivo» y «La cena del 24 de octubre en la Taberna El Patio la pagué yo, fui con Sara y Marcos» (nombrar el comercio), el Resumen con sus preguntas y «Lo que he aprendido».
  4. `pytest -q` y `git push` (pedir confirmación a Pablo); comprobar el despliegue en Render y Vercel.
  5. Entrega antes de las 23:59 (Z1-Z6 de `PLAN.md`): README, PDF, PowerPoint con la curva y las frases del crítico, vídeo de respaldo.
