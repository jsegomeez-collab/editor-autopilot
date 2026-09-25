# Puesta en marcha con TU marca (con Claude Code)

Con esta guía clonas el editor, lo instalas y lo configuras con tus colores, tipografías y estilo, todo desde Claude Code. Solo tienes que copiar y pegar los prompts. Tiempo: ~45 min.

## Qué necesitas
- Un Mac con **≥ 10 GB libres**.
- **Claude Code** instalado (https://code.claude.com/docs) y con la sesión iniciada con tu suscripción de Claude (Pro o Max). En Terminal: `claude` → `/login`.
- Acceso al repo privado en GitHub (te invita el propietario) y **GitHub CLI** con sesión iniciada: `brew install gh` y después `gh auth login`.
- La **clave de ElevenLabs**, que te pasan por privado. Nunca la pegues en el chat.
- Opcional: 1–3 vídeos tuyos ya editados con el estilo que te gusta, tu logo en PNG y tus tipografías.

---

## Paso 1 — Descargar el editor (en Terminal)
```
mkdir -p ~/Developer && cd ~/Developer
gh repo clone jsegomeez-collab/editor-autopilot
cd editor-autopilot
claude
```
Se abre Claude Code dentro del proyecto. A partir de aquí todo son prompts.

## Paso 2 — Instalar
Pega esto en Claude Code:
```
/instalar
```
Si prefieres escribirlo en tus palabras, este prompt hace lo mismo:
```
Lee INSTALACION.md y CLAUDE.md. Ejecuta ./instalar.sh --comprobar, dime qué falta y ve instalándolo conmigo paso a paso con ./instalar.sh, pidiéndome permiso antes de instalar nada. La clave de ElevenLabs la pego yo cuando el script la pida, no me la pidas en el chat. Para cuando todo salga en verde.
```
Cuando el instalador pida la clave de ElevenLabs, pégala en la ventana del script, no en el chat.

## Paso 3 — Configurar tu marca
Antes de este paso, deja tu material en una carpeta, por ejemplo `~/Desktop/mi_marca/` (vídeos de referencia, logo, tipografías). Después pega esto, cambiando `cristian` por el nombre corto de tu marca:
```
/configurar-marca cristian
```
y, en el mismo mensaje o en el siguiente:
```
Mi material de referencia está en ~/Desktop/mi_marca/: analiza los vídeos para sacar mis colores, mi estilo de subtítulos y mi ritmo, y úsalos como valores por defecto del cuestionario.
```
Claude te hará **un único cuestionario** con todo: colores, tipografías, subtítulos, música, CTA, glosario… Responde "ok" en lo que te valga el valor propuesto. Después te enseñará cómo quedan las plantillas con tu marca. Pide los cambios que quieras hasta que te guste, por ejemplo:
```
El amarillo de acento cámbialo por #00E0B8 y los subtítulos en MAYÚSCULAS. Vuelve a enseñarme las plantillas.
```

## Paso 4 — Primer vídeo de prueba
Pega esto, con la ruta de un vídeo tuyo de 30–90 s:
```
/editar ~/Desktop/mi_video.mp4 cristian 1
```
En ~7 min tendrás el vídeo editado, su portada y su informe de calidad. Míralo y dile a Claude lo que cambiarías, por ejemplo:
```
Añade a perfiles/cristian/correcciones.md que quiero los subtítulos un poco más grandes y menos stickers en cámara completa, y vuelve a editar el vídeo.
```

## Paso 5 — Uso diario (sin Claude Code)
1. Doble clic en **`Iniciar editor.command`** (en `~/Developer/editor-autopilot`). Se abre http://127.0.0.1:8765.
2. ⚙️ **Ajustes**: elige tu carpeta de destino, tu perfil por defecto y cuántas versiones quieres por vídeo (1 = solo la edición; 2–6 = variantes para Trial Reels).
3. Arrastra tus vídeos (uno o muchos) y pulsa **Editar**. Se editan de uno en uno y los tienes en tu carpeta al terminar.

### Estilo de edición
En Ajustes (o al subir) elige el estilo:
- **Con motions:** motion graphics en pantalla partida que representan lo que dices, más stickers, subtítulos con palabra activa y efectos con sentido.
- **Con título:** más básico y rápido (~4–7 min por vídeo):
  - un título fijo arriba, sacado de lo que dices, con palabras clave en tu color de acento;
  - la cámara en todo el vídeo con zooms alternos;
  - subtítulos básicos;
  - imágenes (iconos y logos de tu marca) saltando junto a tu cara cada 2–3 s;
  - efectos de sonido muy frecuentes.

## Prompts útiles para después
- **Actualizar el editor:**
  ```
  Haz git pull, ejecuta ./instalar.sh --comprobar y dime si hay algo nuevo que instalar.
  ```
- **Añadir un término al glosario:**
  ```
  Añade a mi glosario que "n8n" se escribe así y que el transcriptor suele escribir "ene ocho ene".
  ```
- **Añadir el logo de una herramienta que menciono:**
  ```
  Añade la imagen ~/Desktop/logo_notion.png a mi catálogo de imágenes para el término "Notion", tipo logo, fuente "kit de prensa oficial".
  ```
- **Diagnosticar un vídeo que falló:**
  ```
  El último vídeo de la cola ha fallado: lee su log en ~/VideoAutopilot/errores/ y explícame qué pasó y cómo arreglarlo.
  ```

## Si algo va mal
- `./instalar.sh --comprobar` te dice qué falta sin tocar nada.
- Un vídeo en **"Esperando espacio en disco"**: libera espacio (hacen falta ≥ 2,5 GB libres).
- Un vídeo **"Pausado por límite"**: has llegado al límite de uso de tu suscripción de Claude; se reintenta solo más tarde.
