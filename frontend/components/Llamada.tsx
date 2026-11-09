"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { detallePropuesta, enviarFeedback, hablarTexto, sesionVoz } from "@/lib/api";
import type { AccionOfrecida, EventoVoz, Propuesta, ResultadoFeedback, TarjetaConfirmacion } from "@/lib/api";
import { textoVisible } from "@/lib/formato";
import InsigniaIA from "./InsigniaIA";
import TarjetaAccion from "./TarjetaAccion";
import Transcripcion from "./Transcripcion";
import type { Turno } from "./Transcripcion";

type Rapida = { texto: string; mensaje?: string; feedback?: ResultadoFeedback };

// «Sí, hazlo» se lo dice a Meisam; las otras dos cierran el aviso con un Feedback.
const RAPIDAS: Rapida[] = [
  { texto: "Sí, hazlo", mensaje: "Sí, hazlo." },
  { texto: "Ahora no", feedback: "rechazada" },
  { texto: "No me avises de esto", feedback: "no_avisar_tipo" },
];

function reloj(segundos: number): string {
  const m = Math.floor(segundos / 60);
  return `${String(m).padStart(2, "0")}:${String(segundos % 60).padStart(2, "0")}`;
}

// El backend puede mandar la tarjeta sola o envuelta en {tarjeta}.
function extraerTarjeta(datos: unknown): TarjetaConfirmacion | null {
  const d = datos as { tarjeta?: TarjetaConfirmacion } & Partial<TarjetaConfirmacion>;
  const t = d?.tarjeta ?? (d?.token_confirmacion ? (d as TarjetaConfirmacion) : null);
  return t && t.token_confirmacion ? t : null;
}

export default function Llamada({ propuestaId, usuarioId }: { propuestaId: string; usuarioId: string }) {
  const [propuesta, setPropuesta] = useState<Propuesta | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [tarjeta, setTarjeta] = useState<TarjetaConfirmacion | null>(null);
  const [tokenSesion, setTokenSesion] = useState<string | null>(null);
  const [hablando, setHablando] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [segundos, setSegundos] = useState(0);
  const [terminada, setTerminada] = useState(false);
  const [hecha, setHecha] = useState(false);
  const arrancada = useRef(false);
  const contador = useRef(0);
  const senal = useRef<AbortController | null>(null);

  useEffect(() => {
    const id = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const turnoId = () => `t${++contador.current}`;

  // Envía un mensaje (o el saludo, si va vacío) y pinta la respuesta en streaming.
  const hablar = useCallback(
    async (token: string, texto?: string) => {
      const idMeisam = turnoId();
      setTurnos((t) => [
        ...t,
        ...(texto ? [{ id: turnoId(), rol: "usuario" as const, texto }] : []),
        { id: idMeisam, rol: "meisam" as const, texto: "", enCurso: true },
      ]);
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
            if (e.tipo === "texto") {
              const trozo = e.datos.texto;
              cambiar((x) => ({ ...x, texto: x.texto + trozo }));
            } else if (e.tipo === "tarjeta") {
              const t = extraerTarjeta(e.datos);
              if (t) setTarjeta(t);
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
        cambiar((x) => ({ ...x, error: m, enCurso: false }));
      } finally {
        setHablando(false);
      }
    },
    [],
  );

  const abrir = useCallback(async () => {
    setError(null);
    try {
      const [detalle, sesion] = await Promise.all([
        detallePropuesta(usuarioId, propuestaId),
        // Nivel 3 del plan B (docs/diseno/experiencia.md §6.5). F6 pedirá "voz" cuando exista la llamada de ElevenLabs.
        sesionVoz(propuestaId, usuarioId, "texto_kit"),
      ]);
      setPropuesta(detalle.propuesta);
      setTokenSesion(sesion.token_sesion);
      await hablar(sesion.token_sesion);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    }
  }, [usuarioId, propuestaId, hablar]);

  useEffect(() => {
    if (arrancada.current) return;
    arrancada.current = true;
    void abrir();
  }, [abrir]);

  useEffect(() => () => senal.current?.abort(), []);

  const feedback = (resultado: ResultadoFeedback) =>
    enviarFeedback({ usuarioId, propuestaId, resultado, canal: "texto" }).catch(() => undefined);

  async function rapida(r: Rapida) {
    if (!tokenSesion || hablando) return;
    if (r.mensaje) {
      await hablar(tokenSesion, r.mensaje);
    } else if (r.feedback) {
      setTurnos((t) => [...t, { id: turnoId(), rol: "usuario", texto: r.texto }]);
      await feedback(r.feedback);
      setTarjeta(null);
      setTerminada(true);
    }
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const texto = mensaje.trim();
    if (!texto || !tokenSesion || hablando) return;
    setMensaje("");
    await hablar(tokenSesion, texto);
  }

  async function colgar() {
    senal.current?.abort();
    if (!hecha && !terminada) await feedback("vista_sin_accion");
    setTerminada(true);
  }

  const ofrecida: AccionOfrecida | undefined = tarjeta
    ? propuesta?.acciones_ofrecidas.find((a) => a.accion_id === tarjeta.accion_id)
    : undefined;

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

      {propuesta && (
        <p className="llamada-tema">
          <strong>{textoVisible(propuesta.titulo)}</strong>
        </p>
      )}

      {error && (
        <div className="error banda" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="boton-secundario"
            onClick={() => {
              arrancada.current = true;
              setTurnos([]);
              void abrir();
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      <Transcripcion
        turnos={turnos.map((t) => ({ ...t, texto: t.rol === "meisam" ? textoVisible(t.texto) : t.texto }))}
        hijos={
          tarjeta && !terminada ? (
            <TarjetaAccion
              key={`${tarjeta.accion_id}-${tarjeta.propuesta_id}`}
              tarjeta={tarjeta}
              usuarioId={usuarioId}
              parametrosBase={ofrecida?.parametros}
              alCambiarTarjeta={setTarjeta}
              alResultado={(r) => r.ok && setHecha(true)}
              alAhoraNo={() => void feedback("rechazada")}
            />
          ) : undefined
        }
      />

      {!terminada ? (
        <div className="llamada-pie">
          <div className="rapidas" role="group" aria-label="Respuestas rápidas">
            {RAPIDAS.map((r) => (
              <button key={r.texto} type="button" className="chip grande" disabled={!tokenSesion || hablando} onClick={() => rapida(r)}>
                {r.texto}
              </button>
            ))}
          </div>
          <form className="llamada-entrada" onSubmit={enviar}>
            {/* Sitio del botón de voz (F6: llamada de ElevenLabs). De momento, solo texto. */}
            <div className="hueco-voz" data-futuro="f6-voz" />
            <label htmlFor="mensaje-llamada" className="solo-lectores">
              Escribe a Meisam
            </label>
            <input
              id="mensaje-llamada"
              className="campo"
              value={mensaje}
              maxLength={500}
              autoComplete="off"
              placeholder="Escribe aquí…"
              onChange={(e) => setMensaje(e.target.value)}
              disabled={!tokenSesion}
            />
            <button type="submit" className="boton-principal" disabled={!tokenSesion || hablando || !mensaje.trim()}>
              Enviar
            </button>
          </form>
        </div>
      ) : (
        <p className="tarjeta-accion-nota" role="status">
          La llamada ha terminado.
        </p>
      )}

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
