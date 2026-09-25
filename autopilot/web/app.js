/* =========================================================
   Editor Autopilot — lógica de la interfaz (JS vanilla)
   Habla con el motor local mediante la API /api/*.
   ========================================================= */
"use strict";

const MAX_ARCHIVOS = 15;
const INTERVALO_SONDEO_MS = 2000;

// Etapas visibles en el stepper (las dos de gráficos se agrupan en un paso).
const PASOS = [
  { clave: "normalizando", nombre: "Normalizar" },
  { clave: "transcribiendo", nombre: "Transcribir" },
  { clave: "decidiendo_cortes", nombre: "Cortes" },
  { clave: "cara_y_layout", nombre: "Cara y layout" },
  { clave: "graficos", nombre: "Gráficos" },
  { clave: "montaje", nombre: "Montaje" },
  { clave: "audio", nombre: "Audio" },
  { clave: "control_calidad", nombre: "Calidad" },
];

const INDICE_ETAPA = {
  en_cola: -1,
  normalizando: 0,
  transcribiendo: 1,
  decidiendo_cortes: 2,
  cara_y_layout: 3,
  decidiendo_graficos: 4,
  renderizando_graficos: 4,
  montaje: 5,
  audio: 6,
  control_calidad: 7,
  terminado: 8,
};

const NOMBRE_ETAPA = {
  en_cola: "En cola",
  normalizando: "Normalizando el vídeo",
  transcribiendo: "Transcribiendo",
  decidiendo_cortes: "Decidiendo cortes",
  cara_y_layout: "Cara y layout",
  decidiendo_graficos: "Diseñando gráficos",
  renderizando_graficos: "Renderizando gráficos",
  montaje: "Montaje",
  audio: "Música y efectos",
  control_calidad: "Control de calidad",
  terminado: "Terminado",
};

const ESTADOS_COLA = ["procesando", "pausado_por_limite", "pendiente", "error"];
const PRIORIDAD_COLA = { procesando: 0, pausado_por_limite: 1, pendiente: 2, error: 3 };

// Iconos SVG en línea (sin dependencias externas).
const ICONO = {
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="14" rx="2.5"/><path d="m16 10 5-3v10l-5-3"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/></svg>',
  reloj: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  reintentar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/></svg>',
  carpeta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  ojo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  cerrar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  flecha: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
  pausa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6v12M15 6v12"/></svg>',
  alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.01"/></svg>',
};

// ---------------------------------------------------------
// Estado de la aplicación
// ---------------------------------------------------------
const app = {
  estado: null,          // última respuesta de /api/estado
  conectado: null,       // null = aún no sabemos
  seleccion: [],         // File[] elegidos antes de subir
  subiendo: false,
  perfilTocado: false,   // si el usuario cambió el perfil a mano, no lo pisamos
  tarjetasCola: new Map(),
  tarjetasResultado: new Map(),
  videoAbierto: null,    // id del vídeo en el modal
  verPendiente: null,    // id pedido por ?ver= antes de tener datos
  ajustesAbiertos: false,
  carpetaBorrador: null, // ruta elegida en el panel aún sin guardar
};

const $ = (sel) => document.querySelector(sel);

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function formatearTamano(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1).replace(".", ",")} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2).replace(".", ",")} GB`;
}

function formatearDuracion(segundos) {
  if (segundos == null || isNaN(segundos)) return "—";
  const s = Math.round(segundos);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${r}` : `${m}:${r}`;
}

function fecha(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d) ? null : d;
}

function hora(iso) {
  const d = fecha(iso);
  return d ? d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "";
}

