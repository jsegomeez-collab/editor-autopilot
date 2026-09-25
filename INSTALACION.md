# Instalar el Editor Autopilot en un Mac

Tiempo: ~20–30 minutos, la mayor parte esperando descargas.

## Antes de empezar
- Un Mac con macOS y **al menos 10 GB libres**.
- Acceso al repo privado `jsegomeez-collab/editor-autopilot`: pídele a Jose que te invite.
- La **clave de ElevenLabs** (te la pasa Jose por un canal privado; nunca va en el repo).
- Tu **suscripción de Claude** (Pro o Max).

## Pasos
1. **Homebrew.** Si no lo tienes, sigue las instrucciones de https://brew.sh.
2. **Claude Code.** Instálalo siguiendo https://code.claude.com/docs. Después abre Terminal, escribe `claude` y haz `/login` con tu cuenta de claude.ai (no uses API key).
3. **GitHub.** En Terminal: `brew install gh`, después `gh auth login`, y elige GitHub.com → HTTPS → iniciar sesión con el navegador.
4. **Descarga el editor:**
   ```
   mkdir -p ~/Developer && cd ~/Developer
   gh repo clone jsegomeez-collab/editor-autopilot
   cd editor-autopilot
   ./instalar.sh
   ```
   El instalador comprueba todo. Antes de instalar algo (ffmpeg, Node 22, uv…) te pregunta, y te pide la clave de ElevenLabs sin mostrarla en pantalla. También descarga la biblioteca de música y efectos (~264 MB). Al terminar hace un render de prueba y te dice **"Todo listo"**.

## Uso diario
1. Doble clic en **`Iniciar editor.command`** (dentro de `~/Developer/editor-autopilot`). Se abre el navegador en http://127.0.0.1:8765.
2. ⚙️ **Ajustes** → **Elegir carpeta…**: dónde quieres los vídeos terminados. Los que el control de calidad marque para revisar van a la subcarpeta `revisar/`.
3. Arrastra tus vídeos (1 o muchos), elige el perfil y pulsa **Editar**. Se editan de uno en uno y ves el progreso de cada uno.
4. En **Terminados** los ves, lees su informe de calidad y los abres en Finder.

### Estilo de edición
En Ajustes (o al subir) elige el estilo:
- **Con motions:** motion graphics en pantalla partida que representan lo que dices, más stickers, subtítulos con palabra activa y efectos con sentido.
- **Con título:** más básico y rápido (~4–7 min por vídeo):
  - un título fijo arriba, sacado de lo que dices, con palabras clave en tu color de acento;
  - la cámara en todo el vídeo con zooms alternos;
  - subtítulos básicos;
  - imágenes (iconos y logos de tu marca) saltando junto a tu cara cada 2–3 s;
  - efectos de sonido muy frecuentes.

### Versiones para Trial Reels
En Ajustes (o al subir) elige **Versiones por vídeo**. Con 1 se hace solo la edición. Con 2–6 se generan además variantes creativas reales del mismo vídeo (`…_V1`, `…_V2`…), cada una con:
- otro gancho;
- otros motion graphics y stickers;
- otros subtítulos, otra música y otra densidad de efectos;
- otro patrón de zoom.

La V3 (y la V6) son versiones cortas de 15–30 s. Junto a los vídeos se guarda `…_variantes.csv`, que explica qué cambia en cada una, para leer los resultados del test.

Cada versión extra tarda ~5 min y usa algo más de la suscripción de Claude. **No** se tocan metadatos ni se usan trucos para ocultar duplicados: son vídeos distintos de verdad.

Para pararlo, cierra la ventana de Terminal que abre el lanzador.

## Actualizar
```
cd ~/Developer/editor-autopilot && git pull && ./instalar.sh
```

## Si algo falla
- `./instalar.sh --comprobar` te dice qué falta sin tocar nada.
- Vídeo en **"Esperando espacio en disco"**: libera espacio. Hacen falta ≥ 2,5 GB por vídeo en proceso.
- Vídeo en **"Pausado por límite"**: se alcanzó el límite de uso de tu suscripción de Claude. Se reintenta solo más tarde.
- Vídeo en **error** (falló dos veces): pulsa **Reintentar**. El log queda en `~/VideoAutopilot/errores/`.

## Qué se comparte y qué es de cada Mac
- **Compartido (repo):** el código, las plantillas, el perfil `jose` (colores, tipografías, glosario, correcciones) y la biblioteca de audio (release del repo).
- **De cada Mac:**
  - la clave de ElevenLabs (`~/Developer/video-use/.env`);
  - la sesión de Claude;
  - los vídeos (`~/VideoAutopilot/`);
  - los ajustes del frontend;
  - el historial de rotación de música.
