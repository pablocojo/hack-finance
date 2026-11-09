"use client";

import { useState } from "react";
import InsigniaIA from "./InsigniaIA";

export type ModuloActivable = { id: string; nombre: string; ejemplo: string; disponible: boolean };

// Módulos del MVP. `id` es el del catálogo del backend; «próximamente» no se puede marcar.
export const MODULOS_MVP: ModuloActivable[] = [
  { id: "cena_compartida", nombre: "Cena compartida", ejemplo: "«Pagaste 120 € de una cena para cinco y falta un Bizum de 24 €: te ayudamos a pedirlo.»", disponible: true },
  { id: "cobro_duplicado", nombre: "Cobro duplicado", ejemplo: "«Te han cobrado dos veces 9,99 € en el mismo comercio.»", disponible: true },
  { id: "fin_de_prueba", nombre: "Fin de prueba gratis", ejemplo: "«Tu prueba gratis de Streamflix acaba en 3 días; después te cobrará 9,99 € al mes.»", disponible: true },
  { id: "renovacion", nombre: "Renovación de suscripciones", ejemplo: "Te avisaremos antes de que se renueve una suscripción.", disponible: false },
];

export default function Activacion({
  ocupado,
  alActivar,
}: {
  ocupado: boolean;
  alActivar: (modulos: string[]) => void;
}) {
  const [marcados, setMarcados] = useState<string[]>(["cena_compartida", "cobro_duplicado", "fin_de_prueba"]);
  const [consentimiento, setConsentimiento] = useState(false);

  const alternar = (id: string) => setMarcados((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));
  const puede = consentimiento && marcados.length > 0 && !ocupado;

  return (
    <form
      className="activacion"
      aria-labelledby="act-titulo"
      onSubmit={(e) => {
        e.preventDefault();
        if (puede) alActivar(marcados);
      }}
    >
      <h2 id="act-titulo">
        Activa Meisam <InsigniaIA />
      </h2>
      <p>Meisam vigila tus movimientos y te avisa solo cuando hay algo que resolver.</p>

      <fieldset>
        <legend>Qué quieres que vigile</legend>
        {MODULOS_MVP.map((m) => (
          <label key={m.id} className={`modulo-opcion${m.disponible ? "" : " apagado"}`}>
            <input
              type="checkbox"
              checked={m.disponible && marcados.includes(m.id)}
              disabled={!m.disponible}
              onChange={() => alternar(m.id)}
            />
            <span>
              <strong>
                {m.nombre}
                {!m.disponible && <em className="pronto">próximamente</em>}
              </strong>
              <small>{m.ejemplo}</small>
            </span>
          </label>
        ))}
      </fieldset>

      <label className="modulo-opcion consentimiento">
        <input type="checkbox" checked={consentimiento} onChange={(e) => setConsentimiento(e.target.checked)} />
        <span>
          <strong>Acepto que Meisam analice mis movimientos</strong>
          <small>Solo para avisarme y aprender mis hábitos. Puedo ver, editar y borrar lo aprendido cuando quiera.</small>
        </span>
      </label>

      <button type="submit" className="boton-principal" disabled={!puede}>
        {ocupado ? "Activando…" : "Activar"}
      </button>
      {!consentimiento && <p className="pequeno tenue">Marca el consentimiento para poder activar.</p>}
    </form>
  );
}
