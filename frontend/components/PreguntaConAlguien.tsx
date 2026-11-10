"use client";

import { useState } from "react";
import { rutaNoDisponible } from "@/lib/api";
import type { CasoResumen, Movimiento } from "@/lib/api";
import { pagoDeCaso, preguntaDeCaso } from "@/lib/cuentas";
import { descartarCaso } from "@/lib/cuentasApi";
import { eur, fechaLarga, textoVisible } from "@/lib/formato";
import FlujoReparto from "./FlujoReparto";

type Props = {
  usuarioId: string;
  caso: CasoResumen;
  // Movimientos ya conocidos, por si `movimiento_origen` solo trae el id.
  movimientos?: Movimiento[];
  // Si se pasa, aparece «Ahora no» (el Resumen lo usa; «Mis cuentas» no lo necesita).
  alAhoraNo?: () => void;
  alCambiar: () => void;
};

// «¿Fuiste con alguien a …?»: pregunta del Resumen para un pago que quizá fue compartido. Nunca es una notificación.
export default function PreguntaConAlguien({ usuarioId, caso, movimientos, alAhoraNo, alCambiar }: Props) {
  const [reparto, setReparto] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<string | null>(null);

  const pago = pagoDeCaso(caso, movimientos);

  async function ibaSolo() {
    setOcupado(true);
    setError(null);
    try {
      await descartarCaso(usuarioId, caso.id, "Iba solo");
      // La nota se queda en el sitio de la pregunta; la lista se actualiza en la próxima carga.
      setHecho("Anotado. Gracias, Meisam lo tendrá en cuenta.");
    } catch (fallo) {
      setError(rutaNoDisponible(fallo) ? "Esta función todavía no está disponible en el servidor." : fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setOcupado(false);
    }
  }

  if (hecho) {
    return (
      <p className="tarjeta-accion-nota" role="status">
        {hecho}
      </p>
    );
  }

  return (
    <article className="pregunta-tarjeta" aria-label="Pregunta del resumen">
      <h3>{textoVisible(preguntaDeCaso(caso, pago))}</h3>
      {pago && (pago.importe || pago.fecha) && (
        <p className="pequeno tenue">
          {pago.importe && eur(pago.importe)}
          {pago.importe && pago.fecha && " · "}
          {pago.fecha && fechaLarga(pago.fecha)}
        </p>
      )}
      {reparto && pago ? (
        <FlujoReparto
          usuarioId={usuarioId}
          pago={pago}
          alCerrar={() => {
            setReparto(false);
            alCambiar();
          }}
        />
      ) : (
        <div className="fila-botones">
          <button type="button" className="boton-secundario grande" disabled={ocupado} onClick={ibaSolo}>
            Iba solo
          </button>
          <button type="button" className="boton-principal grande" disabled={ocupado || !pago} onClick={() => setReparto(true)}>
            Sí, con…
          </button>
          {alAhoraNo && (
            <button type="button" className="boton-texto" disabled={ocupado} onClick={alAhoraNo}>
              Ahora no
            </button>
          )}
        </div>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}
