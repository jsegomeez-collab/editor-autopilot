# PLAN.md — editor-autopilot (Fase 0)

## Contexto
Fase 0 del ENCARGO: reconocimiento sin instalar nada. Se ha leído entero el upstream `browser-use/video-use` (README, install.md, SKILL.md, los 6 helpers y los tests) con un subagente, además de la documentación de HyperFrames (v0.8.76) y la de Claude Code, y se ha auditado la máquina. Este documento es el contenido de `PLAN.md`. Cuando lo apruebes, la única acción será crear `~/Developer/editor-autopilot/` con `PLAN.md` y `PROGRESO.md` dentro. No habrá commit hasta la Fase 2, porque `git init` pertenece a esa fase.

## 1. Auditoría del sistema (verificada)
| Elemento | Estado | Impacto |
|---|---|---|
| SO | macOS 15.7.4 arm64, 8 GB de RAM | OK. No hace falta WSL2 |
| **Disco** | **994 MiB libres de 228 GiB (100 %)** | **🛑 BLOQUEANTE.** Chrome de HyperFrames (~93 MiB en zip), venv con librosa, intermedios 4K y ProRes. `hyperframes doctor` exige ≥ 2 GB. Pido liberar **≥ 30 GB** (candidatos: `~/Library/Caches` 7,7 G, `~/.npm` 5,7 G, `~/Downloads` 4,9 G) |
| ffmpeg | 9.0.1 de Homebrew core: libx264, libvpx(-vp9), prores_ks, sidechaincompress, loudnorm, ebur128, afftdn, blackdetect, tonemap, colorspace, xfade | **Faltan libass (filtro `subtitles`/`ass`), zscale y libplacebo**, además de drawtext/freetype |
| Node | Activa la v20.20.1; la v22.23.2 está instalada en nvm | Usar `nvm use 22` (o la ruta absoluta) para HyperFrames |
| Python | Sistema 3.9.6. uv 0.11.7 ya tiene 3.12 y 3.13 | video-use pide `>=3.10` → `uv sync --python 3.12` |
| Claude Code | v2.1.119 | La documentación describe funciones de v2.1.198 en adelante. `--max-turns` no aparece en `--help`. Que acepte `claude-sonnet-5` está sin verificar (se probará en la Fase 2) |
| Entorno | `ANTHROPIC_API_KEY` y `CLAUDE_CODE_OAUTH_TOKEN` no definidas | Bien. El runner las elimina igualmente con `env -u` |
| `~/Developer` | No existe | Se crea en la Fase 1 |

## 2. Conflictos entre el ENCARGO y el código real, y cómo se resuelven

1. **ffmpeg sin libass.** Hace falta para la sección 6.5 (ASS con `fontsdir`). Upstream también lo usa en `build_final_composite`.
   - **Propuesta:** instalar ffmpeg desde el tap `homebrew-ffmpeg/ffmpeg` con libass y zimg. Es "ffmpeg", que está permitido, pero **sustituye** al actual, así que pido tu OK.
   - Las opciones exactas (`--with-libass`, `--with-zimg`, `--with-libplacebo`) están **SIN VERIFICAR**. Se comprobarán con `brew options` antes de instalar.
   - Después se verifica con `ffmpeg -filters | grep -E "subtitles|zscale|libplacebo"`.
2. **ffmpeg sin zscale.** El `TONEMAP_CHAIN` de upstream falla con fuentes HDR.
   - Se resuelve con el punto 1 más nuestra normalización (6.1): la copia normalizada ya es SDR BT.709, así que el tone map de upstream nunca llega a ejecutarse.
   - Si zscale no llegara a estar disponible, hay un respaldo: `colorspace` + `tonemap`, que es peor. Te avisaría.
3. **Caché de transcripciones indexada solo por el nombre del archivo** (`edit/transcripts/<stem>.json`, sin hash). La regla 9 pide no re-transcribir si la fuente no cambia, pero upstream no detecta cambios.
   - Nuestro wrapper nombra la copia normalizada con el hash del original (`src_<sha1-12>.mp4`). Así, mismo stem ⇔ mismo contenido, y no hay colisiones.
