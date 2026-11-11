import type { CasoResumen, ContactoResumen, DeudorCaso, EscenarioCaso, Movimiento, MovimientoOrigen, Relacion } from "./api";
import { nombreVisible } from "./formato";

export const ESCENARIO: Record<EscenarioCaso, string> = {
  pago_individual: "Quizá fuiste con alguien",
  pago_por_otro: "Pagaste por otra persona",
  gasto_compartido: "Gasto compartido",
  gasto_fijo_compartido: "Gasto fijo compartido",
};
export const nombreEscenario = (e: string | null | undefined) => (e ? (ESCENARIO as Record<string, string>)[e] ?? e : "Por aclarar");

export const RELACION: Record<Relacion, string> = {
  amigo: "Amigo o amiga",
  familia: "Familia",
  pareja: "Pareja",
  companero: "Compañero o compañera",
  otro: "Otro",
};
export const RELACIONES = Object.keys(RELACION) as Relacion[];

export const ESTADO_CASO: Record<string, string> = {
  abierto: "Abierto",
  dudoso: "Por aclarar",
  pedido: "Pedido por Bizum",
  saldado: "Saldado",
  descartado: "Cerrado",
  caducado: "Caducado",
};
export const ESTADO_DEUDOR: Record<string, string> = {
  detectada: "Pendiente",
  pedida: "Pedida por Bizum",
  saldada: "Saldada",
  rechazada: "Rechazada",
  caducada: "Caducada",
  olvidada: "En pausa",
};
// Para completar «saldada …»: «saldada por Bizum», «saldada en efectivo», «saldada con una invitación».
export const VIA_SALDADO: Record<string, string> = {
  bizum: "por Bizum",
  efectivo: "en efectivo",
  invitacion: "con una invitación",
  otro: "por otro motivo",
};

// «Pendiente de cobrar»: la cuenta sigue abierta para ese deudor. La «olvidada» sigue abierta pero no se insiste.
export const deudorAbierto = (d: DeudorCaso) => d.estado === "detectada" || d.estado === "pedida" || d.estado === "olvidada";
export const casoAbierto = (c: CasoResumen) => c.estado === "abierto" || c.estado === "dudoso" || c.estado === "pedido";

// Dinero siempre en céntimos enteros; la API manda cadenas como «24.00» o «-120.00».
export function centimosAbs(importe: string | null | undefined): number {
  if (!importe) return 0;
  const [e, d = "0"] = importe.replace("-", "").trim().split(".");
  const c = Number(e) * 100 + Number(d.padEnd(2, "0").slice(0, 2));
  return Number.isFinite(c) ? c : 0;
}
export const comoEuros = (c: number) => `${c < 0 ? "-" : ""}${Math.floor(Math.abs(c) / 100)}.${String(Math.abs(c) % 100).padStart(2, "0")}`;

export const nombreContacto = (c: Pick<ContactoResumen, "contraparte" | "nombre">) => c.nombre || nombreVisible(c.contraparte);

// Lo que se necesita de un pago para repartirlo. `importe` en positivo.
export type PagoRepartible = { id: string; comercio: string; importe: string | null; fecha?: string | null };

export function pagoDeMovimiento(m: Movimiento): PagoRepartible {
  return { id: m.id, comercio: m.comercio || m.concepto, importe: m.importe.replace("-", ""), fecha: m.fecha };
}

export function idMovimientoOrigen(o: MovimientoOrigen | null | undefined): string | null {
  if (!o) return null;
  return typeof o === "string" ? o : o.id ?? null;
}

export function pagoDeCaso(caso: CasoResumen, conocidos: Movimiento[] = []): PagoRepartible | null {
  const id = idMovimientoOrigen(caso.movimiento_origen);
  if (!id) return null;
  const m: Partial<Movimiento> | undefined =
    typeof caso.movimiento_origen === "object" && caso.movimiento_origen ? caso.movimiento_origen : conocidos.find((x) => x.id === id);
  return {
    id,
    comercio: m?.comercio || m?.concepto || "este pago",
    importe: m?.importe ? m.importe.replace("-", "") : null,
    fecha: m?.fecha ?? null,
  };
}

// Pregunta del Resumen: la del backend si llega; si no, se compone con el comercio del pago.
export function preguntaDeCaso(caso: CasoResumen, pago: PagoRepartible | null): string {
  const dicha = typeof caso.pregunta === "string" ? caso.pregunta : caso.pregunta?.texto;
  if (dicha) return dicha;
  return pago && pago.comercio !== "este pago" ? `¿Fuiste con alguien a ${nombreVisible(pago.comercio)}?` : "¿Fuiste con alguien a este pago?";
}
