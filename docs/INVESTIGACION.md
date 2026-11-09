# Investigación

El subagente `investigador` añade aquí una sección por pregunta, con fecha, tabla de opciones y enlaces.

## Punto de partida (7 nov 2026)
| Opción | Qué ofrece | Coste y límites | Enlace |
|---|---|---|---|
| Frankfurter | Tipos de cambio de referencia (BCE y otros bancos centrales) | Gratis y sin clave | https://frankfurter.dev |
| Alpha Vantage | Cotizaciones y datos de mercado; servidor MCP oficial | Clave gratuita, 25 consultas al día | https://www.alphavantage.co/support/ |
| Open banking | Cuentas reales | Proveedor autorizado (PSD2); el acceso gratuito de GoCardless ya no admite altas | https://openbankingtracker.com/guides/free-open-banking-apis |

## Verificación 9 nov (planificar)

Fecha: 9 nov 2026. Pregunta: confirmar con fuentes actuales lo que el diseño dejó sin verificar (voz, Bizum, competencia, cifra para el pitch). Estado por punto: confirmado, distinto de lo que decía el diseño, o sin fuente.

### 1. ElevenLabs Agents
| Punto | Qué dicen las fuentes | Estado | Enlace |
|---|---|---|---|
| `dynamicVariables` en React | La referencia de `@elevenlabs/react` documenta en `startSession` solo `agentId`, `signedUrl`, `conversationToken`, `userId` y `connectionType`; la palabra `dynamicVariables` no aparece. El único ejemplo oficial con `dynamicVariables` usa `Conversation.startSession` de `@elevenlabs/client` (JS sin React). Como `@elevenlabs/react` reexporta `@elevenlabs/client`, probablemente funcione igual, pero no está documentado en React | Distinto de lo que decía el diseño (no confirmado en React). Plan B documentado: llamar a `Conversation` del cliente, o inyectar el contexto vía `overrides` / herramienta del servidor | https://elevenlabs.io/docs/eleven-agents/libraries/react , https://elevenlabs.io/docs/eleven-agents/customization/personalization/dynamic-variables |
| Variables dinámicas (reglas) | Valores string, número o booleano; nombres sensibles a mayúsculas; cada una debe aparecer como `{{nombre}}` en prompt, primer mensaje o herramienta; prefijo `system__` reservado (`system__is_text_only`, `system__time`, etc.) | Confirmado | misma página de variables dinámicas |
| Modo solo texto | `textOnly: true` es opción de `useConversation` (no de `startSession`), o en `overrides.conversation.textOnly`. No pide micrófono ni crea contexto de audio. El agente debe estar configurado para texto | Confirmado, con matiz: va en `useConversation` | https://elevenlabs.io/docs/eleven-agents/libraries/react |
| Plan gratuito | 15 minutos de llamada y 4 llamadas concurrentes. La licencia comercial figura desde el plan Starter, no en el gratuito | Confirmado: 15 min; el gratuito no incluye licencia comercial (una demo ante jurado es de bajo riesgo, pero no publicar la demo abierta) | https://elevenlabs.io/pricing/agents |
| Pago por minuto | Cada plan de pago incluye minutos (Starter 75, Creator 275, Pro 1.238...); adicional 0,08 USD/min; exceso de concurrencia 0,16 USD/min; mensaje de texto 0,003 USD. El coste del LLM se factura aparte según modelo | Confirmado (cifras extraídas de la FAQ; la tabla de la página tiene columnas desalineadas, revisar en el panel antes de pagar) | https://elevenlabs.io/pricing/agents |
| LLM de Claude disponibles | Opus 5.5, Opus 5, Opus 4.8, 4.7, 4.6; Sonnet 5.5, Sonnet 5, 4.6, 4.5; Haiku 4.5. Algunos modelos no están con residencia de datos UE (no dice cuáles) | Confirmado. Ojo: Haiku disponible es 4.5, no «5.5» | https://elevenlabs.io/docs/agents-platform/customization/llm |

### 2. Bizum
| Punto | Qué dicen las fuentes | Estado | Enlace |
|---|---|---|---|
| Solicitud de dinero | Existe: desde la app del banco, sección Bizum, «solicitar», importe y destinatario; el destinatario tiene 7 días para aceptar o rechazar antes de que caduque | Confirmado | https://bizum.com/es/en/send-and-receive-money/ , https://n26.com/es-es/blog/limite-bizum |
| Límite por operación | Mín. 0,50 EUR, máx. 1.000 EUR (Bankinter lo aplica a enviadas y recibidas). El banco puede poner un tope menor (N26: 500 EUR) | Confirmado como cifra habitual; la oficial no aparece en bizum.com, la dan los bancos | https://www.bankinter.com/blog/finanzas-personales/limite-bizum-maximo , https://n26.com/es-es/blog/limite-bizum |
| Límites diario y mensual | 2.000 EUR al día y 5.000 al mes es lo más repetido (Openbank, Bankinter, Bankkers); depende del banco. Una fuente (Tecnobits) da 500/1.500 y no parece fiable | Confirmado con reservas (varía por banco). Sin fuente oficial para límite específico de solicitudes | https://bankkers.com/?p=4036 , https://www.openbank.es/pagar-con-bizum/hacer-bizum-particulares |
| Tope de número de operaciones | Se cita un máximo de 60 cobros o solicitudes al mes; Genbeta no deja claro si cuenta solicitudes o recepciones | Sin fuente clara | https://www.genbeta.com/actualidad/bizum-cambia-hoy-15-junio-sus-condiciones-uso-esto-que-pasara-a-partir-ahora |
| Usuarios y volumen | 30,6 millones de usuarios y 1.237 millones de operaciones en 2025 (+13,2 %), 67.751 millones EUR, 3,4 millones de operaciones al día; previsión 2026 de 32,5 millones de usuarios | Confirmado (nota de prensa de Bizum, enero 2026) | https://bizum.com/es/en/press-area , https://www.infobae.com/espana/agencias/2026/01/19/el-volumen-de-operaciones-con-bizum-crecio-un-53-en-2025-y-se-situo-en-67751-millones/ |

