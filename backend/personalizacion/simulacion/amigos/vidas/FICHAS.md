# Fichas de las vidas ocultas (curva de amigos)

Las escribe `experto-usuarios` (11 nov). Son **verdad oculta**: solo las leen el generador, el usuario y el amigo simulados,
las medidas y el `oraculo` (`ESQUEMA.md`). Las cifras exactas están en `<id>.yaml`; aquí va el porqué. Las fuentes,
con enlace, están en `FUENTES.md` (`[F#]`). Lo que no tiene fuente dice **supuesto**.

Todo es inventado: Madrid, personas, claves de Bizum y comercios. Ningún rasgo sensible (salud, religión, ideología,
orientación). Las frases sobre amigos son de hechos («suele tardar 2 o 3 días»), nunca juicios.

## 0. Reglas comunes

**Calendario** (lo fija el protocolo, `ESQUEMA.md` §0): historial previo semanas −3..0 (7 sep-4 oct 2026, Meisam
apagado) y 8 semanas activas desde el lunes 5 oct. Lo que pasa de verdad en esas fechas en Madrid [F22]:

| Semana | Fechas | Qué cambia |
|---|---|---|
| −3..0 | 7 sep-4 oct | Arranque de curso: planes de «inicio de curso», grupos aún formándose |
| 1 | 5-11 oct | El sábado 10 empieza el puente del Pilar: quien es de fuera se va a casa |
| 2 | 12-18 oct | Lunes 12, festivo nacional |
| 3 | 19-25 oct | Normal |
| 4 | 26 oct-1 nov | Sábado 31, Halloween; domingo 1, Todos los Santos (escapadas y pueblo) |
| 5 | 2-8 nov | El sábado 7 empieza el puente de la Almudena |
| 6 | 9-15 nov | Lunes 9, festivo local de Madrid capital |
| 7-8 | 16-29 nov | Parciales y entregas (supuesto); viernes 27, Black Friday |

**Lo que ve el banco** (y nada más): fecha (sin hora), comercio tal como sale en el extracto, importe, Bizums y
transferencias con la contraparte («Laura Vidal Ortega» o «LAURA VIDAL O») y la nota. El efectivo no deja rastro.

**Comercios.** Nombres inventados y genéricos. Casi todos llevan una palabra que el motor reconoce sin red (`TASCA`,
`PIZZERIA`, `TABERNA`, `CERVECERIA`, `BAR`, `CAFETERIA`); algunos no (`RAMEN SHIKI`, `HAMBURGUESERIA EL CHUT`,
`BRUNCH CLUB`), como pasa en los extractos reales, y dependen de la categoría del banco.

**Claves.** Son lo que calcula el motor: nombre legal + inicial del primer apellido. Por eso a veces **no coinciden con
cómo llama el usuario a su amigo**, como en la vida real: «Nacho» es `IGNACIO P`, «Lola» es `DOLORES V`, «Maite» es
`MARIA T` (el motor coge la T de Teresa), «Concha» es `CONCEPCION M`, «Toni» es `ANTONIO F` y «José Luis» es `JOSE L`.

**Precios de Madrid** que anclan los importes por persona:

| Qué | Rango que usamos | Fuente |
|---|---|---|
| Menú del día | 13,50-16,50 € | 14,5 € de media en Madrid en 2025 [F8] |
| Menú de cafetería universitaria | 4,50-7,50 € | supuesto (la tabla oficial de la UAM [F27] no se pudo leer) |
| Caña o refresco | 2,50-3,50 € | guías de precios y cartas reales [F9]; supuesto |
| Raciones y cañas de sábado | 13-19 €/persona | supuesto: 3-4 consumiciones + 1-2 raciones compartidas |
| Pizza a domicilio | 8,50-11,50 €/persona | mediana en oferta 6-11 € + bebida [F11]; supuesto |
| Entrada de cine | 8,50-11,50 € | 7,7 € de media en España en 2025 [F10]; Madrid centro, más caro (supuesto) |
| Cena de cumpleaños en restaurante | 24-40 €/persona | supuesto |
| Abono Joven | 10 €/mes | [F20] |

**Cómo devuelve la gente.** En España el efectivo sigue siendo lo más habitual entre particulares (63 %) y Bizum lo
siguiente (33 %) [F1]; los jóvenes usan más el móvil [F3] y los mayores de 65, mucho más el efectivo [F1]. No hay un
estudio español de cuánto se tarda en devolver: las referencias son extranjeras (la mayoría espera que se le devuelva en
24 h y ve normal recordarlo a los 4 días [F13]; medias de 4 a 10 días según el grupo [F14]; un tercio de la generación Z
reconoce retrasarse [F15]). Todos los retrasos por persona son **supuestos** coherentes con eso: la mayoría paga en 0-3
días, alguno tarda una o dos semanas y alguno solo paga si se lo piden.

**Cómo trata cada persona a Meisam.** No hay datos públicos de cuánta gente contesta una pregunta transaccional de su
banco. Las notificaciones de marketing de banca se abren un 7-9 % y las contextuales un 14-16 % [F25]; una pregunta
sobre tu propio dinero debería ir mucho mejor, pero **los porcentajes de respuesta son supuestos** y probablemente
optimistas. Recomendación: medir también con las tasas de respuesta a la mitad (análisis de sensibilidad).

## 1. Álvaro, 20 (`alvaro`, ajuste): la rutina de manual

**Quién es.** 2.º de Informática en una universidad pública de Madrid. Es de Talavera y comparte piso en Argüelles con
Rodrigo, Marcos e Iker. Rutina 0,85.

**Lo visible.**
- **Ingresos:** 700 € de sus padres el día 1, por transferencia. No incluimos beca: la del Ministerio se cobra de una
  vez y tarde (diciembre o enero), fuera de la ventana [F17].
