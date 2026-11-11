// Puerta de entrada de las pantallas de cuentas: llama a la API real y, solo con `?mock=1` en la URL (se recuerda en
// la pestaña; `?mock=0` lo quita), usa una maqueta en memoria con datos inventados. Nunca se activa por defecto.
import * as api from "./api";
import type { CasoResumen, ContactoResumen, EscenarioCaso, Movimiento, NuevoDeudor, Relacion, ViaSaldado } from "./api";
import { centimosAbs, comoEuros, idMovimientoOrigen } from "./cuentas";

const CLAVE_MOCK = "meisam-mock";

export function esMaqueta(): boolean {
  if (typeof window === "undefined") return false;
  const parametro = new URLSearchParams(window.location.search).get("mock");
  if (parametro === "1") window.sessionStorage.setItem(CLAVE_MOCK, "1");
  if (parametro === "0") window.sessionStorage.removeItem(CLAVE_MOCK);
  return window.sessionStorage.getItem(CLAVE_MOCK) === "1";
}

// ---- Maqueta ----------------------------------------------------------------------------------------------------

const HOY = "2026-11-10";
let contactosMock: ContactoResumen[] = [
  { contraparte: "LAURA M", nombre: "Laura M.", telefono: "+34 6** *** 214", relacion: "amigo", saldo_total: "0.00", casos_abiertos: 0 },
  { contraparte: "DANIEL P", nombre: "Daniel P.", telefono: "+34 6** *** 087", relacion: "companero", saldo_total: "12.00", casos_abiertos: 1 },
  { contraparte: "SARA L", nombre: "Sara L.", telefono: "+34 6** *** 450", relacion: "amigo", saldo_total: "0.00", casos_abiertos: 0 },
  { contraparte: "MARCOS R", nombre: "Marcos R.", telefono: "+34 6** *** 123", relacion: "amigo", saldo_total: "24.00", casos_abiertos: 1 },
  { contraparte: "ANA T", nombre: "Ana T.", telefono: "+34 6** *** 391", relacion: null, saldo_total: "15.00", casos_abiertos: 1 },
];
let casosMock: CasoResumen[] = [
  {
    id: "mock-c1",
    escenario: "gasto_compartido",
    estado: "pedido",
    aviso: "notificar",
    creado: "2026-11-06",
    avisar_desde: "2026-11-09",
    movimiento_origen: { id: "mock-m1", comercio: "LA TASCA", importe: "-120.00", fecha: "2026-11-06" },
    deudores: [
      { contraparte: "LAURA M", cuota: "24.00", estado: "saldada", via_saldado: "bizum" },
      { contraparte: "DANIEL P", cuota: "24.00", estado: "saldada", via_saldado: "bizum" },
      { contraparte: "SARA L", cuota: "24.00", estado: "saldada", via_saldado: "bizum" },
      { contraparte: "MARCOS R", cuota: "24.00", estado: "pedida", pedida: "2026-11-10" },
    ],
  },
  {
    id: "mock-c2",
    escenario: "pago_individual",
    estado: "abierto",
    aviso: "resumen",
    creado: "2026-11-08",
    pregunta: "¿Fuiste con alguien a PIZZERIA NAPOLI?",
    pregunta_nivel: 2,
    sugerencia: { personas: ["LAURA M", "MARCOS R"], forma: "iguales", cuotas: {}, confianza: 0.7 },
    movimiento_origen: { id: "mock-m2", comercio: "PIZZERIA NAPOLI", importe: "-64.00", fecha: "2026-11-07" },
    deudores: [],
  },
  {
    id: "mock-c3",
    escenario: "pago_individual",
    estado: "abierto",
    aviso: "silencioso",
    creado: "2026-11-09",
    movimiento_origen: { id: "mock-m3", comercio: "CINES YELMO", importe: "-18.50", fecha: "2026-11-08" },
    deudores: [],
  },
  {
    id: "mock-c4",
    escenario: "pago_por_otro",
    estado: "abierto",
    aviso: "notificar",
    creado: "2026-11-03",
    avisar_desde: "2026-11-05",
    movimiento_origen: { id: "mock-m4", comercio: "FARMACIA CENTRO", importe: "-15.00", fecha: "2026-11-03" },
    deudores: [{ contraparte: "ANA T", cuota: "15.00", estado: "olvidada" }],
  },
  {
    id: "mock-c5",
    escenario: "gasto_fijo_compartido",
    estado: "abierto",
    aviso: "notificar",
    creado: "2026-09-01",
    avisar_desde: "2026-11-03",
    movimiento_origen: { id: "mock-m5", comercio: "INTERNET FIBRA", importe: "-36.00", fecha: "2026-11-01" },
    deudores: [{ contraparte: "DANIEL P", cuota: "12.00", estado: "detectada" }],
  },
];
const movimientosMock: Movimiento[] = [
  { id: "mock-m3", fecha: "2026-11-08", concepto: "COMPRA TARJETA CINES YELMO", comercio: "CINES YELMO", importe: "-18.50", canal: "tarjeta", categoria: "ocio" },
  { id: "mock-m2", fecha: "2026-11-07", concepto: "COMPRA TARJETA PIZZERIA NAPOLI", comercio: "PIZZERIA NAPOLI", importe: "-64.00", canal: "tarjeta", categoria: "restaurantes" },
  { id: "mock-m1", fecha: "2026-11-06", concepto: "COMPRA TARJETA LA TASCA MADRID", comercio: "LA TASCA", importe: "-120.00", canal: "tarjeta", categoria: "restaurantes" },
  { id: "mock-nomina", fecha: "2026-11-05", concepto: "NOMINA", importe: "1250.00", canal: "transferencia", categoria: "ingresos" },
  { id: "mock-m4", fecha: "2026-11-03", concepto: "COMPRA TARJETA FARMACIA CENTRO", comercio: "FARMACIA CENTRO", importe: "-15.00", canal: "tarjeta", categoria: "salud" },
  { id: "mock-m5", fecha: "2026-11-01", concepto: "RECIBO INTERNET FIBRA", comercio: "INTERNET FIBRA", importe: "-36.00", canal: "recibo", categoria: "suministros" },
  { id: "mock-m6", fecha: "2026-10-31", concepto: "COMPRA TARJETA MERCADONA", comercio: "MERCADONA", importe: "-42.30", canal: "tarjeta", categoria: "supermercado" },
];

