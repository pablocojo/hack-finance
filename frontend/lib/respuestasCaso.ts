// Respuestas de un toque a las preguntas de Meisam (Resumen). Reutilizan la herramienta `actualizar_caso` de la
// llamada (backend/casos/llamada.py, acciones de lista cerrada, validadas en el servidor y con rastro en el caso):
// la app abre una sesión general sin aviso («Hablar con Meisam») solo para obtener su token, sin voz ni modelo.
// Nada de esto mueve dinero. Con `?mock=1` (maqueta) las respuestas se resuelven en memoria.
import { ErrorApi, sesionVoz, vozDeshacer, vozHerramienta } from "./api";
import { centimosAbs, comoEuros, idMovimientoOrigen } from "./cuentas";
import { casos as pedirCasos, crearCaso, descartarCaso, esMaqueta } from "./cuentasApi";

// Acciones de `casos/llamada.py::ACCIONES` que usan las preguntas del Resumen.
export type AccionPregunta = "iba_solo" | "nadie_me_debe" | "con_personas" | "responder_duda";
export type CamposRespuesta = { persona?: string; importe?: number; respuesta?: "si" | "no" };
// `cambioId` y `token` solo sirven para «Deshacer»; si no hay (maqueta), no se ofrece.
export type RespuestaAplicada = { hecho: string; cambioId: string | null; token: string | null };

const VIDA_TOKEN_MS = 8 * 60 * 1000; // el servidor da 10 minutos
let guardada: { usuarioId: string; token: string; desde: number } | null = null;

async function tokenDe(usuarioId: string, renovar: boolean): Promise<string> {
  if (!renovar && guardada && guardada.usuarioId === usuarioId && Date.now() - guardada.desde < VIDA_TOKEN_MS) return guardada.token;
  const s = await sesionVoz(null, usuarioId, "texto_kit");
  guardada = { usuarioId, token: s.token_sesion, desde: Date.now() };
  return s.token_sesion;
}

const sesionCaducada = (fallo: unknown) => fallo instanceof ErrorApi && (fallo.estado === 401 || fallo.estado === 410);

export async function aplicarRespuesta(usuarioId: string, casoId: string, accion: AccionPregunta, campos: CamposRespuesta = {}): Promise<RespuestaAplicada> {
  if (esMaqueta()) {
    if (accion === "con_personas") {
      // Maqueta: reparte a partes iguales entre las personas y tú (en la versión real lo calcula el servidor).
      const caso = (await pedirCasos(usuarioId)).find((k) => k.id === casoId);
      const movimiento = idMovimientoOrigen(caso?.movimiento_origen);
      const total = typeof caso?.movimiento_origen === "object" && caso.movimiento_origen?.importe ? centimosAbs(caso.movimiento_origen.importe) : 0;
      const claves = (caso?.sugerencia?.personas ?? []);
      if (!movimiento || claves.length === 0) throw new Error("No puedo apuntar a esas personas en la maqueta.");
      const cuota = comoEuros(Math.floor(total / (claves.length + 1)));
      await crearCaso(usuarioId, movimiento, claves.map((c) => ({ contraparte: c, importe: cuota })));
      return { hecho: "Personas añadidas al reparto", cambioId: null, token: null };
    }
    await descartarCaso(usuarioId, casoId, accion === "iba_solo" ? "Iba solo" : "Nadie me debe");
    return { hecho: accion === "nadie_me_debe" ? "Anotado: nadie te debe" : "Anotado: ibas solo", cambioId: null, token: null };
  }
  const llamar = async (renovar: boolean) => {
    const token = await tokenDe(usuarioId, renovar);
    return { token, r: await vozHerramienta("actualizar_caso", token, { caso_id: casoId, accion, ...campos }) };
  };
  let hecho;
  try {
    hecho = await llamar(false);
  } catch (fallo) {
    if (!sesionCaducada(fallo)) throw fallo;
    hecho = await llamar(true);
  }
  if (!hecho.r.ok) throw new Error(hecho.r.error ?? "No he podido anotarlo ahora.");
  return {
    hecho: typeof hecho.r.hecho === "string" ? hecho.r.hecho : "Anotado.",
    cambioId: hecho.r.cambio_id ?? null,
    token: hecho.token,
  };
}

export async function deshacerRespuesta(aplicada: RespuestaAplicada): Promise<void> {
  if (!aplicada.cambioId || !aplicada.token) throw new Error("Este cambio ya no se puede deshacer.");
  const r = await vozDeshacer(aplicada.token, aplicada.cambioId);
  if (!r.ok) throw new Error(r.error ?? "Este cambio ya no se puede deshacer.");
}
