---
name: medir
description: Mide el Copiloto sin gastar crédito. Calcula la precisión, la exhaustividad y los días de retraso de cada detector sobre los escenarios etiquetados, y la curva de aprendizaje de la personalización con usuarios simulados. Compara con la ejecución anterior. Úsala tras cambiar un detector, la política o un módulo, cada noche y antes de la demo.
argument-hint: "[motor | personalizacion | todo]"
---

# /medir $ARGUMENTS

1. Ejecuta `python evals/medir.py --parte <parte>` con la parte que indique `$ARGUMENTS` (si no indica ninguna, `todo`). El script lo crea `/esqueleto`; si aún no existe, dilo y para.
2. Resume en una tabla:
   - **Motor**: por detector, precisión, exhaustividad, días de retraso medios y falsos positivos en las trampas.
   - **Personalización**: con los usuarios simulados, avisos útiles, molestias evitadas y arrepentimiento en la semana 1 frente a la última.
3. Compara con la ejecución anterior de `evals/resultados/` y marca lo que empeora. Si algo empeora, di qué cambio lo explica (`git log -5`) y a quién va el arreglo: `ingeniero-deteccion` o `cientifico-personalizacion`.
4. Guarda el resultado con la fecha. Esas cifras son las que enseñan el panel del jurado y el pitch.

Respuesta: 15 líneas como mucho.