const quedaPendiente = (estado: string) => estado === "detectada" || estado === "pedida" || estado === "olvidada";

// Recalcula saldo y casos abiertos de cada persona desde los casos, como haría el backend.
function recalcular(): void {
  contactosMock = contactosMock.map((c) => {
    const pendientes = casosMock.flatMap((k) => k.deudores.filter((d) => d.contraparte === c.contraparte && quedaPendiente(d.estado)));
    const total = pendientes.reduce((suma, d) => suma + centimosAbs(d.cuota), 0);
    return { ...c, saldo_total: comoEuros(total), casos_abiertos: pendientes.length };
  });
}

function cerrarSiNadiePendiente(caso: CasoResumen): CasoResumen {
  if (caso.deudores.length > 0 && !caso.deudores.some((d) => quedaPendiente(d.estado))) return { ...caso, estado: "saldado" };
  return caso;
}
function reemplazar(caso: CasoResumen): CasoResumen {
  casosMock = casosMock.map((c) => (c.id === caso.id ? caso : c));
  recalcular();
  return caso;
}
function buscar(id: string): CasoResumen {
  const caso = casosMock.find((c) => c.id === id);
  if (!caso) throw new api.ErrorApi("Ese caso ya no existe.", 404);
  return caso;
}
const esperar = () => new Promise((resolver) => setTimeout(resolver, 250));

