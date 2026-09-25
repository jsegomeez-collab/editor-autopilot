# cifra

**Cuándo:** cuando en la ventana se dice una cifra concreta que conviene fijar en la memoria (ingresos, ahorro, porcentaje, precio). La cifra tiene que decirse en esa ventana: nunca se inventa.

**Qué muestra:** la cifra grande con su símbolo (`$`, `€` o `%`) en formato es-LatAm ("$30.000", "93%", "4,5%") y, debajo, una etiqueta corta (≤ 5 palabras) con un trazo de acento.

**Animación:** la cifra entra y cuenta desde 0 durante ~1 s (easing `power2.out`, cada fotograma ya con el formato correcto) y llega al valor exactamente en `t_aterrizaje`. En ese momento se tiñe de acento y da un pequeño golpe de escala. Medio segundo después aparece la etiqueta. El resplandor y el conjunto derivan suavemente hasta el final. Si `t_aterrizaje` deja menos de 1 s al final, se adelanta para sostener el último estado.

**Datos:** ver `schema.json`.
