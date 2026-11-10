// Reglas del panel de avisos del cliente. Solo clasifica y redacta lo que ya decide el backend: la interfaz no inventa avisos.
import type { CasoResumen, EstadoNotificacion, Notificacion } from "./api";
import { textoVisible } from "./formato";

export type FiltroAvisos = "todas" | "pendientes" | "resueltas";

export const FILTROS: { id: FiltroAvisos; texto: string }[] = [
  { id: "todas", texto: "Todas" },
  { id: "pendientes", texto: "Pendientes" },
  { id: "resueltas", texto: "Resueltas" },
];

export const ESTADO_AVISO: Record<EstadoNotificacion, string> = {
  nueva: "Nueva",
  vista: "Vista",
  resuelta: "Resuelta",
  rechazada: "Rechazada",
  ignorada: "Ignorada",
};

export const esAhora = (n: Notificacion) => n.decision.accion === "notificar_ahora";
export const esResumen = (n: Notificacion) => n.decision.accion === "resumen";
// Lo que cuenta la campana: solo avisos de ahora que aún no se han abierto.
export const sinVer = (n: Notificacion) => esAhora(n) && n.estado === "nueva";
export const esPendiente = (n: Notificacion) => n.estado === "nueva" || n.estado === "vista";

export function pasaFiltro(n: Notificacion, filtro: FiltroAvisos): boolean {
  if (filtro === "todas") return true;
  return filtro === "pendientes" ? esPendiente(n) : !esPendiente(n);
}

// Casos de deuda que merecen una línea en el panel pero nunca una notificación.
export const casoSilencioso = (c: CasoResumen) => c.aviso === "silencioso";
export const casoDeResumen = (c: CasoResumen) => c.aviso === "resumen";

const MAX_CUERPO = 140;

// Texto de la notificación del navegador. Sale del aviso, que el backend ya envía enmascarado; no se añade nada más
// (ni importes de terceros ni conceptos) y se recorta para que no ocupe la pantalla de bloqueo.
export function textoNavegador(n: Notificacion): { titulo: string; cuerpo: string } {
  const cuerpo = textoVisible(n.propuesta.mensaje_notificacion);
  return {
    titulo: textoVisible(n.propuesta.titulo),
    cuerpo: cuerpo.length > MAX_CUERPO ? `${cuerpo.slice(0, MAX_CUERPO - 1).trimEnd()}…` : cuerpo,
  };
}
