"use client";

import { useEffect, useRef, useState } from "react";
import { confirmarAccion, deshacerAccion, prepararAccion, prepararAccionEditada } from "@/lib/api";
import type { AccionId, ResultadoAccion, TarjetaConfirmacion } from "@/lib/api";
import { centimos, importeDeTexto, textoVisible } from "@/lib/formato";
import DetalleBaja from "./DetalleBaja";

// Reglas de Bizum para una solicitud (docs/diseno/deudas-casos.md): de 0,50 a 1.000 €. El concepto, 60 como en el servidor.
const IMPORTE_MIN = 50;
const IMPORTE_MAX = 100000;
const CONCEPTO_MAX = 60;

const coma = (importe: string) => importe.replace(".", ",");

function validar(importeTxt: string, concepto: string): { importe?: string; concepto?: string; valor?: string } {
  const errores: { importe?: string; concepto?: string; valor?: string } = {};
  const importe = importeDeTexto(importeTxt);
  if (importe === null) errores.importe = "Escribe un importe válido, por ejemplo 12,50.";
  else if (centimos(importe) < IMPORTE_MIN || centimos(importe) > IMPORTE_MAX) errores.importe = "Bizum admite solicitudes de 0,50 a 1.000 €.";
  else errores.valor = importe;
  if (!concepto.trim()) errores.concepto = "Escribe un concepto.";
  else if (concepto.trim().length > CONCEPTO_MAX) errores.concepto = `El concepto admite hasta ${CONCEPTO_MAX} caracteres.`;
  return errores;
}

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
  const [editando, setEditando] = useState(false);
  const [importeTxt, setImporteTxt] = useState("");
  const [conceptoTxt, setConceptoTxt] = useState("");
  const [parametros, setParametros] = useState<Record<string, unknown>>(parametrosBase ?? {});

  useEffect(() => setTarjeta(inicial), [inicial]);
  useEffect(() => titulo.current?.focus(), []);

  const esBaja = tarjeta.accion_id === "cancelar_suscripcion";
  const esBizum = tarjeta.accion_id === "pedir_bizum";
  const errores = editando ? validar(importeTxt, conceptoTxt) : {};
  const hayErrores = Boolean(errores.importe || errores.concepto);
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

  function abrirEdicion() {
    const legible = importeDeTexto(tarjeta.parametros_legibles["Importe"] ?? "");
    const actual = typeof parametros.importe === "string" ? importeDeTexto(parametros.importe) : null;
    setImporteTxt(coma(legible ?? actual ?? ""));
    const concepto = tarjeta.parametros_legibles["Concepto"] ?? (typeof parametros.concepto === "string" ? parametros.concepto : "");
    setConceptoTxt(textoVisible(concepto));
    setError(null);
    setEditando(true);
  }

  // Se vuelve a preparar con lo editado; si el servidor lo rechaza, la tarjeta anterior sigue intacta.
  const aplicarCambios = () =>
    ejecutar(async () => {
      if (hayErrores || !errores.valor) return;
      const cambios = { importe: errores.valor, concepto: conceptoTxt.trim() };
      const nueva = await prepararAccionEditada(usuarioId, tarjeta.propuesta_id, tarjeta.accion_id as AccionId, parametros, cambios);
      setParametros({ ...parametros, ...cambios });
      setTarjeta(nueva);
      alCambiarTarjeta?.(nueva);
      setEditando(false);
    });

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

      {esBizum && !editando && (
        <button type="button" className="boton-texto" onClick={abrirEdicion} disabled={ocupado}>
          Cambiar importe o concepto
        </button>
      )}
      {esBizum && editando && (
        <form
          className="edicion-tarjeta"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void aplicarCambios();
          }}
        >
          <div className="campo-etiquetado">
            <label htmlFor={`importe-${tarjeta.propuesta_id}`}>Importe (euros)</label>
            <input
              id={`importe-${tarjeta.propuesta_id}`}
              className="campo"
              inputMode="decimal"
              autoComplete="off"
              value={importeTxt}
              onChange={(e) => setImporteTxt(e.target.value)}
              aria-invalid={Boolean(errores.importe)}
              aria-describedby={`importe-ayuda-${tarjeta.propuesta_id}`}
            />
            <small id={`importe-ayuda-${tarjeta.propuesta_id}`} className={errores.importe ? "error" : "tenue"}>
              {errores.importe ?? "Entre 0,50 y 1.000 €."}
            </small>
          </div>
          <div className="campo-etiquetado">
            <label htmlFor={`concepto-${tarjeta.propuesta_id}`}>Concepto</label>
            <input
              id={`concepto-${tarjeta.propuesta_id}`}
              className="campo"
              maxLength={CONCEPTO_MAX}
              autoComplete="off"
              value={conceptoTxt}
              onChange={(e) => setConceptoTxt(e.target.value)}
              aria-invalid={Boolean(errores.concepto)}
              aria-describedby={`concepto-ayuda-${tarjeta.propuesta_id}`}
            />
            <small id={`concepto-ayuda-${tarjeta.propuesta_id}`} className={errores.concepto ? "error" : "tenue"}>
              {errores.concepto ?? `${conceptoTxt.length} de ${CONCEPTO_MAX} caracteres.`}
            </small>
          </div>
          <div className="tarjeta-botones">
            <button type="submit" className="boton-secundario grande" disabled={ocupado || hayErrores}>
              Aplicar cambios
            </button>
            <button type="button" className="boton-secundario grande" disabled={ocupado} onClick={() => setEditando(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="tarjeta-botones">
        <button type="button" className="boton-principal grande" onClick={confirmar} disabled={ocupado || editando}>
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
      {editando && <p className="pequeno tenue">Aplica los cambios para poder confirmar.</p>}
    </section>
  );
}
