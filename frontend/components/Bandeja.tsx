"use client";

import Link from "next/link";
import { useState } from "react";
import { prepararAccion } from "@/lib/api";
import type { Notificacion, TarjetaConfirmacion } from "@/lib/api";
import { eur, textoVisible } from "@/lib/formato";
import InsigniaIA from "./InsigniaIA";
import TarjetaAccion from "./TarjetaAccion";

type Pestana = "ahora" | "resumen";
type Props = { usuarioId: string; ahora: Notificacion[]; resumen: Notificacion[]; alResolver?: () => void };

const URGENCIA: Record<string, string> = { alta: "Urgente", media: "Importante", baja: "Sin prisa" };

function sin<T>(registro: Record<string, T>, clave: string): Record<string, T> {
  const copia = { ...registro };
  delete copia[clave];
  return copia;
}

export default function Bandeja({ usuarioId, ahora, resumen, alResolver }: Props) {
  const [pestana, setPestana] = useState<Pestana>("ahora");
  const [tarjetas, setTarjetas] = useState<Record<string, TarjetaConfirmacion>>({});
  const [preparando, setPreparando] = useState<string | null>(null);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const lista = pestana === "ahora" ? ahora : resumen;

  // Acceso rápido: sin llamada, prepara la primera acción ofrecida y pinta la misma tarjeta de confirmación.
  async function accesoRapido({ propuesta }: Notificacion) {
    const accion = propuesta.acciones_ofrecidas[0];
    if (!accion) return;
    setPreparando(propuesta.id);
    setErrores((e) => sin(e, propuesta.id));
    try {
      const t = await prepararAccion(usuarioId, propuesta.id, accion.accion_id, accion.parametros);
      setTarjetas((ts) => ({ ...ts, [propuesta.id]: t }));
    } catch (fallo) {
      const mensaje = fallo instanceof Error ? fallo.message : String(fallo);
      setErrores((e) => ({ ...e, [propuesta.id]: mensaje }));
    } finally {
      setPreparando(null);
    }
  }

  return (
    <section className="bandeja" aria-label="Avisos de Meisam">
      <div className="pestanas" role="tablist" aria-label="Bandeja">
        {(["ahora", "resumen"] as const).map((p) => (
          <button
            key={p}
            role="tab"
            id={`pestana-${p}`}
            aria-selected={pestana === p}
            aria-controls="panel-bandeja"
            className={`pestana${pestana === p ? " activa" : ""}`}
            onClick={() => setPestana(p)}
          >
            {p === "ahora" ? "Ahora" : "Resumen"}
            <span className="contador">{(p === "ahora" ? ahora : resumen).length}</span>
          </button>
        ))}
      </div>

      <div id="panel-bandeja" role="tabpanel" aria-live="polite" aria-labelledby={`pestana-${pestana}`} className="lista-avisos">
        {lista.length === 0 && (
          <p className="vacio-bandeja">
            {pestana === "ahora"
              ? "Nada que resolver ahora. Meisam solo te avisa cuando ahorra o protege."
              : "Todavía no hay nada en el resumen."}
          </p>
        )}
        {lista.map((notificacion) => {
          const { propuesta, decision, estado } = notificacion;
          const tarjeta = tarjetas[propuesta.id];
          const primera = propuesta.acciones_ofrecidas[0];
          return (
            <article key={propuesta.id} className={`aviso-tarjeta urgencia-${propuesta.urgencia}`}>
              <header className="aviso-cab">
                <span className="aviso-marca">
                  Meisam <InsigniaIA />
                </span>
                <span className={`urgencia urgencia-${propuesta.urgencia}`}>{URGENCIA[propuesta.urgencia]}</span>
              </header>
              <h3>{textoVisible(propuesta.titulo)}</h3>
              <p className="aviso-mensaje">{textoVisible(propuesta.mensaje_notificacion)}</p>
              {propuesta.valor_estimado_eur && (
                <p className="aviso-valor">
                  <strong>{eur(propuesta.valor_estimado_eur)}</strong>
                  <span> en juego</span>
                </p>
              )}
              {propuesta.contexto_personal && <p className="aviso-contexto">{textoVisible(propuesta.contexto_personal)}</p>}
              {decision.motivos[0] && <p className="aviso-motivo">Por qué te aviso: {textoVisible(decision.motivos[0])}</p>}
              {estado !== "nueva" && <p className="pequeno tenue">Estado: {estado}</p>}
              {tarjeta ? (
                <TarjetaAccion
                  tarjeta={tarjeta}
                  usuarioId={usuarioId}
                  parametrosBase={primera?.parametros}
                  alResultado={() => alResolver?.()}
                  alAhoraNo={() => setTarjetas((ts) => sin(ts, propuesta.id))}
                  alCambiarTarjeta={(t) => setTarjetas((ts) => ({ ...ts, [propuesta.id]: t }))}
                />
              ) : (
                <div className="aviso-botones">
                  <Link href={`/app/llamada/${encodeURIComponent(propuesta.id)}`} className="enlace-boton grande">
                    Resolver
                  </Link>
                  {primera && (
                    <button
                      type="button"
                      className="boton-secundario grande"
                      disabled={preparando === propuesta.id}
                      onClick={() => accesoRapido(notificacion)}
                    >
                      Hacerlo ya
                    </button>
                  )}
                </div>
              )}
              {errores[propuesta.id] && (
                <p className="error" role="alert">
                  {errores[propuesta.id]}
                </p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
