"use client";

import { useId, useState } from "react";
import { rutaNoDisponible } from "@/lib/api";
import type { CasoResumen, DeudorCaso, ViaSaldado } from "@/lib/api";
import { deudorAbierto, VIA_SALDADO } from "@/lib/cuentas";
import { descartarCaso, saldarCaso } from "@/lib/cuentasApi";

const MOTIVO_MAX = 60;
type Via = Exclude<ViaSaldado, "bizum">;
const VIAS: { via: Via; texto: string }[] = [
  { via: "efectivo", texto: "Me lo ha dado en efectivo" },
  { via: "invitacion", texto: "Me ha invitado a algo" },
  { via: "otro", texto: "Otro motivo" },
];

type Props = {
  usuarioId: string;
  caso: CasoResumen;
  deudor: DeudorCaso;
  nombre: string;
  alHecho: (mensaje: string) => void;
};

// «Marcar como saldado» y «No me debe» para un deudor. Cierran la cuenta sin insistir y nunca mueven dinero.
export default function AccionesDeudor({ usuarioId, caso, deudor, nombre, alHecho }: Props) {
  const id = useId();
  const [modo, setModo] = useState<"saldar" | "nodebe" | null>(null);
  const [via, setVia] = useState<Via>("efectivo");
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!deudorAbierto(deudor)) return null;

  // Si solo queda esta persona por pagar, «No me debe» cierra el caso entero; si hay más, solo su parte.
  const pendientes = caso.deudores.filter(deudorAbierto).length;

  async function ejecutar(tarea: () => Promise<unknown>, hecho: string) {
    setOcupado(true);
    setError(null);
    try {
      await tarea();
      alHecho(hecho);
      setModo(null);
    } catch (fallo) {
      setError(rutaNoDisponible(fallo) ? "Esta función todavía no está disponible en el servidor." : fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setOcupado(false);
    }
  }

  const saldar = () =>
    ejecutar(
      () => saldarCaso(usuarioId, caso.id, via, deudor.contraparte, motivo.trim() || undefined),
      `Hecho. La cuenta con ${nombre} queda saldada ${VIA_SALDADO[via]}. Meisam ya no te la recordará.`,
    );
  const noMeDebe = () =>
    ejecutar(
      () =>
        pendientes <= 1
          ? descartarCaso(usuarioId, caso.id, "No me debe")
          : saldarCaso(usuarioId, caso.id, "otro", deudor.contraparte, "No me debe nada"),
      `Hecho. ${nombre} ya no figura como pendiente en esta cuenta. Meisam no se lo recordará.`,
    );

  if (modo === null) {
    return (
      <div className="fila-botones">
        <button type="button" className="boton-secundario" onClick={() => setModo("saldar")}>
          Marcar como saldado<span className="solo-lectores">: {nombre}</span>
        </button>
        <button type="button" className="boton-texto" onClick={() => setModo("nodebe")}>
          No me debe<span className="solo-lectores">: {nombre}</span>
        </button>
      </div>
    );
  }

  return (
    <div className="formulario-inline" role="group" aria-label={modo === "saldar" ? `Marcar como saldado: ${nombre}` : `No me debe: ${nombre}`}>
      {modo === "saldar" ? (
        <>
          <fieldset className="opciones-radio">
            <legend>¿Cómo se ha saldado con {nombre}?</legend>
            {VIAS.map((o) => (
              <label key={o.via} className="opcion-radio">
                <input type="radio" name={`${id}-via`} checked={via === o.via} onChange={() => setVia(o.via)} />
                <span>{o.texto}</span>
              </label>
            ))}
          </fieldset>
          {via === "otro" && (
            <div className="campo-etiquetado">
              <label htmlFor={`${id}-motivo`}>Cuéntalo en pocas palabras (opcional)</label>
              <input
                id={`${id}-motivo`}
                className="campo"
                maxLength={MOTIVO_MAX}
                autoComplete="off"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
              />
              <small className="tenue">{motivo.length} de {MOTIVO_MAX} caracteres. Meisam lo guarda como una nota tuya.</small>
            </div>
          )}
          <p className="pequeno tenue">Meisam lo anota y no insiste más. No se mueve dinero.</p>
          <div className="fila-botones">
            <button type="button" className="boton-principal" disabled={ocupado} onClick={saldar}>
              {ocupado ? "Guardando…" : "Confirmar"}
            </button>
            <button type="button" className="boton-secundario" disabled={ocupado} onClick={() => setModo(null)}>
              Volver
            </button>
          </div>
        </>
      ) : (
        <>
          <p role="alert">
            ¿Cerramos esta cuenta con {nombre}? {pendientes <= 1 ? "Meisam cerrará el caso y no volverá a recordarlo." : "Solo se cierra su parte; el resto del gasto sigue abierto."}
          </p>
          <div className="fila-botones">
            <button type="button" className="boton-principal" disabled={ocupado} onClick={noMeDebe}>
              {ocupado ? "Guardando…" : "Sí, cerrar"}
            </button>
            <button type="button" className="boton-secundario" disabled={ocupado} onClick={() => setModo(null)}>
              Volver
            </button>
          </div>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
