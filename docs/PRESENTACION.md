# Meisam: qué funciona hoy y cómo presentarlo

Para leer antes de presentar. Solo lo que funciona hoy y está comprobado.

## 1. En una frase
**Meisam es un extra para apps de gastos compartidos (Splitwise, Tricount) que vive dentro de la app del banco: ve tus pagos y tus Bizums, te avisa en el momento justo y lo resuelve con un toque o hablando.**

## 2. El problema
Pagas por varios y el dinero no vuelve solo.
- Tienes que acordarte de quién te debe.
- Tienes que apuntarlo en Splitwise o Tricount (casi nadie lo hace a tiempo).
- Tienes que perseguir Bizums sin quedar de pesado.

Pagas tú, y además haces de administrador.

## 3. Qué añade a Splitwise o Tricount
En esas apps apuntas tú quién te debe. El banco ya sabe el resto: el pago con tarjeta y los Bizums que entran.
- **Te contacta él**, cuando pagaste por varios y no te han devuelto.
- Calcula cuánto, quién falta y lo cierra cuando llega el Bizum.
- Solo avisa si hay dinero en juego. Si no, calla.

## 4. Lo que funciona hoy (y cómo se ve)
| Bloque | En la demo |
|---|---|
| **Gastos compartidos.** Detecta Bizums que llegan, quién falta y cuánto. | Pizzas: «Falta Nacho, 13 €». |
| **Cine con búsqueda web real.** Solo el nombre del comercio sale a internet. Los precios vuelven como tabla; el código estima cuántos fuisteis. | Kinepolis, 32,70 €: «parecen 3 entradas». |
| **Preguntas de un toque.** «Sí, con…», «Iba solo», «Nadie me debe», «Otra respuesta». | La pregunta del cine. |
| **Pedir Bizum.** Botón y token de un solo uso. El caso se cierra solo cuando llega el pago. | «Pedir Bizum» a Nacho; al día siguiente, «Saldado». |
| **El Bizum que no cuadra.** Si llega un importe distinto, no insiste: te lo pregunta con un toque. | Resumen. |
| **Chat y voz con ElevenLabs.** Apuntar un gasto con tus palabras, consultar y cambiar casos, «recordar sobre mí». Todo con «Deshacer». | «La cena del viernes la pagué yo, era con Sergio». |
| **Resumen semanal.** Te deben, preguntas pendientes, quién pagó. | Pestaña Resumen. |
| **«Lo que he aprendido».** Se ve, se edita y se borra. | Pantalla Aprendido. |
| **Privacidad y seguridad.** Los datos van marcados como datos. Acciones de una lista cerrada. Nada se mueve sin tu botón. Sin puntuar a nadie y con frases neutras sobre los amigos. | Insignia «IA» visible. |

Otros momentos que ya están en el motor y **no salen en la demo**: prueba gratuita que se va a cobrar, cobro duplicado y recibo que sube.

**Cómo se comprobó**
- 1.519 tests de pytest, sin gasto de crédito. La demo de Pablo tiene tests propios (`tests/test_demo_pablo.py`: fechas, avisos, pedir Bizum y cierre, también por HTTP).
- Evals de la llamada: **35/35** (0,77 US$).
- Revisión de seguridad independiente: sin bloqueantes.
- Voz real probada el 11 nov.

## 5. Guion de la demo (Pablo, 3 minutos)
Escenario `demo-pablo` (`backend/escenarios/demo-pablo.yaml`). Activación el 1/11 con historial desde el 21/9. Pablo es estudiante en Madrid; datos inventados.

1. **Vie 6/11, cena en Taberna El Búho con Sergio (34,60 €).** Meisam no avisa: un viernes es señal débil. Pablo la apunta por el chat: «La cena del viernes en El Búho la pagué yo, era con Sergio». Sergio debe 17,30 €. Se ve «Apuntado…» con «Deshacer».
2. **Sáb 7/11, Kinepolis Ciudad de la Imagen (32,70 €).** El lunes 9/11 llega la notificación: «32,70 € en Kinepolis… parecen 3 entradas. ¿Fuiste con alguien?». Pablo contesta con un toque. Se dice: «El precio sale de la web real; solo el nombre del cine sale de aquí».
3. **Dom 8/11, Pizzería Mamma Rosa (52 € entre cuatro).** Rodrigo e Irene pagan 13 € cada uno esa noche. El martes 10/11 llega el aviso: falta Nacho (13 €). Pablo pulsa **Pedir Bizum**, confirma y al día siguiente (11/11) entra el Bizum de Nacho y el caso queda **«Saldado»**.
4. **El resto** (cafetería, súper, metro, farmacia, Primark) no activa nada. **Meisam calla cuando no hace falta.**

Frase de cierre de la demo: «Dos avisos en dos semanas. Los dos, con dinero en juego».

**Plan B**
- Si falla la voz: **el chat** (mismo agente, mismas herramientas).
- Si falla todo: **el vídeo de respaldo**, abierto en otra pestaña.
- El servidor gratuito de Render tarda **~1 minuto** si está dormido: **abrirlo antes de presentar**.
- La demo avanza el reloj simulado con la barra de días de `/app`; no hace falta esperar.

## 6. Cómo hemos trabajado con Claude
- **Un solo desarrollador (Pablo) con un orquestador y subagentes especializados** (detección, personalización, módulos, voz, banca, usuarios, tests, evals, revisión).
- **71 subagentes lanzados en 3 días** (`python scripts/informe_agentes.py`; detalle en `registro/agentes.jsonl`). Más usados: programador (15), ingeniero de detección (14) y personalización (10).
- **Revisión con el contexto limpio:** el `revisor` miró la seguridad (5 veces) y el `critico-necesidad` juzgó sin conocer nuestra historia. Sus hallazgos se arreglaron o se recortaron del pitch.
- **Tests y evals:** 1.519 tests y evals del agente (35/35 en la llamada).
- **Tiempo:** lo estimado en ~20 h tardó ~5 h reales (`docs/PLAN.md`, columna «h real»).
- **Regla de oro:** el código calcula y Claude razona. Los modelos nunca hacen cuentas.
- Compañeros: entrevistas, ideas, marca y pruebas de usuario (`docs/IDEAS.md`).

## 7. Hoja de ruta (honesta)
- **Planes grandes y cambiantes:** saber quién falta en cenas de 8-12 personas.
- **Lo que debes tú:** solicitudes de Bizum que te han hecho.
- **Deudas sin cargo en tu cuenta** (efectivo).
- **«¿Te debía algo?»** para un Bizum suelto.
- **Conexión real con Splitwise o Tricount** (hoy es una demo con el banco simulado).
- **Aprender de cada persona:** ya recoge lo que le dices y lo que ve; falta validarlo con usuarios reales.
- **Web Push real** (hoy las notificaciones son dentro de la app).

## 8. Preguntas del jurado
- **¿Es real el banco?** No. Banco, Bizum y reloj son simulados. Las acciones se validan en el servidor y quedan auditadas.
- **¿Y si el modelo se inventa una cifra?** No calcula: el código usa `Decimal`. La IA solo clasifica y explica.
- **¿Qué sale a internet?** Solo el nombre del comercio. Nunca importes ni datos del cliente.
- **¿Puede mover dinero solo?** No. Hace falta tu botón y un token de un solo uso.
- **¿Puntúa a tus amigos?** No. Frases neutras, solo para ti, y se pueden borrar.
- **¿Y si avisa mal?** Decide con los euros en juego y puedes decirle que no avise.
