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
