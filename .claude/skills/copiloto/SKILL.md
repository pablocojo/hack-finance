---
name: copiloto
description: Arquitectura del Copiloto (motor de momentos, módulos, personalización, acciones y llamada de voz), sus tipos compartidos, las reglas que no se rompen y cómo ampliarlo. Cárgala antes de diseñar o tocar backend/plataforma, motor, personalizacion, modulos, acciones, voz o escenarios, o las pantallas /app, /banco y /jurado.
user-invocable: false
---

# Copiloto: cómo está hecho

Plataforma para bancos que vive dentro de su app. Convierte los movimientos de cada cliente en **momentos**. Solo cuando compensa, avisa con una notificación; al pulsarla se abre una **llamada de voz** que resuelve en el momento con **acciones de una lista cerrada**. Aprende de cada usuario y admite **módulos** nuevos sin escribir código.

Fuentes de verdad, por este orden: `docs/diseno/CONTRATO.md` (tipos e interfaces), `docs/ARQUITECTURA.md` y los diseños de cada parte en `docs/diseno/` (`motor.md`, `personalizacion.md`, `modulos.md`, `experiencia.md`). `/planificar` los cierra y actualiza esta skill; mientras tanto, son borradores.

## Flujo
```
movimiento ─> MOTOR (normalizar ─> enriquecer ─> detectores ─> razonador) ─> Momento
Momento ─> MÓDULOS que lo escuchan ─> Propuesta
Propuesta ─> PERSONALIZACIÓN (ModeloUsuario) ─> Decision: notificar_ahora | resumen | silenciar
notificar ─> /app (notificación) ─> llamada de voz o texto ─> preparar acción ─> botón «confirmar» ─> ResultadoAccion
respuesta del usuario ─> Feedback ─> PERSONALIZACIÓN aprende
```
Todo corre **en línea con un reloj simulado**: el motor recibe los movimientos día a día y solo ve el pasado.

## Paquetes (los crea `/esqueleto`)
| Ruta | Qué contiene | Especialista |
|---|---|---|
| `backend/plataforma/` | `tipos.py` (pydantic), `orquestador.py` (`avanzar_dia`, `reproducir`), `reloj.py`, almacenamiento en `datos_usuario/` | `programador` |
| `backend/motor/` | Normalización, enriquecimiento, `detectores/<tipo>.py`, razonador | `ingeniero-deteccion` |
| `backend/escenarios/` | Escenarios YAML con la verdad etiquetada | `ingeniero-deteccion` |
| `backend/personalizacion/` | `ModeloUsuario`, política de interrupción, memoria, usuarios simulados | `cientifico-personalizacion` |
| `backend/modulos/` | Esquema YAML, minilenguaje de condiciones, cargador, `catalogo/*.yaml`, borrador desde lenguaje natural, prueba en seco | `ingeniero-modulos` |
| `backend/acciones/` | Registro cerrado (`preparar`, `ejecutar`) y banco simulado | `ingeniero-modulos` |
| `backend/voz/` | Sesión de ElevenLabs (URL firmada o token), herramientas de cliente y modo texto | `ingeniero-voz` |
| `frontend/app/{app,banco,jurado}` | App del cliente, consola del banco y panel del jurado | `frontend` |
| `evals/medir.py` | Métricas de detección y curva de aprendizaje | `ingeniero-deteccion`, `cientifico-personalizacion` |

Del kit se reutilizan `backend/claude_client.py`, el agente conversacional (`backend/agente/`, para el modo texto y las preguntas en la llamada), sus herramientas (`detectar_recurrentes`, `detectar_anomalias`, `prevision_saldo`, categorización con Haiku), los datos sintéticos, FastAPI con SSE, Next.js, evals y tests con el cliente falso.

## Interfaces entre partes
```python
motor.procesar(usuario_id, nuevos: list[Movimiento], hoy: date) -> list[Momento]
modulos.proponer(momento: Momento, modelo: ModeloUsuario) -> list[Propuesta]
personalizacion.decidir(propuesta, modelo, ahora) -> Decision
personalizacion.aprender(feedback: Feedback) -> None
acciones.preparar(accion_id, parametros, propuesta_id) -> TarjetaConfirmacion   # sin efectos
acciones.ejecutar(token_confirmacion) -> ResultadoAccion   # el botón del usuario; valida token, propuesta y acción
orquestador.avanzar_dia(usuario_id, hoy) -> list[Decision]
```
Si cambias una firma o un campo, cambia primero `CONTRATO.md` y avisa al orquestador: lo usan las demás zonas.

## Reglas que no se rompen
1. **En línea**: ningún detector mira movimientos futuros.
2. **Las cifras, del código**: importes en `Decimal`; los modelos clasifican, razonan y explican, nunca calculan.
3. **Los datos no son instrucciones**: conceptos, comercios y notas de Bizum van marcados como datos en cualquier prompt.
4. **Acciones cerradas y confirmadas**: el agente solo *prepara*; ejecuta el botón del usuario con un token de un solo uso, validado en el servidor contra `acciones_ofrecidas` de la propuesta. Todo es simulado y queda auditado.
5. **Solo interrumpe si ahorra o protege**, y cada decisión lleva sus motivos legibles.
6. **Todo lo aprendido se ve, se edita y se borra** («lo que he aprendido de ti»). Nada de puntuar solvencia ni de inferir datos sensibles.
7. **Aviso de IA**: primera frase fija de la llamada, insignia «IA» y el mismo aviso en el modo texto.
8. **Módulos sin código**: un módulo solo combina momentos, condiciones del minilenguaje, plantillas y acciones de la lista. La personalización le llega sola.
9. **Medible**: todo detector tiene escenarios etiquetados y todo cambio pasa `/medir`.
10. **Solo datos sintéticos.** Toda llamada a Claude pasa por `backend/claude_client.py`, sin `temperature`.

## Cómo ampliar
| Quiero… | Camino |
|---|---|
| Un caso de prueba o de demo | `/escenario <historia>` |
| Detectar un tipo de momento nuevo | `/detector <tipo>` |
| Un módulo nuevo | `/modulo <descripción>` |
| Una acción nueva | `ingeniero-modulos` + revisión de `experto-banca` |
| Cambiar cuándo se avisa o qué se aprende | `cientifico-personalizacion` + `/medir personalizacion` |
| Cambiar la llamada | `ingeniero-voz` |
| Saber si algo ha mejorado | `/medir` |