- **Fijos:** habitación 380 € (recibo, día 2), Abono Joven 10 € y móvil 10 €.
- **Fondo:** súper 1,5 veces por semana, de 10 a 35 €.
- **Comercios habituales:** `SUPERMERCADOS EL ALMENDRO`, `PIZZERIA VESUBIO ARGUELLES`, `LA TASCA DE ARGUELLES` y
  `CAFETERIA FACULTAD INFORMATICA`.

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Jueves de pizzas | jueves, cena | 0,85 | Pizzería Vesubio (3/4) o Da Toni (1/4) | Rodrigo y Marcos; Iker con prob. 0,3 (los jueves suele irse a su pueblo) | Álvaro 85 %, Marcos 15 % | iguales | 8,50-11,50 |
| Sábado de raciones | sábado, noche | 0,70 | La Tasca de Argüelles (3/5), Taberna El Candil o Cervecería El Tranvía | Laura y Marcos; Rodrigo con prob. 0,35 | Álvaro 50 %, Laura 25 %, Marcos 25 % | iguales | 13-19 |

Las pizzas suman 25-35 € **un jueves**: con las reglas de hoy no abren nada (entre semana hace falta el doble del
umbral), así que solo se ven por los Bizums de los demás o por el chat. El sábado típico es el del pitch: 48 € en La
Tasca entre tres, a 16 € cada uno.

**Planes esporádicos**
- **Cena de inicio de curso** (semana −2, jueves): paga Laura y Álvaro le manda su parte (Bizum enviado: ruido).
- **Entradas de Halloween** (semana 4, miércoles): compra en línea 4 entradas de 15 € para él, Rodrigo, Marcos e Iker.
  Es un comercio de ocio entre semana: solo lo delatan los Bizums.
- **Cumpleaños de Laura** (semana 4, viernes): cena para 7 en `RESTAURANTE LA PARRILLA DE MONCLOA`. Laura está
  invitada, así que pagan 6 a 24-28 € cada uno. Va Carla, una amiga de Laura que no está en su agenda.

**Gastos en solitario:** cafetería de la facultad entre semana (prob. 0,55 al día, 2,50-6,50 €), kebab después del
sábado (0,35, 5-8 €) y hamburguesa los domingos (0,2, 11-15 €).

**Cambios de rutina:** el puente del Pilar (semana 1) se va a casa (el sábado baja a 0,3); parciales en las semanas
7-8 (pizzas ×0,6, sábados ×0,35, cafetería ×1,3).

**Amigos**

| Clave | Le llama | Relación | Retraso por su cuenta (días) | Paga solo | Tras pedírselo | Canal | Redondea | Otros |
|---|---|---|---|---|---|---|---|---|
| `RODRIGO S` | Rodrigo | compañero de piso | 2 (50 %), 3 (35 %), 5 (15 %) | 0,85 | 0-1 d | Bizum | casi nunca | Suele pagar el fin de semana |
| `MARCOS B` | Marcos | compañero de piso | 0-1 | 0,97 | mismo día | Bizum | al euro (50 %) | |
| `IKER G` | Iker | compañero de piso | 0-2 | 0,90 | 0-1 d | Bizum 60 %, efectivo 40 % | a 5 € (40 %) | Deja el dinero en la mesa del salón |
| `LAURA V` | Laura | amiga de clase | 0-2 | 0,95 | mismo día | Bizum | al euro (30 %) | |
| `IGNACIO P` | Nacho | amigo de clase | 3-10 | 0,50 | 1-3 d | Bizum | a 5 € (50 %) | No paga nunca: 5 % |
| `CARLA F` | Carla | amiga de Laura | 1-2 | 0,90 | 0-1 d | Bizum | no | No está en la agenda |

**Con Meisam:** contesta el 60 % del Resumen y el 75 % de los avisos (casi todo en el día). Cuenta por chat el 30 % de
los gastos compartidos y escribe sin tildes y con prisa. Tolera 4 avisos por semana; tras 4 preguntas inútiles
seguidas, silencia. Si alguien no paga: pide Bizum (70 %), se lo dice en el piso (25 %) o lo deja (5 %). Marca el
efectivo de Iker el 40 % de las veces. Aceptaría que Meisam abra solo el caso de las pizzas (nivel 4).

**Pone a prueba:** sugerencia de grupo («¿Con Laura y Marcos, 16 € cada uno?»), Rodrigo a los 2-3 días (no recordar el
jueves siguiente si paga el domingo), pizzas que las reglas no ven, cumpleaños con la homenajeada invitada,
hipocorístico (Nacho = `IGNACIO P`), persona nueva y efectivo sin declarar.

## 2. Irene, 21 (`irene`, ajuste): la caótica

**Quién es.** Estudiante italiana de Comunicación, de Erasmus en Madrid de septiembre a enero. Abrió una cuenta
española para tener Bizum. Comparte piso en Lavapiés con Sofía, también italiana. Rutina 0,25.

**Lo visible.**
- **Ingresos:** su madre le manda 450 € (± 50) el día 3 desde Italia. La beca Erasmus (300-350 €/mes [F21]) se cobra
  casi toda al principio de la estancia: va en el saldo inicial (1.450 €), no como ingreso mensual (supuesto).
- **Fijos:** habitación 480 € (día 1), Abono Joven 10 €, tarjeta prepago del móvil 10 € y música 10,99 €.
- **Fondo:** súper 24 horas dos veces por semana (8-30 €).

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Intercambio de idiomas | martes, tarde | 0,55 | `BAR LA LENGUA SUELTA` | Nuria; Alejandro, Chloé y Jonas a veces | cada uno 50 %, Irene 30 %, Nuria 20 % | iguales | 7-13 |
| Salida Erasmus | jueves, viernes o sábado (uno), noche | 0,90 | 6 sitios distintos con el mismo peso (taberna, pizzería, cervecería, karaoke, mexicano, bar) | Sofía; los demás, cada uno entre 0,25 y 0,6 | Irene 40 %, cada uno 30 %, Sofía 30 % | por consumo (±30 %) | 12-24 |
| Domingo de Rastro | domingo, comida | 0,35 | `BAR EL RASTRILLO` | Maja; Luca a veces | Irene 50 %, cada uno 50 % | iguales | 9-15 |

