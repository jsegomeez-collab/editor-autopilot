# ENCARGO: Editor de vídeo automático "Autopilot" construido sobre video-use

## 0. Cómo trabajar este encargo (léelo entero antes de hacer nada)

- Es un proyecto grande. Trabaja por fases (sección 9). Empieza en MODO PLAN: la Fase 0 solo investiga y escribe `PLAN.md`. No instales nada ni escribas código hasta que yo apruebe el plan.
- Al terminar cada fase: actualiza `PROGRESO.md`, haz commit y reporta `✅ Fase N — qué se hizo — archivos afectados`. En las fases marcadas con 🛑, para y espera mi OK.
- NUNCA inventes flags, APIs ni opciones. Todo lo que dependa de una herramienta externa (ffmpeg, HyperFrames, ElevenLabs, Claude Code CLI, MediaPipe/OpenCV) verifícalo con `--help`, su documentación o una prueba real antes de usarlo. Si no puedes verificar algo, dilo explícitamente.
- Si un mismo paso falla 3 veces seguidas, para y repórtame el error con el log. No entres en bucles.
- Usa subagentes (herramienta Agent) de forma explícita para leer el repo upstream completo en la Fase 0 y para crear plantillas nuevas cuando haga falta. El render de las plantillas lo hace un script en paralelo (6.4), no subagentes.
- Construye solo lo que pide este documento. Nada de features extra, abstracciones innecesarias ni frameworks adicionales.
- Responde, comenta el código y documenta en español.
- **Modelo:** en el uso diario todo el sistema funciona con Claude Sonnet 5, fijado por su ID completo (`claude-sonnet-5`) y no por alias, para que un cambio de versión nunca altere el comportamiento sin que yo lo decida. Aplica al runner por lotes, a los comandos slash y a cualquier subagente (incluido el subagente editor de video-use). Antes de configurarlo, verifica en la documentación de Claude Code cómo se fija el modelo en cada sitio: flag `--model`, clave `model` en `.claude/settings.json` del proyecto y modelo de los subagentes.

## 1. Objetivo

Construir un sistema que edite vídeos de persona hablando a cámara en español de forma autónoma, uno a uno o por lotes, sin que yo escriba prompts en el día a día: dejo el vídeo en una carpeta y obtengo un vídeo final editado (cortes limpios, motion graphics a pantalla partida alternando con cámara completa, subtítulos, música y efectos de sonido, exportación) más un informe de calidad, listo para revisar y publicar.

## 2. Contexto

**Negocio [EDITABLE]:** agencia de contenido para marcas personales (nicho principal: educación en inversión inmobiliaria y negocio digital). Reels, TikToks y Shorts de 30–90 s, grabados sobre todo con móvil en vertical, una persona hablando a cámara, en español. Hay varias marcas, así que el sistema debe soportar varios perfiles de marca.

**Base técnica:** https://github.com/browser-use/video-use (skill para agentes con acceso a terminal). Lo que ya sé de ella:
- Transcribe con ElevenLabs Scribe (palabra a palabra, diarización, eventos de audio), empaqueta en `takes_packed.md`, el LLM decide los cortes en `edl.json` y `helpers/render.py` hace extracción por segmento → concat → overlays → subtítulos al final. Tiene un bucle de autoevaluación con `timeline_view` (máx. 3 pasadas) y memoria en `edit/project.md`.
- Anima con HyperFrames (HTML/CSS/GSAP, requiere Node 22+, se invoca con `npx --yes hyperframes ...` dentro de `edit/animations/slot_<id>/`), Remotion, Manim o PIL.
- Su SKILL.md tiene 12 reglas duras. Dos chocan con este proyecto y hay que resolverlas así:
  - **Regla 11 / principio 3** ("no tocar el corte hasta que el usuario apruebe la estrategia") y el paso "Converse" (preguntar tipo de contenido, duración, estética...). → En este sistema, **el perfil de marca + las reglas de este documento SON la estrategia ya aprobada por mí**. El autopilot no pregunta: lee el perfil, escribe la estrategia aplicada en `project.md` y ejecuta.
  - **Regla 12** (nunca escribir dentro de `video-use/`). → No se modifica el repo upstream en absoluto: ni SKILL.md ni helpers/. Toda la personalización vive en un repo propio que usa y envuelve a video-use. Así un `git pull` en upstream nunca rompe nada.
