#!/bin/zsh
# Reconstruye el trabajo de prueba de JOSE49 hasta el layout (la transcripción sale de la caché).
set -e
cd "$(dirname "$0")/.."
T=~/VideoAutopilot/trabajos/prueba_JOSE49
E=$T/edit
P=perfiles/jose
SRC=$(uv run python pipeline/preparar_fuente.py tests/muestras/JOSE49.mp4 --destino $T/fuente --sin-espera)
STEM=$(basename $SRC .mp4)
uv run python pipeline/transcribir.py $SRC --edit $E >/dev/null
uv run python pipeline/corregir_transcripcion.py $E/transcripts/$STEM.json -o $E/transcripts_corregidas/$STEM.json \
  --glosario $P/glosario.yaml --idioma es-LatAm >/dev/null
uv run python pipeline/construir_edl.py $E/transcripts/$STEM.json tests/fixtures/JOSE49_seleccion.json --video $SRC -o $E/edl.json
uv run python pipeline/detectar_cara.py $SRC -o $E/caras.json 2>/dev/null
uv run python pipeline/planificar_layout.py --edl $E/edl.json --transcripcion $E/transcripts_corregidas/$STEM.json \
  --caras $E/caras.json --perfil $P -o $E/layout.json | head -1
echo "$E"
