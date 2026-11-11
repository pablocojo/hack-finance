"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Conversation } from "@elevenlabs/client";
import { detallePropuesta, enviarConversacion, enviarFeedback, hablarTexto, sesionVoz, vozDeshacer, vozFeedback, vozHerramienta, vozPreparar } from "@/lib/api";
import type { AccionOfrecida, EventoVoz, NombreHerramientaVoz, Propuesta, ResultadoAccion, ResultadoFeedback, SesionVoz, TarjetaConfirmacion } from "@/lib/api";
import { textoVisible } from "@/lib/formato";
import { camposDeHerramienta, extraerTarjeta, fallaPorMicrofono, parametrosDeHerramienta, reloj, RESULTADOS_AGENTE, resumenPrevio } from "@/lib/llamada";
import IconoMicro from "./IconoMicro";
import InsigniaIA from "./InsigniaIA";
import PreLlamada from "./PreLlamada";
import TarjetaAccion from "./TarjetaAccion";
import Transcripcion from "./Transcripcion";
import type { Turno } from "./Transcripcion";

type Rapida = { texto: string; mensaje?: string; feedback?: ResultadoFeedback };
// Cambio hecho por el agente con `actualizar_caso` o `apuntar_gasto`: se avisa en pantalla y, si el servidor lo permite, se puede deshacer.
// `token` es el de la sesión que lo hizo (al cambiar de canal hay otra sesión, y el cambio sigue siendo suyo).
type CambioHecho = { id: string; hecho: string; token: string; estado: "hecho" | "deshaciendo" | "deshecho" | "no"; error?: string };
// Canal activo: voz (ElevenLabs, micrófono), chat (ElevenLabs, solo texto) o kit (nivel 3: /voz/texto con el agente del kit).
type Canal = "voz" | "chat" | "kit" | null;

const RAPIDAS: Rapida[] = [
  { texto: "Sí, hazlo", mensaje: "Sí, hazlo." },
  { texto: "Ahora no", feedback: "rechazada" },
  { texto: "No me avises de esto", feedback: "no_avisar_tipo" },
];

// Sin aviso no hay «Ahora no» ni «No me avises»: se sugieren preguntas que las herramientas de consulta saben responder.
const RAPIDAS_GENERAL: Rapida[] = [
  { texto: "¿Quién me debe?", mensaje: "¿Quién me debe dinero ahora mismo?" },
  { texto: "Lo que sabes de mí", mensaje: "¿Qué sabes de mí?" },
];

const TEXTO_CAIDA_KIT = "La voz de Meisam no está disponible ahora: seguimos por chat con el asistente de respaldo.";

