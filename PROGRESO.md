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

## ✅ Fase 2 — Repo propio + perfil (2026-09-25)
- Repo `~/Developer/editor-autopilot` con la estructura de la sección 4, `git init`, `.gitignore` (excluye `.env`, vídeos y audio) y `~/VideoAutopilot/{entrada,trabajos,revision,errores}`.
- Entorno `uv` con Python 3.12: pydantic, pyyaml, text2num y pytest (dev).
- `.claude/settings.json`: `model: claude-sonnet-5`, más `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` y `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`. Verificado en headless con un subagente: `modelUsage` solo contiene `claude-sonnet-5`. Sin la variable HAIKU, Claude Code usaba claude-haiku-4-5 para tareas internas.
- Autenticación headless sin variables de API: `authMethod: claude.ai`, suscripción Max. Ojo: `total_cost_usd` de la salida es una estimación a precio de lista (`costBasis: list`), no una factura.
- `pipeline/corregir_transcripcion.py`: aplica el glosario y pasa las cifras en letra a dígitos con su unidad (%, €, $), sin tocar timestamps. En la muestra hizo 18 correcciones (p. ej. "Cloud Code" → "Claude Code", "diez mil dólares" → "10.000 $").
- `pipeline/perfil.py`: esquema pydantic estricto + CLI de validación que también comprueba los archivos. Perfil de ejemplo en `perfiles/_ejemplo/`.
- Tests: 13 en verde (`uv run pytest -q tests`).
- Estilo analizado a partir de JOS1 y JOS12 (`tests/referencias/ANALISIS_ESTILO.md`). Cambios de reglas aprobados: PLAN.md §7.
- Esquema ampliado: ventanas de layout, subtítulos (mixto, mayúsculas, posición), transición destello, logo opcional, fuente de énfasis y CTA con `{palabra}`. Formato de cifras según idioma.
- Perfil `perfiles/jose/` validado: perfil.yaml, glosario.yaml (8 términos), correcciones.md y 4 fuentes OFL.
- Prueba real: `corregir_transcripcion.py` sobre JOSE49 con el perfil jose da, por ejemplo, "diez mil dólares" → "$10.000" y "Cloud Code" → "Claude Code".
- Tests: 14 en verde.

## 🛑 Fase 3 — Normalización + cara + layout (2026-09-25, pendiente de revisión)
- `pipeline/preparar_fuente.py`: espera tamaño estable, ficha ffprobe y copia `src_<sha1-12>.mp4` (CFR 25/30, HDR→SDR con zscale+tonemap, 48 kHz, rotación aplicada, lado corto ≤ 1080, CRF 14). Probado con JOSE49 y con un clip sintético HLG 4K rotado a 29,97 fps → SDR BT.709 1080×1920 a 30 fps.
- `pipeline/transcribir.py`: helper de video-use (`--language es`) + caché global `~/VideoAutopilot/cache_transcripciones/` indexada por hash. Caché sembrada con la transcripción de JOSE49 (misma duración, mismo audio): 0 s transcritos en esta fase.
- `pipeline/construir_edl.py`: el LLM elige tramos de palabras y el script calcula los cortes (bordes de palabra, padding 40/60, silencios ≥ 300 ms, alineado a fotogramas, prohibido reordenar). JOSE49: 68 s → 51,0 s en 14 rangos.
- `pipeline/detectar_cara.py`: YuNet de OpenCV (MediaPipe 1.0.1 aborta en macOS por Metal: 2 intentos, descartado). 284/284 muestras con cara.
- `pipeline/planificar_layout.py`: gancho hasta la primera pausa de fin de frase entre 3 y 10 s; alternancia con las ventanas del perfil; CTA en full; recorte estático por mediana; barbilla por encima de la zona segura; destellos en cambios de bloque. JOSE49: 25 ventanas de 1,23 a 3,12 s.
- `pipeline/componer.py`: segmentos con `afade` de 30 ms → concat `-c copy` → una pasada final (3 cadenas full/punch/split + destellos + huecos para overlays y ASS). Duración exacta: 1275 fotogramas = 51,000 s = EDL. Pico de RAM ~1 GB.
- `pipeline/zonas_debug.py`: dibuja el área útil y la divisoria sobre fotogramas.
- Revisión: `tests/revisiones/fase3_frames.png` y `fase3_layout.mp4`.
- Tests: 18 en verde.
