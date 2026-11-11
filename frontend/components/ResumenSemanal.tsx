import { fraseResumen } from "@/lib/preguntas";
import type { ResumenSemanal as Datos } from "@/lib/preguntas";
import InsigniaIA from "./InsigniaIA";

// «Te deben 85 € entre 3 personas · 1 pregunta pendiente · Marcos te pagó». Es una sección del Resumen, no una
// notificación. Las cifras las suma el código en céntimos (lib/preguntas.ts); aquí solo se pintan.
export default function ResumenSemanal({ datos }: { datos: Datos }) {
  const partes = fraseResumen(datos);
  if (partes.length === 0) return null;
  return (
    <section className="resumen-semanal" aria-label="Resumen de la semana">
      <header>
        <h3>Tu semana con amigos</h3>
        <InsigniaIA />
      </header>
      <ul>
        {partes.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </section>
  );
}
