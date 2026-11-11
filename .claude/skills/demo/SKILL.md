---
name: demo
description: Prepara la entrega y la presentación. Congelación, revisión final, evals, despliegue, grabación del modo demo, guion, README, vídeo de respaldo y plan B.
disable-model-invocation: true
---

# /demo

## 1. Congelar (11 nov, 14:00)
Desde aquí solo arreglos. Anótalo en `docs/PLAN.md`.

## 2. Revisión final en paralelo
- `revisor`: todo el cambio desde el kickoff (`git diff <commit del kickoff>`).
- `experto-finanzas`: las cifras y los textos legales que salen en la demo.
- `evaluador`: `/evals` completo.
Arregla todo lo que sea `BLOQUEA` con `/feature`.

## 3. Desplegar (lista de comprobación)
- [ ] Backend en Render con `render.yaml` (o Docker con el `Dockerfile`). Variables: `ANTHROPIC_API_KEY_PRODUCTO`, `ORIGENES_CORS=<url del frontend>`, `MODO_DEMO=reproducir`, `NOMBRE_PRODUCTO`.
- [ ] Frontend en Vercel con la carpeta `frontend/` como raíz y `NEXT_PUBLIC_API_URL=<url del backend>`.
- [ ] Prueba la URL pública de principio a fin desde otro dispositivo.
- [ ] El día de la presentación, abre el backend 5 minutos antes: los planes gratuitos se duermen.

## 4. Grabar el modo demo (plan B sin red ni API)
1. `MODO_DEMO=grabar uvicorn backend.api.main:app` en local.
2. Haz exactamente las preguntas del guion de `docs/DEMO.md`.
3. Commit de `demo/grabaciones/`. Con `MODO_DEMO=reproducir`, esas preguntas se responden sin llamar a la API y las demás, en directo.

## 5. Historia y documentos (`pitch`)
`docs/PRESENTACION.md`, `docs/DEMO.md`, `README.md` y el guion del vídeo, con cifras reales de `python scripts/informe_agentes.py`, de los evals y de los tests.

## 6. Vídeo de respaldo
El usuario graba 2 minutos siguiendo el guion (OBS, QuickTime o la grabación de pantalla del sistema). Guárdalo fuera del repositorio y súbelo donde pidan las bases.

## 7. Entrega
- [ ] Repositorio con README, licencia si la piden y sin `.env`.
- [ ] URL pública, vídeo y diapositivas donde pidan las bases.
- [ ] Etiqueta `git tag v1.0` en el commit entregado.
- [ ] Dos ensayos cronometrados con los compañeros, con preguntas del jurado.