**Planes esporádicos**
- **Viaje a Granada**: reserva el alojamiento para 5 la semana 1 (jueves), a 55-65 € cada uno, y viaja en el puente
  de Todos los Santos (semana 4). Los amigos van devolviendo a lo largo de 3 semanas, por canales distintos.
- **Cumpleaños de Sofía** (semana 5, viernes): compra la bebida y la tarta en el súper (7-10 € por persona). Es un
  súper: las reglas nunca preguntan y solo lo delatan los Bizums o el chat.
- **Despedida de Luca** (semana 6, jueves): Luca se vuelve a Italia y está invitado. Irene paga la cena de 6 (20-26 €
  por persona).

**Gastos en solitario:** café y bollo entre semana (0,4 al día, 2,50-5 €).

**Cambios de rutina:** el puente del Pilar (semana 2), más salidas (×1,3); viaje (semana 4), salidas ×0,3 y sin Rastro.

**Amigos**

| Clave | Le llama | Relación | Retraso (días) | Paga solo | Tras pedírselo | Canal | Redondea | Otros |
|---|---|---|---|---|---|---|---|---|
| `SOFIA M` | Sofi | compañera de piso | 0-2 | 0,90 | 0-1 d | Bizum 70 %, efectivo 30 % | no | Paga lo de Luca el 30 % de las veces |
| `CHLOE D` | Chloé | amiga | 2-9 | 0,80 | 1-3 d | transferencia 55 %, efectivo 45 % | a 5 € (70 %) | Sin Bizum (cuenta francesa) |
| `JONAS W` | Jonas | amigo | 0-1 | 0,98 | mismo día | transferencia | no, al céntimo | Sin Bizum (cuenta alemana) |
| `LUCA B` | Luca | amigo | 3-15 | 0,50 | 2-5 d | transferencia 40 %, efectivo 40 %, Bizum 20 % | no | Se va en la semana 6: no paga nunca el 25 % |
| `NURIA C` | Nuria | amiga (intercambio) | 0-2 | 0,95 | mismo día | Bizum | al euro (30 %) | |
| `ALEJANDRO R` | Álex | compañero de clase | 1-6 | 0,70 | 0-1 d | Bizum | no | En una nota bromea con «ignorar a Meisam» (inyección) |
| `MAJA K` | Maja | amiga | 1-7 | 0,85 | 1-2 d | efectivo 70 %, transferencia 30 % | a 5 € (50 %) | |

**Con Meisam:** contesta el 50 % del Resumen y el 60 % de los avisos, a veces tarde. Acierta el 85 % (en grupos que
cambian no siempre recuerda quién estaba). Usa mucho el chat (60 %), mezcla español e italiano, sin tildes y con varias
cosas en un mensaje. Tolera 5 avisos por semana. Si alguien no paga: pide (40 %), se lo dice (40 %) o lo deja (20 %;
sobre todo importes pequeños). No acepta el nivel 4.

**Pone a prueba:** el límite de la rutina (sitios y grupos que no se repiten), amigos sin Bizum (pedir Bizum fallaría:
hay que recordar, no pedir), transferencias con un solo apellido, redondeos a 5 €, alguien que se va y no paga, gastos de
súper compartidos, chat desordenado y una inyección en una nota.

## 3. Hugo, 19 (`hugo`, ajuste): el equipo grande

**Quién es.** 1.º de ADE y vive con sus padres en Moratalaz. Juega al fútbol sala en una liga universitaria los
viernes por la noche y lleva las cuentas del equipo. Rutina 0,70.

**Lo visible.**
- **Ingresos:** su madre le pasa 200 € el día 1 y su abuela le manda un Bizum de unos 20 € (± 10) hacia el día 20.
- **Fijos:** cuota del club, 30 € al mes por recibo (gasto fijo propio: no es una deuda), Abono Joven 10 € y móvil 12 €.
- **Fondo:** algo de ropa y deporte de vez en cuando.

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Cena del equipo tras el partido | viernes, noche | 0,75 | `CERVECERIA LA PRORROGA` (3/6), `HAMBURGUESERIA EL CHUT` (2/6) o `PIZZERIA EL TRIPLETE` (1/6) | Dani, Adrián y Mario; otros 8 con prob. entre 0,55 y 0,85 (suelen ser 8-11 con Hugo) | Hugo 45 % (lleva las cuentas), Dani (capitán) 25 %, cada uno 30 % | iguales | 10-15 |

Cuando paga Hugo, le deben entre 6 y 11 personas: es la prueba de agrupar avisos («faltan 3 de 10») en vez de mandar
diez.

**Planes esporádicos**
- **Camisetas de entrenamiento** (semana 2, jueves): las encarga Hugo en línea para 10 (17 € cada una). Es una compra:
  las reglas nunca preguntan.
- **Cumpleaños de Dani** (semana 3, sábado): paga Mario y Hugo le manda su parte (Bizum enviado).

**Gastos en solitario:** kebab después de entrenar martes y jueves (0,5, 6-9 €) y cafetería de la facultad (0,5, 2-5 €).

**Cambios de rutina:** jornada de descanso de la liga en el puente del Pilar (semana 2, cena ×0,2); parciales en las
semanas 7-8 (×0,6).

**Amigos** (once compañeros de equipo; todos con Bizum salvo donde se dice)

