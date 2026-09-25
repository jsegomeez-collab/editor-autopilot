---
description: Crea el perfil de marca propio (colores, tipografías, estilo, glosario, logo) y lo deja por defecto
argument-hint: "[nombre corto de la marca, p. ej. cristian]"
---
Vas a crear el perfil de marca de esta persona para el Editor Autopilot. Habla SIEMPRE en español, claro y sin tecnicismos.
Nombre corto sugerido (carpeta): "$ARGUMENTS". Si está vacío, pregúntalo en el cuestionario.

## Contexto (léelo antes de preguntar nada)
- `CLAUDE.md`, `PLAN.md` (sobre todo §7, §9 y §10), `pipeline/perfil.py` (el esquema: es la única fuente de verdad de los campos válidos), `perfiles/_ejemplo/` y `perfiles/jose/` (perfil completo de referencia), `tests/referencias/ANALISIS_ESTILO.md` (cómo se analizó el estilo de Jose) y `plantillas/REGLAS_SELECCION.md`.
- NO modifiques el perfil `jose` ni ningún otro perfil existente.

## Paso 1 — Material de referencia (opcional pero recomendado)
Pregunta si tiene 1–3 vídeos suyos ya editados con el estilo que le gusta, y su logo, tipografías o manual de marca si los tiene. Si da vídeos:
- Extrae hojas de contactos a 1 fps con ffmpeg y míralas. Mide los cortes con `scdetect` y el loudness con `ebur128`.
- Muestrea los colores dominantes (acento, fondo) con PIL, como en `tests/referencias/ANALISIS_ESTILO.md`.
- Resume lo que ves (colores en hex, estilo de subtítulos, ritmo, tipo de gráficos) en `perfiles/<nombre>/ANALISIS_ESTILO.md`.

## Paso 2 — Un único cuestionario
Hazle UNA sola vez TODAS las preguntas juntas, numeradas y con un valor por defecto entre [corchetes] (propuesto a partir del análisis si lo hay), para que pueda responder "ok":
1. Nombre de la marca tal como debe salir y nombre corto de la carpeta.
2. Español es-ES o es-LatAm (cambia el formato de cifras: "30.000 $" o "$30.000").
3. Plataformas.
4. Colores en hex:
   - fondo de los paneles (oscuro, legible);
   - color del texto;
   - 1–2 acentos.
5. Tipografías: titulares, subtítulos, énfasis (serif itálica opcional) y respaldo. Si no tiene archivos, propón fuentes libres de Google Fonts (licencia OFL) parecidas a su estilo.
6. Logo (PNG transparente; solo va en el CTA final) o ninguno.
7. Ritmo: rápido o natural.
8. Densidad de cambios visuales. Puede elegir el mismo ritmo "dopamínico" de Jose (ventanas de 1,2–3,5 s, 62 % split) o algo más pausado.
9. Subtítulos:
   - estilo mixto, caja o contorno;
   - mayúsculas o minúsculas;
   - posición en cámara completa (% del alto).
10. Transición: corte, push o destello.
11. Música (estados de ánimo permitidos y el de por defecto) y efectos (densidad baja, media o alta).
12. CTA por defecto (admite `{palabra}`, que se toma de lo que dice en cada vídeo) y CTAs alternativos.
13. Duración máxima objetivo en segundos.
14. Glosario: nombres de marcas, productos o personas que usa a menudo, con su grafía exacta.
15. Imágenes de marca para la plantilla `imagen` (logos de herramientas que menciona), si quiere, con su procedencia.

## Paso 3 — Crear el perfil
- Crea `perfiles/<nombre>/` con `perfil.yaml`, `glosario.yaml`, `correcciones.md` (vacío con su cabecera), `fuentes/` y, si los hay, `logo/` e `imagenes/` (con `catalogo.yaml`).
- **Tipografías:**
  - de Google Fonts, descarga los TTF estáticos: `curl "https://fonts.googleapis.com/css2?family=<Familia>:wght@700"` devuelve la URL del .ttf;
  - comprueba con `uvx --from fonttools` que tienen `¿ÁÉÍÓÚÑ ÜÇ 300 € 10 %?`;
  - usa en `familia` el nombre de familia INTERNO (con `fc-scan`).
- **Plantillas:** en `plantillas_permitidas` incluye todas las de `pipeline/perfil.py` salvo las que la persona excluya. Nunca quites gancho, cta ni palabra_clave.
- **Validación:** `uv run python pipeline/perfil.py perfiles/<nombre>` tiene que decir ✅. Si falla, corrige y repite.

## Paso 4 — Enseñarle cómo queda
- Renderiza los previews de todas las plantillas con SU perfil: `uv run python pipeline/render_plantillas.py --preview <plantilla> --perfil perfiles/<nombre> --duracion 3 --fps 25 -o /tmp/prev_<plantilla>.mp4` (de 2 en 2 como máximo, la máquina puede tener poca RAM).
- Si dio un vídeo suyo, haz una hoja de contactos en contexto como `pipeline/hoja_plantillas.py`. Si no, un mosaico de fotogramas clave de los previews.
- Ábreselo (`open …`) y pregunta qué cambiaría. Itera hasta que diga que le gusta.

## Paso 5 — Dejarlo por defecto
- Con el editor arrancado: `curl -s -X POST http://127.0.0.1:8765/api/ajustes -H 'Content-Type: application/json' -d '{"perfil_por_defecto":"<nombre>"}'`.
- Si no está arrancado, escribe `{"perfil_por_defecto": "<nombre>"}` fusionado con lo que ya haya en `~/VideoAutopilot/ajustes.json`.
- Crea `~/VideoAutopilot/entrada/<nombre>/`.

## Paso 6 — Cierre
- Haz `git add perfiles/<nombre> && git commit` con un mensaje claro. NO hagas `git push` sin preguntar primero: el repo es compartido.
- Explícale en 4–5 líneas cómo usarlo:
  - doble clic en «Iniciar editor.command», elegir su perfil y arrastrar vídeos;
  - si quiere un cambio que se aplique siempre, basta con añadir una línea a `perfiles/<nombre>/correcciones.md`.

Reglas: no inventes flags ni campos (mira el esquema); si algo falla 3 veces, para y enseña el error.