function haceCuanto(iso) {
  const d = fecha(iso);
  if (!d) return "";
  const seg = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (seg < 60) return "hace un momento";
  const min = Math.floor(seg / 60);
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h} h`;
  return d.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
}

function transcurrido(iso) {
  const d = fecha(iso);
  if (!d) return "0:00";
  return formatearDuracion((Date.now() - d.getTime()) / 1000);
}

// ---------------------------------------------------------
// Red
// ---------------------------------------------------------
async function pedir(ruta, opciones = {}) {
  const resp = await fetch(ruta, { cache: "no-store", ...opciones });
  if (!resp.ok) {
    let detalle = "";
    try { detalle = (await resp.json()).detail || ""; } catch (_) { /* sin cuerpo JSON */ }
    const err = new Error(detalle || `Error ${resp.status}`);
    err.http = resp.status;
    throw err;
  }
  const tipo = resp.headers.get("content-type") || "";
  return tipo.includes("application/json") ? resp.json() : null;
}

function postJSON(ruta, cuerpo) {
  return pedir(ruta, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
}

function marcarConexion(ok) {
  if (app.conectado === ok) return;
  const antes = app.conectado;
  app.conectado = ok;
  if (!ok) {
    toast("Sin conexión con el motor", "error");
    pintarEstadoMotor();
  } else if (antes === false) {
    toast("Conectado de nuevo con el motor", "ok");
  }
}

// Manejo común de errores de acciones puntuales.
function errorAccion(err, texto) {
  if (err && err.http) toast(`${texto}: ${err.message}`, "error");
  else { toast("Sin conexión con el motor", "error"); }
}

// ---------------------------------------------------------
// Sondeo del estado
// ---------------------------------------------------------
let temporizadorSondeo = null;

async function sondear() {
  clearTimeout(temporizadorSondeo);
  try {
    const datos = await pedir("/api/estado");
    app.estado = datos;
    marcarConexion(true);
    pintarTodo();
  } catch (err) {
    marcarConexion(false);
  } finally {
    temporizadorSondeo = setTimeout(sondear, INTERVALO_SONDEO_MS);
  }
}

function pintarTodo() {
  pintarEstadoMotor();
  pintarContador();
  pintarAvisoCarpeta();
  pintarPerfiles();
  pintarCola();
  pintarResultados();
  pintarVacio();

  // ?ver=<id> pedido antes de tener datos.
  if (app.verPendiente) {
    const id = app.verPendiente;
    app.verPendiente = null;
    abrirVideo(id);
  }
  if (app.videoAbierto) pintarInfoModal();
}

// ---------------------------------------------------------
// Cabecera
// ---------------------------------------------------------
function pintarEstadoMotor() {
  const caja = $("#estadoMotor");
  const texto = $("#estadoMotorTexto");
  if (app.conectado === false) {
    caja.dataset.estado = "offline";
    texto.textContent = "Sin conexión";
    return;
  }
  const motor = app.estado?.motor;
  if (!motor) return;
  const pausa = fecha(motor.pausado_hasta);
  if (pausa && pausa > new Date()) {
    caja.dataset.estado = "pausado";
    texto.textContent = `Pausado por límite hasta las ${hora(motor.pausado_hasta)}`;
  } else if (motor.trabajando) {
    caja.dataset.estado = "trabajando";
    texto.textContent = "Trabajando";
  } else {
    caja.dataset.estado = "espera";
    texto.textContent = "En espera";
  }
}

function pintarContador() {
  const motor = app.estado?.motor;
  if (!motor) return;
  const hechos = motor.hechos_hoy ?? 0;
  const limite = motor.limite_diario || 0;
  $("#contadorTexto").textContent = `${hechos} / ${limite}`;
  const frac = limite ? Math.min(1, hechos / limite) : 0;
  const circ = 2 * Math.PI * 15;
  const anillo = $("#anilloValor");
  anillo.style.strokeDasharray = circ;
  anillo.style.strokeDashoffset = circ * (1 - frac);
  anillo.style.stroke = frac >= 1 ? "var(--revisar)" : "var(--acento)";
}

function pintarAvisoCarpeta() {
  const ajustes = app.estado?.ajustes;
  $("#avisoCarpeta").hidden = !ajustes || !!ajustes.carpeta_salida;
}

function rellenarSelect(select, perfiles, valor) {
  const actuales = [...select.options].map((o) => o.value).join("|");
  if (actuales !== perfiles.join("|")) {
    select.innerHTML = perfiles.map((p) => `<option value="${escapar(p)}">${escapar(p)}</option>`).join("");
  }
  if (valor != null && perfiles.includes(valor)) select.value = valor;
}

function pintarPerfiles() {
  const perfiles = app.estado?.perfiles || [];
  const porDefecto = app.estado?.ajustes?.perfil_por_defecto;
  const select = $("#selectPerfil");
  rellenarSelect(select, perfiles, app.perfilTocado ? select.value : porDefecto);
}

// ---------------------------------------------------------
// Cola
// ---------------------------------------------------------
function htmlStepper(item) {
  const idx = INDICE_ETAPA[item.etapa] ?? -1;
  return PASOS.map((paso, i) => {
    let clase = "";
    if (i < idx) clase = "paso--hecho";
    else if (i === idx) clase = "paso--activo";
    return `<div class="paso ${clase}" title="${escapar(paso.nombre)}"><div class="paso__linea"></div><span class="paso__nombre">${escapar(paso.nombre)}</span></div>`;
  }).join("");
}

function badgeEstado(estado) {
  switch (estado) {
    case "procesando": return '<span class="badge badge--procesando">Editando</span>';
    case "pendiente": return '<span class="badge badge--pendiente">En espera</span>';
    case "pausado_por_limite": return '<span class="badge badge--pausado">Pausado por límite</span>';
    case "error": return '<span class="badge badge--error">Error</span>';
    default: return "";
  }
}

function crearTarjetaCola(item) {
  const el = document.createElement("article");
  el.className = "tarjeta-cola";
  el.dataset.id = item.id;
  el.innerHTML = `
    <div class="cola__miniatura"></div>
    <div class="cola__cuerpo">
      <div class="cola__fila">
        <span class="cola__nombre"></span>
        <span class="cola__perfil"></span>
      </div>
      <div class="cola__fila cola__progreso">
        <span class="cola__etapa"></span>
        <div class="barra cola__barra"><div class="barra__relleno"></div></div>
        <span class="cola__pct"></span>
      </div>
      <div class="stepper"></div>
      <div class="cola__fila"><span class="cola__mensaje"></span></div>
    </div>
    <div class="cola__acciones">
      <span class="cola__badge"></span>
      <span class="cola__tiempo"></span>
      <span class="cola__boton"></span>
    </div>`;
  el.addEventListener("click", (ev) => {
    const boton = ev.target.closest("[data-reintentar]");
    if (boton) reintentar(boton.dataset.reintentar, boton);
  });
  return el;
}

function actualizarTarjetaCola(el, item, posicion) {
  const estado = item.estado;
  const mini = el.querySelector(".cola__miniatura");
  if (estado === "pendiente") {
    // Los pendientes muestran su turno en la miniatura.
    if (mini.dataset.pos !== String(posicion)) {
      mini.dataset.pos = posicion;
      mini.innerHTML = `<span class="cola__turno">#${posicion}</span>`;
    }
  } else if (el.dataset.estado !== estado) {
    delete mini.dataset.pos;
    mini.innerHTML = estado === "error" ? ICONO.alerta : estado === "pausado_por_limite" ? ICONO.pausa : ICONO.video;
  }
  if (el.dataset.estado !== estado) {
    el.dataset.estado = estado;
    el.querySelector(".cola__badge").innerHTML = badgeEstado(estado);
    el.querySelector(".cola__boton").innerHTML = estado === "error"
      ? `<button class="boton boton--peligro boton--pequeno" type="button" data-reintentar="${escapar(item.id)}">${ICONO.reintentar}Reintentar</button>`
      : "";
  }

  el.querySelector(".cola__nombre").textContent = item.nombre;
  el.querySelector(".cola__nombre").title = item.nombre;
  el.querySelector(".cola__perfil").textContent = `Perfil ${item.perfil}`;

  let etapa = NOMBRE_ETAPA[item.etapa] || item.etapa;
  if (estado === "error") etapa = `Falló en: ${etapa}`;
  if (estado === "pendiente") etapa = "Esperando turno";
  el.querySelector(".cola__etapa").textContent = etapa;

  const progreso = Math.max(0, Math.min(100, Math.round(item.progreso || 0)));
  const barra = el.querySelector(".cola__barra");
  barra.className = "barra cola__barra" +
    (estado === "error" ? " barra--error" : estado === "pausado_por_limite" ? " barra--pausa" : estado === "pendiente" ? " barra--quieta" : "");
  barra.firstElementChild.style.width = `${progreso}%`;
  el.querySelector(".cola__pct").textContent = `${progreso}%`;

  const stepper = el.querySelector(".stepper");
  if (stepper.dataset.etapa !== item.etapa) {
    stepper.dataset.etapa = item.etapa;
    stepper.innerHTML = htmlStepper(item);
  }

  let mensaje = item.mensaje || "";
  if (estado === "error") mensaje = item.error || mensaje || "Algo salió mal al editar este vídeo.";
  if (estado === "pausado_por_limite" && !mensaje) mensaje = "Se ha alcanzado el límite diario. Continuará automáticamente.";
  if (estado === "pendiente" && !mensaje) mensaje = "Empezará en cuanto termine el vídeo anterior.";
  const msg = el.querySelector(".cola__mensaje");
  msg.textContent = mensaje;
  msg.title = mensaje;

  const tiempo = el.querySelector(".cola__tiempo");
  if (estado === "procesando" && item.iniciado) {
    tiempo.dataset.desde = item.iniciado;
    tiempo.innerHTML = `${ICONO.reloj}<span>${transcurrido(item.iniciado)}</span>`;
  } else {
    delete tiempo.dataset.desde;
    tiempo.textContent = `Añadido ${haceCuanto(item.creado)}`;
  }
}