- Las otras 10 reglas duras se respetan SIEMPRE, también en todo el código nuevo: subtítulos los últimos en la cadena de filtros, extracción por segmento + concat con `-c copy`, fades de audio de 30 ms en cada corte, `setpts=PTS-STARTPTS+T/TB` en overlays, subtítulos con offsets de la timeline de salida, nunca cortar dentro de una palabra, padding de 30–200 ms, ASR palabra a palabra verbatim, caché de transcripciones. La regla 10 (un subagente en paralelo por animación) se sustituye SOLO para animaciones con plantilla, porque su render es determinista: se renderizan en paralelo con procesos simultáneos (6.4). Esto reduce mucho el consumo de uso de Claude por vídeo.

**Descartado a propósito:** Whisper/WhisperX en local (la propia skill lo marca como antipatrón: lento y normaliza las muletillas). Remotion y Manim (estandarizamos en HyperFrames + PIL para que todo sea consistente).

## 3. Estado final ("terminado" significa esto)

1. video-use instalado según su `install.md`, con symlink en `~/.claude/skills/video-use` y la clave de ElevenLabs verificada.
2. Repo propio `~/Developer/editor-autopilot/` (con git) con la arquitectura de la sección 4.
3. Skill `video-autopilot` registrada en `~/.claude/skills/video-autopilot` + comandos slash.
4. Al menos un perfil de marca completo (el mío), creado con mis datos.
5. Biblioteca de 10 plantillas de motion graphics HyperFrames y biblioteca de audio por defecto (música por estado de ánimo + SFX), ambas aprobadas por mí.
6. Modo individual: suelto un vídeo en `entrada/<perfil>/` → aparece en `revision/<perfil>/` el vídeo final + portada + informe.
7. Modo lote: 5 vídeos en la carpeta se procesan en cola sin intervención.
8. Módulo de variantes creativas funcionando.
9. `README_USO.md` entendible por alguien no técnico.

## 4. Arquitectura

```
~/Developer/video-use/                  ← upstream, INTACTO (solo lectura + git pull)
~/Developer/editor-autopilot/           ← nuestro repo
├── CLAUDE.md                           ← contexto persistente del proyecto (conciso)
├── PLAN.md / PROGRESO.md
├── skill/SKILL.md                      ← skill "video-autopilot" (symlink → ~/.claude/skills/video-autopilot)
├── .claude/commands/                   ← comandos slash (secciones 6.9, 7 y 8)
├── perfiles/<marca>/
│   ├── perfil.yaml                     ← configuración completa de la marca (sección 5)
│   ├── fuentes/  logo/  audio/         ← archivos de marca; audio/ (opcional) sustituye a la biblioteca común
│   ├── glosario.yaml                   ← nombres y términos y cómo se escriben
│   └── correcciones.md                 ← reglas aprendidas de mis revisiones
├── plantillas/<nombre>/                ← biblioteca HyperFrames parametrizada (6.4)
├── biblioteca_audio/                   ← audio por defecto común a todas las marcas (6.6)
│   ├── _entrada/                       ← aquí dejo audio nuevo para importar
│   ├── musica/<estado_animo>/          ← pistas + catalogo.yaml
│   └── sfx/<tipo>/                     ← 3–5 variantes por tipo + catalogo.yaml
├── pipeline/                           ← scripts Python nuevos (un script = una responsabilidad)
├── autopilot/                          ← cola, watcher, runner headless
└── tests/muestras/                     ← vídeos de prueba
~/VideoAutopilot/                       ← carpetas de trabajo (ruta configurable)
├── entrada/<perfil>/                   ← aquí suelto los vídeos
├── trabajos/<AAAAMMDD-HHMM>_<nombre>/  ← original + normalizado + edit/ (outputs de video-use)
├── revision/<perfil>/                  ← final + portada + informe, listos para revisar
└── errores/                            ← trabajos fallidos con su log
```

Tras leer `render.py` entero en la Fase 0, decide si nuestro compositor llama al flujo de render de video-use o replica su lógica en `pipeline/` respetando las reglas duras. Justifícalo en `PLAN.md`. En ningún caso se edita upstream.

## 5. Perfil de marca (`perfil.yaml`)

