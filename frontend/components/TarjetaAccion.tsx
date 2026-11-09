"use client";

import { useEffect, useRef, useState } from "react";
import { confirmarAccion, deshacerAccion, prepararAccion } from "@/lib/api";
import type { AccionId, ResultadoAccion, TarjetaConfirmacion } from "@/lib/api";
import { textoVisible } from "@/lib/formato";
import DetalleBaja from "./DetalleBaja";

type Props = {
  tarjeta: TarjetaConfirmacion;
  usuarioId: string;
  // Parámetros de la acción ofrecida en la propuesta (para volver a preparar con otro valor de bloquear_cobros).
  parametrosBase?: Record<string, unknown>;
  alResultado?: (resultado: ResultadoAccion) => void;
  alAhoraNo?: () => void;
  alCambiarTarjeta?: (tarjeta: TarjetaConfirmacion) => void;
};

// El token de confirmación vive solo en el estado del componente: nunca se pinta ni se guarda.
export default function TarjetaAccion({ tarjeta: inicial, usuarioId, parametrosBase, alResultado, alAhoraNo, alCambiarTarjeta }: Props) {
  const [tarjeta, setTarjeta] = useState(inicial);
  const [resultado, setResultado] = useState<ResultadoAccion | null>(null);
  const [deshecho, setDeshecho] = useState<ResultadoAccion | null>(null);
  const [descartada, setDescartada] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titulo = useRef<HTMLHeadingElement>(null);

  useEffect(() => setTarjeta(inicial), [inicial]);
  useEffect(() => titulo.current?.focus(), []);

  const esBaja = tarjeta.accion_id === "cancelar_suscripcion";
  const bloquea = tarjeta.detalle_baja?.bloquea_cobros ?? false;
  const comercio = typeof parametrosBase?.comercio === "string" ? parametrosBase.comercio : "el comercio";

  async function ejecutar(tarea: () => Promise<void>) {
    setOcupado(true);
    setError(null);
    try {
      await tarea();
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setOcupado(false);
    }
  }

  const alternarBloqueo = (valor: boolean) =>
    ejecutar(async () => {
      const nueva = await prepararAccion(usuarioId, tarjeta.propuesta_id, tarjeta.accion_id as AccionId, {
        ...(parametrosBase ?? {}),
        bloquear_cobros: valor,
      });
      setTarjeta(nueva);
      alCambiarTarjeta?.(nueva);
    });

  const confirmar = () =>
    ejecutar(async () => {
      const r = await confirmarAccion(usuarioId, tarjeta.token_confirmacion);
      setResultado(r);
      alResultado?.(r);
    });

  const deshacer = () =>
    ejecutar(async () => {
      if (!resultado?.deshacer) return;
      setDeshecho(await deshacerAccion(usuarioId, resultado.deshacer.resultado_id));
    });

  if (descartada) {
    return (
      <p className="tarjeta-accion-nota" role="status">
        Vale, lo dejamos para más tarde.
      </p>
    );
  }

  if (resultado) {
    return (
      <section className={`tarjeta-accion ${resultado.ok ? "hecha" : "fallida"}`} aria-label="Resultado de la acción">
        <div className="tarjeta-accion-cab">
          <span className="insignia-simulado">Simulado</span>
          <span className="pequeno tenue">No se mueve dinero real</span>
        </div>
        <h3 ref={titulo} tabIndex={-1}>
          {resultado.ok ? "Hecho" : "No se ha podido hacer"}
        </h3>
        <p role="status">{textoVisible(deshecho ? deshecho.mensaje : resultado.mensaje)}</p>
        {resultado.deshacer && !deshecho && (
          <button type="button" className="boton-secundario grande" onClick={deshacer} disabled={ocupado}>
            Deshacer
          </button>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>
    );
  }

  return (
    <section className="tarjeta-accion" aria-label="Confirmar acción">
      <div className="tarjeta-accion-cab">
        <span className="insignia-simulado">Simulado</span>
        <span className="pequeno tenue">No se mueve dinero real</span>
      </div>
      <h3 ref={titulo} tabIndex={-1}>
        {textoVisible(tarjeta.titulo)}
      </h3>
      <dl className="parametros">
        {Object.entries(tarjeta.parametros_legibles).map(([clave, valor]) => (
          <div key={clave}>
            <dt>{clave}</dt>
            <dd>{textoVisible(valor)}</dd>
          </div>
        ))}
      </dl>

      {esBaja && tarjeta.detalle_baja && (
        <>
          <DetalleBaja detalle={tarjeta.detalle_baja} comercio={textoVisible(comercio)} />
          <label className="interruptor">
            <input type="checkbox" checked={bloquea} disabled={ocupado} onChange={(e) => alternarBloqueo(e.target.checked)} />
            <span>
              Bloquear también sus cobros con tarjeta
              <small>
                Según lo que permita tu banco emisor; no vale para recibos domiciliados. Bloquear no cancela el contrato:
                el comercio podría reclamarte lo que debas.
              </small>
            </span>
          </label>
        </>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="tarjeta-botones">
        <button type="button" className="boton-principal grande" onClick={confirmar} disabled={ocupado}>
          Confirmar
        </button>
        <button
          type="button"
          className="boton-secundario grande"
          disabled={ocupado}
          onClick={() => {
            setDescartada(true);
            alAhoraNo?.();
          }}
        >
          Ahora no
        </button>
      </div>
    </section>
  );
}
