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

export const DEMO_KEY = process.env.NEXT_PUBLIC_DEMO_KEY ?? "";

// Cabeceras comunes: la clave de demo, si existe (no es seguridad real).
function cabeceras(extra: Record<string, string> = {}): Record<string, string> {
  return { ...(DEMO_KEY ? { "X-Demo-Key": DEMO_KEY } : {}), ...extra };
}

// Error de la API con su código HTTP: permite distinguir «la ruta aún no existe» (404/501) de un fallo real.
export class ErrorApi extends Error {
  constructor(
    mensaje: string,
    readonly estado: number,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }
}
export const rutaNoDisponible = (fallo: unknown) => fallo instanceof ErrorApi && (fallo.estado === 404 || fallo.estado === 501);

async function leerJson<T>(respuesta: Response): Promise<T> {
  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const cuerpo = (await respuesta.json()) as { detail?: string };
      if (cuerpo.detail) detalle = cuerpo.detail;
    } catch {
      // el cuerpo no era JSON
    }
    throw new ErrorApi(detalle, respuesta.status);
  }
  return (await respuesta.json()) as T;
}

export async function salud(): Promise<Salud> {
  return leerJson<Salud>(await fetch(`${API_URL}/salud`));
}

export async function cargarEjemplo(perfil: string, sesionId?: string | null): Promise<DatosSesion> {
  const respuesta = await fetch(`${API_URL}/datos/ejemplo`, {
    method: "POST",
    headers: cabeceras({ "Content-Type": "application/json" }),
    body: JSON.stringify({ perfil, sesion_id: sesionId ?? null }),
  });
  return leerJson<DatosSesion>(respuesta);
}

export async function subirCsv(archivo: File, sesionId?: string | null): Promise<DatosSesion> {
  const formulario = new FormData();
  formulario.append("archivo", archivo);
  const consulta = sesionId ? `?sesion_id=${encodeURIComponent(sesionId)}` : "";
  return leerJson<DatosSesion>(await fetch(`${API_URL}/movimientos${consulta}`, { method: "POST", headers: cabeceras(), body: formulario }));
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

// Lee un cuerpo SSE a trozos (EventSource no admite POST ni cabeceras) y entrega cada bloque ya interpretado.
export async function leerSse<E>(respuesta: Response, alEvento: (evento: E) => void): Promise<void> {
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
      if (evento) alEvento(evento as E);
      corte = pendiente.indexOf("\n\n");
    }
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

export async function preguntar(opciones: OpcionesPregunta): Promise<void> {
  const respuesta = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: cabeceras({ "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify({
      mensaje: opciones.mensaje,
      sesion_id: opciones.sesionId ?? null,
      modelo: opciones.modelo ?? "auto",
      adjunto: opciones.adjunto ?? null,
    }),
    signal: opciones.senal,
  });
  await leerSse<EventoChat>(respuesta, opciones.alEvento);
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

// =====================================================================================================
// Copiloto (Meisam): contrato de docs/ARQUITECTURA.md §3.1 y §4. El dinero llega como cadena con
// 2 decimales y NUNCA se convierte a float para operar: solo se formatea (lib/formato.ts).
// =====================================================================================================

export type Euros = string;

export type AccionId =
  | "pedir_bizum"
  | "cancelar_suscripcion"
  | "bloquear_comercio"
  | "reclamar_cargo"
  | "mover_dinero"
  | "recordar";
export type TipoMomento =
  | "cargo_duplicado"
  | "renovacion_proxima"
  | "subida_recibo"
  | "saldo_negativo_previsto"
  | "posible_estafa"
  | "gasto_compartido"
  | "ingreso_extra"
  | "viaje_detectado"
  | "prueba_gratuita";
export type Urgencia = "alta" | "media" | "baja";
export type AccionDecision = "notificar_ahora" | "resumen" | "silenciar";
export type ResultadoFeedback =
  | "resuelta"
  | "vista_sin_accion"
  | "rechazada"
  | "ignorada"
  | "no_avisar_tipo"
  | "no_avisar_comercio"
  | "no_avisar_contacto"
  | "falso_positivo";
export type CanalFeedback = "voz" | "texto" | "app";
export type ModoVoz = "voz" | "texto_el" | "texto_kit" | "grabado";
export type EstadoModulo = "borrador" | "en_prueba" | "activo" | "pausado";
export type Bandeja = "ahora" | "resumen" | "silenciadas";
export type EstadoNotificacion = "nueva" | "vista" | "resuelta" | "rechazada" | "ignorada";

