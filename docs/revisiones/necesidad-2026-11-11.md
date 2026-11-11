# Revisión de necesidad: curva de amigos (I3, 11 nov, `critico-necesidad`)

**Fuentes:** `evals/resultados/amigos-final-2026-11-11.json` (git `41b30e7`, vidas `08e2e31a`), `amigos-2026-11-11.json`, `curva-amigos.svg`, `registro/ajuste-amigos.md` y los diarios de Álvaro, Diego, Carmen, Nerea y Pilar. También he recalculado los eventos con las semillas 100-119, con el mismo protocolo y un script fuera del repo. Lo marcado con **(propio)** no está en el JSON. Todo es **simulación**.

## Veredicto
- **Necesidad:** es real, pero aquí se ve poco. Sirve a quien adelanta pagos a un grupo estable y tiene algún amigo que «se olvida». Casi todo vuelve solo: sin Meisam se escaparían 47,7 € por usuario en 8 semanas y con Meisam se escapan 46,1 € **(propio)**. Molesta poco: 0,8 preguntas y 1 aviso por usuario en 8 semanas.
- **La curva** se sostiene solo en lo que dice su título:
  - el dinero no cambia;
  - las preguntas inútiles bajan 0,33 por usuario en 8 semanas (diferencia pareada, IC95 de −0,41 a −0,24 **(propio)**), y el 87 % de esa bajada es de Diego;
  - los recordatorios a destiempo bajan 8 puntos (IC95 de −15 a −2 **(propio)**).
- **Qué no se puede decir:** que recupera dinero, que en la semana 8 propone «¿Con Laura y Marcos?», que las preguntas inútiles bajan «a la mitad» ni que Diego pasa de 11,9 a 7,4.

## Hallazgos
**BLOQUEA (frases del pitch)**
1. **La cifra de Diego está duplicada.** El JSON da **5,95 → 3,70** (`por_vida.diego.preguntas_inutiles.total`); 11,9 → 7,4 es el doble.
2. **Las propuestas de los niveles 2 y 3 casi no aparecen:** una vez en 160 corridas de ajuste y tres en Nerea. El acierto de «0,0 %» es de n = 1. Se puede enseñar como función en la demo, nunca como resultado medido.
3. **No hay línea base sin Meisam.** Sin ella no se pueden citar euros recuperados. Los 282 € «recuperados» vuelven casi todos solos. Cambio: después de la congelación, una política `nada` en `medir_amigos`.

**IMPORTANTE**
4. **El diagnóstico del orquestador se confirma, con un matiz.** El 91 % de lo que se escapa no está en ningún caso:
   - el 70 % son pagos con caso abierto pero sin saber quién falta («nadie»), en planes esporádicos de 4 a 10 personas (el cumpleaños de Belén, el viaje a Granada, el torneo, las camisetas): ahí no hay costumbre que aprender;
   - el 30 % no deja ningún rastro.
   No está comprobado que la IA de dudas lo arreglara (en la simulación va apagada).
5. **Avisos que piden dinero a quien no lo debe.** En las 8 vidas, de las personas nombradas en los avisos, el 45 % no debía ese pago y el 16 % ya había pagado. Pasa igual con las dos políticas **(propio)**, y lo he comprobado en una muestra: no es un efecto de agrupar avisos.
   - Ejemplos: a Álvaro le propone pedir Bizum a Laura por las entradas de Halloween y por su propia cena de cumpleaños; a Pilar le llega un aviso al móvil para recordar a Concha, que le pagó en efectivo en la mesa.
   - **Esto sí haría desinstalar la app.** Cambio: no nombrar a nadie que el usuario no haya dicho o que no esté en el grupo aprendido, y medirlo.
6. **Casos duplicados para un mismo pago (uno del chat y otro del motor):** 21 con `personalizada` y 15 con `reglas`. Producen dos avisos el mismo día (Carmen, casa rural) y que se lo pida en persona dos veces (Álvaro, semilla 0). Cambio: el motor no abre caso si el pago ya tiene uno del usuario.
7. **Una frase promete algo que no cumple.** «Aquí sueles ir solo: no te pregunto» sale con evidencia ≥ 1,5, pero callar exige ≥ 2,5, y lo aprendido además decae. A Diego se lo dice en la semana 5 y le vuelve a preguntar en la 6 y en la 7. Cambio de una línea en `aprende_amigos._frase_sitio`: usar el mismo umbral o quitar «no te pregunto».
8. **La evaluación usa las mismas 8 vidas que el ajuste;** solo cambian las semillas. Además, la regla de ajuste se cambió a las 16:20 para optimizar las preguntas inútiles, que es justo lo que se enseña. En las dos vidas nuevas:
   - preguntas inútiles: de 0,80 a 0,83;
   - recordatorios a destiempo: del 40 % al 34 %, sin significación.
   Hay que decirlo.
