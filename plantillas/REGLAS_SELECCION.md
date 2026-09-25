# Reglas de selección de gráficos (las lee el LLM en cada vídeo)

## Principio
Cada ventana **split** debe REPRESENTAR VISUALMENTE lo que se dice en ella, no repetirlo en texto. El texto solo aparece como rótulo corto (≤ 4 palabras, literal de lo dicho). Ritmo "dopamínico": algo nuevo en pantalla casi todo el tiempo.

## Ventanas split: qué plantilla usar (en este orden de preferencia)
1. Primera ventana → `gancho` (titular ≤ 7 palabras literales del gancho, con 1–2 palabras destacadas).
2. Hay una cifra, dinero o porcentaje dicho en la ventana:
   - crecimiento o evolución → `crecimiento`;
   - solo el dato → `cifra`;
   - varios datos comparables → `grafico`.
3. Conexiones, integraciones, "con X proveedores/herramientas", un paquete de cosas → `red` (con `cantidad` si se dice el número).
4. Algo que se convierte en otra cosa ("convierte X en Y", "de X a Y", "pasa de…") → `transformacion`.
5. Una persona que hace mucho / multiplicar resultados → `uno_vs_muchos`.
6. Usar una herramienta, pedirle algo a la IA, comandos, Claude Code trabajando → `terminal` (líneas literales o resumidas de lo dicho).
7. Enumeración ("primero… segundo…", "tres cosas") → `lista`. Proceso → `pasos`. Contraste mito/realidad o antes/después → `comparativa`.
8. Error, peligro o advertencia → `alerta`. Pregunta retórica → `pregunta`.
9. Se nombra una marca con imagen en el catálogo del perfil (p. ej. Claude) → `imagen`. No se repite la misma imagen en ventanas seguidas.
10. Cualquier otra idea representable con un objeto o un concepto → `icono`, eligiendo el icono del catálogo cuyo significado encaje y un `movimiento` con sentido:
    - `subir`: crecer, despegar, mejorar;
    - `caer`: tirar, perder, desperdiciar; con `icono_receptor` si algo cae "en" algo;
    - `latir`: importancia, aviso;
    - `girar`: sistema, automatizar;
    - `sacudir`: error, prohibido;
    - `dibujar`: el resto.
11. `palabra_clave` SOLO si de verdad no hay nada visualizable (se anota en QA).
Última ventana (CTA, siempre full) → `cta` con la palabra que se pide comentar, en MAYÚSCULAS.

## Ventanas full: stickers
En cada ventana full (salvo la del CTA) pon 1–3 `sticker` sobre palabras clave representables con un icono.
- **Tiempos:** cada sticker dura 0,6–1,2 s y aterriza 0,25 s después de su inicio, que debe caer 0,25 s antes de la palabra. Tiene que terminar antes del fin de su ventana y no puede solaparse con otro sticker.
- **Contenido:** alterna el lado (izquierda/derecha). Rótulo de 1–2 palabras dichas.

## Contenido (NO negociable)
- Toda cifra que aparezca (en rótulos, `valor` o `cantidad`) tiene que decirse DENTRO de esa ventana. Si no se dice en la ventana, no pongas cifra.
- Los rótulos y textos salen de lo dicho (literal o resumido sin añadir información). Nada de datos inventados.
- Los tiempos `t`, `t_a` y `t_aterrizaje` son segundos desde el inicio de la ventana (o del sticker). Haz que coincidan con el momento en que se dice la palabra clave; el sistema deja ≥ 1 s de plano sostenido al final.
- Solo iconos que existan en el catálogo de iconos, y solo imágenes que existan en el catálogo de imágenes del perfil.
- `sonido` (opcional) fija el SFX con sentido. Tipos: moneda, papel, despegue, red, teclado, candado, reloj, subida, bajada, transformacion, camara, mensaje, engranaje, pop, click, ding, alerta, swipe, whoosh.