4. **`transcribe.py` no fija el idioma** y usa `model_id=scribe_v1`. Siempre se pasará `--language es`. Con la muestra se comprobará que las muletillas se conservan.
5. **render.py no admite layout.** Solo hay una cadena `-vf` fija (tonemap → `scale=1920:-2` → grade), los overlays van en x=0/y=0 sin escalar, no se puede inyectar un `filter_complex` y los WebM con alfa se decodifican sin alfa. `--preview` y `MarginV` no coinciden con SKILL.md.
6. **Decisión del compositor: replicar la lógica en `pipeline/`, sin llamar a render.py.**
   - **Por qué:** layout split/full, overlays posicionados y ASS tienen que ir en UNA pasada final (6.3), y render.py no lo permite sin modificarlo, cosa que está prohibida.
   - Importar sus funciones internas nos ataría a firmas privadas que un `git pull` puede romper. Hay además un fallo silencioso: si `helpers/` no está en `sys.path`, el grade desaparece sin error.
   - Se reutiliza de upstream por CLI (interfaz estable): `transcribe.py`, `transcribe_batch.py`, `pack_transcripts.py` y `timeline_view.py`.
   - Se replican las reglas duras con los mismos parámetros:
     - extracción por segmento con `afade` de 30 ms,
     - concat con `-c copy`,
     - `setpts=PTS-STARTPTS+T/TB`,
     - offsets de la timeline de salida,
     - subtítulos los últimos.
   - Un test compara nuestra extracción y concat con la de render.py sobre la muestra, para que la duración sea idéntica (±1 frame).
7. **El formato de la EDL se mantiene igual** (`sources`, `ranges[] {source,start,end,beat,quote,reason}`). Así `edl.json` sigue siendo compatible con el subagente editor de upstream. Layout, gráficos y SFX van en archivos aparte (`layout.json`, `graficos.json`, `sfx_timeline.json`).
8. **Regla 11 y paso "Converse".** Se sustituyen tal como dice el ENCARGO: el perfil + `correcciones.md` son la estrategia aprobada. La skill `video-autopilot` escribe la estrategia en `edit/project.md` con el formato `## Session N` de upstream y ejecuta sin preguntar.
9. **Regla 12.** Todo lo que se genere va a `trabajos/<id>/edit/`. Upstream nunca se modifica: el symlink `~/.claude/skills/video-use` apunta al repo completo.
10. **Regla 10 (un subagente por animación).** Se sustituye solo para plantillas: `render_plantillas.py` lanza `npx hyperframes render --variables-file ...` como procesos en paralelo.
11. **Alfa de los overlays.**
    - Paneles split: MP4 opaco a 1080×960.
    - Overlays a pantalla completa: **`--format mov` (ProRes 4444 con alfa, verificado en la documentación de HyperFrames)**. Se evita el WebM, que necesitaría `-c:v libvpx-vp9` antes del `-i`.
12. **Duración fija en las plantillas.** Las variables de HyperFrames no pueden cambiar la duración. `render_plantillas.py` escribe `data-duration` en una copia del `index.html` de cada slot antes de renderizar. La plantilla original no se toca.
13. **Paralelismo con 8 GB de RAM.** HyperFrames activa `--low-memory-mode` por sí solo. Valores por defecto: concurrencia de 2 procesos, `--workers 1` cada uno (cada worker es un Chrome de ~256 MB; con varios workers en macOS se escriben frames RGBA crudos, ~25 GB/min). Concurrencia configurable.
14. **Modelo `claude-sonnet-5` fijado en tres sitios:**
    - `--model claude-sonnet-5` en el runner,
    - `"model": "claude-sonnet-5"` en `.claude/settings.json` del proyecto,
    - subagente editor definido en `.claude/agents/editor-video.md` con `model: claude-sonnet-5`, además de `CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-5` en el entorno del runner.

    La verificación se hace con las claves de `modelUsage` del JSON headless. En `-p`, el orden de prioridad es `--model` > `ANTHROPIC_MODEL` > settings.
15. **Suscripción, no API.**
    - El runner usa `env -u ANTHROPIC_API_KEY -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_AUTH_TOKEN`. Según la documentación de autenticación, `ANTHROPIC_AUTH_TOKEN` también tiene prioridad sobre el login.
    - Nunca `--bare`, porque en ese modo solo acepta API key.
    - Permisos: `--allowedTools` con lista blanca (Read, Edit, Write, Glob, Grep, Agent, `Bash(ffmpeg *)`, `Bash(ffprobe *)`, `Bash(uv run *)`, `Bash(npx --yes hyperframes *)`…) y `--add-dir` limitado al trabajo y a `editor-autopilot/`.
    - Sin `bypassPermissions`.
    - La lista exacta de reglas se valida en la Fase 7 con `permission_denials`.
