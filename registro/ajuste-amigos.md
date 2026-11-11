# Bucle de ajuste de la curva de amigos (I2, 11 nov)

## Resumen

- **Vidas**: hash `08e2e31a0d7c5d8ed50128d9dad96dfa66320d81d63d322ed590b18cf34f0a3c` (fase ajuste, 8 vidas, semillas 0-9).
- **Medida**: `DATOS_USUARIO_DIR=$(mktemp -d) python evals/medir.py --parte amigos --semillas 0-9 --sin-sensibilidad
  --salida <tmp>`. Cifras del total de 8 semanas.
- **Regla** (encargo del orquestador, 11 nov 16:20): el cambio se queda si baja las preguntas inútiles o los
  recordatorios a destiempo sin empeorar el dinero que se escapa ni el otro indicador, y con los tests en verde.
- **Base del worktree**: `main` en `ab270da` (avance rápido desde `827c8cb` al empezar).
- **Se paró** tras 8 vueltas (16:48). Se quedan 3 cambios: V2, V3 y V8. V4 se quedó en el bucle, pero la batería
  completa del final mostró que retrasa un día el aviso de la demo de la cena (del 9 al 10 de noviembre): se
  deshizo (la demo no se toca).

| Política | Dinero que se escapa | Preguntas inútiles (usuario, 8 semanas) | Recordatorios a destiempo |
|---|---|---|---|
| reglas | 17,8 % | 1,12 | 37,4 % |
| personalizada, antes | 17,8 % | 1,31 | 32,4 % |
| **personalizada, después** | **17,8 %** | **0,86** | **32,4 %** |

En una frase: «lo que deduzco de un Bizum vale media visita, porque nunca veo cuándo vas solo; lo que me contestas a una
pregunta que sobraba vale más, y el tipo de sitio y franja pide más pruebas que el comercio».

Cada vida queda igual o por debajo de `reglas` en preguntas inútiles (antes, Carmen, Irene, Álvaro, Sergio, Hugo y
Javier estaban por encima). Diagnóstico aparte (script fuera del repo que registra cada decisión de la escalera, 8 vidas
x 10 semillas): preguntas mostradas 105 -> 69 (todas siguen siendo inútiles); las abiertas por lo aprendido
(`senal = "aprendida"`), 28 -> 0; silencios que habrían sido útiles, 4 -> 4 (los mismos de las reglas, `senal debil`).

Los recordatorios a destiempo se quedan como estaban (32,4 % frente a 37,4 % de `reglas`). Con `margen_dias = 2`
bajaban a 28,7 %, pero el aviso de la demo pasaba al día siguiente (ver la duda 9).

Otras medidas (personalizada): días hasta cobrar 1,42 = 1,42; casos cerrados solos 3,2 % = 3,2 %; recuperado 291,84 € =
291,84 €; toques 3,73 -> 3,71. `toques_por_100_eur` sube de 0,87 a 1,06, pero es un artefacto de la media de razones
por corrida (los toques bajan y lo recuperado no cambia). El acierto de la sugerencia pasa de 0 % a «sin datos»: en
estas 8 vidas ya no se muestra ninguna sugerencia de nivel 2 o 3.

### Dudas anotadas (no se preguntó nada)

1. **Alcance**: V2, V3 y V8 no son solo valores: añaden `peso_bizum`, `peso_inutil` y `min_evidencia_motor_tipo` a
   `PARAMETROS` y unas pocas líneas en `aprende_amigos.py` que los usan (`_peso_inutil`, `peso` en `_sumar_grupo`, el
   umbral por tipo en `compania_para_motor`). Lo tomé como permitido por las ideas del encargo («que una pregunta
   inútil pese más», «exigir más evidencia por tipo de sitio y franja»). Si no, se deshacen sin tocar el resto.
