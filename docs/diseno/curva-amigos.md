# Encargo: curva de aprendizaje de los gastos con amigos

**Para:** `arquitecto`; después, el orquestador. **De:** Pablo, 11 nov, 14:00.

**Límites:**
- trabajo sin supervisión hasta las **17:00**;
- congelación a las **19:00**;
- tope de gasto de la tanda: **100 €** (al llegar a 80 €, se para y se avisa).

## 1. Qué queremos poder enseñar

El jurado tiene que ver, con una simulación que cualquiera puede repetir, que **Meisam aprende de cada persona** y que eso resuelve un problema real: no tener que estar pendiente de quién te debe dinero.

- **Semana 1.** Meisam sabe poco. Pregunta lo básico en el resumen («Pagaste 48 € en La Tasca el sábado. ¿Fuiste con alguien?») y recuerda a todos con el mismo plazo.
- **Semana 8.** Pregunta menos y mejor:
  - calla donde siempre vas solo;
  - propone en un toque a quienes suelen ir contigo («¿Con Laura y Marcos, 16 € cada uno?»);
  - recuerda a cada amigo cuando toca («Rodrigo suele devolvértelo a los 2 o 3 días: te lo recuerdo el jueves»).
- **Chat sin aviso.** El usuario escribe «las pizzas de ayer las pagué yo, eran con Marcos y Rodrigo». Meisam crea el caso, lo vigila y aprende de esa frase.

La curva compara a Meisam aprendiendo con las reglas de hoy (sin aprender):
- durante 8 semanas;
- con usuarios independientes;
- con la misma suerte para todos.

También enseña dónde **no** mejora.

## 2. Decisiones de Pablo para este encargo (11 nov)

1. **Hechos por persona, dichos tal cual.** Meisam aprende y enseña cosas de cada amigo: «Rodrigo suele tardar 2 o 3 días», «Pilar suele pagarte en efectivo». **Cambia la decisión del 9 nov** («sin hechos que valoren a terceros»). Registradlo en `DECISIONES.md` con estas salvaguardas:
   - frases neutras y de hechos («suele devolvértelo a los 2 o 3 días»), nunca juicios («es moroso», «no es de fiar»);
   - solo sirven para los recordatorios del propio usuario: no salen de él, no van al banco ni a otros módulos y nunca son una puntuación;
   - se ven, se editan y se borran en «Lo que he aprendido», y desaparecen al borrar el contacto;
   - `critico-necesidad` revisa el tono.
2. **El chat solo crea casos sobre pagos que están en la cuenta.** Las deudas sin cargo («le pagué en efectivo la Coca-Cola») van a la hoja de ruta. Que el amigo te devuelva el dinero en efectivo sí entra: ya existe `marcar_saldado` con la vía `efectivo`, y se aprende por persona.
3. **Presupuesto: 100 €** para toda la tanda (construcción, chat y ajuste). Al llegar a 80 €, se para y se avisa.
4. **La curva va en la presentación.** Un script genera la gráfica a partir del JSON de `/medir`. No se toca la app para esto.
5. **Usuarios independientes.** Cada vida tiene sus propios amigos: no hay contactos compartidos ni aprendizaje entre usuarios, y todos empiezan desde cero con los mismos valores por defecto. La mayoría son estudiantes universitarios, con algunos perfiles distintos.
6. **Dos agentes nuevos.** Quien ajusta el aprendizaje nunca escribe las vidas.
   - `experto-usuarios`: realismo de las vidas y de la personalización; escribe las vidas ocultas y el corpus del chat.
   - `critico-necesidad`: juicio independiente, con el contexto limpio, sobre la necesidad real, las molestias y la honestidad de las cifras.

## 3. Qué hay ya (no rehacer)

