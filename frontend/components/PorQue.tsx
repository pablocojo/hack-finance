"use client";

import { useId, useState } from "react";
import { detallePropuesta, enviarFeedback } from "@/lib/api";
import type { DetallePropuesta, ResultadoFeedback } from "@/lib/api";
import { nombreVisible, textoVisible } from "@/lib/formato";

type Props = { usuarioId: string; propuestaId: string };
type Opcion = { resultado: ResultadoFeedback; texto: string };

// «Por qué te aviso»: la explicación del momento, el contexto personal y los motivos de la decisión del portero,
// con botones para corregir a Meisam. Se carga al abrirlo (la consulta marca el aviso como visto).
export default function PorQue({ usuarioId, propuestaId }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [detalle, setDetalle] = useState<DetallePropuesta | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [respuesta, setRespuesta] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const idPanel = useId();

  async function alternar() {
    const siguiente = !abierto;
    setAbierto(siguiente);
    if (!siguiente || detalle || cargando) return;
    setCargando(true);
    setError(null);
    try {
      setDetalle(await detallePropuesta(usuarioId, propuestaId));
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setCargando(false);
    }
  }

  async function dar(opcion: Opcion) {
    setEnviando(true);
    setError(null);
    try {
      const r = await enviarFeedback({ usuarioId, propuestaId, resultado: opcion.resultado, canal: "app" });
      const nuevos = r.hechos_nuevos.map((h) => textoVisible(h.texto));
      setRespuesta(
        nuevos.length > 0
          ? `Anotado. Meisam ha aprendido: ${nuevos.join(" ")} Lo ves y lo borras en «Lo que he aprendido».`
          : "Anotado. Gracias, Meisam lo tendrá en cuenta.",
      );
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setEnviando(false);
    }
  }

  const p = detalle?.propuesta;
  const opciones: Opcion[] = [{ resultado: "falso_positivo", texto: "No era esto" }];
  if (p) {
    opciones.push({ resultado: "no_avisar_tipo", texto: "No me avises de este tipo de cosas" });
    if (p.comercio) opciones.push({ resultado: "no_avisar_comercio", texto: `No me avises de ${nombreVisible(p.comercio)}` });
    if (p.contraparte) opciones.push({ resultado: "no_avisar_contacto", texto: `No me avises sobre ${nombreVisible(p.contraparte)}` });
  }

  return (
    <div className="porque">
      <button type="button" className="boton-texto" aria-expanded={abierto} aria-controls={idPanel} onClick={alternar}>
        {abierto ? "Ocultar los motivos" : "Ver todos los motivos"}
      </button>
      {abierto && (
        <div id={idPanel} className="porque-panel">
          {cargando && <p className="tenue pequeno" role="status">Cargando…</p>}
          {detalle && (
            <>
              <p>{textoVisible(detalle.momento.explicacion)}</p>
              {(p?.contexto_personal ?? detalle.momento.contexto_personal) && (
                <p className="aviso-contexto">{textoVisible(p?.contexto_personal ?? detalle.momento.contexto_personal)}</p>
              )}
              {detalle.decision.motivos.length > 0 && (
                <>
                  <h4>Por qué sí te lo cuento ahora</h4>
                  <ul>
                    {detalle.decision.motivos.map((m, i) => (
                      <li key={i}>{textoVisible(m)}</li>
                    ))}
                  </ul>
                </>
              )}
              <p className="pequeno tenue">
                Confianza de la detección: {Math.round(detalle.momento.confianza * 100)} %.
              </p>
              {respuesta ? (
                <p className="porque-gracias" role="status">{respuesta}</p>
              ) : (
                <div className="porque-feedback" role="group" aria-label="Corregir a Meisam">
                  {opciones.map((o) => (
                    <button key={o.resultado} type="button" className="chip" disabled={enviando} onClick={() => dar(o)}>
                      {o.texto}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
          {error && <p className="error" role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}