Diseña el esquema y valídalo (pydantic o jsonschema). Como mínimo:
- `identidad`: nombre, variante de idioma (es-ES / es-LatAm), plataformas destino.
- `colores`: fondo, primario, acento (hex). Máximo 2 colores de acento.
- `tipografias`: titulares, subtítulos y respaldo (archivo + nombre de familia interno).
- `logo`: ruta y uso (solo en el CTA final, nunca al inicio).
- `ritmo`: `rapido` (por defecto) o `natural` (6.2).
- `layout`: patrón por defecto `split-hook-oscilante` (6.3), transición (`corte` por defecto, o `push`).
- `subtitulos`: estilos permitidos y estilo por defecto (6.5).
- `audio`: música sí/no, estados de ánimo permitidos y por defecto, SFX sí/no, estilo de SFX (`minimal` / `energetico`), densidad de SFX (`baja` / `media` / `alta`; `media` por defecto), niveles.
- `cta_por_defecto` (p. ej. "Comenta PISO") y CTAs alternativos.
- `duracion_objetivo_max_s`.
- `muletillas_extra` y `palabras_a_no_cortar`.
- `zonas_seguras` (valores por defecto en 6.3).
- `plantillas_permitidas`.

En la Fase 2 hazme UN único cuestionario con todas las preguntas juntas para rellenar mi perfil y pídeme los archivos que falten. Durante el uso diario no hay preguntas.

## 6. Pipeline por vídeo

### 6.1 Ingesta y normalización (`pipeline/preparar_fuente.py`)
- Espera a que el archivo termine de copiarse (tamaño estable durante ≥ 5 s) antes de tocarlo.
- `ffprobe`: resolución, fps, si es VFR, si es HDR (transfer `arib-std-b67` o `smpte2084`), rotación y audio.
- Crea una copia intermedia normalizada: CFR (30 fps, o 25 si la fuente es 25), HDR → SDR BT.709 con tone mapping (verifica qué filtros tiene el ffmpeg instalado: `zscale`+`tonemap` o `libplacebo`), audio a 48 kHz, rotación aplicada. Alta calidad (CRF ≤ 14 o códec intermedio). Si la fuente es 4K, conserva esa resolución hasta el compositor para que el recorte de cara en split no pierda nitidez.
- La copia normalizada es la que entra al pipeline (también a la transcripción). El original NUNCA se modifica ni se borra.

### 6.2 Transcripción y cortes
- Transcribe con los helpers de video-use (caché obligatoria). Verifica con la muestra que Scribe detecta bien el español y conserva las muletillas.
- Después aplica `glosario.yaml` para corregir nombres propios y términos en el texto que irá a subtítulos y gráficos (sin alterar timestamps).
- El EDL lo decide el LLM con el brief de editor de video-use y estas reglas fijas:
  - **Eliminar:** muletillas de vacilación en español ("eh", "em", "mmm", "este...", "o sea", "bueno", "pues", "vale", "¿vale?", "¿no?", "digamos", "en plan", "tipo") solo cuando no aportan significado en esa frase; falsos comienzos; frases repetidas (quedarse con la última toma limpia y completa); silencios.
  - **Eliminar el preámbulo:** saludos y arranques ("hola, ¿qué tal?", "hoy te voy a contar...") situados antes de la primera frase con contenido. El vídeo empieza en la primera palabra del gancho.
  - **Ritmo `rapido`:** cortar silencios ≥ 300 ms; padding de 40 ms antes y 60 ms después. **Ritmo `natural`:** silencios ≥ 500 ms; padding 60/100 ms.
  - **PROHIBIDO:** reordenar ideas, eliminar ideas completas o cambiar el sentido. Si el resultado supera `duracion_objetivo_max_s`, no recortes contenido: márcalo en el informe QA.
- El `project.md` de cada trabajo registra la estrategia aplicada (sustituye a la confirmación conversacional).

### 6.3 Layout: gancho a pantalla partida + oscilación (`pipeline/detectar_cara.py`, `pipeline/planificar_layout.py`)
Salida: `layout.json` sobre la timeline de salida, con ventanas `split` y `full`.

**Geometría 9:16 (1080×1920), split arriba/abajo por defecto:**
- Panel superior 1080×960: motion graphic sobre el color de fondo de la marca. Su área útil respeta la zona segura superior (contenido entre y=220 e y=960).
- Panel inferior 1080×960: mi cara. Recorte centrado en la cara (cabeza y hombros), ojos a ~1/3 del alto del panel, barbilla por encima de la zona segura inferior.
- `full`: cámara a pantalla completa. Si la fuente es horizontal, recorte 9:16 centrado en la cara.

