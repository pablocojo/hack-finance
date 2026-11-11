# Meisam

**Meisam es un extra para apps de gastos compartidos (Splitwise, Tricount) que vive dentro de la app del banco: ve tus pagos y tus Bizums, te avisa en el momento justo y lo resuelve con un toque o hablando.**

Pagas por varios y el dinero no vuelve solo. Meisam sabe quién falta y cuánto, te lo cuenta solo si hay dinero en juego y cierra el caso cuando llega el Bizum. Proyecto del hackathon Hack Finance (BEST UC3M, noviembre de 2026).

## Enlaces
- **Demo pública:** https://hack-finance.vercel.app (abre directamente la app del cliente). Backend: https://meisam-api.onrender.com. El servidor gratuito tarda ~1 minuto en despertar la primera vez.
- **Qué funciona hoy y cómo presentarlo:** [`docs/PRESENTACION.md`](docs/PRESENTACION.md)
- **Guion de la demo, plan B y vídeo:** [`docs/DEMO.md`](docs/DEMO.md)

## Qué funciona hoy
- **Gastos compartidos:** detecta los Bizums que llegan, quién falta y cuánto (pizzas: «Falta Nacho, 13 €»).
- **Cine con búsqueda web:** solo el nombre del comercio sale a internet; el código estima cuántos fuisteis.
- **Preguntas de un toque** («Sí, con…», «Iba solo», «Nadie me debe») y **«Pedir Bizum»** con botón y token de un solo uso. El caso se cierra solo cuando llega el pago.
- **Chat y voz con ElevenLabs:** apuntar un gasto con tus palabras, consultar y cambiar casos, todo con «Deshacer».
- **Resumen semanal** y **«Lo que he aprendido»**: se ve, se edita y se borra.
- **Cumplimiento:** insignia «IA» visible, datos personales enmascarados, acciones de una lista cerrada y revisor de cumplimiento.

El banco, el Bizum y el reloj son **simulados**. Hoy no hay conexión real con Splitwise ni Tricount.

## Requisitos
- Python 3.11 y Node.js 20 o superior.
- Claves de Claude (Anthropic) y de ElevenLabs (agente de voz y chat). Sin ellas, los avisos funcionan pero no la llamada ni el chat.

## Arrancar en local
Backend, desde la raíz del repositorio:
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # rellena tus claves (ver «Configuración»)
uvicorn backend.api.main:app --reload
```
Frontend, en otra terminal:
```bash
cd frontend
npm install
cp .env.example .env.local           # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```
Abre http://localhost:3000 (redirige a `/app`). El backend responde en http://localhost:8000/salud. Después, sigue [`docs/DEMO.md`](docs/DEMO.md).

## Configuración
Variables de entorno. Los valores van solo en `.env` y `.env.local` (no se suben a git) o en el panel de Render y Vercel; nunca en el código.

| Variable | Dónde | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY_PRODUCTO` | backend | Clave de Claude del producto |
| `ELEVENLABS_API_KEY` | backend | Clave de ElevenLabs |
| `ELEVENLABS_AGENT_ID` | backend | Agente de voz de ElevenLabs |
| `DEMO_KEY` | backend | Cadena inventada que protege las rutas que cambian datos; opcional en local |
| `NEXT_PUBLIC_API_URL` | frontend | URL del backend (por defecto `http://localhost:8000`) |
| `NEXT_PUBLIC_DEMO_KEY` | frontend | El mismo valor que `DEMO_KEY` |

El resto de variables opcionales están en `.env.example`. Las claves de Claude y de ElevenLabs solo viven en el backend. Despliegue en Render y Vercel: [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).

## Cómo se verifica
```bash
pytest -q                                          # tests, sin gastar crédito
python evals/medir.py --parte motor                # métricas del motor de detección
python evals/ejecutar.py --conjunto llamada        # evals del agente de la llamada (gasta crédito)
python evals/ejecutar.py --conjunto llamada --simulado   # lo mismo con cliente falso, sin crédito
```
Los tests de la demo están en `tests/test_demo_pablo.py` (fechas, avisos, pedir Bizum y cierre del caso, también por HTTP). Los resultados de los evals se guardan en `evals/resultados/`.

## Cómo funciona
```
App del cliente (Next.js) → API (FastAPI) → motor de detección → decisión de avisar (portero)
                                         → agente de voz y chat (Claude + ElevenLabs) → acciones simuladas
```
- El **motor** procesa los movimientos día a día con un reloj simulado y convierte lo que pasa en «momentos».
- **El código calcula y Claude razona:** el dinero va con `Decimal`; los modelos clasifican, razonan y explican, nunca hacen cuentas.
- Solo avisa si ahorra dinero o protege, y cada decisión lleva sus motivos legibles.
- Las acciones salen de una **lista cerrada**: el agente las prepara y se ejecutan con tu botón y un token de un solo uso, validado en el servidor.

## Estructura
```
backend/     API, motor, escenarios (demo-pablo.yaml), personalización, módulos, acciones y voz
frontend/    Next.js: /app (cliente), /banco (consola), /jurado (métricas), /kit (chat del kit)
evals/       evals del agente (ejecutar.py) y métricas del motor (medir.py)
tests/       pytest con cliente simulado
docs/        PRESENTACION, DEMO, ARQUITECTURA, PLAN, DECISIONES, DIARIO, IDEAS…
.claude/     subagentes y skills con los que se ha construido
```

## Cómo hemos trabajado con Claude
- Un solo desarrollador con **Claude Code como orquestador** y subagentes especializados (detección, personalización, módulos, voz, banca, usuarios, tests, evals, revisión y pitch), más skills con nuestro flujo de trabajo (`.claude/agents/` y `.claude/skills/`).
- **Revisión con el contexto limpio:** un revisor de seguridad y un crítico de necesidad que juzga sin conocer nuestra historia.
- **Memoria entre días** en `docs/DIARIO.md`, decisiones en `docs/DECISIONES.md`, plan con estado en `docs/PLAN.md` y un hook que registra cada subagente (`python scripts/informe_agentes.py`).
- Los compañeros aportaron entrevistas, ideas, marca y pruebas de usuario (`docs/IDEAS.md`).
- Detalle y cifras en [`docs/PRESENTACION.md` §6](docs/PRESENTACION.md).

## Aviso y limitaciones
- **Datos sintéticos.** No hay datos personales reales.
- **Acciones simuladas.** Banco y Bizum son simulados; no se mueve dinero real.
- **La IA no da asesoramiento financiero.** La información es orientativa; Meisam no recomienda productos ni puntúa la solvencia de nadie.
- Las notificaciones son dentro de la app (no hay Web Push real).
- En el plan gratuito de Render el disco es efímero: si el servidor se reinicia se pierden los datos de la demo y hay que activar de nuevo.
- Pendiente: conexión real con Splitwise o Tricount, planes grandes de 8-12 personas, deudas en efectivo y validar lo que aprende de cada persona con usuarios reales. Más en `docs/PRESENTACION.md` §7.