- **U3** (`backend/personalizacion/simulacion/`: `perfiles.py`, `protocolo.py`, `generador.py`, `vidas.py`; medida en `evals/medir_personalizacion.py`).
  - Es una curva genérica sobre **propuestas inventadas** de todos los módulos: 4 usuarios, 5 políticas, 13 de 15 criterios. No pasa por el motor ni por los casos.
  - **Se queda como está.** Reutilizad sus ideas: la verdad oculta aislada (`verificar_aislamiento`), el azar sorteado antes y común a todas las políticas, y las semillas fijas.
- **Escenarios de deuda**:
  - `pago_individual`: señal de lugar y día con reglas fijas en `motor/parametros.py::PagoIndividual`; nunca hace push.
  - `gasto_compartido`: `motor/reparto.py` (múltiplos, redondeos y dudosos), con fase 2 en `motor/dudas.py` (`DUDAS_IA`).
  - `pago_por_otro`: avisa a los 2 días fijos sin Bizum.
  - `gasto_fijo_compartido`.
- **Paquete `casos/`**: ciclo de vida, cierre por Bizum, transiciones, `llamada.py` (7 acciones) y `resumir.py` (post-llamada).
- **Crear un caso desde un movimiento**: `orquestador.crear_caso_usuario` (`POST /usuarios/{id}/casos`). Hoy solo lo usa el botón de la app.
- **Personalización**:
  - Beta-Bernoulli jerárquica (`politica.py`, `aprendizaje.py`);
  - perfil de vida con `Grupo.retraso_p75_dias` (`perfil.py`);
  - contactos y agenda (`personalizacion/amigos.py`);
  - «Lo que he aprendido» (`edicion.py`, `memoria.py`).
- **«Hablar con Meisam» sin aviso**: `voz/contexto.py` y `voz/texto.py`; herramientas en `voz/herramientas_llamada.py` y `voz/consultas.py`. Puede consultar y cambiar casos, pero **no crearlos**.
- **Hueco anotado el 10 nov**: la respuesta a la pregunta de un caso dudoso no resolvía la duda (`hechos["pregunta"].estado`). Comprobad si `responder_duda` lo cerró: la simulación depende de que las respuestas cuenten.

## 4. Qué hay que construir

### 4.1 Lo que aprende Meisam de cada usuario (el corazón)

Cómo se hace:
- todo con funciones puras, como `aprender`;
- el estado vive en `ModeloUsuario` (los cambios de tipos van primero en `tipos.py` y `CONTRATO.md`);
- todo es visible en «Lo que he aprendido».

Fuentes: respuestas a las preguntas, casos creados (con el botón o el chat), Bizums que llegan y casos cerrados.

| Qué aprende | Ejemplo | Para qué lo usa |
|---|---|---|
| Dónde y cuándo vas acompañado | Por comercio, y por tipo de sitio y franja: «en la cafetería de la uni, siempre solo» | Decidir entre callar, preguntar en el resumen o avisar |
| Con quién | Grupo habitual por sitio y día: «sábados en La Tasca: Laura y Marcos» | Rellenar la pregunta y el reparto |
| Cómo repartís | Partes iguales, cada uno lo suyo o redondeo, por grupo | Proponer importes e interpretar Bizums redondeados |
| Cuándo recordar a cada persona | Retraso típico (p75, con al menos 2 observaciones; antes, el del grupo o el general) | `avisar_desde` de cada deudor: no recordar antes de que pague por su cuenta |
| Cómo te paga cada persona | «Pilar suele pagarte en efectivo» | Que el recordatorio ofrezca primero «ya me lo dio» |
| Cuánto molestar | Tope semanal y agrupar avisos en un resumen (el portero ya lo hace) | Menos avisos sueltos |

**Pesos (ajuste I2, 11 nov; detalle en `registro/ajuste-amigos.md`).** No todas las observaciones valen lo mismo:
- un Bizum que llega cuenta como media visita acompañado (`peso_bizum = 0,5`), porque el banco ve cuándo vas con gente y nunca cuándo vas solo; para el grupo (quién fue) cuenta entero;
- «iba solo» o «nadie me debe» al contestar una pregunta pesa 1,5 (`peso_inutil`): con dos así en un sitio, Meisam deja de preguntar ahí;
- el tipo de sitio y franja (que mezcla planes) necesita ~3 observaciones recientes para que lo aprendido abra preguntas (`min_evidencia_motor_tipo = 2,5`); el comercio, ~2.