2. **Cruce con A3b** (otro agente, `grupos_para_motor`): con `peso_bizum` un ámbito aprendido solo de Bizums tiene
   `con_alguien` a la mitad, pero `GrupoHabitual.veces` entero. Si `grupos_para_motor` calcula la frecuencia como
   `veces / con_alguien`, puede pasar de 1 (habría que recortarla a 1). Y si exige `min_evidencia_motor` sobre
   `evidencia_de`, los ámbitos solo de Bizums tardan el doble en entrar. Hay que volver a medir el dinero que se
   escapa después de integrar las dos ramas.
3. **La curva para el jurado**: con 0 preguntas abiertas por lo aprendido en estas vidas, el acierto de la sugerencia
   se queda sin datos. Si el pitch necesita enseñar sugerencias aceptadas, hay que mirarlo en las vidas de
   evaluación (semillas 100-119), que aquí no se han corrido para no ajustar sobre ellas.
4. **Ya existía, no lo toqué**: la frase «Aquí sueles ir solo: no te pregunto» sale con evidencia >= 1,5
   (`min_evidencia_frase`), pero la escalera solo calla con >= 2,5. La frase puede decir «no te pregunto» cuando aún
   pregunta.
5. **Ya existía, no lo toqué**: un Bizum que llega pone `ignoradas = 0` en el ámbito, como si fuera una respuesta.
6. **pytest por vuelta**: el subconjunto de amigos (13 archivos, ~35 s), porque la batería completa tarda ~3,5 min.
   La completa se pasó al principio y al final.
7. **Gasto**: el subagente no tiene `/cost`. Fueron 8 corridas de `medir` y 4 diagnósticos en local, sin crédito de
   Claude.
8. **Texto de las preguntas**: no lo toqué. No cambia ninguna de las tres medidas.
9. **Recordatorios a destiempo**: `margen_dias = 2` los bajaba de 32,4 % a 28,7 % sin empeorar nada en las vidas,
   pero retrasa un día el aviso de la cena de la demo (`test_api_copiloto` y `test_casos`, `cena-lucia`). Si Pablo
   prefiere la mejora, hay que mover la demo y sus tests, y eso es decisión suya. Mientras, `margen_dias = 1`.

## Línea base (ab270da)

| Política | Dinero que se escapa | Preguntas inútiles | Recordatorios a destiempo |
|---|---|---|---|
| reglas | 17,8 % | 1,12 | 37,4 % |
| personalizada | 17,8 % | 1,31 | 32,4 % |

Diagnóstico: 105 preguntas y las 105 inútiles. 28 las abre lo aprendido y acaban en «nadie debe» o «iba solo»; salen de
ámbitos con 2-3 Bizums vistos y ninguna respuesta del usuario (evidencia 1,5-2,5). Las otras 77 las abren las reglas
(`media`, restaurantes): son la primera visita a cada sitio o sitios con 1-2 «iba solo» (evidencia < 2,5).

## Vueltas

Cifras de `personalizada`, total de 8 semanas: dinero que se escapa / preguntas inútiles / recordatorios a destiempo.
`reglas` no cambia en ninguna vuelta: 17,8 % / 1,12 / 37,4 %.
Las vueltas 5-8 se midieron con V4 dentro; el estado final (sin V4) se midió aparte, al final.

