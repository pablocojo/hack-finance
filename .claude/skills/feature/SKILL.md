---
name: feature
description: Implementa una tarea del plan de principio a fin. Plan con rutas, delegación al especialista, tests, correcciones (2 vueltas como máximo), revisión y cierre con commit.
argument-hint: "<tarea o id de docs/PLAN.md>"
disable-model-invocation: true
---

# /feature $ARGUMENTS

## 1. Entender
Busca la tarea en `docs/PLAN.md` (por id o por texto). Si no está, defínela: objetivo, criterio de aceptación y verificación. Si toca más de una zona, divídela.

## 2. Plan con rutas exactas
Escribe en 5-10 líneas: archivos que se tocan, qué cambia en cada uno, interfaces que no se pueden romper y cómo se verificará (qué test y qué comando).

## 3. Delegar en el especialista
| Zona | Subagente |
|---|---|
| Motor: normalización, detectores, razonador (`backend/motor/`, `backend/escenarios/`) | `ingeniero-deteccion` (o las skills `/detector` y `/escenario`) |
| Personalización: modelo de usuario, política, memoria (`backend/personalizacion/`) | `cientifico-personalizacion` |
| Módulos y acciones (`backend/modulos/`, `backend/acciones/`) | `ingeniero-modulos` (o la skill `/modulo`) |
| Llamada de voz y modo texto (`backend/voz/`) | `ingeniero-voz` |
| Prompt, enrutado o guardarraíles del agente conversacional | `ingeniero-agente` |
| Herramienta nueva del agente conversacional | skill `/herramienta` |
| Plataforma, orquestador, API y datos | `programador` |
| Interfaz web (app del cliente, consola del banco, panel del jurado) | `frontend` |

Plantilla de encargo:
```
Objetivo:
Archivos:
Interfaces que respetar:
Criterio de aceptación:
Verificación (comandos):
Devuelve: qué has hecho, archivos tocados, resultado de la verificación y pendientes.
```

## 4. Verificar
- `pytest -q` en verde (o `tester` si hacen falta tests nuevos).
- Si falla, devuelve el error exacto al mismo especialista. Máximo 2 vueltas; si sigue fallando, `/depurar`.
- Frontend: `npm run build` dentro de `frontend/` y el flujo probado con el backend arrancado.

## 5. Revisión según el riesgo
- Dinero, seguridad, datos de usuario, acciones o prompts: `revisor` con el diff.
- Fórmulas o cifras nuevas: `experto-finanzas`.
- Acciones bancarias, módulos o textos legales: `experto-banca`.
- Cambios en un detector, la política o un módulo: `/medir` y comparar con la ejecución anterior.
- Cambios en el agente conversacional o en el de voz: `/evals` con los casos afectados.
Corrige lo que sea `BLOQUEA` antes de cerrar.

## 6. Cerrar
- Marca la tarea como hecha en `docs/PLAN.md`.
- Commit pequeño en español: `feat: <qué>` o `fix: <qué>`.
- Si trabajas en un worktree, recuerda al usuario integrarlo en `main` con los tests en verde.
- Resume en 4 líneas: qué se ha hecho, cómo se ha verificado, coste aproximado y la siguiente tarea recomendada.
