# Guion de la demo (Pablo, 3 minutos)

Planteamiento y frases en `docs/PRESENTACION.md`. Escenario: `demo-pablo` (`backend/escenarios/demo-pablo.yaml`); lo prueban los tests de `tests/test_demo_pablo.py`. Pablo es un estudiante de Madrid con datos inventados.

- Demo pública: https://hack-finance.vercel.app (abre directamente `/app`).
- Backend: https://meisam-api.onrender.com (comprobar con `/salud`).

## Antes de empezar
- [ ] **Abrir la app 2-3 minutos antes.** El plan gratuito de Render duerme y tarda ~1 minuto en despertar. Abre también https://meisam-api.onrender.com/salud hasta que responda.
- [ ] Probar los **auriculares** y el micrófono (permiso del navegador concedido) con una llamada corta.
- [ ] Navegador con zoom al 125 %, notificaciones del sistema silenciadas, vista de móvil si cabe.
- [ ] La app en el estado inicial: pantalla «Activa Meisam». Si ya hay una demo empezada, pulsa **Reiniciar escenario** al final de `/app`.
- [ ] Vídeo de respaldo abierto en otra pestaña.

## Pasos
| # | Qué hago | Qué debe verse | Tiempo |
|---|---|---|---|
| 1 | **Activar Meisam.** Dejo marcados los módulos que vienen marcados, acepto el consentimiento y pulso «Activar». | Saldo de la cuenta y la fecha simulada (domingo 1/11). Insignia «IA» y aviso fijo al pie. | 15 s |
| 2 | **Avanzar hasta el lunes 9/11** con la barra de varios días (se arrastra y avanza al soltar) o con «Reproducir». | Llega la notificación **«¿Fuiste con alguien a Kinepolis Ciudad de la Imagen?»** con el texto «32,70 € en Kinepolis Ciudad de la Imagen el sábado: parecen 3 entradas. ¿Fuiste con alguien?». | 25 s |
| 3 | **Abrir «Ver todos los motivos»** (el «por qué» del aviso). | Dos combinaciones posibles de precios. La IA ve más probable 3 entradas (80 %). La fuente es taquilla.com. Solo salió a internet el nombre del comercio. Digo: «Nunca el importe ni datos del cliente». | 20 s |
| 4 | **Responder** con un toque («Sí, con…») o **abrir la llamada**. | La llamada empieza con «Hola Pablo, sobre tu aviso: …» y la insignia «IA» visible. | 20 s |
| 5 | **Avanzar al martes 10/11.** | Notificación de las pizzas de **Pizzeria Mamma Rosa**: 52 € entre cuatro, Rodrigo e Irene ya pagaron, falta **Nacho (13 €)**. | 15 s |
| 6 | Pulsar **«Pedir Bizum»** y luego **«Confirmar»**. | Botón y token de un solo uso; acción simulada, queda auditada. Digo: «Nada se mueve sin mi botón». | 15 s |
| 7 | **Avanzar al miércoles 11/11.** | Entra el Bizum de Nacho, el caso queda **«Saldado»** y el saldo sube 13 €. | 15 s |
| 8 | **«Hablar con Meisam»** (voz o chat). Digo: **«La cena del viernes en El Búho la pagué yo, era con Sergio»**. | Meisam apunta que **Sergio debe 17,30 €** y muestra «Apuntado…» con **«Deshacer»**. | 30 s |
| 9 | **«Lo que he aprendido de ti».** | Lo que Meisam sabe de Pablo: se ve, se edita y se borra. | 15 s |
| 10 | **Remate.** Abro «Movimientos». | Cafetería, súper, metro, farmacia y Primark no activaron nada. Cierro: **«Dos avisos en dos semanas. Los dos, con dinero en juego».** | 10 s |

Total: unos 3 minutos con margen.

### Consejos para que salga bien
- En el paso 8 **nombra el comercio** («en El Búho»): así Meisam encuentra el pago. Con una frase vaga puede pedirte aclaración.
- Si cambias un caso por voz, di el nombre completo del amigo: **«Sergio M.»**.
- Habla despacio y frases cortas; los auriculares evitan que el micrófono recoja la voz del agente.
- La barra de días avanza **al soltar**: no la sueltes antes de llegar a la fecha que quieres.