| Clave | Le llama | Retraso (días) | Paga solo | Canal | Redondea | Otros |
|---|---|---|---|---|---|---|
| `DANIEL F` | Dani | 0-1 | 0,98 | Bizum | no | Capitán |
| `ADRIAN L` | Adri | 0-3 | 0,90 | Bizum | al euro (40 %) | Paga lo de su hermano Samuel el 65 % de las veces |
| `SAMUEL L` | Samu | 1-2 | 0,80 | Bizum | no | |
| `KEVIN M` | Kevin | 7-21 | 0,30 | efectivo 60 %, Bizum 40 % | no | Casi nunca responde a las solicitudes; a veces lo da en mano en el entreno; no paga nunca: 30 % |
| `MARIO C` | Mario | 0-1 | 0,95 | Bizum | al euro (60 %) | |
| `OSCAR R` | Óscar | 1-4 | 0,85 | Bizum | no | |
| `YAGO T` | Yago | 0-1 | 0,95 | Bizum | a 5 € (50 %) | |
| `ERIC S` | Eric | 2-7 | 0,60 | Bizum 80 %, efectivo 20 % | no | |
| `LUCAS P` | Lucas | 0-1 | 0,95 | Bizum | no | |
| `GONZALO N` | Gonza | 1-3 | 0,80 | Bizum | al euro (50 %) | |
| `RUBEN D` | Rubén | 0-5 | 0,75 | Bizum 70 %, efectivo 30 % | no | |

**Con Meisam:** contesta el 40 % del Resumen y el 55 % de los avisos, tarde. Acierta el 90 % (con 10 personas se le
olvida alguien). Chat poco (15 %), con abreviaturas. Tolera 3 avisos por semana. Si no pagan: pide Bizum (50 %), se lo
dice en el entreno (40 %) o lo deja (10 %). Aceptaría el nivel 4 para la cena del equipo.

**Pone a prueba:** muchos deudores a la vez, quien paga por dos (hermanos), uno que casi nunca paga, el recibo del club
como gasto fijo que no se pregunta y compras compartidas que solo se ven por los Bizums. Inyección en el nombre del
comercio de las camisetas.

## 4. Marta, 22 (`marta`, ajuste): «cada una lo suyo»

**Quién es.** 4.º de Periodismo. Vive con sus padres en Carabanchel y trabaja de camarera los viernes y sábados por la
noche. Rutina 0,55.

**Lo visible.**
- **Ingresos:** nómina de unos 540 € (± 40) el día 4, de `RESTAURACION MALVARROSA SL`: un tiempo parcial de fin de
  semana sobre el SMI de 2026 [F18]. Las propinas, en efectivo, no se ven (supuesto).
- **Fijos:** Abono Joven 10 €, móvil 15 € y streaming 6,99 €.
- **Fondo:** súper poco (0,7 veces por semana) y copistería para el TFG.

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Comida del domingo con las de clase | domingo, comida | 0,60 | `TABERNA LA MORENA` (2/3) o `BAR EL OLIVO` | Clara y Bea; Inés 0,6; Andrea 0,3 | **cada una lo suyo 70 %**, Marta 15 %, Clara 15 % | por consumo (±25 %) | 17-26 |
| Tarde con Andrea | martes o miércoles, tarde | 0,55 | `BAR EL OLIVO` (2/3) o `CINES LUNA AZUL` | Andrea | Marta 50 %, cada una 30 %, efectivo 20 % | iguales | 6-11 |

El domingo, con las reglas de hoy, sale cada semana «¿Fuiste con alguien?», y la verdad es «sí, pero cada una pagó lo
suyo». Cada vez más restaurantes no separan la cuenta [F12]: por eso, a veces paga una y las demás le devuelven por
consumo, con importes distintos.

**Planes esporádicos:** cena de clase del TFG (semana 3, jueves; cada uno lo suyo, con 6-10 desconocidos) y regalo de
cumpleaños de Inés entre tres (semana 5, jueves; compra de 12-15 € por persona).

**Gastos en solitario:** cafetería de la facultad (0,5 al día, 1,50-5 €) y bocadillo antes del turno del viernes
(0,3, 4-7 €).

**Cambios de rutina:** trabaja el domingo de Todos los Santos (semana 4: sin comida del domingo); entregas del TFG en
las semanas 7-8 (tardes ×0,6).

**Amigos**

| Clave | Le llama | Relación | Retraso (días) | Paga solo | Canal | Redondea | Otros |
|---|---|---|---|---|---|---|---|
| `ANDREA G` | Andrea | amiga del barrio | 1-6 | 0,90 | **efectivo 85 %**, Bizum 15 % | a 5 € (30 %) | Se lo da en mano la siguiente vez que se ven |
| `CLARA P` | Clara | compañera de clase | 0-2 | 0,95 | Bizum | al euro (40 %) | |
| `BEA S` | Bea | compañera de clase | 1-3 | 0,85 | Bizum | no | |
| `INES M` | Inés | compañera de clase | 0-4 | 0,80 | Bizum | al euro (30 %) | |

**Con Meisam:** contesta el 60 % del Resumen y el 70 % de los avisos. Poco chat (10 %). Tolera solo 2 avisos por semana
y silencia tras 3 preguntas inútiles seguidas. **No quiere que se le recuerde nada a Andrea** («nos lo apañamos en
mano»). Si alguien no paga, se lo dice en persona (60 %). Solo marca el efectivo de Andrea el 30 % de las veces.

**Pone a prueba:** aprender a callar sin callar de más (a veces sí hay deuda en el mismo sitio y día), repartos por
consumo, efectivo sin declarar y una persona en `no_recordar`.

## 5. Diego, 20 (`diego`, ajuste): el que come solo