16. **Skills en `-p`.** Se cargan desde `~/.claude/skills` y se invocan con `/video-autopilot` dentro del prompt. En la Fase 6 se comprueba de verdad. Si fallara, el runner pasa el SKILL.md con `--append-system-prompt`.
17. **Límite de uso.** En la salida se ve como `is_error` con un texto de límite, o como `system/api_retry` con `error:"rate_limit"` en `stream-json`. Su forma exacta está sin verificar. El runner usará `--output-format stream-json` y, si detecta ese patrón, dejará el trabajo en `pausado_por_limite`.
18. **Registro de uso por vídeo:** `total_cost_usd` (estimación), `usage`, `modelUsage`, `num_turns` y `duration_ms` del resultado JSON, más los minutos de audio transcritos (calculados con ffprobe del WAV).
19. **Detección de cara con MediaPipe Face Detection** (con OpenCV solo para leer frames).
    - Por qué: es más robusto de perfil y con poca luz que Haar, da landmarks de ojos para colocar los ojos a 1/3 de la altura y es ligero en CPU arm64.
    - Está sin verificar que haya wheel para arm64 con Python 3.12; se comprueba en la Fase 3. Si no hubiera, el respaldo es el DNN de OpenCV (res10 SSD).

## 3. Arquitectura (sin cambios respecto a la sección 4 del ENCARGO)
- Entorno Python propio con `uv` (3.12) en `editor-autopilot/`. Dependencias: pydantic, pyyaml, mediapipe, opencv-python-headless, librosa, watchdog (o sondeo simple para no añadir dependencias; se decide en la Fase 7).
- Los scripts de `pipeline/` se llaman por CLI desde la skill, y cada uno tiene una sola responsabilidad.
- Node 22 con ruta absoluta de nvm en `render_plantillas.py`, para no depender del shell.

## 4. Decisiones que necesito de ti antes de la Fase 1 (🛑)
1. **Liberar disco (≥ 30 GB).** Yo no borro nada.
2. **OK para reemplazar ffmpeg** por la variante del tap `homebrew-ffmpeg` con libass y zimg (libplacebo si existe la opción).
3. **¿Actualizar Claude Code** (`claude update`) antes de la Fase 2? La 2.1.119 va muy por detrás de la documentación.
4. Un **vídeo de muestra de 30–60 s** en `tests/muestras/` (vertical, de móvil, a ser posible HDR, para probar el tone map).

## 5. Verificación de la Fase 0
- Tras la aprobación: `PLAN.md` y `PROGRESO.md` creados en `~/Developer/editor-autopilot/`.
- Reporte: `✅ Fase 0 — reconocimiento y plan — PLAN.md, PROGRESO.md`.

## 6. Decisiones aprobadas (2026-09-25)
- Disco: 6,5 GB libres. Se aceptan los tres cambios de ahorro:
  1. La copia normalizada se genera a 1080×1920 (no se conserva el 4K). Cambia la regla 6.1.
  2. Los overlays con alfa se renderizan en WebM VP9 (no ProRes 4444), leídos con `-c:v libvpx-vp9` antes del `-i`.
  3. Cuando un trabajo llega a `revision/`, se borran solos sus intermedios regenerables (clips, base, temporales). El original nunca se borra.
- `~/VideoAutopilot/` sigue siendo configurable (se puede mover a un disco externo).
- Aprobado sustituir ffmpeg por una versión con libass y zimg, y actualizar Claude Code.
- Muestra: `tests/muestras/JOSE49.mp4` (68 s, 1080×1920, 25 fps CFR, SDR, AAC 48 kHz). No es HDR, así que el tone map se probará con un clip sintético.

