"use client";

import Link from "next/link";
import { useState } from "react";
import { detallePropuesta, prepararAccion } from "@/lib/api";
import type { Notificacion, TarjetaConfirmacion } from "@/lib/api";
import { ESTADO_AVISO, esPendiente } from "@/lib/avisos";
import { eur, fechaLarga, textoVisible } from "@/lib/formato";
import InsigniaIA from "./InsigniaIA";
import PorQue from "./PorQue";
import TarjetaAccion from "./TarjetaAccion";

const URGENCIA: Record<string, string> = { alta: "Urgente", media: "Importante", baja: "Sin prisa" };

type Props = { usuarioId: string; notificacion: Notificacion; alCambiar: () => void };

// Una entrada del historial: el aviso con su estado, el porqué de la decisión y, si sigue pendiente, la llamada,
// la tarjeta de acción rápida y «Marcar como vista». Abrir el detalle marca el aviso como visto en el servidor.
export default function EntradaAviso({ usuarioId, notificacion, alCambiar }: Props) {
  const { propuesta, decision, estado } = notificacion;
  const [tarjeta, setTarjeta] = useState<TarjetaConfirmacion | null>(null);
  const [ocupado, setOcupado] = useState<"vista" | "tarjeta" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pendiente = esPendiente(notificacion);
  const primera = propuesta.acciones_ofrecidas[0];
  const nueva = estado === "nueva";

  async function ejecutar(tipo: "vista" | "tarjeta", tarea: () => Promise<void>) {
    setOcupado(tipo);
    setError(null);
    try {
      await tarea();
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setOcupado(null);
    }
  }

  const marcarVista = () =>
    ejecutar("vista", async () => {
      await detallePropuesta(usuarioId, propuesta.id); // la consulta del detalle es la que marca la notificación como vista
      alCambiar();
    });
  const hacerlo = () =>
    ejecutar("tarjeta", async () => {
      if (!primera) return;
      setTarjeta(await prepararAccion(usuarioId, propuesta.id, primera.accion_id, primera.parametros));
    });

  return (
    <article className={`aviso-tarjeta urgencia-${propuesta.urgencia}${nueva ? " es-nueva" : ""}${pendiente ? "" : " cerrada"}`}>
      <header className="aviso-cab">
        <span className="aviso-marca">
          Meisam <InsigniaIA />
        </span>
        <span className="aviso-etiquetas">
          {pendiente && propuesta.urgencia !== "baja" && <span className={`urgencia urgencia-${propuesta.urgencia}`}>{URGENCIA[propuesta.urgencia]}</span>}
          <span className={`estado-aviso estado-aviso-${estado}`}>{ESTADO_AVISO[estado]}</span>
        </span>
      </header>
      <p className="pequeno tenue">{fechaLarga(propuesta.creada)}</p>
      <h3>{textoVisible(propuesta.titulo)}</h3>
      <p className="aviso-mensaje">{textoVisible(propuesta.mensaje_notificacion)}</p>
      {propuesta.valor_estimado_eur && (
        <p className="aviso-valor">
          <strong>{eur(propuesta.valor_estimado_eur)}</strong>
          <span> en juego</span>
        </p>
      )}
      {decision.motivos[0] && <p className="aviso-motivo">Por qué te aviso: {textoVisible(decision.motivos[0])}</p>}
      <PorQue usuarioId={usuarioId} propuestaId={propuesta.id} alCargar={alCambiar} />
      {pendiente &&
        (tarjeta ? (
          <TarjetaAccion
            tarjeta={tarjeta}
            usuarioId={usuarioId}
            parametrosBase={primera?.parametros}
            alResultado={alCambiar}
            alAhoraNo={() => setTarjeta(null)}
            alCambiarTarjeta={setTarjeta}
          />
        ) : (
          <div className="aviso-botones">
            <Link href={`/app/llamada/${encodeURIComponent(propuesta.id)}`} className="enlace-boton grande">
              Resolver
            </Link>
            {primera && (
              <button type="button" className="boton-secundario grande" disabled={ocupado !== null} onClick={hacerlo}>
                Hacerlo ya
              </button>
            )}
          </div>
        ))}
      {nueva && !tarjeta && (
        <button type="button" className="boton-texto" disabled={ocupado !== null} onClick={marcarVista}>
          Marcar como vista
        </button>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}
