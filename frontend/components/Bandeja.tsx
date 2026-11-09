"use client";

import { useState } from "react";
import type { Notificacion } from "@/lib/api";
import { eur } from "@/lib/formato";
import InsigniaIA from "./InsigniaIA";

type Pestana = "ahora" | "resumen";

const URGENCIA: Record<string, string> = { alta: "Urgente", media: "Importante", baja: "Sin prisa" };

export default function Bandeja({ ahora, resumen }: { ahora: Notificacion[]; resumen: Notificacion[] }) {
  const [pestana, setPestana] = useState<Pestana>("ahora");
  const lista = pestana === "ahora" ? ahora : resumen;

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
        {lista.map(({ propuesta, decision, estado }) => (
          <article key={propuesta.id} className={`aviso-tarjeta urgencia-${propuesta.urgencia}`}>
            <header className="aviso-cab">
              <span className="aviso-marca">
                Meisam <InsigniaIA />
              </span>
              <span className={`urgencia urgencia-${propuesta.urgencia}`}>{URGENCIA[propuesta.urgencia]}</span>
            </header>
            <h3>{propuesta.titulo}</h3>
            <p className="aviso-mensaje">{propuesta.mensaje_notificacion}</p>
            {propuesta.valor_estimado_eur && (
              <p className="aviso-valor">
                <strong>{eur(propuesta.valor_estimado_eur)}</strong>
                <span> en juego</span>
              </p>
            )}
            {propuesta.contexto_personal && <p className="aviso-contexto">{propuesta.contexto_personal}</p>}
            {decision.motivos[0] && <p className="aviso-motivo">Por qué te aviso: {decision.motivos[0]}</p>}
            {estado !== "nueva" && <p className="pequeno tenue">Estado: {estado}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}