function ordenarCola(a, b) {
  const p = PRIORIDAD_COLA[a.estado] - PRIORIDAD_COLA[b.estado];
  if (p) return p;
  return (fecha(a.creado) || 0) - (fecha(b.creado) || 0); // los más antiguos se editan antes
}

function sincronizarOrden(contenedor, elementos) {
  const actuales = [...contenedor.children];
  const iguales = actuales.length === elementos.length && actuales.every((e, i) => e === elementos[i]);
  if (iguales) return;
  // Solo se añaden/mueven los que no están en su sitio para no reiniciar animaciones.
  elementos.forEach((el, i) => {
    if (contenedor.children[i] !== el) contenedor.insertBefore(el, contenedor.children[i] || null);
  });
}

function pintarCola() {
  const items = (app.estado?.items || []).filter((i) => ESTADOS_COLA.includes(i.estado)).sort(ordenarCola);
  const contenedor = $("#listaCola");
  const vivos = new Set();
  let turno = items.some((i) => i.estado === "procesando") ? 1 : 0;
  const elementos = items.map((item) => {
    vivos.add(item.id);
    let el = app.tarjetasCola.get(item.id);
    if (!el) {
      el = crearTarjetaCola(item);
      app.tarjetasCola.set(item.id, el);
    }
    if (item.estado === "pendiente") turno++;
    actualizarTarjetaCola(el, item, turno);
    return el;
  });
  for (const [id, el] of app.tarjetasCola) {
    if (!vivos.has(id)) { el.remove(); app.tarjetasCola.delete(id); }
  }
  sincronizarOrden(contenedor, elementos);
  $("#chipCola").textContent = items.length;
  $("#seccionCola").hidden = items.length === 0;
}

