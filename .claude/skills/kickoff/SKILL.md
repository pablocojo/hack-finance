---
name: kickoff
description: Arranque del hackathon al recibir el reto. Análisis e investigación en paralelo, elección de idea, arquitectura, plan por días y esqueleto funcionando de principio a fin.
argument-hint: "[ruta del reto; por defecto reto/RETO.md]"
disable-model-invocation: true
---

# /kickoff

Objetivo: salir con la idea cerrada, el plan por días y el esqueleto funcionando de principio a fin. La idea debe estar cerrada antes de las 13:00 del 8 de noviembre.

## 0. Comprobar la entrada
- Lee el reto (`$ARGUMENTS` o `reto/RETO.md`). Si todavía es la plantilla, para y pide al usuario que pegue el enunciado literal, los criterios del jurado y el formato de entrega.
- Lee `docs/IDEAS.md` (lluvia de ideas de los compañeros) si tiene contenido.

## 1. Análisis en paralelo (una sola tanda de subagentes)
Lanza a la vez, con encargos completos (no ven esta conversación):
- `analista-reto`: escribir `docs/ANALISIS.md` con criterios, 3 ideas comparadas y MVP recomendado.
- `investigador`: APIs, datos y competidores concretos del tema (qué existe, coste, límites), en `docs/INVESTIGACION.md`.
- `experto-finanzas`: riesgos regulatorios del tema y qué datos sintéticos harían falta para que la demo sea realista.

## 2. Decisión con el usuario
Resume en 15 líneas como mucho: las 3 ideas con su puntuación, la recomendada y su MVP. Pregunta con opciones (la recomendada primero) qué idea se elige y si el MVP vale. Anota la decisión en `docs/DECISIONES.md`.

## 3. Arquitectura y plan
`arquitecto`: actualizar `docs/ARQUITECTURA.md` y escribir en `docs/PLAN.md` las tareas por zona, con criterio de aceptación, verificación, día y puertas (idea cerrada 8 nov 13:00, esqueleto vivo y desplegado 8 nov noche, MVP con evals en verde 10 nov noche, congelación 11 nov 14:00, entrega 12 nov).

## 4. Adaptar el agente del producto
`ingeniero-agente`: nombre del producto (`NOMBRE_PRODUCTO`), foco del prompt, herramientas que sobran o faltan y 3-5 casos de eval nuevos para el MVP. Las herramientas nuevas se crean con `/herramienta`.

## 5. Esqueleto de principio a fin
En paralelo si no comparten archivos: `programador` (endpoints y datos mínimos del MVP) y `frontend` (pantalla principal adaptada a la idea). Después, `tester` con `pytest -q`.

## 6. Comprobar que funciona
- Backend: `uvicorn backend.api.main:app --reload` y `curl -s http://localhost:8000/salud`.
- Una pregunta real de principio a fin (web o panel). Cuesta céntimos con la clave del producto.

## 7. Cerrar
- Commit: `kickoff: idea, plan y esqueleto`.
- Muestra al usuario: la idea, el MVP, las puertas y las 3 primeras tareas para lanzar en paralelo, con sus comandos (`claude --worktree <zona>` y `/feature <id>` en cada una).
