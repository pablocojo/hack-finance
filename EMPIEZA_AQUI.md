# Empieza aquí

Kit v2 del hackathon: Claude Code de serie con 11 subagentes, 11 skills y hooks, más un agente de finanzas con IA que ya funciona de principio a fin (backend FastAPI, web Next.js, panel Streamlit, evals y tests). El razonamiento completo está en el documento "Plan maestro del hackathon".

Cómo se usa en una frase: hablas con la sesión principal de Claude Code (Opus 5.5), lanzas una skill (`/kickoff`, `/feature`…) y ella delega en el subagente adecuado y guarda la memoria del proyecto en `docs/`.

## Hoy, 7 de noviembre (unas 3 horas)

### 1. Repositorio
```bash
unzip hack-finance.zip && cd hack-finance
git init && git add . && git commit -m "kit v2"
# Crea un repositorio privado en GitHub y súbelo (con gh o desde la web):
gh repo create hack-finance --private --source . --push
```

### 2. Claude Code
```bash
curl -fsSL https://claude.ai/install.sh | bash      # macOS y Linux
irm https://claude.ai/install.ps1 | iex             # Windows (PowerShell)
claude doctor
```

### 3. Claves (cada una con su uso)
- **Clave 1 → Claude Code**, en la variable de entorno del sistema:
  - macOS/Linux: añade `export ANTHROPIC_API_KEY="sk-ant-..."` a `~/.zshrc` o `~/.bashrc` y abre otra terminal.
  - Windows: `setx ANTHROPIC_API_KEY "sk-ant-..."` y abre otra terminal.
  - La primera vez, Claude Code pregunta si usar esa clave: di que sí.
- **Claves 2 y 3 → producto y evals**: `cp .env.example .env` y rellena `ANTHROPIC_API_KEY_PRODUCTO` y `ANTHROPIC_API_KEY_EVALS`.
- Claves 4 a 6: en el gestor de contraseñas, de reserva.

### 4. Entorno
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd frontend && npm install && cp .env.example .env.local && cd ..
```

### 5. Comprobar
```bash
python scripts/comprobar_entorno.py   # dice qué falta, sin mostrar claves
pytest                                # todo en verde, sin gastar crédito
python scripts/probar_api.py          # una llamada real (menos de un céntimo)
python scripts/probar_api.py --agente # opcional: una pregunta completa al agente (céntimos)
```

### 6. Arrancar todo (tres terminales)
```bash
uvicorn backend.api.main:app --reload          # API en http://localhost:8000/docs
cd frontend && npm run dev                     # web en http://localhost:3000
streamlit run panel/app.py                     # panel interno
```
Haz una pregunta de prueba en la web ("¿Ves algo raro en mis cargos?").

### 7. Plugins oficiales
Dentro de `claude`:
```
/plugin install frontend-design@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
```

### 8. Cuentas de despliegue
Crea cuenta en Render (backend) y Vercel (frontend) y conecta el repositorio. Pasos en `docs/DESPLIEGUE.md`.

### 9. Ensayo de una hora (en una rama que luego se borra)
```bash
git switch -c ensayo
cp reto/EJEMPLO_RETO.md reto/RETO.md
claude
```
Dentro: `/kickoff`, después una `/feature` del plan y al final `/cierre-dia`. Fíjate en que los subagentes arrancan, en que el hook de inicio enseña el diario y en lo que gasta (`/usage`). Al terminar:
```bash
git add -A && git commit -qm "ensayo"          # por si quedó algo sin guardar
git switch main && git branch -D ensayo && rm -f registro/agentes.jsonl
```

### 10. Compañeros y bases
- Envía `docs/COMPANEROS.md` a los compañeros (tareas, fechas y prompts para usar con Claude).
- Lee las bases y pregunta a la organización: si se puede llegar con código hecho y si las claves comparten saldo y límites.

## Mañana, 8 de noviembre
1. **8:30** Portátil cargado, red probada, `git pull` y `claude` abierto en `main`.
2. **9:00** Pega el enunciado literal en `reto/RETO.md` (borra la línea PLANTILLA).
3. **9:00-10:00** Lluvia de ideas con los compañeros en `docs/IDEAS.md`.
4. **10:00** `/kickoff`.
5. **Antes de las 13:00** Idea y MVP cerrados.
6. **Tarde** Esqueleto de principio a fin con 2 o 3 sesiones en paralelo.
7. **Noche** Primer despliegue, `/evals` como línea base y `/cierre-dia`.

## Rutina de cada día
1. Por la mañana: `/estado` y elegir 2 o 3 tareas que no toquen los mismos archivos.
2. Una sesión por tarea, cada una en su terminal:
   ```bash
   claude --worktree backend
   claude --worktree frontend
   ```
   y en cada una `/feature <id de la tarea>`.
3. Al terminar una tarea: commit en el worktree y, desde `main`, `git merge <rama del worktree>` (el nombre sale en `git worktree list`) con los tests en verde.
4. Después de tocar el agente: `/evals`.
5. Por la noche: `/cierre-dia`.

## Comandos útiles de Claude Code
| Comando | Para qué |
|---|---|
| `/usage` | Ver el gasto de la sesión |
| `/clear` | Empezar limpio al cambiar de tarea |
| `/compact` | Resumir una sesión larga |
| `/model sonnet` | Bajar de modelo para tareas mecánicas |
| `/agents` | Ver y editar los subagentes |
| Shift+Tab | Modo plan para cambios grandes |
| Esc | Interrumpir a Claude |

## Si algo falla
| Síntoma | Arreglo |
|---|---|
| La web dice que no hay conexión | Arranca el backend; revisa `frontend/.env.local` y reinicia `npm run dev` |
| `/salud` avisa de la clave | Falta `ANTHROPIC_API_KEY_PRODUCTO` en `.env` |
| Error 429 | Demasiadas sesiones a la vez: cierra una y espera un minuto |
| "credit balance too low" | Cambia a una clave de reserva |
| En un worktree falta `.env` | Cópialo a mano o revisa `.worktreeinclude` |
| No quedan ideas | `/depurar <síntoma>` |

## Mapa del repositorio
```
CLAUDE.md                 reglas del proyecto para Claude (la "constitución")
.claude/agents/           11 subagentes
.claude/skills/           11 skills (/kickoff, /feature, /herramienta, /depurar, /evals, /estado, /cierre-dia, /demo y 3 de conocimiento)
.claude/settings.json     modelo, permisos, límites de subagentes, plugins y hooks
backend/                  agente, herramientas, datos y API
frontend/                 web en Next.js
panel/                    panel Streamlit
evals/                    casos y ejecución de evals
tests/                    pytest con cliente simulado
scripts/                  comprobaciones, hooks e informes
docs/                     plan, arquitectura, decisiones, diario, ideas, pitch y demo
reto/                     enunciado (y el de práctica)
datos_ejemplo/            extractos CSV sintéticos para probar la subida
demo/grabaciones/         respuestas grabadas para el modo demo
```