async function reintentar(id, boton) {
  if (boton) boton.disabled = true;
  try {
    await postJSON(`/api/reintentar/${encodeURIComponent(id)}`);
    toast("Vídeo de nuevo en la cola", "ok");
    sondear();
  } catch (err) {
    errorAccion(err, "No se pudo reintentar");
    if (boton) boton.disabled = false;
  }
}

// ---------------------------------------------------------
// Resultados
// ---------------------------------------------------------
function urlPortada(item) {
  return `/api/portada/${encodeURIComponent(item.id)}?v=${encodeURIComponent(item.terminado || "")}`;
}

function badgeVeredicto(item, extra = "") {
  return item.veredicto === "REVISAR"
    ? `<span class="badge badge--revisar badge--emoji ${extra}">⚠️ Revisar</span>`
    : `<span class="badge badge--listo badge--emoji ${extra}">✅ Listo</span>`;
}

function htmlAvisos(avisos, abierto = false) {
  if (!avisos || !avisos.length) return "";
  const n = avisos.length;
  return `
    <details class="avisos"${abierto ? " open" : ""}>
      <summary>${n} ${n === 1 ? "aviso" : "avisos"} que revisar ${ICONO.flecha}</summary>
      <ul>${avisos.map((a) => `<li>${escapar(a)}</li>`).join("")}</ul>
    </details>`;
}

