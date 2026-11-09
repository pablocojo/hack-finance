# Despliegue

Desplegar el primer día y volver a desplegar cada día: el último día no hay tiempo para sorpresas.

## Backend en Render
1. Sube el repositorio a GitHub (sin `.env`).
2. En Render: New → Blueprint → elige el repositorio. Usa `render.yaml`.
3. Variables de entorno en Render: `ANTHROPIC_API_KEY_PRODUCTO` (clave 2), `ORIGENES_CORS` (la URL de Vercel, por ejemplo `https://tu-app.vercel.app`), `NOMBRE_PRODUCTO` y, para la demo, `MODO_DEMO=reproducir`.
4. Comprueba `https://<tu-backend>.onrender.com/salud`.

Los planes gratuitos se duermen tras un rato sin uso: abre `/salud` 5 minutos antes de presentar.

## Alternativa con Docker
`docker build -t agente-finanzas . && docker run -p 8000:8000 --env-file .env agente-finanzas`. Sirve en Railway, Fly.io o cualquier servicio que acepte un `Dockerfile`.

## Frontend en Vercel
1. New Project → el repositorio → Root Directory: `frontend`.
2. Variable: `NEXT_PUBLIC_API_URL=https://<tu-backend>.onrender.com`.
3. Deploy. Si cambias la variable, vuelve a desplegar (se fija al compilar).

## Comprobación final
- [ ] La web carga los datos de ejemplo.
- [ ] Una pregunta responde en streaming y la traza aparece.
- [ ] Subir un CSV de `datos_ejemplo/` funciona.
- [ ] El aviso de IA se ve en la cabecera y en el pie.

## Meisam (9 nov): variables nuevas y comprobación

**Render** (backend, servicio `meisam-api` del `render.yaml`). Rellenar a mano en *Environment*, nunca en git:
- `ANTHROPIC_API_KEY_PRODUCTO` (clave 2), `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`.
- `DEMO_KEY`: una cadena inventada y larga; protege las rutas que cambian datos (no es seguridad real: el frontend la envía).
- `ORIGENES_CORS`: la URL de Vercel, sin barra final (varias, separadas por comas).
- Ya vienen en el blueprint: `PYTHON_VERSION=3.11.9`, `NOMBRE_PRODUCTO=Meisam`, `MODO_DEMO=off`, `BUSQUEDA_WEB=off`.
- El disco del plan gratuito es efímero: tras un reinicio se pierden los usuarios; `POST /demo/cargar` los vuelve a crear. El primer arranque tras un rato dormido tarda ~1 minuto.

**Vercel** (frontend, *Root Directory* `frontend`):
- `NEXT_PUBLIC_API_URL`: la URL de Render (`https://meisam-api-xxxx.onrender.com`, sin barra final).
- `NEXT_PUBLIC_DEMO_KEY`: el mismo valor que `DEMO_KEY`.
- Las `NEXT_PUBLIC_*` se incrustan al compilar: si cambian, hay que volver a desplegar.

**Comprobación**: `GET /salud` responde 200; `GET /escenarios` lista `cena-lucia`; en `/app` de Vercel, «Cargar» y «Avanzar un día» hasta el 9/11 muestran el aviso de la cena; `GET /metricas/motor` devuelve la línea base.

**URL públicas (9 nov)**: frontend https://hack-finance.vercel.app · backend https://meisam-api.onrender.com
