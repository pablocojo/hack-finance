import type { DetalleBaja as Detalle } from "@/lib/api";

// Baja guiada: el enlace solo se pinta si el backend dice que es un enlace comprobado (url_es_enlace).
// Si no, se muestra como texto y se avisa de que hay que comprobarlo en la web oficial.
export default function DetalleBaja({ detalle, comercio }: { detalle: Detalle; comercio: string }) {
  return (
    <div className="detalle-baja">
      <p className="detalle-titulo">Cómo darte de baja en {comercio}</p>
      {detalle.url_baja &&
        (detalle.url_es_enlace ? (
          <p>
            <a href={detalle.url_baja} target="_blank" rel="noopener noreferrer">
              Abrir la página de baja de {comercio}
            </a>
          </p>
        ) : (
          <p>
            Dirección orientativa: <code>{detalle.url_baja}</code>. Compruébalo en la web oficial.
          </p>
        ))}
      {!detalle.url_baja && <p>No tenemos la dirección de baja. Compruébalo en la web oficial de {comercio}.</p>}
      {detalle.pasos.length > 0 && (
        <ol>
          {detalle.pasos.map((paso, i) => (
            <li key={i}>{paso}</li>
          ))}
        </ol>
      )}
      <p className="pequeno tenue">
        La baja la confirmas tú en {comercio}. Fuente: {detalle.fuente}.
      </p>
    </div>
  );
}
