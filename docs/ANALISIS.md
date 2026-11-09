# Análisis de la idea: Copiloto

9 de noviembre de 2026. Sustituye a la idea municipal del día 8 (el porqué está en `docs/DECISIONES.md`). La rúbrica está en `reto/RETO.md`.

## La idea en 5 líneas
Plataforma para bancos que vive dentro de su app. Un motor convierte los movimientos de cada cliente en momentos: un cobro duplicado, una suscripción que se renueva, una cena que tus amigos no te han devuelto, un recibo que sube, que te vas a quedar en negativo o una posible estafa. Solo cuando ahorra dinero o protege, avisa. Al pulsar el aviso se abre una llamada de voz con un agente que ya conoce el contexto y lo resuelve con acciones de una lista cerrada, que el cliente confirma con un botón. Aprende de cada persona y el banco puede añadir módulos nuevos describiéndolos.

Frase del pitch: «Los demás te enseñan tus finanzas. Nosotros te llamamos solo cuando hay algo que resolver, y lo resolvemos en la llamada».

## Problema
- Lo que cuesta dinero pasa desapercibido: cobros duplicados, renovaciones anuales olvidadas, recibos que suben, quedarse en negativo o un Bizum a quien no debías.
- El dinero entre amigos se pierde por desorden: pagas la cena, unos te devuelven su parte y otros no, y meses después nadie sabe quién debe qué.
- Lo que existe es reactivo o exige trabajo. Los asistentes de los bancos responden si preguntas y Personetics da consejos. Splitwise y Tricount piden instalar otra app y apuntar cada gasto a mano.

## Usuario y comprador
- **Usuario**: el cliente de un banco. Tres perfiles sintéticos: estudiante (comparte gastos), familia (muchos recibos) y autónomo (ingresos variables).
- **Comprador**: bancos medianos y neobancos, que tienen los datos pero no pueden construir algo así dentro. MyInvestor, patrocinador del hackathon, es el ejemplo natural.
- **Por qué paga el banco**: sus clientes usan más su app, evita reclamaciones y puede crear funciones nuevas en días.

## Cómo puntúa en la rúbrica
| Criterio | Peso | Cómo puntuamos alto | Qué enseñamos en la demo |
|---|---|---|---|
| Innovación y viabilidad | 30 | Actúa en lugar de solo avisar; comprador claro; módulos sin código | La cena compartida y un módulo creado en directo |
| IA frontera (lenguaje y audio) | 15 | Detección con razonamiento, llamada de voz con contexto e impacto medible | La llamada y las cifras del panel |
| Experiencia y accesibilidad | 15 | No hay que instalar ni apuntar nada; resolver hablando; pocas interrupciones | Activación, notificación y llamada en 30 segundos |
| Implementación técnica | 30 | Motor en línea, tests, escenarios etiquetados, evals y métricas | El panel del jurado y el repositorio |
| Presentación | 10 | Una historia que todos han vivido y cifras reales | Guion de 3 minutos |

## Competencia
Las fuentes están en `docs/diseno/experiencia.md` (sección 8).

| Alternativa | Qué hace | Qué le falta |
|---|---|---|
| Personetics | Avisos y consejos personalizados para bancos que aprenden de la respuesta | En su web no constan voz ni ejecución de acciones |
| Backbase | Plataforma de banca digital con agentes de IA con permisos definidos por el banco | En su web no constan voz ni proactividad autónoma |
| Asistentes de BBVA, CaixaBank y Santander | Responden, operan cuando se les pide o guían la contratación | Esperan a que preguntes |
| Splitwise y Tricount | Dividen gastos entre amigos | Instalar otra app y apuntar a mano (Tricount solo automatiza con cuenta de bunq) |

En el pitch, con cautela: «en su web no consta» no equivale a «no lo hacen».

## MVP
Lo marca `docs/PLAN.md`: motor en línea con cuatro detectores (gastos compartidos, cobro duplicado, renovación y saldo negativo), personalización con curva de aprendizaje, módulos con acciones confirmadas y uno creado en directo, llamada de voz con modo texto y panel del jurado.

## Riesgos regulatorios
- **AI Act, artículo 50**: el cliente debe saber que habla con una IA. Primera frase fija de la llamada e insignia «IA».
- **Nada de puntuar solvencia** (alto riesgo en el AI Act). La personalización decide cuándo avisar, no qué productos merece alguien.
- **RGPD**: consentimiento por módulo al activar el servicio, transparencia de lo aprendido y derecho a borrarlo. Solo datos sintéticos.
- **Acciones**: simuladas y siempre confirmadas. Bloquear un cobro no da de baja un contrato, y el agente lo explica.
- **Seguros**: si se activa el módulo opcional, solo información con su ficha y sin presionar; distribuirlos de verdad exige un mediador registrado.

## Preguntas abiertas
- Marca y nombre definitivo (los compañeros).
- Minutos de ElevenLabs disponibles para la demo.
- Historias reales de cenas compartidas para los escenarios (entrevistas de los compañeros).
