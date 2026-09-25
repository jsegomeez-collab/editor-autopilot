# editor-autopilot

Editor automático de vídeos verticales en español, construido sobre video-use.

- Encargo completo: `ENCARGO_editor_autopilot.md`. Decisiones: `PLAN.md`. Estado: `PROGRESO.md`.
- Upstream `~/Developer/video-use/` es de SOLO LECTURA: nunca se edita. Se usan sus helpers por CLI con `~/Developer/video-use/.venv/bin/python`.
- Modelo fijado: `claude-sonnet-5` (ID completo, nunca alias), en todo: runner, comandos y subagentes.
- Python: `uv run` (3.12). Node 22 para HyperFrames (el Node por defecto es 20).
- Un script de `pipeline/` = una responsabilidad. Código, comentarios y documentación en español.
- Las 10 reglas duras de video-use se respetan siempre: subtítulos los últimos; extracción por segmento y concat `-c copy`; fades de audio de 30 ms; `setpts=PTS-STARTPTS+T/TB`; offsets de la timeline de salida; nunca cortar dentro de una palabra; padding de 30–200 ms; ASR palabra a palabra; caché de transcripciones.
- El texto en pantalla sale de `pipeline/corregir_transcripcion.py` (glosario + cifras en dígitos). Nunca se inventan cifras.
- Tests: `uv run pytest -q tests`.
- Comandos del proyecto: `/instalar` (instala y comprueba), `/configurar-marca <nombre>` (crea un perfil de marca nuevo) y `/editar <video> [perfil] [versiones]`. Guía para usuarios nuevos: `PUESTA_EN_MARCHA.md`.
- Frontend local: `autopilot/servidor.py` (http://127.0.0.1:8765). Motor: `autopilot/editar.py`. Cola: `autopilot/cola.py`.