**Escalera de la pregunta.** Sube con la confianza aprendida y baja con «iba solo» o cuando se ignora.

| Nivel | Qué hace | Cuándo |
|---|---|---|
| 0 | Silencio | Sitio donde casi siempre vas solo |
| 1 | Resumen genérico: «¿Fuiste con alguien?» | Lo de hoy |
| 2 | Resumen con sugerencia: «¿Con Laura y Marcos?» → [Sí] [Otros] [Iba solo] | Confianza media |
| 3 | Notificación de un toque: «48 € en La Tasca: ¿con Laura y Marcos, 16 € cada uno?» | Confianza alta e importe relevante |
| 4 | *Si sobra tiempo*: el caso se abre solo y solo avisa si alguien no paga a tiempo | Rutina confirmada 3 veces o más que el usuario acepta («a partir de ahora, ábrelo tú») |

- El nivel 3 **cambia la regla «`pago_individual` nunca hace push»**: registradlo en `DECISIONES.md`.
- El nivel 4 es el «escenario personalizado» que `deudas-casos.md` dejaba en la hoja de ruta.

Las reglas de siempre siguen mandando:
- ante la duda, silencio;
- el código pone las cifras;
- el dinero solo se mueve con el botón;
- la IA solo redacta y resuelve dudas.

### 4.2 Crear casos desde el chat (producto real)

- **Herramienta nueva** (por ejemplo, `apuntar_gasto`) en `voz/herramientas_llamada.py`:
  - vale para la conversación sin aviso y para la llamada, en ElevenLabs y en el plan B de texto;
  - parámetros: pista del pago (comercio o descripción, que es dato), fecha aproximada, importe total si lo dice el usuario, y personas con importe opcional.
- **El backend busca el cargo por código** (fecha ± 3 días, comercio e importe):
  - si no lo encuentra, lo dice;
  - si hay varios, devuelve los candidatos enmascarados para que el usuario elija;
  - si hay uno, llama a `crear_caso_usuario`, que convierte el `pago_individual` si ya existe.
- **Reparto e importes**:
  - a partes iguales con el usuario incluido, salvo que diga otra cosa;
  - importes con `Decimal`, entre 0,50 € y 1.000 €, sin pasar del pago;
  - con «Deshacer», como `actualizar_caso`;
  - nunca mueve dinero.
- **Frases que enseñan sin crear un caso** («los jueves ceno con los del piso», «Rodrigo me lo paga en efectivo»): se guardan como hechos aprendidos con origen `chat`, de una lista cerrada de tipos, visibles y borrables. *Prioridad menor dentro de este hilo.*
- **Deuda sin cargo** («le pagué en efectivo»): Meisam responde que aún no se puede (hoja de ruta) y no crea nada.
- **Evals nuevas** en `evals/casos_llamada.yaml`:
  - caso bien creado;
  - dos cargos candidatos;
  - persona nueva;
  - importe imposible;
  - inyección en el comercio;
  - deuda en efectivo;
  - «ya me lo pagó».
- **A mano (Pablo)**: dar de alta la herramienta en el panel de ElevenLabs con el texto que deje `ingeniero-voz` en `experiencia.md` §6.7.

### 4.3 Simulador de vidas con amigos