function htmlTarjetaResultado(item) {
  const portada = item.tiene_portada
    ? `<img src="${urlPortada(item)}" alt="" loading="lazy">`
    : `<div class="resultado__sin-portada">${ICONO.video}</div>`;
  return `
    <button class="resultado__portada" type="button" data-ver="${escapar(item.id)}" aria-label="Ver ${escapar(item.nombre)}">
      ${portada}
      ${badgeVeredicto(item, "resultado__badge")}
      <span class="resultado__play">${ICONO.play}</span>
      <span class="resultado__duracion">${formatearDuracion(item.duracion_s)}</span>
    </button>
    <div class="resultado__cuerpo">
      <div class="resultado__nombre" title="${escapar(item.nombre)}">${escapar(item.nombre)}</div>
      <div class="resultado__meta"><span>Perfil ${escapar(item.perfil)}</span><span>·</span><span>${escapar(haceCuanto(item.terminado || item.creado))}</span></div>
      ${htmlAvisos(item.avisos)}
      <div class="resultado__acciones">
        <button class="boton boton--secundario boton--pequeno" type="button" data-ver="${escapar(item.id)}">${ICONO.ojo}Ver</button>
        <button class="boton boton--fantasma boton--pequeno" type="button" data-abrir="${escapar(item.id)}" title="Mostrar en Finder">${ICONO.carpeta}Finder</button>
      </div>
    </div>`;
}

function pintarResultados() {
  const items = (app.estado?.items || []).filter((i) => i.estado === "listo" || i.estado === "revisar");
  const galeria = $("#galeria");
  const vivos = new Set();
  const elementos = items.map((item) => {
    vivos.add(item.id);
    // Firma: si no cambia, no se toca la tarjeta (se conserva el desplegable abierto).
    const firma = [item.estado, item.veredicto, item.duracion_s, item.tiene_portada, item.terminado, (item.avisos || []).join("¦"), item.nombre].join("|");
    let el = app.tarjetasResultado.get(item.id);
    if (!el) {
      el = document.createElement("article");
      el.className = "tarjeta-resultado";
      el.dataset.id = item.id;
      app.tarjetasResultado.set(item.id, el);
    }
    if (el.dataset.firma !== firma) {
      el.dataset.firma = firma;
      el.dataset.veredicto = item.veredicto || "LISTO";
      el.innerHTML = htmlTarjetaResultado(item);
    }
    return el;
  });
  for (const [id, el] of app.tarjetasResultado) {
    if (!vivos.has(id)) { el.remove(); app.tarjetasResultado.delete(id); }
  }
  sincronizarOrden(galeria, elementos);
  $("#chipResultados").textContent = items.length;
  $("#galeriaVacia").hidden = items.length > 0;
}

function pintarVacio() {
  const hay = (app.estado?.items || []).length > 0;
  $("#estadoVacio").hidden = hay;
  $("#seccionResultados").hidden = !hay;
}

async function abrirEnFinder(id, boton) {
  if (boton) boton.disabled = true;
  try {
    await postJSON(`/api/abrir/${encodeURIComponent(id)}`);
  } catch (err) {
    errorAccion(err, "No se pudo abrir en Finder");
  } finally {
    if (boton) boton.disabled = false;
  }
}

// Delegación de eventos de la galería.
$("#galeria").addEventListener("click", (ev) => {
  const ver = ev.target.closest("[data-ver]");
  if (ver) return abrirVideo(ver.dataset.ver);
  const abrir = ev.target.closest("[data-abrir]");
  if (abrir) abrirEnFinder(abrir.dataset.abrir, abrir);
});

// ---------------------------------------------------------
// Modal de vídeo
// ---------------------------------------------------------
function buscarItem(id) {
  return (app.estado?.items || []).find((i) => i.id === id);
}

function abrirVideo(id) {
  if (!app.estado) { app.verPendiente = id; return; }
  const item = buscarItem(id);
  if (!item) { toast("Ese vídeo ya no está disponible", "aviso"); return; }
  app.videoAbierto = id;
  const video = $("#modalVideoEl");
  video.src = `/api/video/${encodeURIComponent(id)}`;
  if (item.tiene_portada) video.poster = urlPortada(item);
  else video.removeAttribute("poster");
  pintarInfoModal(true);
  $("#capaVideo").hidden = false;
  document.body.style.overflow = "hidden";
}

