---
name: planificar
description: Fase de diseño del Copiloto con subagentes. Parte del contrato y de los borradores de docs/diseno/, resuelve contradicciones, los pule con los especialistas en paralelo, cierra la arquitectura y el plan por tareas y lo revisa con contexto limpio. Sin código. Úsala al empezar o si hay que replantear el diseño.
argument-hint: "[parte que replantear: motor, personalizacion, modulos, experiencia o todo]"
disable-model-invocation: true
---

# /planificar $ARGUMENTS

Objetivo: salir con el diseño cerrado y coherente entre partes, la arquitectura y el plan por tareas escritos, y nada de código todavía. Si `$ARGUMENTS` nombra una parte, haz solo lo que le afecta.

## 0. Leer lo justo
- `docs/diseno/CONTRATO.md` (idea, flujo, tipos e interfaces), `reto/RETO.md` (rúbrica) y `docs/DECISIONES.md`.
- De cada borrador (`docs/diseno/motor.md`, `personalizacion.md`, `modulos.md` y `experiencia.md`): el resumen inicial, los riesgos y la sección «Cambios propuestos al contrato».

## 1. Resolver el contrato (tú, el orquestador)
- Junta los «Cambios propuestos al contrato». Acepta los que simplifican o desbloquean y rechaza los que rompen otra parte.
- Si dos borradores se contradicen (por ejemplo, en los `datos` de un momento o en quién valida una acción), decide tú.
- Actualiza `CONTRATO.md` y anota cada decisión en `docs/DECISIONES.md` (qué, por qué y qué alternativa se descarta).
- Pregunta a Pablo solo lo que cambie el producto (alcance del MVP o qué módulo es la estrella). Lo técnico lo decides tú.

## 2. Pulir en paralelo (una tanda, como mucho 4 a la vez)
Cada encargo lleva el contrato actualizado, lo decidido en el paso 1, qué debe mejorar y «devuelve como mucho 12 líneas».
- `ingeniero-deteccion` → `docs/diseno/motor.md`: algoritmos finales con parámetros, escenarios etiquetados por detector (incluidas trampas) y métricas objetivo.
- `cientifico-personalizacion` → `docs/diseno/personalizacion.md`: método final, fórmulas con un ejemplo numérico, usuarios simulados y la curva que verá el jurado.
- `ingeniero-modulos` → `docs/diseno/modulos.md`: esquema YAML final, minilenguaje, acciones del MVP y los módulos escritos.
- `ingeniero-voz` → `docs/diseno/experiencia.md`: configuración de ElevenLabs, endpoints que necesita, plan B y guion de la demo.

Segunda tanda, cuando acabe la primera:
- `experto-banca`: revisa acciones, módulos, escenarios y textos (realismo y normativa en España).
- `investigador`: confirma con fuentes lo que haya quedado sin verificar (competencia, ElevenLabs, Bizum) en `docs/INVESTIGACION.md`.

## 3. Arquitectura y plan (`arquitecto`)
- `docs/ARQUITECTURA.md`: componentes, flujo, paquetes, contrato de la API (endpoints, cuerpos y eventos SSE) que comparten `backend/api/main.py` y `frontend/lib/api.ts`, y qué se reutiliza del kit.
- `docs/PLAN.md`: tareas de 2 horas como mucho por zona (`plataforma`, `motor`, `personalizacion`, `modulos`, `voz`, `api`, `frontend`, `demo`), con dependencias, criterio de aceptación, verificación y día. Marca qué va en paralelo. Lo primero es el contrato en código (`backend/plataforma/tipos.py`); después, las zonas.

## 4. Revisión con contexto limpio
`revisor` (solo lectura) sobre `docs/diseno/`, `docs/ARQUITECTURA.md` y `docs/PLAN.md`: incoherencias entre partes, huecos que impiden la demo, riesgos de seguridad o cumplimiento y tareas que no caben en el tiempo. Corrige todo lo que sea `BLOQUEA`.

## 5. Cerrar
- Actualiza la skill `copiloto` con las decisiones finales (tipos, paquetes, endpoints y reglas) para que todos los subagentes las lean.
- Actualiza la sección «Estado» de `docs/PLAN.md`.
- Commit: `plan: diseño cerrado y tareas`.
- Resume a Pablo en 15 líneas como mucho: decisiones, MVP, puertas y las primeras tareas de `/esqueleto`.