| # | Hipótesis y cambio | Antes | Después | ¿Se queda? |
|---|---|---|---|---|
| 1 | Pedir ~3 observaciones para que lo aprendido abra preguntas: `min_evidencia_motor` 1,5 -> 2,5 | 17,8 / 1,31 / 32,4 | 17,8 / 1,16 / 32,4 | **No**: rompe `test_escalera::test_usuario_simulado_aprende_y_molesta_menos` (deudas que se escapan en su simulador: 74 frente a un máximo de 68). Subir el umbral a todo quita también lo aprendido del botón y de las respuestas, que sí recupera dinero |
| 2 | Lo sesgado son los Bizums (el banco ve la compañía, nunca los «solo»): un Bizum cuenta como media visita acompañado, y el grupo entero (`peso_bizum = 0,5`) | 17,8 / 1,31 / 32,4 | 17,8 / 1,04 / 32,4 | **Sí**. Carmen 1,2 -> 0,1; Irene 0,5 -> 0,1; Sergio 0,4 -> 0; Hugo 0,2 -> 0. Test de Bizums ajustado a `peso_bizum` |
| 3 | Una pregunta que acaba en «iba solo» o «nadie me debe» era la que sobraba: pesa 1,5 (`peso_inutil`; solo respuestas a una pregunta, con `nivel`) | 17,8 / 1,04 / 32,4 | 17,8 / 0,91 / 32,4 | **Sí**. Diego 4,7 -> 3,9; Marta 1,2 -> 1,0. «Dos aún no bastan» sigue valiendo sin pregunta |
| 4 | Recordar dos días después del retraso típico, no uno (`margen_dias` 1 -> 2) | 17,8 / 0,91 / 32,4 | 17,8 / 0,91 / 28,7 | **Sí en el bucle; deshecho al final**: Álvaro 30 % -> 8 % y Sergio 21 % -> 13 %, pero la batería completa mostró que el aviso de la demo de la cena pasa del 9 al 10 (3 tests). Los dos tests de `margen_dias` quedan leyendo el parámetro |
| 5 | Con una sola devolución propia ya se usa su retraso (`min_obs_persona` 2 -> 1) | 17,8 / 0,91 / 28,7 | 17,8 / 0,91 / 27,9 | **No** (decisión propia): el mismo parámetro rebaja a una observación las frases de «lo que he aprendido» («suele redondear», «suele pagar cuando se lo pides»), y la mejora es pequeña (0,8 puntos, solo Irene) |
| 6 | Callar antes donde vas solo: `p_solo_max` 0,25 -> 0,30 y `min_evidencia_silencio` 2,5 -> 2,1 | 17,8 / 0,91 / 28,7 | 17,8 / 0,86 / 28,7 | **No**: rompe el mismo test de la escalera (inútiles de las semanas 7-8: 46 frente a un máximo de 23; antes, 8). Callar con poca evidencia hace que, al decaer, se vuelva a preguntar al final. Aislado: el culpable es 2,1 |
| 7 | Tres días de margen (`margen_dias` 2 -> 3) | 17,8 / 0,91 / 28,7 | 17,8 / 0,93 / 26,5 | **No**: empeora las preguntas inútiles (0,91 -> 0,93) |
| 8 | El tipo de sitio y franja mezcla planes: pedirle ~3 observaciones para que abra el motor y dejar ~2 al comercio (`min_evidencia_motor_tipo = 2,5`) | 17,8 / 0,91 / 28,7 | 17,8 / 0,86 / 28,7 | **Sí**. Álvaro 0,3 -> 0; Javier 1,9 -> 1,8. El test de la escalera usa el comercio y no cambia |

## Archivos tocados

- `backend/personalizacion/aprende_amigos.py`: `PARAMETROS` (`peso_bizum`, `peso_inutil`, `min_evidencia_motor_tipo`;
  `margen_dias` sigue en 1, con la razón en el comentario); `_peso_inutil`, `peso` en `_sumar_grupo` y
  `_aprender_ambito`; umbral por tipo en `compania_para_motor`.
- `tests/test_aprende_amigos.py`: 3 tests nuevos (pesos y umbral por tipo) y `margen_dias` leído de `PARAMETROS`.
- `tests/test_observar_bizums.py`: `con_alguien == peso_bizum` y grupo entero.
- `tests/test_portero_escalera.py`: el día del recordatorio sale de `margen_dias`.
- `docs/diseno/curva-amigos.md` §4.1: párrafo «Pesos (ajuste I2)».

Sin tocar: motor, `casos/`, orquestador, vidas, corpus, U3, importes, `acciones/`, tokens, `datos_usuario/`, `.env` ni
`demo-lucia`. Nada por nombre de vida ni de comercio.

## Verificación final

- `pytest -q` completo en el estado final: verde (sin fallos). Con V4 dentro fallaban 3 tests de la demo de la cena.
- `medir --parte amigos --semillas 0-9 --sin-sensibilidad` (estado final, sin V4): 17,8 % / 0,86 / 32,4 % (`reglas`:
  17,8 % / 1,12 / 37,4 %).
