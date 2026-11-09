---
name: copiloto
description: Arquitectura del Copiloto (motor de momentos, módulos, personalización, acciones y llamada de voz), sus tipos compartidos, las reglas que no se rompen y cómo ampliarlo. Cárgala antes de diseñar o tocar backend/plataforma, motor, personalizacion, modulos, acciones, voz o escenarios, o las pantallas /app, /banco y /jurado.
user-invocable: false
---

# Copiloto: cómo está hecho

Plataforma para bancos que vive dentro de su app. Convierte los movimientos de cada cliente en **momentos**. Solo cuando compensa, avisa con una notificación; al pulsarla se abre una **llamada de voz** que resuelve en el momento con **acciones de una lista cerrada**. Aprende de cada usuario y admite **módulos** nuevos sin escribir código.

Fuentes de verdad, por este orden: `docs/diseno/CONTRATO.md` (tipos e interfaces), `docs/ARQUITECTURA.md` y los diseños de cada parte en `docs/diseno/` (`motor.md`, `personalizacion.md`, `modulos.md`, `experiencia.md`). Diseño **cerrado** el 9 nov (`/planificar`). Si hay contradicción, mandan las secciones finales de `CONTRATO.md` («Decisiones de /planificar», «Cambios aceptados», «Revisión de experto-banca» y «Revisión final»). Las tareas están en `docs/PLAN.md`.

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
motor.cargar_historial(usuario_id, historial, hoy); motor.exportar_estado / importar_estado / reiniciar
personalizacion.aprender(feedback, modelo) -> ModeloUsuario   # pura: no guarda
acciones.preparar(accion_id, parametros, propuesta_id) -> TarjetaConfirmacion   # sin efectos
acciones.ejecutar(token_confirmacion) -> ResultadoAccion   # valida token, usuario, propuesta, acción y limites
modulos.crear_borrador / probar_en_seco / aprobar;  voz.sesion(propuesta_id, modo_preferido) -> SesionVoz
orquestador.avanzar_dia(usuario_id, hoy, ahora=None) -> list[Decision]   # ahora por defecto: hoy 20:30
orquestador.reproducir(usuario_id, dias, pausar_en=None) -> eventos dia | momento | propuesta | decision
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

## Decisiones cerradas (9 nov)
- **Detectores del MVP** (deterministas, pandas y `Decimal`; explicación por plantilla): `gasto_compartido` (estrella: cena de Lucía en «La Tasca», 120 €, tres Bizums de 24 €, falta Marcos), `cargo_duplicado`, `renovacion_proxima`, `saldo_negativo_previsto`, `subida_recibo`. Importes de `Momento.datos` en positivo; `ids` por fecha.
- **Módulos del catálogo**: `cena_compartida`, `cobro_duplicado`, `renovacion`, `colchon`; en directo, el banco crea `recibo_al_alza` (escucha `subida_recibo`).
- **Acciones (lista cerrada)**: `pedir_bizum` (solicitud que el otro acepta), `bloquear_comercio` (no cancela el contrato; no se ofrece para duplicados), `reclamar_cargo` (recibo: devolución SEPA 8 semanas; tarjeta: reclamación), `mover_dinero`, `preparar_baja`, `recordar`. Token de un solo uso, 10 min, ligado al hash de parámetros; **nunca llega a ningún modelo**.
- **Personalización**: Beta-Bernoulli jerárquica (global → tipo → tramo → comercio o contacto) y U = q·B − (1−q), con reglas duras antes (consentimiento, solo ahorra o protege, silencios, horario, 2 avisos al día). La protección nunca se silencia por aprendizaje. Aprende por tipo de momento: un módulo nuevo hereda lo aprendido.
- **Persistencia**: JSON por usuario en `datos_usuario/`; solo el orquestador escribe (vía `almacenamiento.py`).
- **Terceros**: nunca se valora a otra persona; amigos con nombre enmascarado, estado y saldo, borrados al saldarse o a los 90 días. Las notas de Bizum no salen del motor. Marcador único de datos: `<datos>…</datos>`.
- **Voz**: ElevenLabs con herramientas de cliente y primer mensaje fijo con el aviso de IA; plan B por niveles (texto con ElevenLabs, texto con el agente del kit en `/voz/texto`, vídeo grabado). La clave solo en el backend.
- **API**: un router por zona; endpoints en `docs/ARQUITECTURA.md` §3; dinero como cadena en JSON; `X-Demo-Key` en rutas que reinician o gastan.