**Detección de cara:** MediaPipe u OpenCV (elige y justifica). Muestreo a 3–5 fps. El recorte de cada ventana es ESTÁTICO (mediana de las posiciones de esa ventana), nunca un seguimiento que tiemble. Si en una ventana no hay cara detectable, esa ventana pasa a `full` y se anota en QA.

**Zonas seguras de Reels (por defecto, configurables):** superior 220 px, inferior 380 px, derecha 120 px. Ni texto, ni cifras, ni subtítulos, ni la cara dentro de ellas. Crea un modo debug que dibuje las zonas sobre un frame.

**Reglas de alternancia (por contenido, no por reloj):**
- Gancho = desde el inicio hasta la primera pausa de fin de frase situada entre los 3 y los 10 s. El gancho arranca en `split` en el frame 0 con la cartela `gancho` (la promesa o tesis con palabras literales del vídeo, ≤ 7 palabras). Sin fundido desde negro, sin logo, sin intro.
- Dentro del gancho, alternancia rápida: ventanas de 2–4 s.
- Resto del vídeo: `split` de 3–6 s cuando lo que se dice es visualizable (cifra, lista, comparación, proceso, concepto clave, advertencia); `full` de 2–5 s en momentos personales, emocionales, opiniones directas e historias.
- Nunca más de 8 s sin cambio visual: si toca un `full` largo, mete un punch-in (zoom digital 110–115 %) en un límite de frase.
- Los cambios de layout ocurren SOLO en límites de palabra o frase, preferiblemente coincidiendo con un corte del EDL. Transición por defecto: corte seco (opcional en perfil: push de 6–8 frames).
- La ventana final (CTA) va en `full` con la cartela de la plantilla `cta`.

**Composición:** el layout se aplica en la MISMA pasada final que los overlays y los subtítulos (no añade una codificación extra). Orden de capas: base con layout → motion graphics → subtítulos (siempre los últimos).

### 6.4 Motion graphics: biblioteca de plantillas, no animaciones desde cero
No se entrena ningún modelo. La consistencia sale de plantillas HyperFrames parametrizadas + reglas de selección fijas.

- Cada plantilla en `plantillas/<nombre>/`: composición HyperFrames, `schema.json` de parámetros (textos y cifras; colores y tipografías se inyectan desde el perfil), `README.md` con cuándo usarla y `preview.mp4`.
- **Plantillas iniciales (10):** `gancho` (titular del gancho), `cifra` (contador animado de número, € o %), `lista` (2–4 puntos que aparecen de uno en uno), `comparativa` (antes/después, mito/realidad, X vs Y), `pasos` (proceso numerado), `pregunta`, `palabra_clave` (tipografía cinética de 1–3 palabras), `alerta` (error o advertencia), `grafico` (barras o línea simple), `cta`.
- **Tamaños:** panel split 1080×960 con fondo opaco de marca; overlay a pantalla completa 1080×1920 con alfa solo si hace falta. Ojo: para leer el alfa de un WebM VP9 en ffmpeg hay que forzar el decodificador `libvpx-vp9` antes del `-i`; verifícalo en la prueba o usa otro formato con alfa (p. ej. ProRes 4444).
- **Selección (por frase de cada ventana `split`):** cifra/dinero/porcentaje → `cifra`; enumeración ("tres cosas", "primero... segundo...") → `lista`; contraste → `comparativa`; secuencia de acciones → `pasos`; pregunta retórica → `pregunta`; error o peligro → `alerta`; datos comparables → `grafico`; resto → `palabra_clave`. Primera ventana → `gancho`. Última → `cta`.
- **Reglas de contenido (NO negociables):**
  - El texto de los gráficos sale de lo dicho en esa ventana (literal o resumido sin añadir información). Máximo 7 palabras por cartela.
  - Toda cifra que aparezca en un gráfico DEBE aparecer en la transcripción de esa ventana. NUNCA inventar cifras, rentabilidades, porcentajes ni datos.
  - Sincronía: el "aterrizaje" de la animación coincide con el timestamp de la palabra clave (la animación empieza `duración_de_revelado` antes).
  - Easing cúbico siempre, nunca lineal. Un elemento nuevo cada vez. Último frame sostenido ≥ 1 s. El panel nunca queda totalmente estático (deriva sutil).
