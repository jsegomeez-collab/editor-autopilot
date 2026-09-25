---
description: Edita un vídeo automáticamente (sin el frontend)
argument-hint: "<ruta-del-video> [perfil] [versiones 1-6]"
---
Edita automáticamente este vídeo con el Editor Autopilot. Argumentos: "$ARGUMENTS" (ruta del vídeo, perfil opcional y número de versiones opcional). Habla en español.

1. Si falta el perfil, usa `perfil_por_defecto` de `~/VideoAutopilot/ajustes.json` (o el único perfil que haya en `perfiles/` aparte de `_ejemplo`). Si faltan las versiones, usa 1.
2. Comprueba que el archivo existe y que hay ≥ 2,5 GB libres (`df -h ~`).
3. Ejecuta en segundo plano:
   `uv run python autopilot/editar.py "<video>" --perfil perfiles/<perfil> --variantes <n>`
   Añade `--salida "<carpeta>"` si `~/VideoAutopilot/ajustes.json` tiene `carpeta_salida`.
4. Mientras trabaja, informa de las etapas en una línea cada vez: normalizar, transcribir, cortes, cara y layout, gráficos, montaje, audio y calidad.
5. Al terminar, resume:
   - el veredicto (✅ LISTO / ⚠️ REVISAR con sus avisos);
   - dónde está cada versión;
   - la duración;
   - el uso de Claude.

   Abre la carpeta del resultado con `open -R`.
6. Si falla, muestra el error exacto y el log (`~/VideoAutopilot/trabajos/<id>/`). No reintentes más de una vez.