export type Movimiento = {
  id: string;
  fecha: string;
  concepto: string;
  comercio?: string | null;
  importe: Euros;
  categoria?: string | null;
  saldo?: Euros | null;
  canal?: "tarjeta" | "recibo" | "bizum" | "transferencia" | "cajero" | null;
  contraparte?: string | null;
  nota?: string | null;
  tipo_operacion?: "cargo" | "verificacion" | "devolucion" | null;
};

export type Momento = {
  id: string;
  tipo: TipoMomento;
  usuario_id: string;
  fecha: string;
  movimientos: string[];
  datos: Record<string, unknown>;
  confianza: number;
  impacto_eur?: Euros | null;
  explicacion: string;
  detector: string;
  version: string;
  impacto_relativo?: Euros | null;
  contexto_personal?: string | null;
};

export type Limites = { importe_max?: Euros | null; contrapartes?: string[] | null };
export type AccionOfrecida = {
  accion_id: AccionId;
  parametros: Record<string, unknown>;
  requiere_confirmacion: boolean;
  limites: Limites;
};

export type Propuesta = {
  id: string;
  modulo_id: string;
  momento_id: string;
  usuario_id: string;
  titulo: string;
  mensaje_notificacion: string;
  contexto_llamada: string;
  acciones_ofrecidas: AccionOfrecida[];
  valor_estimado_eur?: Euros | null;
  urgencia: Urgencia;
  tipo_momento: TipoMomento;
  comercio?: string | null;
  contraparte?: string | null;
  confianza: number;
  impacto_relativo?: Euros | null;
  contexto_personal?: string | null;
  creada: string;
};

export type Decision = {
  propuesta_id: string;
  accion: AccionDecision;
  puntuacion: number;
  probabilidad_util: number;
  motivos: string[];
  politica: string;
};

export type Feedback = {
  propuesta_id: string;
  usuario_id: string;
  resultado: ResultadoFeedback;
  canal: CanalFeedback;
  fecha: string;
  nota?: string | null;
};

export type DetalleBaja = {
  url_baja?: string | null;
  url_es_enlace: boolean;
  pasos: string[];
  bloquea_cobros: boolean;
  canal: string;
  fuente: string;
};

export type TarjetaConfirmacion = {
  accion_id: AccionId;
  propuesta_id: string;
  titulo: string;
  parametros_legibles: Record<string, string>;
  simulada: boolean;
  token_confirmacion: string;
  caduca: string;
  detalle_baja?: DetalleBaja | null;
};

export type ResultadoAccion = {
  accion_id: AccionId;
  ok: boolean;
  mensaje: string;
  datos: Record<string, unknown>;
  simulada: boolean;
  deshacer?: { resultado_id: string; disponible_hasta: string } | null;
};

export type Grupo = { miembros: string[]; veces: number; retraso_p75_dias?: number | null };
export type Suscripcion = {
  comercio: string;
  serie_id?: string | null;
  importe: Euros;
  periodicidad_dias: number;
  proximo_cobro?: string | null;
  en_prueba: boolean;
};

export type PerfilUsuario = {
  version: string;
  calculado: string;
  dias_historial: number;
  dia_cobro_nomina?: number | null;
  ingreso_mensual_tipico?: Euros | null;
  gasto_tipico_por_categoria: Record<string, Euros>;
  ticket_tipico: Euros;
  umbral_relevante_eur: Euros;
  comercios_habituales: string[];
  grupos: Grupo[];
  suscripciones_activas: Suscripcion[];
  resumen_vida?: string | null;
  campos_fijados: string[];
  campos_borrados: string[];
};

export type FrasePerfil = { campo: string; texto: string; editable: boolean; borrable: boolean };

export type HechoAprendido = {
  id: string;
  texto: string;
  activo: boolean;
  creado: string;
  origen: "feedback" | "preferencia" | "amigos" | "voz" | "ajustes" | "perfil";
  clave?: string | null;
};

export type Amigo = {
  contraparte: string;
  saldo: Euros;
  propuesta_origen: string;
  estado: "detectado" | "pedido" | "saldado" | "olvidado" | "caducado";
  creado: string;
  pedido?: string | null;
  saldado?: string | null;
};