9. **La gráfica engaña en detalles:**
   - las etiquetas de la semana 8 (0,11 → 0,06) sugieren «la mitad» con ruido;
   - pone «mejora» en casos cerrados solos (5,4 → 5,7) y en toques por 100 € (1,19 → 1,05), que están dentro del IC (el registro llama artefacto a esta segunda);
   - el eje de 0 a 0,25 por semana oculta que es menos de una pregunta por usuario en dos meses;
   - faltan Nerea y Pilar en cifras, y dos supuestos: el chat usa etiquetas (extracción perfecta) y la IA de dudas va apagada.
   Cambio: poner «igual» cuando los IC se solapan, cambiar las etiquetas por las del total, añadir la fila de evaluación y los dos supuestos.
10. **El chat no encuentra el cargo cuando nombras el plan.** Aun con extracción perfecta, 48 de 161 mensajes que debían crear un caso acaban en «no encuentro el cargo» cuando el usuario dice «las cañas» y el extracto pone `CERVECERIA EL TRANVIA` **(propio)**. Para la demo: una frase que nombre el comercio, y ensayarla.

**MENOR**
11. **Tono de las frases sobre amigos.** Son neutras, con nombre enmascarado, se editan y se borran. No he visto que salgan al banco (solo lo he buscado con grep).
    - «Suele redondear lo que te devuelve» puede leerse como «te da de menos»: mejor «suele devolverte cantidades redondas».
    - «Suele devolvértelo cuando se lo pides» es un hecho y vale, pero sin añadirle nada.
12. **Pilar, «100 % a destiempo»,** sale de un solo recordatorio (n = 1): no citarlo.

## Frases honestas para el pitch (simulación; `amigos-final-2026-11-11.json`)
1. «En una simulación con 8 vidas inventadas y 20 semillas que no usamos para ajustar, Meisam aprende a callar: las preguntas que sobraban bajan de 1,11 a 0,78 por usuario en 8 semanas, sobre todo con quien siempre come solo.»
2. «Aprende cuándo te paga cada amigo: los recordatorios que llegan antes de que el amigo pague por su cuenta bajan del 39 % al 31 %.»
3. «Donde aún no mejora: el dinero que se escapa sigue en el 19 %. Está en planes de grupo grandes y esporádicos, donde Meisam ve que falta alguien pero no sabe quién.»
4. «Con dos personas que no usamos para ajustar, una jubilada a la que pagan en efectivo y una estudiante que lo comparte todo con su pareja, no pregunta menos: el efectivo no deja rastro.»

**Deshonestas:**
- «Meisam recupera X €»;
- «en la semana 8 te propone con quién fuiste»;
- «la mitad de preguntas inútiles»;
- «Diego, de 11,9 a 7,4»;
- «mejora los casos cerrados solos y los toques por euro»;
- «resiste inyecciones» (en la curva el chat va por etiquetas);
- «probado con usuarios».

## Las 5 preguntas más duras
1. **¿Y frente a no tener Meisam?** Apenas cambia: 47,7 € frente a 46,1 € que se escapan por usuario en 8 semanas **(propio)**. Hoy su valor es no molestar; recuperar más depende de saber quién falta en los grupos grandes.
2. **¿Habéis ajustado sobre las mismas vidas?** Sí; solo las semillas son nuevas. En las dos vidas nuevas no pregunta menos.
3. **¿El −29 % es ruido?** No: la diferencia pareada es de −0,33 (IC95 de −0,41 a −0,24). Pero es un tercio de pregunta por usuario en dos meses, y casi todo de un solo perfil.
4. **¿Y si la gente no contesta?** Con la mitad de respuestas, las preguntas inútiles bajan de 1,11 a 0,81 y el dinero sigue igual. Sergio, que contesta el 8 %, no mejora en nada.
5. **¿No lo hace ya Splitwise, o Bizum más WhatsApp?** Esas opciones piden acordarse y apuntarlo; Meisam parte del cargo en tu cuenta. Pero en viajes y cumpleaños de 8 a 10 personas, que es donde se escapa el dinero, hoy no lo hace mejor. No se ha medido con usuarios reales.

> **Nota del orquestador (11 nov, tarde):** después de esta revisión entraron el cine con búsqueda web (K1 ocio) y la regla «una pregunta de un toque molesta una cuarta parte». La curva final se volvió a medir con el código congelado: recordatorios a destiempo 37,6 % → 30,6 % (antes 38,9 % → 31,3 %); preguntas inútiles 1,11 → 0,78 y dinero que se escapa 19,2 % → 19,1 % (dentro del IC). Para el pitch, usar estas cifras: `evals/resultados/amigos-final-2026-11-11.json` y `curva-amigos.svg`.
