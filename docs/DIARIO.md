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