function pintarInfoModal(forzar = false) {
  const item = buscarItem(app.videoAbierto);
  if (!item) return;
  const firma = [item.veredicto, item.duracion_s, (item.avisos || []).join("¦"), item.salida].join("|");
  const modal = $("#capaVideo");
  if (!forzar && modal.dataset.firma === firma) return;
  modal.dataset.firma = firma;

  $("#modalVideoBadge").innerHTML = badgeVeredicto(item);
  $("#modalVideoTitulo").textContent = item.nombre;
  const datos = [
    ["Duración", formatearDuracion(item.duracion_s)],
    ["Perfil", item.perfil],
    ["Terminado", item.terminado ? `${fecha(item.terminado).toLocaleDateString("es-ES", { day: "numeric", month: "short" })}, ${hora(item.terminado)}` : "—"],
    ["Guardado en", item.salida || "Pendiente de carpeta"],
  ];
  $("#modalVideoDatos").innerHTML = datos
    .map(([k, v]) => `<dt>${escapar(k)}</dt><dd title="${escapar(v)}">${escapar(v)}</dd>`).join("");
  $("#modalVideoAvisos").innerHTML = htmlAvisos(item.avisos, true);
}

function cerrarVideo() {
  const video = $("#modalVideoEl");
  video.pause();
  video.removeAttribute("src");
  video.load();
  app.videoAbierto = null;
  $("#capaVideo").hidden = true;
  $("#capaVideo").dataset.firma = "";
  document.body.style.overflow = "";
}

$("#modalVideoFinder").addEventListener("click", (ev) => {
  if (app.videoAbierto) abrirEnFinder(app.videoAbierto, ev.currentTarget);
});

// ---------------------------------------------------------
// Selección y subida de archivos
// ---------------------------------------------------------
const zona = $("#zonaSubida");
const inputArchivos = $("#inputArchivos");

function esVideo(archivo) {
  return archivo.type.startsWith("video/") || /\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(archivo.name);
}

function anadirArchivos(lista) {
  if (app.subiendo) return;
  const archivos = [...lista];
  const videos = archivos.filter(esVideo);
  if (videos.length < archivos.length) toast("Solo se admiten archivos de vídeo; el resto se ha ignorado", "aviso");

  let repetidos = 0;
  for (const f of videos) {
    const ya = app.seleccion.some((s) => s.name === f.name && s.size === f.size);
    if (ya) { repetidos++; continue; }
    if (app.seleccion.length >= MAX_ARCHIVOS) {
      toast(`Máximo ${MAX_ARCHIVOS} vídeos por tanda`, "aviso");
      break;
    }
    app.seleccion.push(f);
  }
  if (repetidos) toast(`${repetidos} ${repetidos === 1 ? "vídeo ya estaba elegido" : "vídeos ya estaban elegidos"}`, "aviso");
  pintarSeleccion();
}

function pintarSeleccion() {
  const lista = $("#listaArchivos");
  lista.innerHTML = app.seleccion.map((f, i) => `
    <li>
      <span class="archivo__icono">${ICONO.video}</span>
      <span class="archivo__nombre" title="${escapar(f.name)}">${escapar(f.name)}</span>
      <span class="archivo__tamano">${formatearTamano(f.size)}</span>
      <button class="archivo__quitar" type="button" data-quitar="${i}" aria-label="Quitar ${escapar(f.name)}" ${app.subiendo ? "disabled" : ""}>${ICONO.cerrar}</button>
    </li>`).join("");
  const n = app.seleccion.length;
  $("#listaVacia").hidden = n > 0;
  $("#contadorSeleccion").textContent = `${n} / ${MAX_ARCHIVOS}`;
  $("#botonEditar").disabled = n === 0 || app.subiendo;
  $("#botonEditarTexto").textContent = app.subiendo
    ? "Subiendo…"
    : n === 0 ? "Editar vídeos" : `Editar ${n} ${n === 1 ? "vídeo" : "vídeos"}`;
}

$("#listaArchivos").addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-quitar]");
  if (!b || app.subiendo) return;
  app.seleccion.splice(Number(b.dataset.quitar), 1);
  pintarSeleccion();
});

inputArchivos.addEventListener("change", () => {
  anadirArchivos(inputArchivos.files);
  inputArchivos.value = "";
});