**Quién es.** 3.º de Ingeniería Industrial. Vive con sus padres en Alcobendas, da clases particulares de matemáticas y
los sábados por la mañana va a una academia de inglés. Rutina 0,90.

**Lo visible.**
- **Ingresos:** su padre le pasa 120 € el día 1 y su madre le manda unos 25 € hacia el 15. Por las clases particulares
  recibe 30 € por Bizum cuatro veces al mes (días 4, 11, 18 y 25) de la madre de su alumno: Bizums entrantes que **no son
  devoluciones**.
- **Fijos:** Abono Joven 10 € y móvil 10 €.
- **Fondo:** poco súper; alguna compra en línea.

**Planes recurrentes:** ninguno compartido.

**Gastos en solitario** (el corazón de esta vida)

| Gasto | Cuándo | Prob. | Sitio | € |
|---|---|---|---|---|
| Menú de la cafetería | lunes a viernes | 0,80 al día | `CAFETERIA ESCUELA INGENIEROS` | 4,50-7,50 |
| Ramen después de la academia | sábado | 0,75 | `RAMEN SHIKI` (sin palabra reconocible: depende de la categoría) | 20-26 |
| Cine | domingo | 0,35 | `CINES ESTRELLA` | 8,50-11,50 |

El ramen del sábado supera los 20 € en fin de semana y en restaurante: **con las reglas de hoy se pregunta casi cada
sábado** y la verdad es siempre «iba solo».

**Planes esporádicos (la trampa)**
- **Ramen con dos compañeros de la academia** (semana 5, sábado): mismo sitio y mismo día, pero paga 3 × 21-26 €. Si
  Meisam ha aprendido a callar ahí, tiene que notar que el importe triplica lo normal. Alba se olvida.
- **Cena de clase** (semana 6, viernes): cada uno paga lo suyo, con 6-10 compañeros. Iba acompañado, pero nadie le
  debe.
- **Cumpleaños de Guille** (semana −1, sábado): paga Guille y Diego le manda su parte (ruido en el historial).

**Cambios de rutina:** parciales en las semanas 7-8 (ramen ×0,6, cine ×0,3).

**Amigos**

| Clave | Le llama | Relación | Retraso (días) | Paga solo | Tras pedírselo | Canal |
|---|---|---|---|---|---|---|
| `GUILLERMO N` | Guille | amigo de clase | 1-3 | 0,90 | 0-1 d | Bizum |
| `ALBA R` | Alba | compañera de la academia | 2-5 | **0,40** (se olvida) | 0-2 d | Bizum |
| `ROSARIO V` | mamá | familia | — | — | — | Bizum (nunca debe nada) |

**Con Meisam:** el más ordenado. Contesta el 75 % del Resumen y el 85 % de los avisos, rápido. Casi no usa el chat
(5 %). Tolera 2 avisos por semana y silencia tras 3 preguntas inútiles. No quiere recordatorios a su madre. Si alguien no
paga, pide Bizum.

**Pone a prueba:** el valor de callar (preguntas inútiles), Bizums entrantes que no son devoluciones (clases y madre),
la excepción del ramen para tres y «acompañado pero nadie me debe».

## 6. Sergio, 21 (`sergio`, ajuste): el que no contesta

**Quién es.** 2.º de Derecho. Vive con sus padres en Chamberí y a veces trabaja de azafato en eventos. Rutina 0,50.

**Lo visible.**
- **Ingresos:** sus padres le pasan 300 € el día 1; la agencia de eventos, unos 95 € (± 40) hacia el 20.
- **Fijos:** Abono Joven 10 €, móvil 12 € y gimnasio low cost 24,99 €.

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Viernes de cena | viernes, cena | 0,60 | `TABERNA EL ALAMBIQUE` (2/3) o `PIZZERIA DONATELLA` | Álex y Carlos; Teresa 0,6, Jorge 0,55 | Sergio 35 %, Álex 30 %, Carlos 15 %, cada uno 20 % | iguales | 12-19 |
| Fútbol en el bar | domingo, tarde | 0,45 | `BAR EL MOLINO` | Álex; Carlos 0,5 | cada uno 40 %, Sergio 30 %, Álex 30 % | iguales | 8-14 |

**Planes esporádicos:** regalo de cumpleaños de Teresa entre cinco (semana 3, miércoles; compra en línea, 12 € cada
uno); cena de clase (semana 4, jueves; cada uno lo suyo).

**Gastos en solitario:** cafetería de la facultad (0,4 al día, 2-5 €).

**Cambios de rutina:** parciales en las semanas 7-8 (viernes ×0,5).

**Amigos**

| Clave | Le llama | Retraso (días) | Paga solo | Tras pedírselo | Canal | Otros |
|---|---|---|---|---|---|---|
| `ALEJANDRO T` | Álex | 1-3 | 0,90 | 0-1 d | Bizum | |
| `CARLOS V` | Carlos | 3-12 | **0,45** | 0-2 d | Bizum | Solo paga si se lo piden la mitad de las veces |
| `TERESA B` | Tere | 0-1 | 0,95 | mismo día | Bizum | Paga lo de Jorge el 70 % de las veces |
| `JORGE M` | Jorge | 2-5 | 0,60 | 1-3 d | Bizum 70 %, efectivo 30 % | |
| `MIRIAM P` | Miriam | 0-2 | 0,90 | mismo día | Bizum | No está en la agenda |

**Con Meisam:** **el límite honesto.** Contesta el 8 % del Resumen y el 15 % de los avisos, con 1-3 días de retraso
(muchas respuestas llegan pasadas las 48 h y no cuentan). Casi no usa el chat (2 %). Tolera 1 aviso por semana y
silencia tras 2 preguntas inútiles. Si alguien no paga, lo deja (70 %). Casi nunca marca el efectivo.