- **Dónde va.** Paquete nuevo `backend/personalizacion/simulacion/amigos/`, sin tocar U3, y `evals/medir_amigos.py`, enganchado como `python evals/medir.py --parte amigos`.
- **Vidas ocultas en YAML** (`.../amigos/vidas/*.yaml`). Las escribe `experto-usuarios`, con rangos y fuentes. Cada vida lleva:
  - lo visible: ingresos (beca, paga o sueldo), día de cobro y comercios habituales;
  - planes recurrentes: día, franja, probabilidad semanal, sitios, grupo, quién paga, cómo se reparte e importe por persona;
  - planes esporádicos (cumpleaños, cena de clase, viaje), gastos en solitario y cambios de rutina (exámenes, puentes);
  - amigos propios con rasgos: retraso, canal (Bizum, efectivo o transferencia), si redondea, si paga por dos y si se olvida hasta que se lo piden. Sus claves usan el formato del alias de Bizum (`LAURA M`);
  - cómo trata a Meisam: si contesta y cuánto tarda, si usa el chat, cuántos avisos tolera, a quién no quiere que se recuerde y qué hace si alguien no paga;
  - grado de rutina, de 0 a 1.
- **El generador** convierte cada vida en movimientos, día a día:
  - tus pagos con tarjeta;
  - los Bizums que te llegan;
  - los que envías tú cuando paga otro (ruido realista);
  - el gasto de fondo (súper, metro, suscripciones);
  - nada cuando se paga en efectivo;
  - y los mensajes del chat, sacados del corpus.
- **Pasa por el sistema real**, con el reloj simulado: motor, casos, portero, personalización y las acciones del caso (responder, iba solo, con personas, pedir Bizum confirmado). Sin mirar el futuro.
  - El usuario simulado reacciona según su verdad oculta, con ruido. El amigo paga tras una solicitud según sus rasgos.
  - Usad `DATOS_USUARIO_DIR` temporal, sin web y con `DUDAS_IA=off` en el bucle. Si da tiempo, una pasada final con la IA activada, grabada.
  - Objetivo: una ejecución completa en **menos de 2 minutos**. Si con el orquestador y el disco no llega, usad las mismas funciones puras que llama el orquestador, sin duplicarlas.
- **Corpus del chat** (`evals/datos/chat_amigos.yaml`):
  - lo escribe `experto-usuarios`, con el estilo de cada persona y su etiqueta (cargo, personas e importes), más ruido y alguna inyección;
  - la extracción con Haiku, con el mismo esquema que la herramienta, se ejecuta **una vez** y se graba; el bucle la reproduce gratis;
  - la precisión de la extracción se informa aparte;
  - si no da tiempo, se usan las etiquetas y se dice.
- **Políticas**, sobre las mismas vidas y la misma suerte:
  - `reglas`: lo de hoy, sin aprender;
  - `personalizada`;
  - `personalizada_sin_chat`: para medir lo que aporta el chat;
  - `oraculo` (opcional): el techo, con la verdad oculta.
- **Duración y semillas**: 8 semanas; semillas 0-9 para ajustar y 100-119 para la curva final.

**Reparto inicial de vidas.** Son inventadas y viven en Madrid; `experto-usuarios` lo ajusta.

| Vida | Quién es | Lo que pone a prueba | Rutina |
|---|---|---|---|
| Álvaro, 20 | 2.º de Informática, comparte piso con 3 | Jueves de pizzas en el piso (paga él) y sábados con los mismos; Rodrigo tarda 2 o 3 días | Muy fija |
| Irene, 21 | Erasmus en Madrid | Grupos y sitios que cambian, redondeos y mucho chat | Caótica |
| Hugo, 19 | 1.º de ADE, juega al fútbol sala | Cena de equipo de 8 a 12 personas tras el partido; cuota mensual (gasto fijo) | Fija |
| Marta, 22 | 4.º de Periodismo, camarera los fines de semana | «Cada uno lo suyo» muy a menudo (aprender a callar) y una amiga que paga en efectivo | Media |
| Diego, 20 | 3.º de Ingeniería, vive con sus padres | Come solo en la cafetería casi a diario (el valor está en no preguntar) | Fija, en solitario |
| Sergio, 21 | 2.º de Derecho | Casi nunca contesta ni usa el chat (el límite honesto) | Media |
| Carmen, 29 | Consultora en su primer trabajo | Comidas de trabajo que le devuelven por transferencia, cumpleaños grandes y escapadas | Media |
| Javier, 44 | Padre | Cenas con otras familias y cuotas del equipo de su hijo | Fija |
| **Nerea, 23** *(solo evaluación)* | Estudiante de máster; comparte casi todo con su pareja | No recordar nunca a la pareja y sí al resto | Fija |
| **Pilar, 66** *(solo evaluación)* | Jubilada | Comida mensual con amigas que le devuelven en efectivo | Muy fija |

