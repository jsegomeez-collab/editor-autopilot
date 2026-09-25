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

## ✅ Fase 3 — Normalización + cara + layout (2026-09-25, aprobada: encuadre, destello y ritmo sin cambios)
- `pipeline/preparar_fuente.py`: espera tamaño estable, ficha ffprobe y copia `src_<sha1-12>.mp4` (CFR 25/30, HDR→SDR con zscale+tonemap, 48 kHz, rotación aplicada, lado corto ≤ 1080, CRF 14). Probado con JOSE49 y con un clip sintético HLG 4K rotado a 29,97 fps → SDR BT.709 1080×1920 a 30 fps.
- `pipeline/transcribir.py`: helper de video-use (`--language es`) + caché global `~/VideoAutopilot/cache_transcripciones/` indexada por hash. Caché sembrada con la transcripción de JOSE49 (misma duración, mismo audio): 0 s transcritos en esta fase.
- `pipeline/construir_edl.py`: el LLM elige tramos de palabras y el script calcula los cortes (bordes de palabra, padding 40/60, silencios ≥ 300 ms, alineado a fotogramas, prohibido reordenar). JOSE49: 68 s → 51,0 s en 14 rangos.
- `pipeline/detectar_cara.py`: YuNet de OpenCV (MediaPipe 1.0.1 aborta en macOS por Metal: 2 intentos, descartado). 284/284 muestras con cara.
- `pipeline/planificar_layout.py`: gancho hasta la primera pausa de fin de frase entre 3 y 10 s; alternancia con las ventanas del perfil; CTA en full; recorte estático por mediana; barbilla por encima de la zona segura; destellos en cambios de bloque. JOSE49: 25 ventanas de 1,23 a 3,12 s.
- `pipeline/componer.py`: segmentos con `afade` de 30 ms → concat `-c copy` → una pasada final (3 cadenas full/punch/split + destellos + huecos para overlays y ASS). Duración exacta: 1275 fotogramas = 51,000 s = EDL. Pico de RAM ~1 GB.
- `pipeline/zonas_debug.py`: dibuja el área útil y la divisoria sobre fotogramas.
- Revisión: `tests/revisiones/fase3_frames.png` y `fase3_layout.mp4`.
- Tests: 18 en verde.

## ✅ Fase 4 — Biblioteca de plantillas (2026-09-25, las 10 aprobadas)
- Base común `plantillas/_comun/` (GSAP 3.14.2 en local, base.css con tokens y área útil 60–960 × 240–860, base.js con HF.revelar/limitar/deriva/tamanoTexto/registrar). Easing siempre power2 (cúbico). Deriva de 1,02 para no salir del área útil. Con t = 0, el elemento ya está aterrizado en el frame 0.
- 10 plantillas con index.html, schema.json, README.md y preview. Gancho la escribí yo; las otras 9 las hicieron 3 subagentes en paralelo, todas verificadas fotograma a fotograma:
  gancho, cifra, lista, comparativa, pasos, pregunta, palabra_clave, alerta, grafico (paneles 1080×960 en mp4) y cta (1080×1920 webm con alfa, verificado con ALPHA_MODE=1).
- `pipeline/render_plantillas.py`: valida con jsonschema (más la palabra clave propia `maxPalabras`), ≤ 7 palabras por texto, cifras presentes en lo dicho en la ventana y tiempos ordenados. Monta un slot por ventana con las fuentes del perfil y renderiza con `npx hyperframes@0.8.77` en procesos paralelos (concurrencia 2, `--workers 1`). Verifica tamaño y duración con ffprobe. Preview de una plantilla: ~17 s.
- `pipeline/hoja_plantillas.py` → `plantillas/_hoja_contactos.png` (cada plantilla en contexto sobre el vídeo maquetado).
- Tests: 26 en verde.
- Plantilla 11 `imagen` (logo o captura de un término mencionado), a petición del cliente tras aprobar las 10. Catálogo en `perfiles/jose/imagenes/catalogo.yaml`, vacío: faltan las imágenes del cliente. Ver PLAN.md §9.

## Fase 5 — Subtítulos, audio, exportación y QA (en curso, 2026-09-25)
- `subtitulos_ass.py`: ASS palabra a palabra en la línea de tiempo de salida. Bloques de 2 palabras y la cifra nunca se separa de su unidad o sustantivo. Palabra activa en acento. Estilo caja, contorno o mixto. Posición según layout (divisoria en split, % del perfil en full, encima del CTA). En minúsculas se respetan el glosario y las siglas. Prueba de glifos "¿ÁÉÍÓÚÑ ÜÇ 300 € 10 %?" correcta con Inter Bold desde fontsdir.
- ElevenLabs: el plan pasó de Free (sin licencia comercial) a Starter. Endpoints verificados (/v1/music, /v1/sound-generation). Piloto: 1 SFX (5 créditos) y 1 pista de 20 s. El contador de la API no refleja la música, así que el límite de gasto se controla por estimación (900 créditos/min de música, ~11/s de SFX).
- `generar_audio_elevenlabs.py`, `importar_audio.py` (exige fuente, licencia y uso_permitido; música a −20 LUFS, SFX con pico a −3 dBFS; BPM plegado a 70–140; inicio_recomendado), `planificar_sfx.py` (eventos visuales → SFX, densidad, sin solapes, variantes reproducibles) y `mezcla_audio.py`:
  - rotación de 5 pistas y bucle con crossfade de 1 compás;
  - ducking medido: música 20,4 dB bajo la voz al hablar;
  - loudnorm en 2 pasadas + limitador a −1,5 dBFS (el AAC sube picos +2,6 dB). Final: −14,6 LUFS / −1,4 dBTP.
- `exportar.py` (mux sin recodificar el vídeo, portada del gancho, transcripcion.txt, nombre AAAAMMDD_perfil_slug) y `qa.py` (15 comprobaciones, veredicto, entrega a revision/ con prefijo REVISAR_ y limpieza de intermedios).
- Corregido en el camino:
  - el CTA se detectaba en "comentarios" (faltaba límite de palabra);
  - faltaba la etiqueta BT.709 en ffmpeg 9 (ahora con setparams).
- Prueba de punta a punta con JOSE49 y 13 gráficos: 14/15 ✅. Pendiente: la biblioteca de SFX (solo existe el pop del piloto).
- Pendiente: OK del cliente al estilo del piloto → generar el kit completo → 🛑 checkpoint de escucha.
- Motion graphics visuales (PLAN §10), a petición del cliente:
  - 138 iconos Lucide etiquetados en español;
  - 6 plantillas nuevas: icono (mía) y red, transformacion, crecimiento, terminal, uno_vs_muchos (subagentes);
  - 36 SFX semánticos (12 tipos × 3, ~207–373 créditos);
  - el sonido de cada gráfico depende del icono o la plantilla.
- Correcciones:
  - los nombres de icono ("trash-2") ya no cuentan como cifras;
  - QA ya no lee iconos como texto;
  - los valores por defecto del schema se aplican antes de inyectar SVG (faltaba el icono "user");
  - terminal en monoespaciada.
- Disco: `uv cache clean` con OK del cliente (quedan ~3,1 GB).
- Vídeo de prueba con gráficos visuales: ✅ LISTO 14/14.
