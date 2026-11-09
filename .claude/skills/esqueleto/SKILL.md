---
name: esqueleto
description: Monta el esqueleto del Copiloto de principio a fin según el contrato. Incluye los tipos, los paquetes con sus interfaces, un escenario etiquetado que recorre todo el sistema, la medición y tests en verde. Úsala justo después de /planificar.
disable-model-invocation: true
---

# /esqueleto

Objetivo: que un escenario sintético recorra todo el sistema con un solo detector y un solo módulo: movimiento → momento → propuesta → decisión → notificación → acción simulada → feedback → aprendizaje. Después, cada zona tiene que poder crecer en paralelo sin tocar las demás.

## 1. El contrato en código (`programador`, o tú si es poco)
- `backend/plataforma/tipos.py`: los modelos de pydantic de `docs/diseno/CONTRATO.md`, con el dinero en `Decimal`.
- `backend/plataforma/reloj.py`: el reloj simulado.
- Almacenamiento con la biblioteca estándar en `datos_usuario/` (fuera de git).
- Tests de los tipos. Commit antes de seguir: es lo que comparten todas las zonas.

## 2. Zonas en paralelo
Usa la plantilla de encargo de `/feature`, con la interfaz exacta del contrato. Cada zona en su worktree (`claude --worktree <zona>`) o como subagente si no comparten archivos.

| Zona | Subagente | Mínimo del esqueleto |
|---|---|---|
| `backend/motor/` y `backend/escenarios/` | `ingeniero-deteccion` | Normalización, el detector `cargo_duplicado` en línea, el formato de escenario y un escenario etiquetado con un caso trampa |
| `backend/personalizacion/` | `cientifico-personalizacion` | `ModeloUsuario` persistente, `decidir()` y `aprender()` con la política v1, y un usuario simulado |
| `backend/modulos/` y `backend/acciones/` | `ingeniero-modulos` | Cargador y validación del YAML, el módulo `cargo_duplicado`, el registro cerrado de acciones y el banco simulado con 2 acciones |
| `backend/voz/` | `ingeniero-voz` | Interfaz de la llamada con modo texto y un falso de ElevenLabs para los tests |

## 3. Unir (`programador`)
- `backend/plataforma/orquestador.py` con `avanzar_dia()`.
- Endpoints mínimos en `backend/api/main.py`: avanzar el reloj, listar notificaciones, enviar feedback y confirmar una acción.
- `evals/medir.py`: precisión, exhaustividad y días de retraso por detector sobre los escenarios, y curva de aprendizaje con usuarios simulados. Guarda el resultado en `evals/resultados/`.
- Test de principio a fin con el escenario del paso 2.

## 4. Pantalla mínima (`frontend`)
La app del banco ficticio con la bandeja de notificaciones y un botón para avanzar un día. `npm run build` en verde.

## 5. Verificar y cerrar
- `pytest -q` en verde. Arranca `uvicorn backend.api.main:app --reload` y prueba el flujo completo a mano.
- `/medir` como línea base.
- `revisor` sobre el diff.
- Puerta **esqueleto vivo**: anótala en `docs/PLAN.md`.
- Commit: `esqueleto: flujo de principio a fin`.