Nerea y Pilar no se usan para ajustar: solo salen en la curva final, por separado.

### 4.4 Medidas

Por usuario y semana, con la media y el intervalo sobre las semillas, y desglosadas por grado de rutina y por uso del chat.

| Medida | Qué cuenta | Debe |
|---|---|---|
| **Dinero que se escapa** (la estrella) | € que te debían y que a los 21 días ni han vuelto ni están reclamados, sobre el total prestado | Bajar |
| Preguntas por semana, y cuántas inútiles | Preguntas en total, y las que acaban en «iba solo», «ya me pagaron» o persona equivocada | Bajar |
| Acierto de la sugerencia | % de propuestas de los niveles 2 y 3 aceptadas sin cambios | Subir |
| Casos cerrados solos | % cerrados por un Bizum sin ningún toque del usuario | Subir |
| Recordatorios a destiempo | % que llegan antes de cuando el amigo habría pagado por su cuenta (la verdad oculta lo sabe) | Bajar |
| Toques por euro recuperado | Esfuerzo del usuario | Bajar |
| Días hasta cobrar | Mediana | Bajar |

**Objetivos orientativos**: `personalizada` en la semana 8 frente a `reglas`, con las semillas de evaluación.

| Medida | Objetivo |
|---|---|
| Dinero que se escapa | La mitad o menos |
| Preguntas inútiles | −50 % |
| Acierto de la sugerencia, en las vidas de rutina fija | ≥ 70 % |
| Recordatorios a destiempo | −50 % |

Se informa el valor real aunque no se llegue.

Además:
- `pytest` en verde;
- `/medir motor` y `/medir personalizacion` sin regresiones;
- la demo de Lucía (`demo-lucia`), intacta;
- `decidir`, igual de rápido.

### 4.5 Honestidad: que la curva aguante las preguntas del jurado

- **Las vidas las escribe `experto-usuarios` y se congelan con un commit antes de ajustar.** El hash va en el registro. Quien ajusta no las toca; si hay un error claro, se corrige, se dice y se vuelve a medir la línea base.
- **La política nunca importa el simulador**: se comprueba con un test como `verificar_aislamiento`. No hay parámetros por nombre de vida ni de comercio concreto, solo reglas generales.
- **Ajuste y evaluación van separados.** Se ajusta con las semillas 0-9 y las 8 vidas de ajuste. La curva final usa las semillas 100-119 e incluye a Nerea y Pilar por separado.
- **El informe dice «simulación»**, lista los supuestos y enseña dónde no mejora: Sergio, el efectivo que nadie declara y las rutinas caóticas.
- **`critico-necesidad`**, con el contexto limpio, revisa la curva, el diario y las frases antes de darlas por buenas.

### 4.6 Bucle de ajuste sin supervisión (hasta las 17:00)

- **Dónde**: en su propia rama o worktree (`ajuste-amigos`), para que `main` siga lista para la demo.
- **Cada vuelta**:
  1. hipótesis;
  2. un cambio pequeño;
  3. `pytest`;
  4. `python evals/medir.py --parte amigos` con las semillas de ajuste.

  El cambio se queda si baja el dinero que se escapa sin empeorar las preguntas inútiles ni los recordatorios a destiempo. Si no, se deshace.
- **Registro**: cada vuelta se anota en `registro/ajuste-amigos.md`, con el cambio, las cifras de antes y después y el gasto acumulado (`/cost` o `/usage`).
- **Se puede tocar**:
  - los priors y la velocidad de aprendizaje;
  - los umbrales de la escalera;
  - el margen de `avisar_desde` por persona;
  - el decaimiento de lo aprendido;
  - el texto de las preguntas.
