---
name: modulo
description: Crea un módulo nuevo del Copiloto de principio a fin. Sigue estos pasos: spec YAML válida, prueba en seco sobre escenarios, acciones de la lista cerrada, casos de eval, tests y revisión bancaria. Úsala para cada módulo, incluido el que se crea en directo en la demo.
argument-hint: "<qué debe hacer el módulo, en lenguaje natural>"
disable-model-invocation: true
---

# /modulo $ARGUMENTS

## 1. Encaje (5 minutos)
- ¿Qué tipo de momento escucha? Si ninguno de los que existen sirve, primero `/detector <tipo nuevo>`.
- ¿Qué acciones necesita? Si alguna no está en el registro cerrado, el `ingeniero-modulos` la añade con su confirmación, sus límites y su efecto en el banco simulado. `experto-banca` confirma que es realista.
- ¿Qué valor da al usuario (dinero ahorrado o riesgo evitado)? Si no ahorra ni protege, no merece interrumpir: replantéalo.

## 2. La spec (`ingeniero-modulos`)
- YAML en `backend/modulos/catalogo/<id>.yaml`, válido contra el esquema de `docs/diseno/modulos.md`.
- Si ya existe el generador desde lenguaje natural, úsalo con `$ARGUMENTS` y revisa lo que produce. Es el mismo camino que se enseña en la demo.
- Condiciones en el minilenguaje (nada de código). Los mensajes, con plantillas cuyos números formatea el código. El primer mensaje de la llamada incluye el aviso de IA.

## 3. Prueba en seco
Ejecútalo sobre los escenarios y el historial sintético: cuántas veces habría saltado, con qué momentos y qué habría propuesto. Si salta de más o de menos, ajusta las condiciones antes de seguir.

## 4. Evals y tests
- Un caso de eval por comportamiento: salta cuando debe, calla en la trampa y no ejecuta nada sin confirmación.
- Un caso de ataque: una nota de Bizum o un concepto con instrucciones escondidas.
- `pytest -q` en verde.

## 5. Personalización
No hace falta código: comprueba que el módulo aparece en la política de interrupción y en «lo que he aprendido de ti», y que el feedback de sus propuestas se registra.

## 6. Cerrar
- Commit: `feat: módulo <id>`.
- Resume en 4 líneas: qué hace, resultado de la prueba en seco, evals y la siguiente tarea recomendada.