**Pone a prueba:** lo que Meisam aprende **sin respuestas**, solo de los Bizums que llegan (retraso de cada amigo,
grupos), y dónde no mejora: el dinero de Carlos se escapa porque Sergio no reclama.

## 7. Carmen, 29 (`carmen`, ajuste): trabajo, cumpleaños y escapadas

**Quién es.** Consultora junior en su primer trabajo fijo. Comparte piso en Malasaña con Lola. Rutina 0,50.

**Lo visible.**
- **Ingresos:** nómina de 1.745 € el día 27 (unos 25-27 k€ brutos al año [F23]) y liquidación de gastos de la empresa
  de unos 95 € (± 45) hacia el día 12. Son transferencias de su empresa, no de amigos.
- **Fijos:** habitación 650 €, abono de transporte (zona A, tarifa adulta con descuento) 32,70 €, gimnasio 39,90 €,
  streaming 12,99 € y móvil 15 €.
- **Fondo:** súper 1,5 veces por semana (15-45 €).

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Menú con los del equipo | martes o jueves, comida | 0,55 | `RESTAURANTE LA MANZANA` (2/3) o `TABERNA DEL PASAJE` | Elena; Víctor 0,6, Marina 0,5 | cada uno 40 %, Carmen 30 %, Elena 30 % | iguales | 13,50-16,50 |
| Comida con un cliente | miércoles, comida | 0,25 | `RESTAURANTE EL MIRADOR DEL CASTELLANA` | 2-3 desconocidos | Carmen (la empresa se lo devuelve) | invita | 25-35 |
| Brunch con Lola | domingo, comida | 0,45 | `BRUNCH CLUB MALASANA` | Lola | Carmen 50 %, Lola 50 % | iguales | 14-22 |
| Cañas después del trabajo | jueves, tarde | 0,35 | `CERVECERIA LA ESTACION` | Víctor; Marina 0,5 | cada uno 60 %, Carmen 20 %, Víctor 20 % | iguales | 9-16 |

La comida con el cliente es la trampa: un pago grande entre semana, acompañada, y **nadie le debe** (se lo devuelve la
empresa en la liquidación del mes).

**Planes esporádicos**
- **Regalo de Belén entre cinco** (semana 3, miércoles): compra por pasarela de pago, 14-16 € por persona.
- **Cumpleaños de Belén** (semana 3, sábado): cena para 9 que paga Carmen. Belén está invitada: pagan 9 a 33-40 €.
  Van tres personas que no están en su agenda (Toni, Martín y Paula).
- **Escapada rural en el puente de la Almudena**: reserva la casa la semana 3 (jueves) para 4 (85-95 € cada uno).
  Belén conduce y paga la gasolina (semana 5, sábado; Carmen le manda su parte), y el domingo hay una cena en el
  pueblo.

**Gastos en solitario:** café de máquina y desayuno (0,6 al día, 2-4,50 €).

**Cambios de rutina:** escapada en la semana 5 (brunch ×0); cierre de proyecto en la semana 7 (menú ×1,3, cañas ×0,5).

**Amigos**

| Clave | Le llama | Relación | Retraso (días) | Paga solo | Canal | Otros |
|---|---|---|---|---|---|---|
| `DOLORES V` | Lola | compañera de piso | 0-3 | 0,92 | Bizum 80 %, efectivo 20 % | |
| `BELEN R` | Belén | amiga | 0-1 | 0,95 | Bizum | |
| `ELENA P` | Elena | compañera de trabajo | 0-3 | 0,90 | Bizum 50 %, **transferencia 50 %** | |
| `VICTOR A` | Víctor | compañero de trabajo | 1-6 | 0,70 | transferencia 60 %, Bizum 40 % | |
| `MARINA S` | Marina | compañera de trabajo | 0-1 | 0,95 | Bizum | |
| `ANA C` | Ana | amiga | 0-2 | 0,95 | Bizum | Redondea a 5 € (50 %) |
| `RAQUEL D` | Raquel | amiga | 1-7 | 0,75 | Bizum | |
| `ISMAEL G` | Isma | amigo | 0-2 | 0,90 | Bizum | Paga lo de Paula (su pareja) el 60 % |
| `PAULA E` | Paula | amiga | 1-2 | 0,80 | Bizum | |
| `ANTONIO F` | Toni | amigo de Belén | 2-10 | 0,55 | Bizum 80 %, efectivo 20 % | No está en la agenda; no paga nunca: 10 % |
| `MARTIN Z` | Martín | amigo de Belén | 0-1 | 0,95 | Bizum | No está en la agenda |
| `JUDITH O` | Judith | amiga | 4-15 | 0,60 | Bizum 60 %, efectivo 40 % | Redondea a 5 € (50 %); suele pagar la casa en el viaje |

**Con Meisam:** contesta el 65 % del Resumen y el 80 % de los avisos. Usa el chat (35 %) con frases completas, con
tildes y varias cosas a la vez. Tolera 4 avisos por semana. Si no pagan, pide Bizum (60 %) o se lo dice (35 %). Marca el
efectivo el 70 % de las veces. Aceptaría el nivel 4 en el brunch con Lola.

**Pone a prueba:** transferencias de compañeros (no solo Bizum), pagos de trabajo que no son deuda, una cena de 9 con
gente nueva, una reserva grande que se devuelve a lo largo de semanas y una pareja que paga por dos.

## 8. Javier, 44 (`javier`, ajuste): las familias

**Quién es.** Jefe de turno en una empresa de logística. Vive en Vicálvaro con su pareja, Mercedes, y sus dos hijos.
El mayor juega en un club de fútbol base y Javier es el delegado del equipo. Rutina 0,80.