- **No se toca**:
  - importes, cuotas, `acciones/` ni tokens;
  - las vidas ni el corpus;
  - U3 ni sus criterios;
  - `datos_usuario/` de Pablo (usad `DATOS_USUARIO_DIR` temporal);
  - `.env`;
  - `demo-lucia`.
- **Cuándo para**: a las 17:00, al llegar a 80 € o tras 3 vueltas seguidas sin mejora. Al parar, deja un resumen arriba del registro.
- **Dudas**: no se pregunta nada salvo algo irreversible. Las dudas se apuntan en el registro y se sigue con otra cosa.

## 5. Orden y calendario (lo ajusta el arquitecto)

| Hora | Qué | Quién |
|---|---|---|
| 14:15-14:45 | Tareas en `PLAN.md`, tipos nuevos en `tipos.py` y `CONTRATO.md`, y decisiones en `DECISIONES.md` | `arquitecto` y sesión principal |
| 14:45-16:15 | **H1**: vidas y corpus; simulador y medidas | `experto-usuarios` (primero las vidas), `cientifico-personalizacion` y `programador` |
| 14:45-16:15 | **H2**: aprendizaje y escalera, con sus usos en motor, casos y portero | `cientifico-personalizacion` e `ingeniero-deteccion` |
| 14:45-16:15 | **H3**: chat que crea casos, con sus evals | `ingeniero-voz` y `evaluador` |
| 16:15 | Congelar las vidas, medir la línea base (`reglas` y `personalizada` sin ajustar) y sacar el diario | sesión principal |
| 16:15-17:00 | Bucle de ajuste | `cientifico-personalizacion` |
| 17:00-17:30 | Revisión | Pablo, `critico-necesidad` y `revisor` |
| 17:30-19:00 | Integrar en `main`, `pytest`, `/medir todo`, evals de la llamada, prueba a mano del chat, panel de ElevenLabs y gráfica | sesión principal y Pablo |

Las tres zonas de 14:45 a 16:15 (H1, H2 y H3) no comparten archivos.

**Si vamos tarde, cae por este orden:**
1. el nivel 4 de la escalera;
2. el `oraculo`;
3. la extracción grabada en la simulación (se usan las etiquetas);
4. los hechos del chat que no crean caso;
5. el bucle de ajuste: se enseña la línea base frente a la personalizada con los valores por defecto.

**Lo que no cae nunca:** el simulador sobre el sistema real, la escalera hasta el nivel 3 y el retraso por persona.

## 6. Entregables

- **Código**: el simulador, el aprendizaje, la herramienta del chat, los tests y `evals/medir_amigos.py`.
- **Resultados**: `evals/resultados/amigos-<fecha>.json`.
- **Gráfica**: `scripts/grafica_amigos.py` genera `evals/resultados/curva-amigos.svg` (o `.html`) sin dependencias nuevas, porque matplotlib no está instalado. La diapositiva compara `reglas` con `personalizada`: dinero que se escapa y preguntas inútiles por semana.
- **Diario**: `scripts/diario_amigos.py --vida alvaro --semana 1` muestra qué preguntó Meisam y qué contestó la persona. Sirve para el contraste de la semana 1 con la 8 en el pitch y para que el crítico juzgue.
- **Documentos**:
  - `registro/ajuste-amigos.md`;
  - `docs/revisiones/necesidad-<fecha>.md`;
  - un apartado nuevo en `docs/diseno/personalizacion.md`.

## 7. Lo que hace Pablo a mano

1. Antes de lanzar, comprobar el saldo de la clave que use esta tanda y ponerle un límite de gasto de 100 € en la consola de Anthropic.
2. Reiniciar Claude Code para que cargue los agentes nuevos.
3. Dar de alta la herramienta del chat en ElevenLabs.
4. Revisar a las 17:00.