- **Ejecución:** el agente principal elige plantilla y rellena los parámetros de TODAS las ventanas en un único `graficos.json` (incluye el timestamp de aterrizaje de cada elemento, que también usan los SFX). `pipeline/render_plantillas.py` los renderiza en paralelo con procesos simultáneos (no subagentes) y verifica duración y dimensiones con `ffprobe`. No se escriben composiciones nuevas durante el uso diario. Si ninguna plantilla encaja, usa `palabra_clave` y anótalo en QA. Los subagentes solo se usan para crear una plantilla nueva.
- 🛑 **Checkpoint de diseño:** al terminar la biblioteca, genera `plantillas/_hoja_contactos.png` (frame clave de cada plantilla con mi perfil aplicado) y los previews. Espera mi aprobación plantilla por plantilla antes de seguir.

### 6.5 Subtítulos (`pipeline/subtitulos_ass.py`)
- Formato ASS (no SRT), generado desde los timestamps palabra a palabra, en la timeline de salida y aplicado el último.
- **Estilo por defecto:** bloques de 2 palabras en MAYÚSCULAS (tildes y Ñ correctas), tipografía del perfil (por defecto Coolvetica), caja oscura semitransparente (`BorderStyle=3`), palabra activa resaltada en el color de acento. Nunca separar un número de su unidad ("300 €", "10 %", "3 PISOS"); sin puntos ni comas finales.
- **Posición según layout:** en `split`, centrados sobre la línea divisoria (y≈960); en `full`, a ~65–70 % de la altura. Siempre fuera de las zonas seguras.
- ffmpeg: pasa `fontsdir` al filtro de subtítulos y usa en el ASS el nombre de familia interno de la fuente (no el nombre del archivo). Comprueba que el ffmpeg instalado tiene libass (`ffmpeg -filters`). Haz un render de prueba con "¿ÁÉÍÓÚÑ ÜÇ 300 € 10 %?"; si falta algún glifo, usa la fuente de respaldo del perfil y avísame.

### 6.6 Audio: voz, música y SFX (`pipeline/importar_audio.py`, `pipeline/planificar_sfx.py`, `pipeline/mezcla_audio.py`)

**Voz:** paso alto ~80 Hz y `loudnorm` en dos pasadas a −14 LUFS integrados, true peak ≤ −1 dBTP. Reducción de ruido (`afftdn`) solo si el suelo de ruido medido lo justifica.

**Biblioteca de audio por defecto (se construye UNA vez, no por vídeo):**
- `biblioteca_audio/` es común a todas las marcas. Si un perfil tiene su propia carpeta `audio/`, esa manda.
- `importar_audio.py` ingiere lo que deje en `biblioteca_audio/_entrada/`: normaliza el loudness (música a un nivel común; SFX a un pico común) para que los niveles del pipeline sean predecibles, mide duración y BPM con librosa (ya es dependencia de video-use), marca un `inicio_recomendado` (primer tiempo fuerte después de la intro) y lo registra en `catalogo.yaml` con: estado de ánimo o tipo, BPM, duración, fuente, licencia y `uso_permitido` (`organico` y/o `anuncios`). Una pista sin fuente y licencia anotadas NO entra al catálogo.
- Fuentes permitidas: (a) audio generado con la API de ElevenLabs (música con Eleven Music y efectos con Sound Effects) mediante `pipeline/generar_audio_elevenlabs.py`, verificando endpoints, parámetros y términos de licencia de mi plan en la documentación oficial; (b) archivos que yo aporte de una librería con licencia. Antes de generar nada con la API, dime cuántas pistas y efectos vas a crear y el coste estimado, y espera mi OK.
- Kit inicial. Música: 5 estados de ánimo (`energetica`, `inspiradora`, `tension`, `neutra`, `emocional`), 4–6 pistas instrumentales de 60–120 s por estado, sin voces. SFX: los tipos de la tabla de abajo, 3–5 variantes por tipo, con estilo coherente (`minimal` por defecto).
- 🛑 Checkpoint de escucha: genera `biblioteca_audio/_escucha/` con un vídeo de prueba ya mezclado y el listado del catálogo. Espera mi aprobación.

