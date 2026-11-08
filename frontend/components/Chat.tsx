"use client";

import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { leerComoBase64, preguntar } from "@/lib/api";
import type { Adjunto, EventoChat, Final } from "@/lib/api";
import { nombreHerramienta } from "@/lib/formato";
import Markdown from "./Markdown";

type Mensaje = {
  id: number;
  rol: "usuario" | "asistente";
  texto: string;
  herramientas: string[];
  avisos: string[];
  final?: Final;
  error?: string;
  corregido?: boolean;
  enCurso?: boolean;
};

const SUGERENCIAS = [
  "¿En qué gasto más?",
  "¿Ves algo raro en mis cargos?",
  "¿Qué suscripciones tengo?",
  "¿Llego a fin de mes?",
  "¿Cuánto pagaría por 10.000 € a 5 años al 7 %?",
];

const MODELOS = [
  { valor: "auto", etiqueta: "Automático" },
  { valor: "rapido", etiqueta: "Rápido" },
  { valor: "normal", etiqueta: "Normal" },
  { valor: "profundo", etiqueta: "A fondo" },
];

const TIPOS_ADJUNTO = ["image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"];

type Props = {
  sesionId: string | null;
  reinicio: number;
  alCambiarSesion: (id: string) => void;
  alTerminar: (final: Final) => void;
};

