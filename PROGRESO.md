# PROGRESO

## ✅ Fase 0 — Reconocimiento y plan (2026-09-25)
- Leído entero el upstream video-use (README, install.md, SKILL.md, helpers/*.py, tests) y la documentación de HyperFrames y Claude Code.
- Auditoría del sistema y conflictos resueltos: ver `PLAN.md`.
- Archivos: `PLAN.md`, `PROGRESO.md`.
- Sin commit: `git init` corresponde a la Fase 2.

## Decisiones de Fase 0 resueltas (ver PLAN.md §6)
1. Liberar ≥ 30 GB de disco.
2. OK para reemplazar ffmpeg (con libass y zimg).
3. ¿Actualizar Claude Code?
4. Vídeo de muestra de 30–60 s.

## ✅ Fase 1 — Instalación upstream (2026-09-25)
- ffmpeg sustituido por homebrew-ffmpeg/ffmpeg 9.0.2 `--with-zimg`: libass (subtitles/ass), zscale, drawtext y decodificador libvpx-vp9. Verificado con `ffmpeg -filters` y `ffmpeg -decoders`.
- Claude Code actualizado de 2.1.119 a 2.1.282.
- video-use clonado en `~/Developer/video-use` (commit b877063) y `uv sync --python 3.12` hecho. `uv.lock` queda sin seguimiento en upstream.
- Symlink `~/.claude/skills/video-use` creado. `timeline_view.py --help` responde bien.
- Clave de ElevenLabs en `~/Developer/video-use/.env` (600, ignorado por git) y verificada: `/v1/user` responde 200.
- Transcripción de `tests/muestras/JOSE49.mp4` con `--language es`: idioma spa (prob. 1.0), 244 palabras, 3,6 s. Caché verificada (segunda llamada = `cached`). `takes_packed.md` generado. Audio transcrito en total: 68 s de los 300 s permitidos.
- Observaciones para fases siguientes:
  - Scribe escribe las cifras en letra ("trescientos", "diez mil dólares"). Hará falta pasarlas a dígitos para subtítulos y gráficos, y comparar valores numéricos en QA.
  - "Claude Code" sale como "Cloud Code" / "Cloud". Lo corrige el glosario (6.2).
  - Hay tomas repetidas y un falso comienzo marcado con `--`. Material útil para probar el EDL.
  - No se ha podido verificar que conserve las muletillas: la muestra no tiene "eh"/"em" ni eventos de audio.

## Fase 2 — Repo propio + perfil (en curso)
- Repo `~/Developer/editor-autopilot` con la estructura de la sección 4, `git init`, `.gitignore` (excluye `.env`, vídeos y audio) y `~/VideoAutopilot/{entrada,trabajos,revision,errores}`.
- Entorno `uv` con Python 3.12: pydantic, pyyaml, text2num y pytest (dev).
- `.claude/settings.json`: `model: claude-sonnet-5`, más `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` y `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`. Verificado en headless con un subagente: `modelUsage` solo contiene `claude-sonnet-5`. Sin la variable HAIKU, Claude Code usaba claude-haiku-4-5 para tareas internas.
- Autenticación headless sin variables de API: `authMethod: claude.ai`, suscripción Max. Ojo: `total_cost_usd` de la salida es una estimación a precio de lista (`costBasis: list`), no una factura.
- `pipeline/corregir_transcripcion.py`: aplica el glosario y pasa las cifras en letra a dígitos con su unidad (%, €, $), sin tocar timestamps. En la muestra hizo 18 correcciones (p. ej. "Cloud Code" → "Claude Code", "diez mil dólares" → "10.000 $").
- `pipeline/perfil.py`: esquema pydantic estricto + CLI de validación que también comprueba los archivos. Perfil de ejemplo en `perfiles/_ejemplo/`.
- Tests: 13 en verde (`uv run pytest -q tests`).
- Pendiente: cuestionario y perfil propio.
