"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import InsigniaIA from "./InsigniaIA";

export type AvisoToast = { clave: string; titulo: string; mensaje: string; propuestaId: string | null; total: number };

const DURACION_MS = 12000;

// Aviso emergente dentro de la app. Se cierra solo a los 12 s, salvo que el ratón o el foco estén encima; Escape lo cierra.
export default function ToastAviso({ toast, alCerrar }: { toast: AvisoToast; alCerrar: () => void }) {
  const [quieto, setQuieto] = useState(false);

  useEffect(() => {
    if (quieto) return;
    const t = window.setTimeout(alCerrar, DURACION_MS);
    return () => window.clearTimeout(t);
  }, [quieto, alCerrar]);

  return (
    <div
      className="toast-aviso"
      role="group"
      aria-label="Aviso nuevo de Meisam"
      onMouseEnter={() => setQuieto(true)}
      onMouseLeave={() => setQuieto(false)}
      onFocus={() => setQuieto(true)}
      onBlur={() => setQuieto(false)}
      onKeyDown={(e) => e.key === "Escape" && alCerrar()}
    >
      <div className="toast-cab">
        <span className="aviso-marca">
          Meisam <InsigniaIA />
        </span>
        <button type="button" className="toast-cerrar" aria-label="Cerrar el aviso" onClick={alCerrar}>
          <span aria-hidden="true">×</span>
        </button>
      </div>
      <p className="toast-titulo">{toast.titulo}</p>
      <p className="toast-mensaje">{toast.mensaje}</p>
      <div className="toast-botones">
        {toast.propuestaId && (
          <Link href={`/app/llamada/${encodeURIComponent(toast.propuestaId)}`} className="enlace-boton" onClick={alCerrar}>
            Resolver
          </Link>
        )}
        <Link href="/app/notificaciones" className="enlace-boton secundario" onClick={alCerrar}>
          {toast.total > 1 ? "Ver los avisos" : "Ver avisos"}
        </Link>
      </div>
    </div>
  );
}