// Arrastrar y soltar (el contador evita parpadeos al pasar por elementos hijos).
let profundidadArrastre = 0;
zona.addEventListener("dragenter", (ev) => { ev.preventDefault(); profundidadArrastre++; zona.classList.add("arrastrando"); });
zona.addEventListener("dragover", (ev) => { ev.preventDefault(); ev.dataTransfer.dropEffect = "copy"; });
zona.addEventListener("dragleave", () => { if (--profundidadArrastre <= 0) { profundidadArrastre = 0; zona.classList.remove("arrastrando"); } });
zona.addEventListener("drop", (ev) => {
  ev.preventDefault();
  profundidadArrastre = 0;
  zona.classList.remove("arrastrando");
  if (ev.dataTransfer?.files?.length) anadirArchivos(ev.dataTransfer.files);
});
// Evita que soltar un archivo fuera de la zona haga que el navegador lo abra.
window.addEventListener("dragover", (ev) => ev.preventDefault());
window.addEventListener("drop", (ev) => ev.preventDefault());

$("#selectPerfil").addEventListener("change", () => { app.perfilTocado = true; });

function mostrarProgresoSubida(pct, texto) {
  $("#progresoSubida").hidden = false;
  $("#progresoSubidaBarra").style.width = `${pct}%`;
  $("#progresoSubidaPct").textContent = `${Math.round(pct)}%`;
  $("#progresoSubidaTexto").textContent = texto;
}

function subir() {
  if (!app.seleccion.length || app.subiendo) return;
  const perfil = $("#selectPerfil").value;
  const datos = new FormData();
  datos.append("perfil", perfil);
  app.seleccion.forEach((f) => datos.append("archivos", f, f.name));

  const total = app.seleccion.reduce((s, f) => s + f.size, 0);
  app.subiendo = true;
  pintarSeleccion();
  mostrarProgresoSubida(0, `Subiendo ${app.seleccion.length} ${app.seleccion.length === 1 ? "vídeo" : "vídeos"} · ${formatearTamano(total)}`);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/subir");
  xhr.upload.onprogress = (ev) => {
    if (ev.lengthComputable) mostrarProgresoSubida((ev.loaded / ev.total) * 100, `Subiendo… ${formatearTamano(ev.loaded)} de ${formatearTamano(ev.total)}`);
  };
  xhr.upload.onload = () => mostrarProgresoSubida(100, "Preparando la cola…");

  const terminar = () => {
    app.subiendo = false;
    setTimeout(() => { if (!app.subiendo) $("#progresoSubida").hidden = true; }, 900);
    pintarSeleccion();
  };

  xhr.onload = () => {
    let r = null;
    try { r = JSON.parse(xhr.responseText); } catch (_) { /* respuesta no JSON */ }
    if (xhr.status >= 200 && xhr.status < 300 && r) {
      const n = (r["añadidos"] || []).length;
      const dup = r.duplicados || [];
      if (n) toast(`${n} ${n === 1 ? "vídeo añadido" : "vídeos añadidos"} a la cola`, "ok");
      if (dup.length) toast(`Ya estaban en cola: ${dup.join(", ")}`, "aviso");
      app.seleccion = [];   // tras subir se limpia la selección
      terminar();
      sondear();
    } else {
      toast((r && r.detail) ? `No se pudo subir: ${r.detail}` : `No se pudo subir (error ${xhr.status})`, "error");
      terminar();
    }
  };
  xhr.onerror = () => { toast("Sin conexión con el motor", "error"); terminar(); };
  xhr.send(datos);
}

$("#botonEditar").addEventListener("click", subir);

// ---------------------------------------------------------
// Panel de ajustes
// ---------------------------------------------------------
function pintarRuta(ruta) {
  const caja = $("#rutaCarpeta");
  caja.dataset.vacia = ruta ? "false" : "true";
  $("#rutaCarpetaTexto").textContent = ruta || "Sin configurar — elige una carpeta";
}

async function abrirAjustes() {
  app.ajustesAbiertos = true;
  $("#capaAjustes").hidden = false;
  document.body.style.overflow = "hidden";

  let ajustes = app.estado?.ajustes;
  try { ajustes = await pedir("/api/ajustes"); } catch (_) { /* usamos los del estado */ }
  if (!app.ajustesAbiertos) return;
  ajustes = ajustes || { carpeta_salida: null, perfil_por_defecto: "", limite_diario: 10 };

  app.carpetaBorrador = ajustes.carpeta_salida || null;
  pintarRuta(app.carpetaBorrador);
  const perfiles = app.estado?.perfiles || (ajustes.perfil_por_defecto ? [ajustes.perfil_por_defecto] : []);
  rellenarSelect($("#ajustePerfil"), perfiles, ajustes.perfil_por_defecto);
  $("#ajusteLimite").value = ajustes.limite_diario ?? "";
}

