#!/bin/zsh
# Instalador del Editor Autopilot para un Mac nuevo (o comprobación en uno ya instalado).
# Uso (desde la carpeta del repo, que debe estar en ~/Developer/editor-autopilot):
#   ./instalar.sh              instala lo que falte (pregunta antes de instalar nada del sistema)
#   ./instalar.sh --comprobar  solo comprueba, no instala nada
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"
VIDEO_USE="$HOME/Developer/video-use"
GH_REPO="jsegomeez-collab/editor-autopilot"
AUDIO_TAG="biblioteca-audio-v1"
AUDIO_SHA="95fa6c8d2fdcc973dd7d7bf4a1730fed5bfab525c1ceb0f3c586930621003464"
SOLO_COMPROBAR=0; [[ "${1:-}" == "--comprobar" ]] && SOLO_COMPROBAR=1
FALLOS=0

ok()    { print -P "%F{green}✔%f $1"; }
mal()   { print -P "%F{red}✘%f $1"; FALLOS=$((FALLOS+1)); }
aviso() { print -P "%F{yellow}!%f $1"; }
titulo(){ print -P "\n%B$1%b"; }
preguntar() {  # preguntar "texto" -> 0 si responde s
  (( SOLO_COMPROBAR )) && return 1
  read "r?$1 [s/N] "; [[ "$r" == [sS]* ]]
}

[[ "$(uname)" == "Darwin" ]] || { mal "Este instalador es para macOS"; exit 1; }
[[ "$REPO" == "$HOME/Developer/editor-autopilot" ]] || aviso "El repo está en $REPO (se recomienda ~/Developer/editor-autopilot)"

titulo "1. Herramientas de base"
if command -v brew >/dev/null; then ok "Homebrew"; else
  mal "Falta Homebrew: instálalo desde https://brew.sh y vuelve a ejecutar este script"; exit 1; fi
for herramienta in git gh; do
  if command -v $herramienta >/dev/null; then ok "$herramienta"
  elif preguntar "Falta $herramienta. ¿Lo instalo con Homebrew?"; then brew install $herramienta && ok "$herramienta instalado"
  else mal "Falta $herramienta"; fi
done
if command -v uv >/dev/null; then ok "uv $(uv --version | cut -d' ' -f2)"
elif preguntar "Falta uv (gestor de Python). ¿Lo instalo con Homebrew?"; then brew install uv && ok "uv instalado"
else mal "Falta uv"; fi

titulo "2. ffmpeg con libass (subtítulos) y zimg (HDR)"
if command -v ffmpeg >/dev/null && ffmpeg -hide_banner -filters 2>/dev/null | grep -q " subtitles " \
   && ffmpeg -hide_banner -filters 2>/dev/null | grep -q " zscale "; then
  ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3) con subtitles y zscale"
elif preguntar "Hace falta ffmpeg de homebrew-ffmpeg con libass y zimg (sustituye al ffmpeg de Homebrew si lo tienes). ¿Lo instalo? (tarda unos minutos)"; then
  brew list ffmpeg >/dev/null 2>&1 && brew uninstall ffmpeg
  brew tap homebrew-ffmpeg/ffmpeg && brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-zimg && ok "ffmpeg instalado"
else mal "ffmpeg sin libass/zscale"; fi

titulo "3. Node ≥ 22 (para HyperFrames)"
node22=""
for d in $HOME/.nvm/versions/node/v2[2-9]*/bin(N) /opt/homebrew/opt/node@22/bin $(dirname "$(command -v node 2>/dev/null || echo /nonexistent)"); do
  [[ -x "$d/node" ]] && [[ $("$d/node" --version | sed 's/v//;s/\..*//') -ge 22 ]] && { node22="$d"; break; }
done
if [[ -n "$node22" ]]; then ok "Node $("$node22/node" --version) en $node22"
elif preguntar "Falta Node 22. ¿Instalo node@22 con Homebrew?"; then brew install node@22 && ok "Node 22 instalado"
else mal "Falta Node ≥ 22"; fi

titulo "4. Claude Code (con tu suscripción, NO con API key)"
if command -v claude >/dev/null; then
  ok "Claude Code $(claude --version | cut -d' ' -f1)"
  estado=$(env -u ANTHROPIC_API_KEY -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_AUTH_TOKEN claude auth status 2>/dev/null)
  if echo "$estado" | grep -q '"authMethod": "claude.ai"'; then ok "Sesión iniciada con la suscripción de claude.ai"
  else mal "Claude Code no tiene sesión de claude.ai: ejecuta 'claude' y haz /login con tu cuenta"; fi
  [[ -n "${ANTHROPIC_API_KEY:-}" ]] && aviso "Tienes ANTHROPIC_API_KEY en el entorno: el editor la ignora, pero bórrala de tu perfil de shell para no pagar por API sin querer"
else mal "Falta Claude Code: instálalo siguiendo https://code.claude.com/docs y haz /login con tu suscripción"; fi