**Música de fondo (automática):**
- Elige el estado de ánimo clasificando el tono de la transcripción, dentro de los permitidos por el perfil: educativo/informativo → `neutra`; motivacional/logro → `inspiradora`; errores, riesgos, advertencias → `tension`; historia personal → `emocional`; ritmo alto o listas rápidas → `energetica`. En caso de duda, el de por defecto del perfil.
- Rotación: nunca la misma pista en los últimos 5 vídeos del mismo perfil (registro en `perfiles/<marca>/uso_audio.json`).
- Ajuste a duración: empieza en `inicio_recomendado`, nunca en una intro lenta. Si la pista es más corta que el vídeo, bucle con crossfade de ~1 compás. Termina con un fade-out que acaba con el vídeo.
- Ducking con `sidechaincompress`: ~18–22 dB por debajo de la voz mientras hablo; en el último segundo sin voz puede subir ~6 dB. Fade in de 0,5 s. La música nunca tapa la voz.

**SFX (automáticos y sincronizados con lo que pasa en pantalla):** se generan en `sfx_timeline.json` a partir de `layout.json` y `graficos.json`, nunca por reloj.

| Evento | Tipo de SFX |
|---|---|
| Frame 0 del gancho (aparece la cartela) | `impacto` suave (máx. 1 por vídeo) |
| Cambio de layout full ↔ split | `whoosh` corto (empieza ~100 ms antes del cambio) |
| Aparición de cartela o palabra clave | `pop` |
| Cada punto de `lista` o `pasos` | `click` |
| Conteo de `cifra` y llegada al número final | `tick` durante el conteo + `ding` al llegar |
| Plantilla `alerta` | `alerta` (zumbido suave) |
| Cambio de lado en `comparativa` | `swipe` |
| Aparición del CTA | `notificacion` |
| Punch-in de zoom | `whoosh` muy corto o nada |

Reglas de SFX:
- Densidad `media`: como máximo 1 SFX cada 2 s de media y nunca dos a la vez. `baja` = solo gancho, cambios de layout y CTA. `alta` = todos los eventos de la tabla.
- Nivel: se oyen pero nunca compiten con la voz; el pico de cada SFX queda ≥ 6 dB por debajo del pico de la voz en ese momento. Microfades de 5–10 ms en cada SFX para evitar clics.
- Si un SFX coincide con la palabra clave hablada y la enmascara, se adelanta al inicio de la palabra o se omite.
- Rotación: variante al azar dentro de cada tipo, sin repetir la misma variante dos veces seguidas.
- Sin SFX (salvo el `whoosh` de cambio de layout) en ventanas `full` personales o emocionales.

**Medición:** mide el resultado final con `ebur128` y regístralo en el informe.

### 6.7 Exportación (`pipeline/exportar.py`)
- Reels/TikTok/Shorts: 1080×1920, 30 fps (25 si la fuente es 25), H.264 High, `yuv420p`, CRF 18, BT.709 etiquetado, AAC 48 kHz 192 kbps, `-movflags +faststart`.
- `portada.jpg`: frame del gancho con la cartela visible.
- `transcripcion.txt` limpia (para escribir el copy del post).
- Nombre: `<AAAAMMDD>_<perfil>_<slug-del-gancho>.mp4`.

### 6.8 Control de calidad (`pipeline/qa.py`) → `informe_qa.md`
Además del bucle de autoevaluación de video-use, comprueba automáticamente:
- Duración real vs EDL (±0,1 s); `blackdetect` sin frames negros; sin silencios > 700 ms en la salida.
- Loudness dentro de ±1 LU del objetivo y sin clipping.
- Cara detectada en el punto medio de cada ventana.
- Subtítulos y textos dentro del área útil; ningún gráfico tapa subtítulos.
- Toda cifra de los gráficos existe en la transcripción; términos del glosario bien escritos.
- SFX dentro de la densidad del perfil y sin solapes; música del catálogo con licencia anotada y no repetida en los últimos 5 vídeos del perfil.
- Veredicto: `✅ LISTO` o `⚠️ REVISAR` con timestamps y motivo. Los `⚠️` también van a `revision/`, con el prefijo `REVISAR_` en el nombre.
- Nada se publica automáticamente. El sistema termina en `revision/`.