// Con `propuestaId` es la llamada de un aviso; sin él («Hablar con Meisam») es una conversación general: se pregunta por
// las cuentas y se piden cambios con las herramientas de consulta y de cambio, pero no hay acciones que confirmar.
export default function Llamada({ propuestaId, usuarioId }: { propuestaId: string | null; usuarioId: string }) {
  const general = !propuestaId;
  const [propuesta, setPropuesta] = useState<Propuesta | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [tarjeta, setTarjeta] = useState<TarjetaConfirmacion | null>(null);
  const [canal, setCanal] = useState<Canal>(null);
  const [conectando, setConectando] = useState(false);
  const [hablando, setHablando] = useState(false); // solo nivel 3: el agente del kit está respondiendo
  const [esperando, setEsperando] = useState(false); // ElevenLabs: se ha enviado un mensaje y falta la respuesta
  const [modoAgente, setModoAgente] = useState<"speaking" | "listening" | null>(null);
  const [silenciado, setSilenciado] = useState(false);
  const [sinSaludo, setSinSaludo] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [nota, setNota] = useState<string | null>(null);
  const [segundos, setSegundos] = useState(0);
  const [terminada, setTerminada] = useState(false);
  const [hecha, setHecha] = useState(false);
  const [cambios, setCambios] = useState<CambioHecho[]>([]);

  const detalleCargado = useRef(false);
  const contador = useRef(0);
  const senal = useRef<AbortController | null>(null);
  const tokenKit = useRef<string | null>(null); // token de sesión del nivel 3 (solo se usa para el SSE de /voz/texto)
  const conversacion = useRef<Conversation | null>(null);
  const generacion = useRef(0); // cada sesión de ElevenLabs tiene la suya: los eventos de una sesión cerrada se ignoran
  const montado = useRef(false);
  const canalRef = useRef<Canal>(null);
  const canalUsado = useRef<Canal>(null); // el último canal abierto: `canalRef` queda en null al colgar
  const terminadaRef = useRef(false);
  const turnosRef = useRef<Turno[]>([]);
  const tarjetaRef = useRef<TarjetaConfirmacion | null>(null);
  const hechaRef = useRef(false);
  const conFeedback = useRef(false); // ya hay un Feedback explícito (rechazo, error, silencio): no se manda vista_sin_accion
  const cierreRegistrado = useRef(false);
  const conversacionEnviada = useRef(false); // la transcripción se manda una sola vez por llamada
  const ultimoToken = useRef<string | null>(null); // token de la última sesión del servidor: de él salen usuario y propuesta
  const huboCambios = useRef(false); // en una conversación general, solo hay caso relacionado si el agente cambió alguno

  useEffect(() => {
    turnosRef.current = turnos;
    tarjetaRef.current = tarjeta;
  }, [turnos, tarjeta]);

  const fijarCanal = (c: Canal) => {
    canalRef.current = c;
    if (c) canalUsado.current = c;
    setCanal(c);
  };
  const terminar = () => {
    terminadaRef.current = true;
    setTerminada(true);
  };

  const activa = canal !== null && !terminada;

  // El reloj de la llamada cuenta desde que se contesta, no desde que se abre la pantalla.
  useEffect(() => {
    if (!activa) return;
    const id = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [activa]);

  // Si en 4 s no llega el saludo, se avisa en pantalla en vez de dejarla en blanco.
  useEffect(() => {
    setSinSaludo(false);
    if ((canal !== "voz" && canal !== "chat") || turnos.length > 0 || terminada) return;
    const id = setTimeout(() => setSinSaludo(true), 4000);
    return () => clearTimeout(id);
  }, [canal, turnos.length, terminada]);

  // «Pensando…» no se queda colgado si la respuesta nunca llega.
  useEffect(() => {
    if (!esperando) return;
    const id = setTimeout(() => setEsperando(false), 20000);
    return () => clearTimeout(id);
  }, [esperando]);

  const anotarCambio = useCallback((id: string, hecho: string, token: string) => {
    huboCambios.current = true;
    setCambios((cs) => (cs.some((c) => c.id === id) ? cs : [...cs.slice(-2), { id, hecho: textoVisible(hecho), token, estado: "hecho" }]));
  }, []);

  const turnoId = () => `t${++contador.current}`;
  const anadir = useCallback((rol: Turno["rol"], texto: string) => {
    const limpio = texto.trim();
    if (!limpio) return;
    const id = `t${++contador.current}`;
    setTurnos((ts) => {
      const ultimo = ts[ts.length - 1];
      if (ultimo && ultimo.rol === rol && ultimo.texto === limpio) return ts; // eco duplicado
      // Al cambiar de canal el agente nuevo repite su primer mensaje (fijo): ya está arriba, no se repite.
      if (rol === "meisam" && ts[0]?.rol === "meisam" && ts[0].texto === limpio) return ts;
      return [...ts, { id, rol, texto: limpio }];
    });
  }, []);

  // ---- Nivel 3: agente del kit por /voz/texto (SSE) ----
  const hablarKit = useCallback(async (token: string, texto?: string, oculto = false) => {
    const idMeisam = turnoId();
    if (!oculto) {
      setTurnos((t) => [
        ...t,
        ...(texto ? [{ id: turnoId(), rol: "usuario" as const, texto }] : []),
        { id: idMeisam, rol: "meisam" as const, texto: "", enCurso: true },
      ]);
    }
    setHablando(true);
    const cambiar = (f: (t: Turno) => Turno) => setTurnos((ts) => ts.map((x) => (x.id === idMeisam ? f(x) : x)));
    const controlador = new AbortController();
    senal.current = controlador;
    try {
      await hablarTexto({
        tokenSesion: token,
        mensaje: texto,
        senal: controlador.signal,
        alEvento: (e: EventoVoz) => {
          if (e.tipo === "tarjeta") {
            const t = extraerTarjeta(e.datos);
            if (t) setTarjeta(t);
          } else if (e.tipo === "cambio") {
            anotarCambio(e.datos.cambio_id, e.datos.hecho, token);
          } else if (oculto) {
            return; // el saludo se pide al servidor para abrir su historial, pero ya estaba en pantalla
          } else if (e.tipo === "texto") {
            const trozo = e.datos.texto;
            cambiar((x) => ({ ...x, texto: x.texto + trozo }));
          } else if (e.tipo === "fin") {
            const final = e.datos.texto;
            cambiar((x) => ({ ...x, texto: final || x.texto, enCurso: false }));
          } else if (e.tipo === "error") {
            const m = e.datos.mensaje;
            cambiar((x) => ({ ...x, error: m, enCurso: false }));
          }
        },
      });
      cambiar((x) => ({ ...x, enCurso: false }));
    } catch (fallo) {
      if (controlador.signal.aborted) return;
      const m = fallo instanceof Error ? fallo.message : String(fallo);
      if (oculto) setError(m);
      else cambiar((x) => ({ ...x, error: m, enCurso: false }));
    } finally {
      setHablando(false);
    }
  }, [anotarCambio]);

  // ---- Feedback: un solo cierre por llamada ----
  const feedback = useCallback(
    (resultado: ResultadoFeedback) =>
      !propuestaId
        ? Promise.resolve(undefined) // sin aviso no hay nada que valorar
        : enviarFeedback({ usuarioId, propuestaId, resultado, canal: canalRef.current === "voz" ? "voz" : "texto" }).catch(() => undefined),
    [usuarioId, propuestaId],
  );
  // Al terminar sin haber hecho nada ni dado un Feedback explícito, la propuesta queda «vista sin acción».
  const registrarCierre = useCallback(() => {
    if (cierreRegistrado.current) return;
    cierreRegistrado.current = true;
    if (!hechaRef.current && !conFeedback.current) void feedback("vista_sin_accion");
  }, [feedback]);

  // Al colgar, la transcripción va al backend (agente post-llamada). Falla en silencio: no bloquea el cierre.
  const enviarTranscripcion = useCallback(() => {
    if (conversacionEnviada.current) return;
    const mensajes = turnosRef.current
      .filter((t) => !t.enCurso && !t.error && t.texto.trim())
      .map((t) => ({ rol: t.rol, texto: t.texto.trim().slice(0, 2000) }))
      .slice(-120);
    if (!mensajes.some((m) => m.rol === "usuario")) return; // el usuario no dijo nada: no hay nada que leer
    if (general && !huboCambios.current) return; // sin aviso y sin cambios en sus casos: no hay caso relacionado
    if (!ultimoToken.current) return; // nunca se llegó a abrir una sesión
    conversacionEnviada.current = true;
    void enviarConversacion({ tokenSesion: ultimoToken.current, mensajes, canal: canalUsado.current === "voz" ? "voz" : "texto" }).catch(() => undefined);
  }, [general]);

  // La llamada termina por cualquier vía (colgar, «ahora no», colgó el agente): se manda la transcripción una vez.
  useEffect(() => {
    if (terminada) enviarTranscripcion();
  }, [terminada, enviarTranscripcion]);

  // ---- ElevenLabs: voz o chat con el mismo agente ----
  const cerrarEleven = useCallback(async () => {
    generacion.current += 1; // lo que aún llegue de la sesión cerrada ya no cuenta
    const c = conversacion.current;
    conversacion.current = null;
    setModoAgente(null);
    setEsperando(false);
    setSilenciado(false);
    if (c) await c.endSession().catch(() => undefined);
  }, []);

  const herramientaDeVoz = useCallback(
    (nombre: NombreHerramientaVoz, token: string, viva: () => boolean) => async (p: Record<string, unknown>) => {
      try {
        const { cambio_id: cambioId, ...alAgente } = await vozHerramienta(nombre, token, camposDeHerramienta(nombre, p));
        // `apuntar_gasto` también deja un aviso «Apuntado …» con Deshacer cuando crea o convierte un caso.
        if ((nombre === "actualizar_caso" || nombre === "apuntar_gasto") && alAgente.ok && cambioId && typeof alAgente.hecho === "string" && viva()) {
          anotarCambio(cambioId, alAgente.hecho, token);
        }
        return JSON.stringify(alAgente);
      } catch (fallo) {
        return JSON.stringify({ ok: false, error: fallo instanceof Error ? fallo.message : "No he podido hacerlo ahora." });
      }
    },
    [anotarCambio],
  );

  const conectarEleven = useCallback(
    async (s: SesionVoz, soloTexto: boolean) => {
      const { Conversation: Conv } = await import("@elevenlabs/client");
      const mia = (generacion.current += 1);
      const viva = () => montado.current && generacion.current === mia;
      // El navegador solo recibe el token o la URL firmada de esta llamada, nunca la clave.
      const base = {
        dynamicVariables: s.variables,
        clientTools: {
          // Al agente solo vuelve {preparada, titulo} (o el motivo del rechazo): nunca la tarjeta ni su token.
          preparar_accion: async (p: Record<string, unknown>) => {
            const { accionId, parametros } = parametrosDeHerramienta(p);
            if (!accionId) return JSON.stringify({ preparada: false, motivo: "Acción no permitida: usa solo una de la lista ofrecida." });
            try {
              const r = await vozPreparar(s.token_sesion, accionId, parametros);
              if (r.tarjeta && viva()) setTarjeta(r.tarjeta);
              return JSON.stringify(r.preparada ? { preparada: true, titulo: r.titulo } : { preparada: false, motivo: r.motivo });
            } catch (fallo) {
              return JSON.stringify({ preparada: false, motivo: fallo instanceof Error ? fallo.message : "Error al preparar" });
            }
          },
          // Consulta y cambio de los casos del usuario: el servidor valida y el usuario sale del token de sesión. El agente
          // recibe el resultado (datos, no instrucciones) sin el `cambio_id`, que solo sirve al botón «Deshacer».
          consultar_cuentas: herramientaDeVoz("consultar_cuentas", s.token_sesion, viva),
          buscar_movimientos: herramientaDeVoz("buscar_movimientos", s.token_sesion, viva),
          lo_que_sabes_de_mi: herramientaDeVoz("lo_que_sabes_de_mi", s.token_sesion, viva),
          actualizar_caso: herramientaDeVoz("actualizar_caso", s.token_sesion, viva),
          apuntar_gasto: herramientaDeVoz("apuntar_gasto", s.token_sesion, viva),
          registrar_feedback: async (p: { resultado?: string }) => {
            const resultado = RESULTADOS_AGENTE.find((r) => r === p?.resultado);
            if (!resultado) return JSON.stringify({ ok: false });
            await vozFeedback(s.token_sesion, resultado).catch(() => undefined);
            conFeedback.current = true;
            if (viva()) setTarjeta(null); // rechazado o error: no queda nada que confirmar
            return JSON.stringify({ ok: true });
          },
        },
        onMessage: (m: { role: "user" | "agent"; message: string }) => {
          if (!viva()) return;
          if (m.role === "agent") setEsperando(false);
          anadir(m.role === "agent" ? "meisam" : "usuario", m.message ?? "");
        },
        onModeChange: ({ mode }: { mode: "speaking" | "listening" }) => {
          if (viva()) setModoAgente(mode);
        },
        onDisconnect: (d: { reason: string }) => {
          if (!viva()) return;
          conversacion.current = null;
          setModoAgente(null);
          setEsperando(false);
          setSilenciado(false);
          fijarCanal(null);
          if (d.reason === "agent") {
            registrarCierre(); // Meisam ha colgado o se ha acabado el tiempo de la llamada
            terminar();
          } else if (d.reason === "error") {
            setError("Se ha cortado la conexión con Meisam.");
          }
        },
        // El texto técnico del SDK no se enseña: puede llevar direcciones de la conexión.
        onError: (e: unknown) => {
          if (process.env.NODE_ENV !== "production") console.warn("[llamada] error del SDK de ElevenLabs:", e);
          if (viva()) setError("Ha habido un problema con la conexión de la llamada.");
        },
      };
      const c = soloTexto
        ? await Conv.startSession({ ...base, signedUrl: s.signed_url ?? "", connectionType: "websocket", textOnly: true })
        : // En voz no se manda `textOnly`: así no se envía ningún override y funciona aunque el agente los tenga desactivados.
          await Conv.startSession({ ...base, conversationToken: s.token ?? "", connectionType: "webrtc" });
      if (!viva()) {
        await c.endSession().catch(() => undefined); // se salió de la pantalla o se colgó mientras conectaba
        return;
      }
      conversacion.current = c;
      fijarCanal(soloTexto ? "chat" : "voz");
      // El agente nuevo no sabe lo hablado por el canal anterior: se le da como contexto (sin provocar respuesta).
      const previo = resumenPrevio(turnosRef.current, tarjetaRef.current?.titulo);
      if (previo) c.sendContextualUpdate(previo);
    },
    [anadir, registrarCierre, herramientaDeVoz],
  );

  // Abre una sesión del tipo pedido. Niveles (experiencia.md §6.5): voz -> chat con ElevenLabs -> agente del kit.
  const abrirCanal = useCallback(
    async (preferido: "voz" | "texto_el", motivo?: string): Promise<void> => {
      setError(null);
      setNota(null);
      setConectando(true);
      try {
        const s = await sesionVoz(propuestaId, usuarioId, preferido);
        ultimoToken.current = s.token_sesion;
        if (terminadaRef.current || !montado.current) return;
        if (s.modo === "voz" && s.token) {
          await conectarEleven(s, false);
          if (motivo) setNota(motivo);
        } else if (s.modo === "texto_el" && s.signed_url) {
          await conectarEleven(s, true);
          if (motivo) setNota(motivo);
        } else {
          // Sin clave o sin red a ElevenLabs el servidor devuelve el nivel 3.
          tokenKit.current = s.token_sesion;
          fijarCanal("kit");
          setNota(motivo ?? TEXTO_CAIDA_KIT);
          await hablarKit(s.token_sesion, undefined, turnosRef.current.length > 0);
        }
      } catch (fallo) {
        if (process.env.NODE_ENV !== "production") console.warn(`[llamada] falló el canal "${preferido}":`, fallo);
        await cerrarEleven();
        if (terminadaRef.current || !montado.current) return;
        if (preferido === "voz") {
          // Micrófono denegado o fallo de ElevenLabs: seguimos por chat con el mismo aviso.
          const aviso = fallaPorMicrofono(fallo) ? "No he podido usar el micrófono. Seguimos por chat." : "La voz no está disponible ahora. Seguimos por chat.";
          await abrirCanal("texto_el", aviso);
        } else {
          try {
            const k = await sesionVoz(propuestaId, usuarioId, "texto_kit");
            ultimoToken.current = k.token_sesion;
            tokenKit.current = k.token_sesion;
            fijarCanal("kit");
            setNota("El chat de voz no está disponible: seguimos con el asistente de respaldo.");
            await hablarKit(k.token_sesion, undefined, turnosRef.current.length > 0);
          } catch (e2) {
            setError(e2 instanceof Error ? e2.message : String(fallo));
          }
        }
      } finally {
        setConectando(false);
      }
    },
    [propuestaId, usuarioId, conectarEleven, hablarKit, cerrarEleven],
  );

  useEffect(() => {
    montado.current = true;
    // Se carga el SDK al abrir la pantalla: en iOS arma el desbloqueo del audio antes del toque de «Contestar».
    void import("@elevenlabs/client").catch(() => undefined);
    return () => {
      montado.current = false;
      enviarTranscripcion(); // salió de la pantalla sin colgar: también cuenta
      generacion.current += 1;
      senal.current?.abort();
      const c = conversacion.current;
      conversacion.current = null;
      void c?.endSession().catch(() => undefined);
    };
  }, []);

  useEffect(() => {
    if (detalleCargado.current || !propuestaId) return;
    detalleCargado.current = true;
    detallePropuesta(usuarioId, propuestaId)
      .then((d) => setPropuesta(d.propuesta))
      .catch((fallo) => setError(fallo instanceof Error ? fallo.message : String(fallo)));
  }, [usuarioId, propuestaId]);

  // ---- Acciones del usuario ----
  async function contestar() {
    await abrirCanal("voz");
  }

  async function prefieroEscribir() {
    await cerrarEleven();
    await abrirCanal("texto_el", general ? "Seguimos por chat." : "Seguimos por chat con el mismo aviso.");
  }

  async function hablarPorVoz() {
    await cerrarEleven();
    await abrirCanal("voz", general ? "Seguimos por voz." : "Seguimos por voz con el mismo aviso.");
  }

  async function deshacerCambio(c: CambioHecho) {
    setCambios((cs) => cs.map((x) => (x.id === c.id ? { ...x, estado: "deshaciendo" } : x)));
    try {
      const r = await vozDeshacer(c.token, c.id);
      setCambios((cs) => cs.map((x) => (x.id === c.id ? { ...x, estado: r.ok ? "deshecho" : "no", error: r.error } : x)));
      if (r.ok) conversacion.current?.sendContextualUpdate(`El usuario ha pulsado Deshacer en pantalla: «${c.hecho}» ha quedado como estaba antes.`);
    } catch (fallo) {
      setCambios((cs) => cs.map((x) => (x.id === c.id ? { ...x, estado: "no", error: fallo instanceof Error ? fallo.message : "No se ha podido deshacer." } : x)));
    }
  }

  async function reintentar() {
    await cerrarEleven();
    await abrirCanal("texto_el");
  }

  function alternarMicro() {
    const c = conversacion.current;
    if (!c || c.type !== "voice") return;
    const nuevo = !silenciado;
    c.setMicMuted(nuevo);
    setSilenciado(nuevo);
  }

  async function enviarTexto(texto: string) {
    const c = conversacion.current;
    if (c) {
      anadir("usuario", texto);
      setEsperando(true);
      c.sendUserMessage(texto);
    } else if (canalRef.current === "kit" && tokenKit.current) {
      await hablarKit(tokenKit.current, texto);
    }
  }

  async function rapida(r: Rapida) {
    if (conectando || hablando) return;
    if (r.mensaje) {
      await enviarTexto(r.mensaje);
    } else if (r.feedback) {
      anadir("usuario", r.texto);
      conFeedback.current = true;
      await feedback(r.feedback);
      setTarjeta(null);
      await cerrarEleven();
      terminar();
    }
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const texto = mensaje.trim();
    if (!texto || conectando || hablando) return;
    setMensaje("");
    await enviarTexto(texto);
  }

  async function colgar() {
    senal.current?.abort();
    await cerrarEleven();
    registrarCierre();
    fijarCanal(null);
    terminar();
  }

  const alResultado = (r: ResultadoAccion) => {
    if (!r.ok) return;
    hechaRef.current = true;
    conFeedback.current = true;
    setHecha(true);
    // El agente lo cuenta con lo que de verdad ha pasado (simulado) y cierra la llamada.
    const c = conversacion.current;
    if (c) {
      c.sendContextualUpdate(`El usuario ha pulsado Confirmar en pantalla: ${r.mensaje} (simulado, no se ha movido dinero real).`);
      c.sendUserMessage("Ya lo he confirmado.");
      setEsperando(true);
    }
  };

  const alAhoraNo = () => {
    conFeedback.current = true;
    void feedback("rechazada");
    conversacion.current?.sendContextualUpdate("El usuario ha pulsado «Ahora no» en la tarjeta: no quiere hacerlo ahora.");
  };

  const ofrecida: AccionOfrecida | undefined = tarjeta
    ? propuesta?.acciones_ofrecidas.find((a) => a.accion_id === tarjeta.accion_id)
    : undefined;
  const enVoz = canal === "voz";
  const previa = canal === null && !terminada && !conectando && !error && turnos.length === 0;
  const pensando: Turno = { id: "esperando", rol: "meisam", texto: "", enCurso: true };
  const turnosVista: Turno[] = (esperando ? [...turnos, pensando] : turnos).map((t) => ({
    ...t,
    texto: t.rol === "meisam" ? textoVisible(t.texto) : t.texto,
  }));

  return (
    <div className="movil llamada">
      <header className="llamada-cab">
        <div>
          <p className="llamada-nombre">Meisam</p>
          <p className="llamada-estado">
            <InsigniaIA texto="Asistente de IA" />
            <span aria-label="Duración de la llamada" className="llamada-reloj">
              {reloj(segundos)}
            </span>
            {enVoz && (
              <span className={`llamada-modo${modoAgente === "speaking" ? " hablando" : ""}`}>
                {modoAgente === "speaking" ? "Hablando…" : silenciado ? "Micrófono apagado" : "Te escucho"}
              </span>
            )}
            {canal === "chat" && <span className="llamada-modo">Por escrito</span>}
          </p>
        </div>
        {terminada ? (
          <Link href="/app" className="boton-colgar volver">
            Volver
          </Link>
        ) : (
          <button type="button" className="boton-colgar" onClick={colgar}>
            Colgar
          </button>
        )}
      </header>

      {propuesta && !previa && (
        <p className="llamada-tema">
          <strong>{textoVisible(propuesta.titulo)}</strong>
        </p>
      )}

      {previa && (
        <PreLlamada
          titulo={propuesta ? textoVisible(propuesta.titulo) : undefined}
          general={general}
          alContestar={contestar}
          alEscribir={prefieroEscribir}
        />
      )}

      {conectando && (
        <p className="tarjeta-accion-nota" role="status">
          Conectando…
        </p>
      )}
      {nota && (
        <p className="banda pequeno" role="status">
          {nota}
        </p>
      )}
      {cambios.map((c) => (
        <div
          key={c.id}
          className="banda pequeno"
          role="status"
          style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
        >
          <span>
            {c.estado === "deshecho"
              ? `Deshecho: ${c.hecho}`
              : c.estado === "no"
                ? `No se puede deshacer: ${c.error ?? "el caso ha cambiado"}`
                : c.hecho.startsWith("Anotado") || c.hecho.startsWith("Apuntado")
                  ? c.hecho
                  : `Hecho: ${c.hecho}`}
          </span>
          {(c.estado === "hecho" || c.estado === "deshaciendo") && (
            <button type="button" className="boton-secundario" disabled={c.estado === "deshaciendo"} onClick={() => deshacerCambio(c)}>
              Deshacer
            </button>
          )}
        </div>
      ))}
      {error && (
        <div className="error banda" role="alert">
          <p>{error}</p>
          {!terminada && (
            <button type="button" className="boton-secundario" onClick={reintentar} disabled={conectando}>
              Reintentar
            </button>
          )}
        </div>
      )}
      {sinSaludo && !terminada && (
        <p className="tarjeta-accion-nota" role="status">
          {general ? "Conectado. Si Meisam no te saluda, escribe «Hola»." : "Conectado. Si Meisam no te saluda, escribe «Hola» o pulsa «Sí, hazlo»."}
        </p>
      )}

      <Transcripcion
        turnos={turnosVista}
        hijos={
          tarjeta && (!terminada || hecha) ? (
            <TarjetaAccion
              key={`${tarjeta.accion_id}-${tarjeta.propuesta_id}`}
              tarjeta={tarjeta}
              usuarioId={usuarioId}
              parametrosBase={ofrecida?.parametros}
              alCambiarTarjeta={setTarjeta}
              alResultado={alResultado}
              alAhoraNo={alAhoraNo}
            />
          ) : undefined
        }
      />

      {activa ? (
        <div className="llamada-pie">
          <div className="rapidas" role="group" aria-label="Respuestas rápidas">
            {(general ? RAPIDAS_GENERAL : RAPIDAS).map((r) => (
              <button key={r.texto} type="button" className="chip grande" disabled={conectando || hablando} onClick={() => rapida(r)}>
                {r.texto}
              </button>
            ))}
          </div>
          <form className="llamada-entrada" onSubmit={enviar}>
            {canal === "chat" && (
              <button
                type="button"
                className="boton-voz"
                onClick={hablarPorVoz}
                disabled={conectando}
                aria-label="Hablar con Meisam por voz"
                title="Hablar con Meisam por voz"
              >
                <IconoMicro />
              </button>
            )}
            <label htmlFor="mensaje-llamada" className="solo-lectores">
              Escribe a Meisam
            </label>
            <input
              id="mensaje-llamada"
              className="campo"
              value={mensaje}
              maxLength={500}
              autoComplete="off"
              placeholder={enVoz ? "También puedes escribir…" : "Escribe aquí…"}
              onChange={(e) => setMensaje(e.target.value)}
              disabled={conectando}
            />
            <button type="submit" className="boton-principal" disabled={conectando || hablando || !mensaje.trim()}>
              Enviar
            </button>
          </form>
          {enVoz && (
            <div className="controles-voz">
              <button type="button" className="boton-secundario" onClick={alternarMicro} aria-pressed={silenciado}>
                <IconoMicro apagado={silenciado} tamano={18} />
                {silenciado ? "Activar micrófono" : "Silenciar micrófono"}
              </button>
              <button type="button" className="boton-secundario" onClick={prefieroEscribir} disabled={conectando}>
                Prefiero escribir
              </button>
            </div>
          )}
        </div>
      ) : terminada ? (
        <p className="tarjeta-accion-nota" role="status">
          La llamada ha terminado.
        </p>
      ) : null}

      <footer className="aviso-ia-fijo">
        <InsigniaIA texto="IA" />
        <span>
          Meisam es un asistente de inteligencia artificial. La información es orientativa y no es asesoramiento
          financiero. Datos sintéticos.
        </span>
      </footer>
    </div>
  );
}