## 7. Cambios de reglas aprobados tras analizar los vídeos de referencia (2026-09-25)
Fuente: `tests/referencias/ANALISIS_ESTILO.md`. Todos son configurables por perfil. Los valores por defecto del esquema siguen siendo los del ENCARGO, y el perfil `jose` los sustituye.
1. Subtítulos: `mayusculas: false`, en minúsculas.
2. Nuevo estilo `mixto`: caja sobre los gráficos y sin caja (solo sombra) sobre la cámara.
3. Posición de los subtítulos en `full`: `posicion_full_pct` (en jose, 50 %; por defecto, 67 %).
4. Ritmo: la duración de las ventanas pasa a ser configurable (`layout.ventanas`). En jose: gancho 1,2–2,5 s, split 1,5–3,5 s, full 1,2–3 s, máximo 4 s sin cambio visual.
5. Formato de cifras según el idioma. es-LatAm: "$30.000" y "93%". es-ES: "30.000 $" y "10 %".
6. Nueva transición `destello`: corte seco más un destello de luz en los cambios de bloque.
7. Fuera de alcance: b-roll automático (capturas de pantalla, clips). El panel superior solo lleva motion graphics desde plantillas.
- Otros cambios: el logo pasa a ser opcional (jose no tiene) y hay una tipografía opcional de `enfasis` (serif itálica para `palabra_clave`). El CTA admite `{palabra}`, que se toma de lo dicho en cada vídeo.
- Tipografías de jose: Inter Bold/ExtraBold, Instrument Serif Italic y Noto Sans Bold, todas OFL y descargadas de Google Fonts. Comprobado con fontTools que tienen los glifos de la prueba "¿ÁÉÍÓÚÑ ÜÇ 300 € 10 %?".
- Las muletillas se detectan automáticamente (`muletillas_extra` vacío). El glosario irá creciendo con cada vídeo.

## 8. Decisiones técnicas de la Fase 3
- Detección de cara con **YuNet (OpenCV)** en lugar de MediaPipe: mediapipe 1.0.1 aborta en macOS (`DrishtiMetalHelper`, "Service is unavailable") incluso con delegado CPU. YuNet devuelve caja + ojos.
- EDL en dos pasos: el LLM elige tramos de palabras (`seleccion.json`) y `construir_edl.py` calcula los tiempos exactos. Así las reglas 6 y 7 se cumplen siempre, sin depender del LLM.
- Bordes del EDL alineados a la rejilla de fotogramas. Sin esto, cada segmento se redondea hacia arriba y el total se desvía (+0,16 s en la prueba), fuera de la tolerancia de ±0,1 s del QA.
- ffmpeg 9 ya no tiene `-filter_complex_script`: se usa `-/filter_complex <archivo>`.
- Composición del layout con 3 cadenas sincronizadas (recorte de tamaño fijo y posición por ventana) en lugar de trocear en N ramas, que obligaría a ffmpeg a acumular frames en memoria (8 GB de RAM).

## 9. Imágenes de marca (aprobado por el cliente, 2026-09-25)
- Excepción acotada al punto 7 del §7 (b-roll fuera de alcance): cuando se menciona un término con imagen en `perfiles/<marca>/imagenes/catalogo.yaml` (p. ej. Claude Code), la ventana split usa la plantilla nueva `imagen` (logo o captura).
- Prioridad: plantillas de datos (cifra, lista, pasos, comparativa, gráfico, alerta, pregunta) > imagen > palabra_clave. No se repite la misma imagen en ventanas seguidas.
- Las imágenes las aporta el cliente, con procedencia anotada en el catálogo. `render_plantillas.py` solo acepta imágenes del catálogo (en los previews, también las de `tests/fixtures/imagenes/`).
- Aviso operativo: el Escritorio y Documentos se sincronizan con iCloud y macOS los descarga ("dataless") cuando falta disco. Las carpetas de trabajo no deben estar ahí (`~/VideoAutopilot/` no lo está).

## 10. Motion graphics visuales (cambio de regla aprobado por el cliente, 2026-09-25)
- Problema: la biblioteca era sobre todo tipográfica y el LLM abusaba de `palabra_clave` (5 de 13 en la prueba). El cliente quiere que cada ventana split **represente visualmente** lo que dice.
- Nuevas plantillas visuales basadas en iconos SVG animados y diagramas: `icono` (icono protagonista + movimiento con significado), `red` (nodo central conectando satélites), `transformacion` (A → B), `terminal` (ventana tech escribiendo), `uno_vs_muchos` y `crecimiento`.
- Iconos: Lucide (licencia ISC), subconjunto con etiquetas en español en `plantillas/_iconos/catalogo.yaml`. `render_plantillas.py` los inyecta en línea en las variables: no hay fetch durante el render.
- Regla de selección nueva: toda ventana split debe llevar una representación visual (icono/diagrama/dato). El texto solo aparece como rótulo corto (1–4 palabras). `palabra_clave` pasa a último recurso y se anota en QA si se usa.
- SFX con sentido: cada icono y plantilla visual lleva un sonido semántico (moneda, papel, despegue, red, teclado, candado, reloj, subida, bajada, transformación, cámara, mensaje). El LLM puede fijarlo en `datos.sonido`. Kit adicional aprobado: ~500 créditos.
- Estilo sin referencias del cliente: flat de líneas con glow, coherente con su paleta (azul marino, blanco, amarillo #FFDB00).