### 6.9 Bucle de mejora sin prompts
- `correcciones.md` del perfil: cuando quiera que algo cambie SIEMPRE ("acento de subtítulos en amarillo, no naranja"), añado una línea. El autopilot lo lee en cada ejecución y lo aplica con prioridad sobre el perfil (nunca sobre las reglas duras).
- Comando `/corregir <trabajo> "<nota>"`: rehace un vídeo concreto reutilizando transcripción y EDL (nunca re-transcribe) y al final pregunta si la nota debe pasar a `correcciones.md`.

## 7. Modos de ejecución

**Individual:** comando `/editar <ruta-video> [perfil]`, o soltar el archivo en `entrada/<perfil>/`.

**Lote desatendido (`autopilot/watcher.py`)**, vigilando `entrada/*/`:
- Cola persistente (`cola.json`), idempotente (hash del archivo: nunca procesa dos veces lo mismo), concurrencia configurable (1 por defecto).
- Por cada vídeo lanza Claude Code CLI en modo no interactivo (`claude -p --model claude-sonnet-5`) con la skill `video-autopilot` y el perfil de la carpeta, autenticado con MI SUSCRIPCIÓN (login de claude.ai), no con API key. El runner elimina explícitamente `ANTHROPIC_API_KEY` y `CLAUDE_CODE_OAUTH_TOKEN` del entorno del proceso (p. ej. con `env -u`), porque si existen Claude Code las usa y factura por API. Tras la primera ejecución headless, comprueba conmigo que el consumo aparece en el uso de la suscripción y no en la consola de la API. Verifica los flags actuales con `claude --help` y la documentación. Verifica también que las skills se cargan en modo headless; si no, pasa las instrucciones de forma explícita. Permisos por lista blanca de herramientas (incluida Agent, que video-use usa para su subagente editor), limitados al directorio del trabajo y a `editor-autopilot/`. NO uses `--dangerously-skip-permissions` ni `bypassPermissions` sin preguntarme.
- Log por trabajo; 1 reintento; si vuelve a fallar → `errores/` con el log y el motivo, y la cola sigue.
- Si se alcanza el límite de uso de la suscripción, el trabajo vuelve a la cola como `pausado_por_limite` y se reintenta más tarde (no cuenta como fallo ni va a `errores/`).
- Registro por vídeo: minutos transcritos en ElevenLabs, duración de la ejecución y el uso de Claude que reporte la salida headless (verifica qué campos incluye). Límite diario de vídeos configurable.
- Arranque con script manual `autopilot/iniciar.sh`. Pregúntame antes de instalar cualquier servicio en segundo plano (launchd/systemd).

## 8. Módulo de variantes creativas (`/variantes <trabajo> <n>`)

Objetivo: versiones realmente distintas del mismo vídeo para tests A/B de creatividades en Meta Ads y para adaptar a cada plataforma, reutilizando transcripción, EDL y renders existentes (sin re-transcribir).

Ejes de variación (combinar sin repetir combinaciones):
- **Gancho:** cartela alternativa y/o apertura en frío con otra frase fuerte del propio vídeo (único caso en que se permite reordenar, y solo la apertura).
- **Subtítulos:** otro estilo de los permitidos por el perfil.
- **Layout:** split primero / full primero / más o menos densidad de gráficos.
- **Audio:** otra pista del catálogo (mismo u otro estado de ánimo permitido) o sin música; otra densidad de SFX. Las variantes marcadas para anuncios solo usan música con `uso_permitido: anuncios`.
- **CTA:** cierre alternativo del perfil.
- **Duración:** versión completa y versión corta (15–30 s) con los beats más fuertes.
- **Formato:** 9:16, 4:5 y 1:1.

Cada variante lleva un nombre codificado (`V03_ganchoB_subsA_musica2_30s.mp4`) y una fila en `variantes.csv` que describe qué cambia, para poder leer los resultados de los tests.

Este módulo NO incluye técnicas para evadir la detección de contenido duplicado de las plataformas ni para falsificar metadatos.

## 9. Fases de construcción

Cada fase termina con una prueba real sobre `tests/muestras/` (pídeme un vídeo de 30–60 s si no hay ninguno) y el reporte ✅.