### 3. Competencia
| Opción | Qué ofrece | ¿Detecta solo que falta un reembolso y lo resuelve por voz? | Enlace |
|---|---|---|---|
| Personetics | Más de 300 insights listos (suscripciones similares, alertas de reembolso, irregularidades, recordatorios de recibos) para bancos | No hallado insight de gasto compartido ni voz. Sin fuente de su catálogo completo | https://www.casestudies.com/company/personetics/case-study/dbs-customer-case-study |
| Cleo | Asistente de presupuesto con chat | No: su ayuda dice que no divide transacciones ni gestiona cuentas conjuntas | https://faqs.meetcleo.com/en/articles/1373454-can-i-divide-transactions-in-a-joint-account |
| Bud, Meniga | Categorización e insights para bancos | Sin fuente: la búsqueda no devolvió nada sobre gastos compartidos | sin enlace |
| Splitwise | Libreta de gastos a mano; importar tarjeta es Pro y solo EE. UU.; en Europa, Pay by Bank con Tink (inicia pago, no detecta) | No detecta; hay que apuntar | https://fintech.global/2025/10/20/splitwise-and-tink-expand-pay-by-bank-across-europe/ |
| Tricount (bunq) | Gratis; con bunq, los gastos con tarjeta bunq se añaden solos al tricount (opt-in); reembolsos desde la app en Bélgica con Aion | Lo más cercano: añade el gasto solo, pero solo con tarjeta bunq, y no detecta el reembolso que falta ni lo resuelve por voz | https://help.tricount.com/articles/link-your-bunq-account-in-tricount , https://ffnews.com/newsarticle/tricount-aion-bank-and-mastercard-join-efforts-to-transform-shared-expense-management |
| BBVA España | Grupos de gasto en la app, abierto a no clientes; saldar con Bizum o transferencia desde la app | No: hay que crear el grupo y apuntar el gasto | https://forbes.es/economia/433770/bbva-permite-a-clientes-y-no-clientes-en-espana-utilizar-la-app-para-compartir-gastos/ |
| Revolut | «Dividir factura»: envía una solicitud que el otro acepta o rechaza; el otro debe ser cliente de Revolut | No: el usuario inicia el reparto | https://www.xatakamovil.com/aplicaciones/cada-vez-uso-bizum-revolut-todavia-sencillo-para-dividir-cuenta |
| CaixaBank (imagin) | imagin permite dividir el pago a partes iguales o a mano | Sin fuente sobre CaixaBankNow | https://www.helpmycash.com/blog/no-mas-amigos-morosos-apps-para-dividir-gastos-de-forma-precisa/ |
| Monzo | Running Split y Single Split, iniciados por el usuario | No | https://www.pymnts.com/?p=2516851 |

Conclusión del punto: en las fuentes consultadas, ninguno detecta de forma autónoma, sin apuntar a mano, que un amigo no ha devuelto su parte de un gasto compartido y lo resuelve por voz. Es una ausencia de evidencia, no una prueba: no he podido abrir los catálogos de Personetics, Bud ni Meniga. Estado: confirmado como hueco probable; matizar en el pitch como «no hemos encontrado», no «nadie lo hace».

### 4. Cifra pública para el pitch
| Cifra | Fuente | Estado | Enlace |
|---|---|---|---|
| Hogares españoles gastan 720 EUR al año en suscripciones, 3,2 por hogar; europeos, 696 EUR | Informe de Bango citado por Merca2 (2024) | Sin fuente primaria verificada; sirve como orden de magnitud | https://www.merca2.es/2024/06/18/telefonica-clientes-suscripciones-1712442/ |
| 37 % de las webs comerciales analizadas usaban patrones oscuros (manipulación, incluida la dirección hacia suscripciones) | Barrido de la Comisión Europea y 23 autoridades nacionales, 2023 | Confirmado por prensa; no es cifra de suscripciones olvidadas | https://brusselstimes.com/361958/eu-nearly-40-of-online-shops-manipulate-consumers |
| Cobros duplicados en España o UE | No encontré ninguna cifra pública | Sin fuente | |

## Recomendación
1. Voz: pasar las variables con `Conversation.startSession({ dynamicVariables })` de `@elevenlabs/client`, o probarlo primero con `useConversation` en 10 minutos; el plan B es contexto vía herramienta del servidor. Ensayar con `textOnly: true`; reservar los 15 minutos gratuitos para la demo.
2. Bizum: modelar la «solicitud» (7 días para aceptar o rechazar, 0,50 a 1.000 EUR, 2.000 al día como tope por defecto). Declararlo en el simulador como «valores habituales; cada banco fija los suyos».
3. Pitch: «Tricount y los bancos exigen apuntar el gasto; el Copiloto lo detecta y reclama por ti». Usar 720 EUR en suscripciones solo con «según Bango».

## Lo que no he podido confirmar
- `dynamicVariables` como opción de `startSession` en `@elevenlabs/react` (comprobar con el tipo en `node_modules`).
- Límite oficial de Bizum para solicitudes y si el tope de 60 incluye solicitudes.
- Catálogos de Personetics, Bud, Meniga y CaixaBankNow sobre gastos compartidos.
- Cifra pública y verificable de cobros duplicados.
- Si el plan gratuito de ElevenLabs permite una demo pública (solo consta que la licencia comercial empieza en Starter).
