# uno_vs_muchos

**Cuándo:** cuando se dice que UNA persona (o un agente) hace el trabajo de muchos: «una sola persona puede encargarse de…», «hace el trabajo de 10», «sin contratar a un equipo», «un agente que lleva todo esto».

**Qué muestra:** una figura central en un círculo con borde de acento (por defecto `user`; también `bot`, `briefcase`…) y, en órbita elíptica alrededor, de 3 a 6 tareas/herramientas en nodos de icono unidas a ella por líneas. Al aterrizar, una insignia amarilla «xN» bajo la figura. Rótulo opcional (≤ 4 palabras) abajo.

**Animación:** la figura se dibuja y crece; desde ella sale una línea hacia cada tarea y el nodo aparece al final de la línea, de uno en uno (con destello de acento en el trazo). En `t_aterrizaje` el contador sube de x1 a xN con `power2.out`, la figura destella y emite una onda de acento. Después, pulsos amarillos viajan de la persona a cada tarea en bucle (tiempos fijos) y la órbita gira: nunca queda estática. Con `t_aterrizaje` = 0 todo está visible en el frame 0.

**Datos:** `icono_persona?` (default `user`), `iconos` (3–6, catálogo), `cantidad?` (entero; debe decirse en la ventana), `rotulo?` (≤ 4 palabras), `t_aterrizaje`, `sonido?`.

**Sonido recomendado:** «pop» suave por cada tarea que se conecta y un golpe/«whoosh» con brillo al aterrizar el contador.
