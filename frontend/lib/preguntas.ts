// Lógica pura del Resumen: qué casos son preguntas de Meisam y la frase del resumen semanal.
// Las cifras salen del código (céntimos enteros, nunca floats ni un modelo); aquí solo se suman y se formatean.
import type { Amigo, CasoResumen } from "./api";
import { casoAbierto, centimosAbs, comoEuros, deudorAbierto } from "./cuentas";
import { eur, nombreVisible } from "./formato";

// individual = nivel 1 («¿Fuiste con alguien?»), sugerida = nivel 2 («¿Fuiste con Laura y Marcos?»), duda = pregunta
// pendiente de un caso dudoso. El nivel 3 es una notificación y el 4 abre el caso solo: no pasan por el Resumen.
export type TipoPregunta = "individual" | "sugerida" | "duda";

export function textoDePregunta(caso: CasoResumen): string | null {
  const p = caso.pregunta;
  if (!p) return null;
  return typeof p === "string" ? p : p.texto || null;
}

export function tipoPregunta(caso: CasoResumen): TipoPregunta | null {
  if (!casoAbierto(caso)) return null;
  const p = caso.pregunta;
  if (caso.estado === "dudoso") return typeof p === "object" && p && p.estado === "pendiente" && p.texto ? "duda" : null;
  if (caso.escenario !== "pago_individual" || caso.aviso !== "resumen" || caso.deudores.length > 0) return null;
  return caso.sugerencia && caso.sugerencia.personas.length > 0 ? "sugerida" : "individual";
}

export const esPregunta = (caso: CasoResumen) => tipoPregunta(caso) !== null;

const DIAS_SEMANA = 7;
const dia = (iso: string) => {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(a, m - 1, d) / 86400000;
};
const primerNombre = (n: string) => nombreVisible(n).split(" ")[0];

export type ResumenSemanal = {
  debenCentimos: number;
  personasQueDeben: { nombre: string; centimos: number }[];
  preguntas: number;
  pagaron: string[]; // nombres de quien te ha pagado en los últimos 7 días
};

const PENDIENTE_AMIGO: readonly string[] = ["detectado", "pedido", "olvidado"];

export function resumenSemanal(amigos: Amigo[] | null, casos: CasoResumen[], hoy: string | null, preguntas: number): ResumenSemanal {
  // Lo que te deben, por persona. Con `/amigos` se usa su saldo (positivo = te debe); si la ruta no está, se suman las cuotas pendientes.
  const por = new Map<string, { nombre: string; centimos: number }>();
  const sumar = (clave: string, nombre: string, c: number) => {
    const previo = por.get(clave);
    por.set(clave, { nombre: previo?.nombre ?? nombre, centimos: (previo?.centimos ?? 0) + c });
  };
  if (amigos) {
    for (const a of amigos) {
      if (!PENDIENTE_AMIGO.includes(a.estado)) continue;
      const negativo = a.saldo.trim().startsWith("-");
      sumar(a.contraparte, nombreVisible(a.contraparte), (negativo ? -1 : 1) * centimosAbs(a.saldo));
    }
  } else {
    for (const c of casos) {
      if (!casoAbierto(c)) continue;
      for (const d of c.deudores) if (deudorAbierto(d)) sumar(d.contraparte, d.nombre || nombreVisible(d.contraparte), centimosAbs(d.cuota));
    }
  }
  const personasQueDeben = [...por.values()].filter((p) => p.centimos > 0);
  const debenCentimos = personasQueDeben.reduce((s, p) => s + p.centimos, 0);

  const pagaron: string[] = [];
  if (hoy) {
    const limite = dia(hoy) - (DIAS_SEMANA - 1);
    for (const c of casos) {
      for (const d of c.deudores) {
        if (d.estado !== "saldada" || !d.saldada) continue;
        const cuando = dia(d.saldada);
        if (cuando < limite || cuando > dia(hoy)) continue;
        const nombre = d.nombre || nombreVisible(d.contraparte);
        if (!pagaron.includes(nombre)) pagaron.push(nombre);
      }
    }
  }
  return { debenCentimos, personasQueDeben, preguntas, pagaron };
}

// «Te deben 85 € entre 3 personas» · «1 pregunta pendiente» · «Marcos te pagó». Sin nada que contar, devuelve [].
export function fraseResumen(r: ResumenSemanal): string[] {
  const partes: string[] = [];
  const n = r.personasQueDeben.length;
  if (n === 1) partes.push(`${primerNombre(r.personasQueDeben[0].nombre)} te debe ${eur(comoEuros(r.debenCentimos))}`);
  else if (n > 1) partes.push(`Te deben ${eur(comoEuros(r.debenCentimos))} entre ${n} personas`);
  if (r.preguntas > 0) partes.push(`${r.preguntas} ${r.preguntas === 1 ? "pregunta pendiente" : "preguntas pendientes"}`);
  const p = r.pagaron.map(primerNombre);
  const repetidos = new Set(p.filter((x, i) => p.indexOf(x) !== i));
  const nombres = r.pagaron.map((x, i) => (repetidos.has(p[i]) ? nombreVisible(x) : p[i]));
  if (nombres.length === 1) partes.push(`${nombres[0]} te pagó`);
  else if (nombres.length === 2) partes.push(`${nombres[0]} y ${nombres[1]} te pagaron`);
  else if (nombres.length === 3) partes.push(`${nombres[0]}, ${nombres[1]} y ${nombres[2]} te pagaron`);
  else if (nombres.length > 3) partes.push(`${nombres.length} personas te pagaron`);
  return partes;
}