**Lo visible.**
- **Ingresos:** nómina de 2.480 € el día 28 (supuesto). Mercedes le manda 390 € por Bizum el día 4: su mitad de la
  hipoteca. Es un gasto fijo compartido **con su pareja**: nunca hay que recordárselo.
- **Fijos:** hipoteca 780 €, comedor escolar 230 €, cuota del club 38 € (supuesto: no hay tarifas publicadas de clubes
  madrileños [F24]), luz y agua.
- **Fondo:** hipermercado dos veces por semana (40-120 €) y gasolina una vez por semana (45-70 €).

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/familia |
|---|---|---|---|---|---|---|---|
| Cena con otras familias | viernes o sábado, cena | 0,40 | `RESTAURANTE LA ALQUERIA` (2/4), `ASADOR EL PORTALON` o `BRASERIA LOS OLMOS` | Mónica y Alberto; Rafa 0,6 | Javier 35 %, Mónica 35 %, Alberto 30 % | iguales **por familia** | 40-58 |
| Aperitivo tras el partido del niño | sábado, comida | 0,50 | `CANTINA CLUB LOS OLMOS` | Mónica; Alberto 0,5 | cada uno 50 %, Javier 25 %, Mónica 25 % | iguales | 6-11 |

**Simplificación del esquema:** cada familia cuenta como una «persona» (la que suele mandar el Bizum). En la vida real,
a veces lo manda su pareja: se pierde ese matiz (ver hallazgos).

**Planes esporádicos**
- **Inscripción al torneo** (semana 4, martes): como delegado, paga 20 € por niño para 11 familias. Seis no están en
  su agenda: Paco, Silvia, Esther, Roberto, Olga y José Luis. Lorena paga también la de su sobrino.
- **Cumpleaños de su hijo** (semana 7, sábado): paga el centro de ocio para los niños del equipo. **Invita**: nadie le
  debe.

**Gastos sin deuda:** comida familiar de domingo en restaurante (0,45, 55-85 €: va con su familia y nadie le debe) y
desayuno en la cafetería del trabajo entre semana (0,6, 2-4 €).

**Cambios de rutina:** Todos los Santos en el pueblo (semana 4: sin cenas ni aperitivo).

**Amigos**

| Clave | Le llama | Relación | Retraso (días) | Paga solo | Canal | Otros |
|---|---|---|---|---|---|---|
| `MERCEDES L` | Merche | pareja | — | — | Bizum | Nunca se le recuerda nada |
| `MONICA F` | Mónica | amiga (familia del equipo) | 0-2 | 0,95 | Bizum | Redondea al euro (60 %) |
| `ALBERTO G` | Alberto | amigo | 1-4 | 0,85 | Bizum | Redondea a 5 € (50 %) |
| `RAFAEL M` | Rafa | amigo | 0-7 | 0,70 | Bizum 80 %, efectivo 20 % | |
| `LORENA B` | Lorena | madre del equipo | 0-1 | 0,90 | Bizum | Paga lo de Silvia (su hermana) el 70 % |
| `FRANCISCO H` | Paco | padre del equipo | 2-5 | 0,60 | Bizum | Fuera de la agenda |
| `SILVIA N` | Silvia | madre del equipo | 1 | 0,80 | Bizum | Fuera de la agenda |
| `ESTHER C` | Esther | madre del equipo | 0-1 | 0,95 | Bizum | Fuera de la agenda |
| `ROBERTO V` | Roberto | padre del equipo | 3-14 | 0,50 | Bizum | Fuera de la agenda; no paga nunca: 10 % |
| `OLGA D` | Olga | madre del equipo | 0-2 | 0,90 | Bizum 60 %, efectivo 40 % | Fuera de la agenda; le da el efectivo en el partido |
| `JOSE L` | José Luis | padre del equipo | 1-4 | 0,85 | Bizum | Fuera de la agenda; clave rara por el nombre compuesto |

**Con Meisam:** contesta el 50 % del Resumen y el 65 % de los avisos. Chat (20 %) con frases largas, como si hablara
(«lo de los de Mónica ya está»). Tolera 3 avisos por semana. Le da apuro pedir dinero a otras familias: se lo dice en
persona (50 %), pide Bizum (30 %) o lo deja (20 %). Aceptaría el nivel 4 para las cenas.

**Pone a prueba:** reparto por familias, pareja que nunca se recuerda, Bizum fijo de la pareja que no es deuda, padres
fuera de la agenda (persona nueva), invitar (nadie debe) y comidas familiares que no deberían preguntarse.

## 9. Nerea, 23 (`nerea`, solo evaluación): la pareja

**Quién es.** Máster en Biotecnología con una beca de colaboración. Vive con su pareja, David, en Tetuán. Rutina 0,75.

**Lo visible.**
- **Ingresos:** beca de colaboración de 650 € el día 10 y 250 € de sus padres el día 1. David le manda 450 € por Bizum
  el día 3: su mitad del alquiler.
- **Fijos:** alquiler 900 € (lo paga ella entero), Abono Joven 10 €, móvil 12 € y luz.

**Planes recurrentes**

| Plan | Cuándo | Prob./semana | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|---|
| Compra grande con David | sábado | 0,90 | `SUPERMERCADO LA DESPENSA` | David | Nerea 60 %, David 40 % | iguales | 22-40 |
| Cena con David | viernes o sábado, cena | 0,60 | `RESTAURANTE EL BUHO`, `TABERNA LA PARRA` o `PIZZERIA ORTIGIA` | David | Nerea 50 %, David 50 % | iguales | 16-26 |
| Cañas del máster | jueves, tarde | 0,50 | `CERVECERIA EL MATRAZ` | Rocío y Héctor; Aitana 0,7; David 0,2 | Nerea 35 %, Rocío 25 %, Héctor 15 %, cada uno 25 % | iguales | 12-18 |