function cerrarAjustes() {
  app.ajustesAbiertos = false;
  $("#capaAjustes").hidden = true;
  document.body.style.overflow = "";
}

$("#botonAjustes").addEventListener("click", abrirAjustes);
$("#botonConfigurarCarpeta").addEventListener("click", abrirAjustes);

$("#botonElegirCarpeta").addEventListener("click", async (ev) => {
  const boton = ev.currentTarget;
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = "Abriendo selector de macOS…";
  try {
    const r = await postJSON("/api/elegir-carpeta");
    if (r && r.ruta) {
      app.carpetaBorrador = r.ruta;
      pintarRuta(r.ruta);
      toast("Carpeta elegida. Pulsa Guardar para aplicarla.", "ok");
    }
  } catch (err) {
    errorAccion(err, "No se pudo abrir el selector");
  } finally {
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }
});

$("#botonGuardarAjustes").addEventListener("click", async (ev) => {
  const limite = parseInt($("#ajusteLimite").value, 10);
  if (!Number.isFinite(limite) || limite < 1) {
    toast("El límite diario debe ser un número mayor que 0", "aviso");
    $("#ajusteLimite").focus();
    return;
  }
  const cuerpo = {
    carpeta_salida: app.carpetaBorrador,
    perfil_por_defecto: $("#ajustePerfil").value,
    limite_diario: limite,
  };
  const boton = ev.currentTarget;
  boton.disabled = true;
  try {
    const guardados = await postJSON("/api/ajustes", cuerpo);
    if (app.estado && guardados) app.estado.ajustes = guardados;
    app.perfilTocado = false;
    toast("Ajustes guardados", "ok");
    cerrarAjustes();
    sondear();
  } catch (err) {
    errorAccion(err, "No se pudieron guardar los ajustes");
  } finally {
    boton.disabled = false;
  }
});

// Cierre de capas: botones, clic en el fondo y tecla Escape.
document.addEventListener("click", (ev) => {
  const c = ev.target.closest("[data-cerrar]");
  if (c) {
    if (c.dataset.cerrar === "ajustes") cerrarAjustes();
    if (c.dataset.cerrar === "video") cerrarVideo();
  }
});
$("#capaAjustes").addEventListener("mousedown", (ev) => { if (ev.target === ev.currentTarget) cerrarAjustes(); });
$("#capaVideo").addEventListener("mousedown", (ev) => { if (ev.target === ev.currentTarget) cerrarVideo(); });
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape") return;
  if (!$("#capaVideo").hidden) cerrarVideo();
  else if (!$("#capaAjustes").hidden) cerrarAjustes();
});

// ---------------------------------------------------------
// Toasts
// ---------------------------------------------------------
function toast(texto, tipo = "info", ms = 4200) {
  const cont = $("#toasts");
  // Evita apilar el mismo mensaje varias veces.
  for (const t of cont.children) if (t.dataset.texto === texto && !t.classList.contains("saliendo")) return;
  const el = document.createElement("div");
  el.className = `toast toast--${tipo}`;
  el.dataset.texto = texto;
  el.textContent = texto;
  cont.appendChild(el);
  setTimeout(() => {
    el.classList.add("saliendo");
    el.addEventListener("animationend", () => el.remove(), { once: true });
  }, ms);
}

// ---------------------------------------------------------
// Reloj: actualiza los tiempos transcurridos cada segundo
// ---------------------------------------------------------
setInterval(() => {
  document.querySelectorAll(".cola__tiempo[data-desde] span").forEach((s) => {
    s.textContent = transcurrido(s.parentElement.dataset.desde);
  });
  pintarEstadoMotor(); // por si expira la pausa por límite
}, 1000);

// ---------------------------------------------------------
// Arranque
// ---------------------------------------------------------
(function iniciar() {
  const params = new URLSearchParams(location.search);
  if (params.get("captura") === "1") document.documentElement.classList.add("sin-animacion");
  if (params.get("ver")) app.verPendiente = params.get("ver");
  pintarSeleccion();
  sondear();
  if (params.get("ajustes") === "1") abrirAjustes();
})();