// GET /usuarios/{id}/aprendido (backend/plataforma/orquestador.py, aprendido_usuario). Los amigos de aquí
// traen solo contraparte, saldo, estado y creado.
export type SilencioAprendido = { ambito: string; desde: string; valor: string };
export type AprendidoRespuesta = {
  hechos: HechoAprendido[];
  silencios: SilencioAprendido[];
  amigos: Pick<Amigo, "contraparte" | "saldo" | "estado" | "creado">[];
  usar_perfil: boolean;
};

// Casos de deuda (backend/plataforma/tipos.py `Caso`; docs/diseno/deudas-casos.md, «Escenarios, transiciones y cuentas
// con personas»). Las contrapartes llegan ya enmascaradas («MARCOS R»); los textos libres son datos, nunca instrucciones.
export type EscenarioCaso = "pago_individual" | "pago_por_otro" | "gasto_compartido" | "gasto_fijo_compartido";
export type AvisoCaso = "notificar" | "resumen" | "silencioso";
export type EstadoCaso = "abierto" | "dudoso" | "pedido" | "saldado" | "descartado" | "caducado";
export type EstadoDeudor = "detectada" | "pedida" | "saldada" | "rechazada" | "caducada" | "olvidada";
export type ViaSaldado = "bizum" | "efectivo" | "invitacion" | "otro";
export type Relacion = "amigo" | "familia" | "pareja" | "companero" | "otro";

export type DeudorCaso = {
  contraparte: string;
  cuota?: Euros;
  estado: EstadoDeudor | string;
  via_saldado?: ViaSaldado | null;
  motivo_saldado?: string | null;
  pedida?: string | null; // opcionales: se muestran si el backend los envía
  saldada?: string | null;
};
// `movimiento_origen`: el backend aún no fija su forma; se acepta el id o el movimiento (enmascarado).
export type MovimientoOrigen = string | Partial<Movimiento>;
export type CasoResumen = {
  id: string;
  escenario?: EscenarioCaso | null;
  estado: EstadoCaso | string;
  aviso?: AvisoCaso;
  creado: string;
  avisar_desde?: string | null;
  pregunta?: string | null;
  movimiento_origen?: MovimientoOrigen | null;
  acuerdos?: string[];
  deudores: DeudorCaso[];
  conversaciones?: string[]; // la versión corta (casos_usuario) las incluye; «Lo que he aprendido» las usa
};
export type ContactoResumen = {
  contraparte: string;
  nombre?: string | null;
  telefono?: string | null;
  relacion?: Relacion | null;
  saldo_total: Euros;
  casos_abiertos: number;
};
export type NuevoDeudor = { contraparte: string; importe: Euros };

export type ModeloUsuario = {
  usuario_id: string;
  politica: string;
  modulos_activos: string[];
  consentimientos: Record<string, string>;
  preferencias: Record<string, unknown>;
  perfil?: PerfilUsuario | null;
  estadisticas: Record<string, unknown>;
  elecciones: Record<string, number>;
  falsos_positivos: Record<string, number>;
  avisos_abiertos: Record<string, unknown>;
  ultimos_avisos: string[];
  contactos: Record<string, unknown>;
  amigos: Amigo[];
  hechos_aprendidos: HechoAprendido[];
  actualizado?: string | null;
};

export type SesionVoz = {
  modo: ModoVoz;
  token?: string | null;
  signed_url?: string | null;
  variables: Record<string, string>;
  token_sesion: string;
  caduca: string;
};

export type MetricasModulo = { avisos: number; resueltas: number; falsos: number; silenciados: number; valor_eur: Euros };
export type Modulo = {
  id: string;
  version: number;
  nombre: string;
  descripcion: string;
  estado: EstadoModulo;
  origen: "catalogo" | "lenguaje_natural";
  escucha: TipoMomento[];
  cuando?: string | null;
  propuesta: Record<string, unknown>;
  acciones: Record<string, unknown>[];
  opcional: boolean;
  ficha_informacion?: string | null;
  aprobado_por?: string | null;
  aprobado_en?: string | null;
  metricas?: MetricasModulo;
};

