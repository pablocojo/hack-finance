// Cliente de la API del backend. La clave de Claude nunca llega al navegador: solo vive en el backend.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type Categoria = { categoria: string; importe: number; porcentaje: number };
export type Mes = { mes: string; ingresos: number; gastos: number; ahorro: number };
export type Comercio = { comercio: string; importe: number; veces: number };

export type Resumen = {
  sesion_id: string;
  vacio: boolean;
  periodo?: { desde: string; hasta: string; meses: number };
  ingresos?: number;
  gastos?: number;
  ahorro?: number;
  tasa_ahorro_pct?: number | null;
  gasto_medio_mensual?: number;
  ingreso_medio_mensual?: number;
  por_categoria?: Categoria[];
  por_mes?: Mes[];
  comercios_principales?: Comercio[];
  nota?: string;
};

export type Salud = {
  ok: boolean;
  producto: string;
  aviso_ia: string;
  aviso_configuracion: string | null;
  modo_demo: string;
  modelo_chat: string;
  perfiles_ejemplo: Record<string, string>;
  herramientas: string[];
  clave_configurada: boolean;
};

export type DatosSesion = {
  sesion_id: string;
  movimientos: number;
  desde?: string;
  hasta?: string;
  origen: string;
  sin_categoria?: number;
  informe?: { importadas: number; descartadas: number; datos_personales_ocultados: number };
};

export type PasoTraza = {
  tipo: string;
  nombre?: string;
  entrada?: Record<string, unknown>;
  ms?: number;
  error?: boolean;
  resumen?: string;
  modelo?: string;
  vuelta?: number;
  stop_reason?: string;
  tokens?: Record<string, number>;
  coste_usd?: number;
  aprobada?: boolean;
  problemas?: string[];
};

export type Final = {
  texto: string;
  modelo: string;
  vueltas: number;
  coste_usd: number;
  coste_sesion_usd: number;
  herramientas: string[];
  trazas: PasoTraza[];
  avisos?: string[];
  reproducido?: boolean;
};

export type Adjunto = { tipo: string; datos_base64: string };

export type EventoChat =
  | { tipo: "sesion"; datos: { sesion_id: string } }
  | { tipo: "texto"; datos: { texto: string } }
  | { tipo: "aviso"; datos: { texto: string } }
  | { tipo: "herramienta_inicio"; datos: { id: string; nombre: string; entrada: Record<string, unknown> } }
  | { tipo: "herramienta_fin"; datos: PasoTraza }
  | { tipo: "revision"; datos: { aprobada: boolean; problemas: string[]; texto: string | null } }
  | { tipo: "fin"; datos: Final }
  | { tipo: "error"; datos: { mensaje: string; tipo?: string } };

async function leerJson<T>(respuesta: Response): Promise<T> {
  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const cuerpo = (await respuesta.json()) as { detail?: string };
      if (cuerpo.detail) detalle = cuerpo.detail;
    } catch {
      // el cuerpo no era JSON
    }
    throw new Error(detalle);
  }
  return (await respuesta.json()) as T;
}

export async function salud(): Promise<Salud> {
  return leerJson<Salud>(await fetch(`${API_URL}/salud`));
}

export async function cargarEjemplo(perfil: string, sesionId?: string | null): Promise<DatosSesion> {
  const respuesta = await fetch(`${API_URL}/datos/ejemplo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ perfil, sesion_id: sesionId ?? null }),
  });
  return leerJson<DatosSesion>(respuesta);
}

export async function subirCsv(archivo: File, sesionId?: string | null): Promise<DatosSesion> {
  const formulario = new FormData();
  formulario.append("archivo", archivo);
  const consulta = sesionId ? `?sesion_id=${encodeURIComponent(sesionId)}` : "";
  return leerJson<DatosSesion>(await fetch(`${API_URL}/movimientos${consulta}`, { method: "POST", body: formulario }));
}

export async function resumen(sesionId: string, meses = 3): Promise<Resumen> {
  const consulta = `sesion_id=${encodeURIComponent(sesionId)}&meses=${meses}`;
  return leerJson<Resumen>(await fetch(`${API_URL}/movimientos/resumen?${consulta}`));
}

function parsearBloque(bloque: string): EventoChat | null {
  let tipo = "message";
  const datos: string[] = [];
  for (const linea of bloque.split("\n")) {
    if (linea.startsWith("event:")) tipo = linea.slice(6).trim();
    else if (linea.startsWith("data:")) datos.push(linea.slice(5).trimStart());
  }
  if (datos.length === 0) return null;
  try {
    return { tipo, datos: JSON.parse(datos.join("\n")) } as EventoChat;
  } catch {
    return null;
  }
}

type OpcionesPregunta = {
  mensaje: string;
  sesionId?: string | null;
  modelo?: string;
  adjunto?: Adjunto | null;
  alEvento: (evento: EventoChat) => void;
  senal?: AbortSignal;
};

// POST con respuesta SSE: EventSource no admite POST, así que se lee el cuerpo a trozos.
export async function preguntar(opciones: OpcionesPregunta): Promise<void> {
  const respuesta = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      mensaje: opciones.mensaje,
      sesion_id: opciones.sesionId ?? null,
      modelo: opciones.modelo ?? "auto",
      adjunto: opciones.adjunto ?? null,
    }),
    signal: opciones.senal,
  });
  if (!respuesta.ok || !respuesta.body) {
    await leerJson<unknown>(respuesta);
    throw new Error("El servidor no ha devuelto una respuesta en streaming.");
  }
  const lector = respuesta.body.getReader();
  const decodificador = new TextDecoder();
  let pendiente = "";
  for (;;) {
    const { value, done } = await lector.read();
    if (done) break;
    pendiente += decodificador.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let corte = pendiente.indexOf("\n\n");
    while (corte >= 0) {
      const evento = parsearBloque(pendiente.slice(0, corte));
      pendiente = pendiente.slice(corte + 2);
      if (evento) opciones.alEvento(evento);
      corte = pendiente.indexOf("\n\n");
    }
  }
}

export function leerComoBase64(archivo: File): Promise<string> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader();
    lector.onload = () => {
      const resultado = typeof lector.result === "string" ? lector.result : "";
      resolver(resultado.split(",")[1] ?? "");
    };
    lector.onerror = () => rechazar(lector.error ?? new Error("No se ha podido leer el archivo."));
    lector.readAsDataURL(archivo);
  });
}