David le devuelve «lo de la semana» de golpe, redondeado a 5 € y sin cuadrar con ningún pago concreto.

**Planes esporádicos:** bebida y picoteo de Halloween para 5 en el súper (semana 4, sábado) y 3 entradas de concierto
(semana 7, viernes; 24-28 €, con David y Aitana).

**Gastos en solitario:** cafetería de la facultad (0,5 al día, 2,50-6 €).

**Cambios de rutina:** entrega del TFM en la semana 8 (cañas ×0,4).

**Amigos**

| Clave | Le llama | Relación | Retraso (días) | Paga solo | Canal | Otros |
|---|---|---|---|---|---|---|
| `DAVID S` | David | pareja | 2-10 | 0,85 | Bizum | Redondea a 5 € (70 %); a veces se compensa y no paga (10 %) |
| `ROCIO V` | Rocío | compañera del máster | 0-2 | 0,95 | Bizum | |
| `HECTOR G` | Héctor | compañero del máster | 2-9 | 0,60 | Bizum | No paga nunca: 5 % |
| `AITANA B` | Aitana | compañera del máster | 0-1 | 0,90 | Bizum | Redondea al euro (60 %) |

**Con Meisam:** contesta el 65 % del Resumen y el 80 % de los avisos. Chat 40 %. Tolera 3 avisos por semana. **Nunca
quiere recordatorios a David**; al resto, sí (pide Bizum el 60 %).

**Pone a prueba** (sin haber ajustado con ella): no recordar nunca a la pareja aunque le deba, Bizums de la pareja que
no cuadran con nada, y seguir recordando a Héctor.

## 10. Pilar, 66 (`pilar`, solo evaluación): el efectivo

**Quién es.** Jubilada, vive sola en Usera. Su hija Noelia vive cerca. Rutina 0,95.

**Lo visible.**
- **Ingresos:** pensión de 1.495 € el día 25 (la media de jubilación es de 1.572 € [F19]). En noviembre cobraría
  además la paga extra: el esquema no lo permite (ver hallazgos).
- **Fijos:** comunidad 85 €, luz, gas y teléfono.
- **Fondo:** súper del barrio 2,5 veces por semana (12-45 €) y panadería casi a diario (1,20-3,50 €).

**Planes**

| Plan | Cuándo | Sitio | Grupo | Quién paga | Reparto | €/persona |
|---|---|---|---|---|---|---|
| Comida mensual con las amigas | 2.º martes de cada mes (8 sep, 13 oct y 10 nov) | `RESTAURANTE EL ROBLE` | Amparo, Concha, Maite y Rosi | Pilar 85 %, efectivo 15 % | iguales | 24-32 |
| Merienda | jueves, prob. 0,8 | `CAFETERIA LA ROSALEDA` | Concha; Amparo 0,5 | efectivo 45 %, Pilar 35 %, cada una 20 % | iguales | 4,50-7,50 |
| Comida con su hija y los nietos | domingo, prob. 0,5 | `MESON LOS ALAMOS` | Noelia y 2-3 de su familia | Pilar 70 %, otros 30 % | **invita** | 14-20 |

La comida mensual solo pasa **dos veces** en las 8 semanas activas (más una en el historial): es el límite de lo que
se puede aprender de una rutina mensual.

**Gastos en solitario:** desayuno en la cafetería (lunes, miércoles y viernes; 0,3; 2,20-4,50 €).

**Cambios de rutina:** Todos los Santos en el pueblo (semana 4: sin comida de domingo y merienda ×0,5).

**Amigas**

| Clave | Le llama | Retraso (días) | Paga solo | Canal | Otros |
|---|---|---|---|---|---|
| `AMPARO S` | Amparo | 0-3 | 0,95 | Bizum 60 % (se lo instaló su nieta), efectivo 40 % | |
| `CONCEPCION M` | Concha | 0-1 | 0,98 | **efectivo 100 %** | Le paga en la mesa |
| `MARIA T` | Maite | 0, 7 o 28 | 0,75 | efectivo 90 %, Bizum 10 % | A veces se lo trae a la comida siguiente |
| `ROSA F` | Rosi | 0-5 | 0,90 | efectivo 70 %, transferencia 30 % | Redondea a 5 € (60 %) |
| `NOELIA P` | Noelia | — | — | Bizum | Hija; nunca debe nada |

**Con Meisam:** contesta el 40 % del Resumen y el 50 % de los avisos, y tarda (no abre la app a diario). Casi no usa el
chat (5 %); cuando lo usa, escribe formal y con todas las letras. Tolera 2 avisos por semana. **No quiere que se pida
dinero a sus amigas por Bizum**: lo arreglan en mano (60 %) o lo deja (40 %). Marca el efectivo el 55 % de las veces.

**Pone a prueba** (sin haber ajustado con ella): aprender «suele pagarte en efectivo» y ofrecer primero «ya me lo dio»,
no pedir nunca Bizum, una rutina mensual con pocas observaciones e invitar a la familia sin preguntar.

## 11. Huecos honestos (dónde Meisam no puede mejorar)

- **Sergio**: sin respuestas, Meisam solo aprende de lo que llega a la cuenta, y lo que no llega (Carlos) se escapa.
- **Efectivo que nadie declara**: Iker, Andrea, Concha, Maite, Maja y parte de Kevin. Si el usuario no lo marca, el caso
  queda abierto aunque esté cobrado. La medida de «dinero que se escapa» debería separar «no ha vuelto» de «volvió en
  efectivo sin declarar».
- **Irene**: sitios y grupos que no se repiten; la sugerencia de grupo no puede acertar mucho.
- **Pilar**: dos observaciones de su comida mensual en 8 semanas.
- **Amigos sin Bizum** (Chloé, Jonas, Luca, Maja): pedir Bizum no sirve; solo recordar.
