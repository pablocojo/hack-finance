---
name: detector
description: Crea o mejora un detector del motor (un tipo de momento) guiado por escenarios etiquetados. Primero el escenario y el test que falla, después el algoritmo con umbrales personalizables y por último la medición antes y después. Úsala para cada tipo de momento nuevo o cuando un detector falle.
argument-hint: "<tipo de momento, por ejemplo gasto_compartido>"
disable-model-invocation: true
---

# /detector $ARGUMENTS

## 1. Diseño (5 minutos)
- Lee el apartado del detector en `docs/diseno/motor.md` y los `datos` mínimos del tipo en `docs/diseno/CONTRATO.md`.
- Si el tipo es nuevo, propón sus `datos` y añádelos al contrato antes de programar (es lo que leen los módulos).
- Decide qué parte es determinista y qué parte, si alguna, necesita Haiku 5.5 (por ejemplo, entender la nota de un Bizum).

## 2. Escenarios primero
Con `/escenario`: al menos un caso que debe detectarse, uno límite y una trampa. Los tests deben fallar antes de implementar.

## 3. Implementación (`ingeniero-deteccion`)
- En `backend/motor/detectores/<tipo>.py`, siguiendo la interfaz del motor.
- En línea: solo ve el pasado. Parámetros con nombre que se personalizan con la línea base del usuario.
- Cada momento lleva sus evidencias (ids), su confianza y una explicación de una frase hecha con plantilla.
- Si llama a Haiku: `claude_client` con salida JSON, caché por concepto y coste sumado. Nunca para calcular importes.

## 4. Medir y validar
- `pytest -q` en verde.
- `/medir motor`: precisión, exhaustividad y días de retraso del detector, antes y después.
- `experto-banca` si el detector interpreta algo bancario (recibos, Bizum o devoluciones).

## 5. Cerrar
- Actualiza `docs/diseno/motor.md` si cambia el algoritmo o los parámetros.
- Commit: `feat: detector <tipo>`.
- Si ningún módulo escucha este tipo de momento, propón crear uno con `/modulo`.