export type BorradorModulo = {
  spec: Record<string, unknown>;
  interpretacion: string[];
  advertencias: string[];
  estado: EstadoModulo;
};
export type InformePrueba = {
  avisos: { fecha: string; momento_id: string; mensaje: string; etiqueta: "acierto" | "falso_positivo" | "sin_etiqueta" }[];
  aciertos: number;
  falsos_positivos: number;
  omitidos: number;
  controles: { nombre: string; ok: boolean; detalle: string }[];
  resumen: string;
};

export type Escenario = { id: string; usuario_id: string; descripcion: string };
export type DemoCargada = { usuario_id: string; hoy: string; activacion: string };
export type Contadores = { momentos: number; ahora: number; resumen: number; silenciadas: number };
export type EstadoUsuario = { hoy: string; activado: boolean; saldo: Euros | null; contadores: Contadores };
export type Notificacion = { propuesta: Propuesta; decision: Decision; estado: EstadoNotificacion };
export type DetallePropuesta = {
  propuesta: Propuesta;
  decision: Decision;
  momento: Momento;
  movimientos: Movimiento[];
};
export type PerfilRespuesta = { perfil: PerfilUsuario | null; usar_perfil: boolean; frases: FrasePerfil[] };

export type EventoReloj =
  | { tipo: "dia"; datos: { fecha: string; movimientos: Movimiento[]; saldo: Euros | null } }
  | { tipo: "perfil"; datos: { calculado: string; umbral_relevante_eur: Euros } }
  | { tipo: "momento"; datos: Momento }
  | { tipo: "propuesta"; datos: Propuesta }
  | { tipo: "decision"; datos: Decision }
  | { tipo: "fin"; datos: { hoy: string; contadores: Contadores; pausado?: boolean } }
  | { tipo: "error"; datos: { mensaje: string; tipo?: string } };

// `cambio`: la herramienta `actualizar_caso` ha cambiado algo (nivel 3); `cambio_id` es para «Deshacer».
export type EventoVoz = EventoChat | { tipo: "tarjeta"; datos: TarjetaConfirmacion } | { tipo: "cambio"; datos: { hecho: string; cambio_id: string } };

export type EventoBorrador =
  | { tipo: "paso"; datos: { nombre: string; estado: string } }
  | { tipo: "borrador"; datos: BorradorModulo }
  | { tipo: "prueba"; datos: InformePrueba }
  | { tipo: "fin"; datos: Record<string, unknown> }
  | { tipo: "error"; datos: { mensaje: string; tipo?: string } };