// ---- API (real o maqueta) ---------------------------------------------------------------------------------------

export async function casos(usuarioId: string): Promise<CasoResumen[]> {
  if (!esMaqueta()) return api.casos(usuarioId);
  recalcular();
  return structuredClone(casosMock);
}

export async function contactos(usuarioId: string): Promise<ContactoResumen[]> {
  if (!esMaqueta()) return api.contactos(usuarioId);
  recalcular();
  return structuredClone(contactosMock);
}

export async function editarContacto(usuarioId: string, clave: string, relacion: Relacion): Promise<ContactoResumen> {
  if (!esMaqueta()) return api.editarContacto(usuarioId, clave, relacion);
  await esperar();
  contactosMock = contactosMock.map((c) => (c.contraparte === clave ? { ...c, relacion } : c));
  return structuredClone(contactosMock.find((c) => c.contraparte === clave)!);
}

export async function movimientos(usuarioId: string): Promise<Movimiento[]> {
  if (!esMaqueta()) return api.movimientosUsuario(usuarioId);
  return structuredClone(movimientosMock);
}

export async function crearCaso(usuarioId: string, movimientoId: string, deudores: NuevoDeudor[], escenario?: EscenarioCaso): Promise<CasoResumen> {
  if (!esMaqueta()) return api.crearCaso(usuarioId, movimientoId, deudores, escenario);
  await esperar();
  const m = movimientosMock.find((x) => x.id === movimientoId);
  if (!m) throw new api.ErrorApi("Ese movimiento no existe.", 404);
  const suma = deudores.reduce((s, d) => s + centimosAbs(d.importe), 0);
  if (suma > centimosAbs(m.importe)) throw new api.ErrorApi("Las partes superan el importe del pago.", 400);
  const previo = casosMock.find((c) => c.escenario === "pago_individual" && idMovimientoOrigen(c.movimiento_origen) === movimientoId);
  const caso: CasoResumen = {
    id: previo?.id ?? `mock-c${Date.now()}`,
    escenario: escenario ?? (deudores.length === 1 ? "pago_por_otro" : "gasto_compartido"),
    estado: "abierto",
    aviso: "notificar",
    creado: HOY,
    avisar_desde: "2026-11-12",
    movimiento_origen: { id: m.id, comercio: m.comercio, importe: m.importe, fecha: m.fecha },
    deudores: deudores.map((d) => ({ contraparte: d.contraparte, cuota: d.importe, estado: "detectada" })),
  };
  casosMock = previo ? casosMock.map((c) => (c.id === previo.id ? caso : c)) : [caso, ...casosMock];
  recalcular();
  return structuredClone(caso);
}

export async function saldarCaso(
  usuarioId: string,
  casoId: string,
  via: Exclude<ViaSaldado, "bizum">,
  contraparte?: string,
  motivo?: string,
): Promise<CasoResumen> {
  if (!esMaqueta()) return api.saldarCaso(usuarioId, casoId, via, contraparte, motivo);
  await esperar();
  const caso = buscar(casoId);
  const deudores = caso.deudores.map((d) =>
    (!contraparte || d.contraparte === contraparte) && quedaPendiente(d.estado)
      ? { ...d, estado: "saldada", via_saldado: via, motivo_saldado: motivo ?? null, saldada: HOY }
      : d,
  );
  return structuredClone(reemplazar(cerrarSiNadiePendiente({ ...caso, deudores })));
}

export async function descartarCaso(usuarioId: string, casoId: string, motivo?: string): Promise<CasoResumen> {
  if (!esMaqueta()) return api.descartarCaso(usuarioId, casoId, motivo);
  await esperar();
  const caso = buscar(casoId);
  return structuredClone(
    reemplazar({ ...caso, estado: "descartado", deudores: caso.deudores.map((d) => (quedaPendiente(d.estado) ? { ...d, estado: "rechazada" } : d)) }),
  );
}