## Plan B
1. **Falla la voz** (micrófono, permisos o sin minutos de ElevenLabs): usa el **chat de texto** de «Hablar con Meisam». Es el mismo agente con las mismas herramientas.
2. **La app tarda o no responde:** el backend está despertando. Espera ~1 minuto, recarga y abre `/salud` para ver cuándo responde.
3. **Algo se descuadra** (fecha pasada, aviso repetido, caso ya saldado): pulsa **«Reiniciar escenario»** (al final de `/app`) y activa de nuevo. Si no se ve el botón: recarga la página y activa de nuevo.
4. **Falla todo:** pon el **vídeo de respaldo** (pestaña abierta) y cuenta el guion sobre él.
5. **Sin internet en la sala:** demo en local (abajo), con el móvil como punto de acceso si hace falta.

## Demo en local
Requisitos: Python 3.11, Node.js 20 o superior y un `.env` con las claves (copia de `.env.example`; nunca se sube a git).

**Backend** (desde la raíz del repositorio):
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # rellena ANTHROPIC_API_KEY_PRODUCTO, ELEVENLABS_API_KEY y ELEVENLABS_AGENT_ID
uvicorn backend.api.main:app --reload
```
Comprobación: http://localhost:8000/salud responde 200.

**Frontend** (otra terminal):
```bash
cd frontend
npm install
cp .env.example .env.local           # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                          # http://localhost:3000, abre /app
```
- Si en el backend pones `DEMO_KEY`, pon el mismo valor en `NEXT_PUBLIC_DEMO_KEY` (en `.env.local`). Sin `DEMO_KEY` se permite todo en local.
- Si cambias `NEXT_PUBLIC_*`, reinicia `npm run dev`.
- Sin claves de Claude o ElevenLabs el recorrido de los avisos funciona, pero no la llamada ni el chat.

## Guion del vídeo de respaldo (máx. 3 minutos)
Grabar la pantalla de https://hack-finance.vercel.app con voz en off y la voz de Meisam audible. Mismos pasos que la demo.

| Tiempo | Pantalla | Voz en off |
|---|---|---|
| 0:00-0:15 | Portada y activación. «Activar». | «Pagas por varios y el dinero no vuelve solo. Meisam vive dentro de la app del banco y ve tus pagos y tus Bizums.» |
| 0:15-0:40 | Avanzar al lunes 9/11. Notificación del cine. | «Sábado, 32,70 € en Kinepolis. El lunes me pregunta si fui con alguien: parecen 3 entradas.» |
| 0:40-1:00 | «Ver todos los motivos». | «Me explica por qué: dos combinaciones posibles, la más probable es de 3 entradas. A internet solo salió el nombre del cine.» |
| 1:00-1:20 | Abrir la llamada. Se oye «Hola Pablo, sobre tu aviso…». | «Se abre una llamada de voz. La insignia IA se ve siempre.» |
| 1:20-1:50 | Martes 10/11: pizzas. «Pedir Bizum» y «Confirmar». Miércoles 11/11: «Saldado» y saldo +13 €. | «Pagué las pizzas de cuatro. Falta Nacho: 13 €. Pido el Bizum con un toque. Al día siguiente entra y el caso se cierra solo.» |
| 1:50-2:25 | «Hablar con Meisam»: «La cena del viernes en El Búho la pagué yo, era con Sergio». «Apuntado» y «Deshacer». | «Y si se me ha pasado una cena, se lo digo hablando. Sergio me debe 17,30 €. Todo se puede deshacer.» |
| 2:25-2:40 | «Lo que he aprendido de ti». | «Lo que aprende de mí se ve, se edita y se borra.» |
| 2:40-3:00 | «Movimientos»: cafetería, súper, metro, farmacia, Primark. | «El resto de pagos no activó nada. Dos avisos en dos semanas, los dos con dinero en juego. Datos sintéticos, acciones simuladas, la IA no da asesoramiento financiero.» |