export default function Chat({ sesionId, reinicio, alCambiarSesion, alTerminar }: Props) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [entrada, setEntrada] = useState("");
  const [modelo, setModelo] = useState("auto");
  const [adjunto, setAdjunto] = useState<{ nombre: string; datos: Adjunto } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const final = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMensajes([]);
  }, [reinicio]);

  useEffect(() => {
    final.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes]);

  function actualizar(id: number, cambio: (m: Mensaje) => Mensaje) {
    setMensajes((previos) => previos.map((m) => (m.id === id ? cambio(m) : m)));
  }

  async function elegirAdjunto(evento: ChangeEvent<HTMLInputElement>) {
    const archivo = evento.target.files?.[0];
    evento.target.value = "";
    if (!archivo) return;
    if (!TIPOS_ADJUNTO.includes(archivo.type)) {
      setAviso("Adjunta una imagen (PNG, JPG, GIF, WEBP) o un PDF.");
      return;
    }
    if (archivo.size > 4_500_000) {
      setAviso("El archivo es demasiado grande (máximo 4,5 MB).");
      return;
    }
    setAviso(null);
    setAdjunto({ nombre: archivo.name, datos: { tipo: archivo.type, datos_base64: await leerComoBase64(archivo) } });
  }

  async function enviar(texto: string) {
    const limpio = texto.trim();
    if (!limpio || ocupado) return;
    const idUsuario = Date.now();
    const idAsistente = idUsuario + 1;
    const enviado = adjunto;
    setMensajes((previos) => [
      ...previos,
      {
        id: idUsuario,
        rol: "usuario",
        texto: enviado ? `${limpio}\n\nAdjunto: ${enviado.nombre}` : limpio,
        herramientas: [],
        avisos: [],
      },
      { id: idAsistente, rol: "asistente", texto: "", herramientas: [], avisos: [], enCurso: true },
    ]);
    setEntrada("");
    setAdjunto(null);
    setOcupado(true);

    const alEvento = (evento: EventoChat) => {
      if (evento.tipo === "sesion") {
        const id = evento.datos.sesion_id;
        if (id !== sesionId) alCambiarSesion(id);
      } else if (evento.tipo === "texto") {
        const trozo = evento.datos.texto;
        actualizar(idAsistente, (m) => ({ ...m, texto: m.texto + trozo }));
      } else if (evento.tipo === "aviso") {
        const textoAviso = evento.datos.texto;
        actualizar(idAsistente, (m) => ({ ...m, avisos: [...m.avisos, textoAviso] }));
      } else if (evento.tipo === "herramienta_inicio") {
        const nombre = evento.datos.nombre;
        actualizar(idAsistente, (m) => ({ ...m, herramientas: [...m.herramientas, nombre] }));
      } else if (evento.tipo === "revision") {
        const corregido = evento.datos.texto;
        if (!evento.datos.aprobada && corregido) {
          actualizar(idAsistente, (m) => ({ ...m, texto: corregido, corregido: true }));
        }
      } else if (evento.tipo === "fin") {
        const datos = evento.datos;
        actualizar(idAsistente, (m) => ({ ...m, texto: datos.texto || m.texto, final: datos, enCurso: false }));
        alTerminar(datos);
      } else if (evento.tipo === "error") {
        const mensajeError = evento.datos.mensaje;
        actualizar(idAsistente, (m) => ({ ...m, error: mensajeError, enCurso: false }));
      }
    };

    try {
      await preguntar({ mensaje: limpio, sesionId, modelo, adjunto: enviado?.datos ?? null, alEvento });
    } catch (error) {
      const mensajeError = error instanceof Error ? error.message : String(error);
      actualizar(idAsistente, (m) => ({ ...m, error: `No se ha podido conectar con el backend: ${mensajeError}` }));
    } finally {
      actualizar(idAsistente, (m) => ({ ...m, enCurso: false }));
      setOcupado(false);
    }
  }

  function alEnviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    void enviar(entrada);
  }

  return (
    <section className="tarjeta chat" aria-label="Conversación con el asistente">
      <div className="chat-mensajes" aria-live="polite">
        {mensajes.length === 0 ? (
          <div className="chat-vacio">
            <p className="chat-saludo">¿Qué quieres saber de tus finanzas?</p>
            <div className="sugerencias">
              {SUGERENCIAS.map((sugerencia) => (
                <button key={sugerencia} type="button" className="chip" onClick={() => void enviar(sugerencia)}>
                  {sugerencia}
                </button>
              ))}
            </div>
          </div>
        ) : (
          mensajes.map((m) => (
            <article key={m.id} className={`burbuja ${m.rol}`}>
              {m.avisos.map((textoAviso) => (
                <p key={textoAviso} className="aviso-pequeno">{textoAviso}</p>
              ))}
              {m.herramientas.length > 0 && (
                <div className="herramientas-usadas">
                  {m.herramientas.map((nombre, i) => (
                    <span key={`${nombre}-${i}`} className="etiqueta">{nombreHerramienta(nombre)}</span>
                  ))}
                </div>
              )}
              {m.texto ? <Markdown texto={m.texto} /> : m.enCurso ? <p className="pensando">Pensando…</p> : null}
              {m.error && <p className="error">{m.error}</p>}
              {m.corregido && <p className="aviso-pequeno">Revisada por el control de cumplimiento.</p>}
              {m.final && (
                <p className="pie">
                  {m.final.reproducido ? "modo demo · " : ""}
                  {m.final.vueltas} paso(s) · {m.final.coste_usd.toFixed(4)} $
                </p>
              )}
            </article>
          ))
        )}
        <div ref={final} />
      </div>

      {aviso && <p className="error">{aviso}</p>}
      <form className="chat-entrada" onSubmit={alEnviar}>
        <label className="boton-icono" title="Adjuntar ticket, factura o extracto (imagen o PDF)">
          <input type="file" accept={TIPOS_ADJUNTO.join(",")} onChange={(e) => void elegirAdjunto(e)} hidden />
          <span aria-hidden="true">+</span>
          <span className="solo-lector">Adjuntar archivo</span>
        </label>
        <input
          className="campo"
          value={entrada}
          onChange={(e) => setEntrada(e.target.value)}
          placeholder={adjunto ? `Pregunta sobre ${adjunto.nombre}…` : "Escribe tu pregunta…"}
          maxLength={4000}
          disabled={ocupado}
          aria-label="Tu pregunta"
        />
        <select value={modelo} onChange={(e) => setModelo(e.target.value)} aria-label="Modo de respuesta">
          {MODELOS.map((m) => (
            <option key={m.valor} value={m.valor}>{m.etiqueta}</option>
          ))}
        </select>
        <button type="submit" className="boton-principal" disabled={ocupado || !entrada.trim()}>
          {ocupado ? "…" : "Enviar"}
        </button>
      </form>
    </section>
  );
}