- **Fase 0 — Reconocimiento y plan (modo plan, sin instalar nada).** Con un subagente, lee completos README.md, install.md, SKILL.md y todos los `helpers/*.py` de video-use (en especial `render.py`, `transcribe.py`, `transcribe_batch.py`, `pack_transcripts.py`, `timeline_view.py`, `grade.py`). Revisa la ayuda y documentación de HyperFrames. Detecta sistema operativo (si es Windows, propón WSL2 y para), versiones de ffmpeg (libass, zscale/libplacebo, libvpx), Node (≥ 22), Python, uv y espacio en disco. Escribe `PLAN.md` con las decisiones de arquitectura, los conflictos detectados entre este documento y el código real, y cómo los resuelves. 🛑 Espera mi aprobación.
- **Fase 1 — Instalación upstream.** Sigue `install.md`. Pídeme la clave de ElevenLabs y guárdala en el `.env` de video-use (nunca en carpetas de vídeo ni en git). Verifica la clave y transcribe la muestra.
- **Fase 2 — Repo propio + perfil.** Estructura de la sección 4, `git init` con `.gitignore` (incluye `.env` y vídeos), `.claude/settings.json` del proyecto con el modelo fijado a `claude-sonnet-5`, `CLAUDE.md`, esquema de perfil con validación y cuestionario único para mi perfil.
- **Fase 3 — Normalización + cara + layout.** Render de prueba solo con layout (sin gráficos) mostrando la oscilación. 🛑 Envíame una imagen con 6 frames clave para revisar encuadre y zonas seguras.
- **Fase 4 — Biblioteca de plantillas.** 🛑 Checkpoint de diseño (6.4).
- **Fase 5 — Subtítulos, biblioteca de audio + música + SFX (🛑 checkpoint de escucha, 6.6), exportación y QA.**
- **Fase 6 — Skill `video-autopilot` + comandos slash + prueba de punta a punta en modo individual.** 🛑 Revisión del primer vídeo final + informe.
- **Fase 7 — Watcher + modo lote.** Prueba con 3 vídeos en cola.
- **Fase 8 — Variantes creativas.** Prueba con n=4.
- **Fase 9 — `README_USO.md`** (cómo añadir un perfil, soltar vídeos, revisar y corregir) y limpieza final.

## 10. Límites y condiciones de parada

Para y pregúntame antes de:
- Modificar cualquier archivo dentro de `~/Developer/video-use/`.
- Borrar cualquier archivo. El material original no se borra nunca, ni siquiera después de procesarlo.
- Instalar dependencias de sistema distintas de ffmpeg, Node 22+, uv y las librerías Python del proyecto, o cualquier servicio en segundo plano.
- Usar modos de permisos amplios en Claude Code headless.
- Transcribir más de 5 minutos de audio en total durante la construcción (coste de API).
- Generar música o efectos con la API de ElevenLabs (dime cantidad y coste estimado antes).
- Definir `ANTHROPIC_API_KEY` en cualquier entorno o archivo de configuración.
- Cambiar una regla de este documento porque creas que hay una opción mejor: propónla, no la apliques.

## 11. Criterios de aceptación finales

- [ ] Un `git pull` en video-use no rompe nada (probado).
- [ ] Un vídeo soltado en `entrada/<perfil>/` produce, sin ninguna intervención, vídeo final + `portada.jpg` + `informe_qa.md` en `revision/<perfil>/`.
- [ ] El vídeo empieza en la primera palabra del gancho, en `split`, con la cartela visible en el frame 0.
- [ ] Alternancia split/full según 6.3; la cara nunca aparece cortada; nada importante dentro de las zonas seguras.
- [ ] Subtítulos de 2 palabras en MAYÚSCULAS con tildes, palabra activa resaltada, nunca tapados por gráficos.
- [ ] Voz a −14 LUFS ±1, música con ducking, sin pops en los cortes.
- [ ] Cada vídeo lleva música del catálogo acorde al tono (no repetida en los últimos 5) y SFX sincronizados con los eventos visuales, sin tapar la voz.
- [ ] El modo lote consume la suscripción de Claude, no la API (verificado).
- [ ] Todas las ejecuciones (individual, lote y subagentes) usan `claude-sonnet-5` (verificado en la salida headless o con `/status`).
- [ ] Ninguna cifra en pantalla que no se haya dicho.
- [ ] Reprocesar el mismo vídeo no vuelve a transcribir (caché).
- [ ] 5 vídeos en lote se procesan en cola; un fallo va a `errores/` sin detener la cola.
- [ ] `/variantes` genera n versiones distintas y su `variantes.csv`.