titulo "5. video-use (base de transcripción) en $VIDEO_USE"
if [[ -d "$VIDEO_USE/.git" ]]; then ok "video-use clonado"
elif preguntar "¿Clono video-use en $VIDEO_USE?"; then
  mkdir -p "$HOME/Developer" && git clone -q https://github.com/browser-use/video-use "$VIDEO_USE" && ok "video-use clonado"
else mal "Falta video-use"; fi
if [[ -d "$VIDEO_USE" ]]; then
  if [[ -x "$VIDEO_USE/.venv/bin/python" ]]; then ok "Entorno de video-use"
  elif (( ! SOLO_COMPROBAR )); then (cd "$VIDEO_USE" && uv sync --python 3.12 -q) && ok "Entorno de video-use creado"
  else mal "Falta el entorno de video-use (uv sync)"; fi
  mkdir -p "$HOME/.claude/skills"; [[ -L "$HOME/.claude/skills/video-use" ]] || ln -sfn "$VIDEO_USE" "$HOME/.claude/skills/video-use"
  # Clave de ElevenLabs: solo en ~/Developer/video-use/.env (nunca en el repo).
  clave=$(sed -n 's/^ELEVENLABS_API_KEY=//p' "$VIDEO_USE/.env" 2>/dev/null | tr -d '[:space:]')
  if [[ -z "$clave" ]] && (( ! SOLO_COMPROBAR )); then
    read -s "clave?Pega la clave de ElevenLabs (no se mostrará): "; echo
    printf 'ELEVENLABS_API_KEY=%s\n' "$clave" > "$VIDEO_USE/.env"; chmod 600 "$VIDEO_USE/.env"
  fi
  if [[ -n "$clave" ]]; then
    codigo=$(curl -s -o /dev/null -w '%{http_code}' -H "xi-api-key: $clave" https://api.elevenlabs.io/v1/user)
    [[ "$codigo" == "200" ]] && ok "Clave de ElevenLabs válida" || mal "La clave de ElevenLabs no funciona (HTTP $codigo)"
  else mal "Falta la clave de ElevenLabs en $VIDEO_USE/.env"; fi
fi

titulo "6. Proyecto (Python) y biblioteca de audio"
if (( ! SOLO_COMPROBAR )); then (cd "$REPO" && uv sync -q) && ok "Entorno Python del proyecto"; fi
musica=$(ls "$REPO"/biblioteca_audio/musica/*/*.flac 2>/dev/null | wc -l | tr -d ' ')
if (( musica >= 20 )); then ok "Biblioteca de audio ($musica pistas de música)"
elif (( ! SOLO_COMPROBAR )); then
  if gh auth status >/dev/null 2>&1 || { aviso "Inicia sesión en GitHub para descargar la biblioteca:"; gh auth login; }; then
    tmp=$(mktemp -d); echo "Descargando la biblioteca de audio (~264 MB)…"
    gh release download "$AUDIO_TAG" --repo "$GH_REPO" -p '*.tar' -D "$tmp" \
      && [[ "$(shasum -a 256 "$tmp"/*.tar | cut -d' ' -f1)" == "$AUDIO_SHA" ]] \
      && tar -xf "$tmp"/*.tar -C "$REPO" && ok "Biblioteca de audio instalada" || mal "No se pudo descargar/verificar la biblioteca de audio"
    rm -rf "$tmp"
  fi
else mal "Falta la biblioteca de audio"; fi
mkdir -p "$HOME/VideoAutopilot"/{entrada,trabajos,revision,errores,cache_transcripciones}

titulo "7. Validación"
if (( ! SOLO_COMPROBAR )) && (( FALLOS == 0 )); then
  (cd "$REPO" && uv run pytest -q tests 2>&1 | tail -1)
  echo "Render de prueba (la primera vez descarga el Chrome de HyperFrames, ~100 MB)…"
  (cd "$REPO" && uv run python pipeline/render_plantillas.py --preview icono --perfil perfiles/jose --duracion 2 --fps 25 \
     -o /tmp/prueba_autopilot.mp4 >/dev/null 2>&1) && ok "Render de plantillas" && rm -f /tmp/prueba_autopilot.mp4 \
     || mal "Falló el render de prueba (revisa Node 22 y el espacio en disco)"
fi
libres=$(df -g "$HOME" | awk 'NR==2 {print $4}')
(( libres >= 5 )) && ok "Espacio libre: ${libres} GB" || aviso "Solo hay ${libres} GB libres: el editor necesita ≥ 2,5 GB por vídeo en proceso (recomendado ≥ 10 GB)"

echo
if (( FALLOS == 0 )); then
  print -P "%F{green}%BTodo listo.%b%f Para empezar: doble clic en «Iniciar editor.command» (o ./autopilot/iniciar.sh)."
else
  print -P "%F{red}%B$FALLOS problema(s).%b%f Corrígelos y vuelve a ejecutar ./instalar.sh"
  exit 1
fi
