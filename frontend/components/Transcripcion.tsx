import type { ReactNode } from "react";
import Markdown from "./Markdown";

export type Turno = { id: string; rol: "meisam" | "usuario"; texto: string; enCurso?: boolean; error?: string };

// La transcripción es una región en vivo: los lectores de pantalla leen cada respuesta nueva de Meisam.
// Los hijos (p. ej. la tarjeta de acción) se pintan al final, dentro del hilo.
export default function Transcripcion({ turnos, hijos }: { turnos: Turno[]; hijos?: ReactNode }) {
  return (
    <div className="transcripcion" role="log" aria-live="polite" aria-relevant="additions text" aria-label="Transcripción de la llamada">
      {turnos.map((t) => (
        <div key={t.id} className={`turno turno-${t.rol}`}>
          <span className="turno-quien">{t.rol === "meisam" ? "Meisam" : "Tú"}</span>
          {t.rol === "meisam" ? (
            t.texto ? <Markdown texto={t.texto} /> : <p className="pensando">Pensando…</p>
          ) : (
            <p>{t.texto}</p>
          )}
          {t.error && (
            <p className="error" role="alert">
              {t.error}
            </p>
          )}
        </div>
      ))}
      {hijos}
    </div>
  );
}
