#!/bin/zsh
# Doble clic para arrancar el Editor Autopilot (abre http://127.0.0.1:8765 en el navegador).
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
echo "Editor Autopilot arrancando… (cierra esta ventana para pararlo)"
exec uv run python autopilot/servidor.py
