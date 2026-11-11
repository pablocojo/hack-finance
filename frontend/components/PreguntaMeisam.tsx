"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReactNode } from "react";
import { rutaNoDisponible } from "@/lib/api";
import { deshacerRespuesta } from "@/lib/respuestasCaso";
import type { RespuestaAplicada } from "@/lib/respuestasCaso";
import { textoVisible } from "@/lib/formato";
import InsigniaIA from "./InsigniaIA";

// Una respuesta fija de un toque. `alElegir` devuelve lo que se aplicó (para confirmar y ofrecer «Deshacer») o `null`
// si en vez de aplicar nada abre un paso propio (por ejemplo elegir personas): entonces el padre pone `flujo`.
export type RespuestaFija = {
  id: string;
  etiqueta: string;
  principal?: boolean;
  alElegir: () => Promise<RespuestaAplicada | null>;
};

type Props = {
  pregunta: string;
  detalle?: string | null;
  // De 2 a 4 respuestas fijas; «Otra respuesta» se añade siempre.
  respuestas: RespuestaFija[];
  // Destino de «Otra respuesta»: el chat «Hablar con Meisam», normalmente con la pregunta como contexto.
  otraRespuestaHref?: string;
  // Paso propio que sustituye a los botones (por ejemplo `FlujoReparto`).
  flujo?: ReactNode;
  alAhoraNo?: () => void;
  alResponder?: () => void; // se contestó con una respuesta fija
  alDeshacer?: () => void;
  etiquetaAria?: string;
};

const mensaje = (fallo: unknown) =>
  rutaNoDisponible(fallo) ? "Esta función todavía no está disponible en el servidor." : fallo instanceof Error ? fallo.message : String(fallo);

// Pregunta de Meisam con respuestas fijas y «Otra respuesta». Genérica: texto + respuestas. Nunca es una notificación.
export default function PreguntaMeisam({
  pregunta,
  detalle,
  respuestas,
  otraRespuestaHref = "/app/hablar",
  flujo,
  alAhoraNo,
  alResponder,
  alDeshacer,
  etiquetaAria = "Pregunta de Meisam",
}: Props) {
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hecha, setHecha] = useState<RespuestaAplicada | null>(null);
  const [nota, setNota] = useState<string | null>(null);

  async function elegir(r: RespuestaFija) {
    setOcupado(r.id);
    setError(null);
    setNota(null);
    try {
      const aplicada = await r.alElegir();
      if (aplicada) {
        setHecha(aplicada);
        alResponder?.();
      }
    } catch (fallo) {
      setError(mensaje(fallo));
    } finally {
      setOcupado(null);
    }
  }

  async function deshacer() {
    if (!hecha) return;
    setOcupado("deshacer");
    setError(null);
    try {
      await deshacerRespuesta(hecha);
      setNota("Lo he dejado como estaba. Puedes contestar de nuevo.");
      setHecha(null);
      alDeshacer?.();
    } catch (fallo) {
      setError(mensaje(fallo));
    } finally {
      setOcupado(null);
    }
  }

  if (hecha) {
    return (
      <article className="pregunta-tarjeta respondida" aria-label={etiquetaAria}>
        <p role="status">
          <strong>{textoVisible(hecha.hecho)}.</strong> Gracias, Meisam lo tendrá en cuenta.
        </p>
        <p className="pequeno tenue">Solo lo apunta Meisam: no se mueve dinero.</p>
        {hecha.cambioId && (
          <div className="fila-botones">
            <button type="button" className="boton-texto" disabled={ocupado !== null} onClick={deshacer}>
              Deshacer
            </button>
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {textoVisible(error)}
          </p>
        )}
      </article>
    );
  }

  return (
    <article className="pregunta-tarjeta" aria-label={etiquetaAria}>
      <span className="aviso-marca">
        Meisam <InsigniaIA />
      </span>
      <h3>{textoVisible(pregunta)}</h3>
      {detalle && <p className="pequeno tenue">{detalle}</p>}
      {nota && (
        <p className="pequeno tenue" role="status">
          {nota}
        </p>
      )}
      {flujo ?? (
        <>
          <div className="respuestas-fijas" role="group" aria-label="Respuestas">
            {respuestas.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`${r.principal ? "boton-principal" : "boton-secundario"} grande`}
                disabled={ocupado !== null}
                onClick={() => void elegir(r)}
              >
                {ocupado === r.id ? "Anotando…" : r.etiqueta}
              </button>
            ))}
          </div>
          <div className="fila-botones">
            <Link href={otraRespuestaHref} className="boton-texto">
              Otra respuesta
            </Link>
            {alAhoraNo && (
              <button type="button" className="boton-texto" disabled={ocupado !== null} onClick={alAhoraNo}>
                Ahora no
              </button>
            )}
          </div>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {textoVisible(error)}
        </p>
      )}
    </article>
  );
}