async function enviar<T>(ruta: string, metodo: string, cuerpo?: unknown): Promise<T> {
  const respuesta = await fetch(`${API_URL}${ruta}`, {
    method: metodo,
    headers: cabeceras(cuerpo === undefined ? {} : { "Content-Type": "application/json" }),
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  return leerJson<T>(respuesta);
}

const usuario = (id: string) => `/usuarios/${encodeURIComponent(id)}`;

export const escenarios = () => enviar<Escenario[]>("/escenarios", "GET");
export const cargarDemo = (escenarioId: string) => enviar<DemoCargada>("/demo/cargar", "POST", { escenario_id: escenarioId });

// El consentimiento principal va con la clave `copiloto` (CONTRATO.md, «Integración del esqueleto»).
export const activar = (usuarioId: string, modulosActivos: string[], consentimientos: { copiloto: boolean; memoria: boolean }) =>
  enviar<ModeloUsuario>(`${usuario(usuarioId)}/activar`, "POST", {
    modulos_activos: modulosActivos,
    consentimientos,
  });
export const estadoUsuario = (usuarioId: string) => enviar<EstadoUsuario>(`${usuario(usuarioId)}/estado`, "GET");
export const avanzarReloj = (usuarioId: string, dias = 1) =>
  enviar<{ hoy: string; decisiones: Decision[] }>("/reloj/avanzar", "POST", { usuario_id: usuarioId, dias });

export async function reproducir(opciones: {
  usuarioId: string;
  dias: number;
  msPorDia?: number;
  pausarEn?: string;
  alEvento: (evento: EventoReloj) => void;
  senal?: AbortSignal;
}): Promise<void> {
  const consulta = new URLSearchParams({
    usuario_id: opciones.usuarioId,
    dias: String(opciones.dias),
    ms_por_dia: String(opciones.msPorDia ?? 1500),
  });
  if (opciones.pausarEn) consulta.set("pausar_en", opciones.pausarEn);
  const respuesta = await fetch(`${API_URL}/reloj/reproducir?${consulta}`, {
    headers: cabeceras({ Accept: "text/event-stream" }),
    signal: opciones.senal,
  });
  await leerSse<EventoReloj>(respuesta, opciones.alEvento);
}

export const notificaciones = (usuarioId: string, bandeja?: Bandeja) =>
  enviar<Notificacion[]>(`${usuario(usuarioId)}/notificaciones${bandeja ? `?bandeja=${bandeja}` : ""}`, "GET");
export const detallePropuesta = (usuarioId: string, propuestaId: string) =>
  enviar<DetallePropuesta>(`${usuario(usuarioId)}/propuestas/${encodeURIComponent(propuestaId)}`, "GET");
export const enviarFeedback = (f: {
  usuarioId: string;
  propuestaId: string;
  resultado: ResultadoFeedback;
  canal: CanalFeedback;
  nota?: string;
}) =>
  enviar<{ ok: boolean; hechos_nuevos: HechoAprendido[] }>("/feedback", "POST", {
    usuario_id: f.usuarioId,
    propuesta_id: f.propuestaId,
    resultado: f.resultado,
    canal: f.canal,
    nota: f.nota,
  });
export const prepararAccion = (usuarioId: string, propuestaId: string, accionId: AccionId, parametros: Record<string, unknown> = {}, editado = false) =>
  enviar<TarjetaConfirmacion>("/acciones/preparar", "POST", {
    usuario_id: usuarioId,
    propuesta_id: propuestaId,
    accion_id: accionId,
    parametros,
    ...(editado ? { editado: true } : {}),
  });

// Tarjeta editable de `pedir_bizum`: al editar importe o concepto se vuelve a preparar con `editado: true`
// (solo el botón del usuario lo envía; el servidor lo guarda dentro del token) y se usa la tarjeta nueva.
export const prepararAccionEditada = (
  usuarioId: string,
  propuestaId: string,
  accionId: AccionId,
  parametrosBase: Record<string, unknown>,
  cambios: { importe?: Euros; concepto?: string },
) => prepararAccion(usuarioId, propuestaId, accionId, { ...parametrosBase, ...cambios }, true);

export const confirmarAccion = (usuarioId: string, tokenConfirmacion: string) =>
  enviar<ResultadoAccion>("/acciones/confirmar", "POST", { usuario_id: usuarioId, token_confirmacion: tokenConfirmacion });
export const deshacerAccion = (usuarioId: string, resultadoId: string) =>
  enviar<ResultadoAccion>("/acciones/deshacer", "POST", { usuario_id: usuarioId, resultado_id: resultadoId });

export const perfil = (usuarioId: string) => enviar<PerfilRespuesta>(`${usuario(usuarioId)}/perfil`, "GET");
export const editarPerfil = (usuarioId: string, campo: string, valor: unknown) =>
  enviar<PerfilRespuesta>(`${usuario(usuarioId)}/perfil`, "PATCH", { campo, valor });
export const borrarCampoPerfil = (usuarioId: string, campo: string) =>
  enviar<PerfilRespuesta>(`${usuario(usuarioId)}/perfil/${encodeURIComponent(campo)}`, "DELETE");
export const borrarPerfil = (usuarioId: string) => enviar<PerfilRespuesta>(`${usuario(usuarioId)}/perfil`, "DELETE");

export const aprendido = (usuarioId: string) => enviar<AprendidoRespuesta>(`${usuario(usuarioId)}/aprendido`, "GET");
export const editarHecho = (usuarioId: string, hechoId: string, cambios: { activo?: boolean; texto?: string }) =>
  enviar<HechoAprendido>(`${usuario(usuarioId)}/aprendido/${encodeURIComponent(hechoId)}`, "PATCH", cambios);
export const borrarHecho = (usuarioId: string, hechoId: string) =>
  enviar<{ ok: boolean }>(`${usuario(usuarioId)}/aprendido/${encodeURIComponent(hechoId)}`, "DELETE");
export const olvidarTodo = (usuarioId: string) => enviar<{ ok: boolean }>(`${usuario(usuarioId)}/aprendido`, "DELETE");

export const registrarPrueba = (usuarioId: string, comercio: string, fechaAlta: string, dias?: number) =>
  enviar<{ ok: boolean }>(`${usuario(usuarioId)}/pruebas`, "POST", { comercio, fecha_alta: fechaAlta, dias });
export const amigos = (usuarioId: string) => enviar<Amigo[]>(`${usuario(usuarioId)}/amigos`, "GET");
// PROVISIONAL: borra a un amigo pendiente (edicion.borrar_amigo existe en el backend, falta la ruta).
export const borrarAmigo = (usuarioId: string, contraparte: string) =>
  enviar<{ ok: boolean }>(`${usuario(usuarioId)}/amigos/${encodeURIComponent(contraparte)}`, "DELETE");
export const casos = (usuarioId: string) => enviar<CasoResumen[]>(`${usuario(usuarioId)}/casos`, "GET");
export const borrarConversacionesCaso = (usuarioId: string, casoId: string) =>
  enviar<{ ok: boolean }>(`${usuario(usuarioId)}/casos/${encodeURIComponent(casoId)}/conversaciones`, "DELETE");

// Casos y cuentas con personas. Nada de esto mueve dinero: solo apunta, cierra o corrige lo que Meisam sabe.
// Las pantallas las llaman a través de lib/cuentasApi.ts, que con `?mock=1` en la URL usa una maqueta.
export const crearCaso = (usuarioId: string, movimientoId: string, deudores: NuevoDeudor[], escenario?: EscenarioCaso) =>
  enviar<CasoResumen>(`${usuario(usuarioId)}/casos`, "POST", {
    movimiento_id: movimientoId,
    deudores,
    ...(escenario ? { escenario } : {}),
  });
export const saldarCaso = (usuarioId: string, casoId: string, via: Exclude<ViaSaldado, "bizum">, contraparte?: string, motivo?: string) =>
  enviar<CasoResumen>(`${usuario(usuarioId)}/casos/${encodeURIComponent(casoId)}/saldar`, "POST", {
    via,
    ...(contraparte ? { contraparte } : {}),
    ...(motivo ? { motivo } : {}),
  });
export const descartarCaso = (usuarioId: string, casoId: string, motivo?: string) =>
  enviar<CasoResumen>(`${usuario(usuarioId)}/casos/${encodeURIComponent(casoId)}/descartar`, "POST", motivo ? { motivo } : {});
export const cambiarEscenarioCaso = (usuarioId: string, casoId: string, escenario: EscenarioCaso, motivo: string) =>
  enviar<CasoResumen>(`${usuario(usuarioId)}/casos/${encodeURIComponent(casoId)}/escenario`, "POST", { escenario, motivo });
export const contactos = (usuarioId: string) => enviar<ContactoResumen[]>(`${usuario(usuarioId)}/contactos`, "GET");
export const editarContacto = (usuarioId: string, clave: string, relacion: Relacion) =>
  enviar<ContactoResumen>(`${usuario(usuarioId)}/contactos/${encodeURIComponent(clave)}`, "PATCH", { relacion });
// PROVISIONAL (no existe aún en el backend): movimientos del usuario de la demo hasta «hoy», más recientes primero.
export const movimientosUsuario = (usuarioId: string, limite = 60) =>
  enviar<Movimiento[]>(`${usuario(usuarioId)}/movimientos?limite=${limite}`, "GET");

// Sin `propuestaId` es una conversación general («Hablar con Meisam»): ligada solo al usuario y sin acciones ofrecidas.
export const sesionVoz = (propuestaId: string | null, usuarioId: string, modoPreferido: "voz" | "texto_el" | "texto_kit") =>
  enviar<SesionVoz>("/voz/sesion", "POST", {
    ...(propuestaId ? { propuesta_id: propuestaId } : {}),
    usuario_id: usuarioId,
    modo_preferido: modoPreferido,
  });
export async function hablarTexto(opciones: {
  tokenSesion: string;
  mensaje?: string;
  alEvento: (evento: EventoVoz) => void;
  senal?: AbortSignal;
}): Promise<void> {
  const respuesta = await fetch(`${API_URL}/voz/texto`, {
    method: "POST",
    headers: cabeceras({ "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify({ token_sesion: opciones.tokenSesion, mensaje: opciones.mensaje }),
    signal: opciones.senal,
  });
  await leerSse<EventoVoz>(respuesta, opciones.alEvento);
}
export const vozPreparar = (tokenSesion: string, accionId: AccionId, parametros: Record<string, unknown> = {}) =>
  enviar<{ preparada: boolean; titulo?: string; motivo?: string; tarjeta?: TarjetaConfirmacion }>("/voz/herramientas/preparar", "POST", {
    token_sesion: tokenSesion,
    accion_id: accionId,
    parametros,
  });
export const vozFeedback = (tokenSesion: string, resultado: ResultadoFeedback) =>
  enviar<{ ok: boolean }>("/voz/herramientas/feedback", "POST", { token_sesion: tokenSesion, resultado });
// Herramientas de consulta y cambio del agente (experiencia.md, «Herramientas de la llamada»): campos planos más el
// token de sesión, que fija el usuario en el servidor. `actualizar_caso` y `apuntar_gasto` (crea un caso desde el chat,
// curva-amigos.md §4.2) devuelven además `cambio_id` y `hecho` (para «Deshacer»), que el navegador no pasa al agente.
export type NombreHerramientaVoz = "consultar_cuentas" | "buscar_movimientos" | "lo_que_sabes_de_mi" | "actualizar_caso" | "apuntar_gasto";
export type ResultadoHerramienta = { ok: boolean; error?: string; hecho?: string; cambio_id?: string; [clave: string]: unknown };
export const vozHerramienta = (nombre: NombreHerramientaVoz, tokenSesion: string, campos: Record<string, unknown> = {}) =>
  enviar<ResultadoHerramienta>(`/voz/herramientas/${nombre}`, "POST", { token_sesion: tokenSesion, ...campos });
export const vozDeshacer = (tokenSesion: string, cambioId: string) =>
  enviar<{ ok: boolean; hecho?: string; error?: string }>("/voz/herramientas/deshacer", "POST", { token_sesion: tokenSesion, cambio_id: cambioId });
// Al colgar: la transcripción va al agente post-llamada (voz y chat). El backend la enmascara y solo aplica cambios de una
// lista cerrada al caso; nunca mueve dinero. Quien la llama debe ignorar el fallo: no bloquea el cierre de la llamada.
// Al colgar o salir de la pantalla: `keepalive` hace que el navegador termine el envío aunque la página se cierre. Usuario y
// propuesta salen de la sesión del servidor (`tokenSesion`), no del cuerpo. Con `keepalive` el cuerpo no puede pasar de
// 64 KB: si la transcripción es larga se recortan los mensajes más antiguos.
export function enviarConversacion(opciones: {
  tokenSesion: string;
  mensajes: { rol: "meisam" | "usuario"; texto: string }[];
  canal: "voz" | "texto";
}): Promise<{ ok: boolean; cambios: string[] }> {
  let mensajes = opciones.mensajes;
  const cuerpo = () => JSON.stringify({ token_sesion: opciones.tokenSesion, mensajes, canal: opciones.canal });
  while (mensajes.length > 1 && cuerpo().length > 60000) mensajes = mensajes.slice(1);
  return fetch(`${API_URL}/voz/conversacion`, {
    method: "POST",
    headers: cabeceras({ "Content-Type": "application/json" }),
    body: cuerpo(),
    keepalive: true,
  }).then((r) => leerJson<{ ok: boolean; cambios: string[] }>(r));
}
export const vozConsultar = (tokenSesion: string, pregunta: string) =>
  enviar<{ respuesta: string }>("/voz/herramientas/consultar", "POST", { token_sesion: tokenSesion, pregunta });

export const modulosBanco = () => enviar<Modulo[]>("/banco/modulos", "GET");
export async function crearBorrador(opciones: {
  descripcion: string;
  usuarioId: string;
  alEvento: (evento: EventoBorrador) => void;
  senal?: AbortSignal;
}): Promise<void> {
  const respuesta = await fetch(`${API_URL}/banco/modulos/borrador`, {
    method: "POST",
    headers: cabeceras({ "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify({ descripcion: opciones.descripcion, usuario_id: opciones.usuarioId }),
    signal: opciones.senal,
  });
  await leerSse<EventoBorrador>(respuesta, opciones.alEvento);
}
export const aprobarModulo = (moduloId: string, aprobadoPor: string) =>
  enviar<Modulo>(`/banco/modulos/${encodeURIComponent(moduloId)}/aprobar`, "POST", { aprobado_por: aprobadoPor });

export type MetricasTipo = "deteccion" | "molestias" | "aprendizaje";
export const metricas = (tipo: MetricasTipo) =>
  enviar<Record<string, unknown> & { generado: string }>(`/metricas/${tipo}`, "GET");
