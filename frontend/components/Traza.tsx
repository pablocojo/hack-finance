import type { Final } from "@/lib/api";
import { nombreHerramienta } from "@/lib/formato";

// Muestra cómo ha razonado el agente en la última respuesta: llamadas a Claude y herramientas.
export default function Traza({ final }: { final: Final | null }) {
  if (!final) {
    return (
      <section className="tarjeta">
        <h2>Cómo lo ha calculado</h2>
        <p className="tenue">Aquí verás qué herramientas ha usado el asistente en cada respuesta.</p>
      </section>
    );
  }
  const pasos = final.trazas.filter((t) => t.tipo === "herramienta" || t.tipo === "llamada" || t.tipo === "revision");
  return (
    <section className="tarjeta" aria-label="Traza de la última respuesta">
      <h2>Cómo lo ha calculado</h2>
      <p className="tenue pequeno">
        {final.modelo} · {final.vueltas} paso(s) · {final.coste_usd.toFixed(4)} $ esta respuesta ·{" "}
        {final.coste_sesion_usd.toFixed(4)} $ la sesión
      </p>
      <ol className="traza">
        {pasos.map((paso, i) => (
          <li key={i} className={paso.error ? "con-error" : undefined}>
            {paso.tipo === "herramienta" && (
              <>
                <strong>{nombreHerramienta(paso.nombre ?? "")}</strong>
                <code>{JSON.stringify(paso.entrada ?? {})}</code>
                <span className="tenue">{paso.ms} ms{paso.error ? " · error, Claude lo corrige" : ""}</span>
              </>
            )}
            {paso.tipo === "llamada" && (
              <span className="tenue">
                Claude ({paso.modelo}) · {paso.tokens?.entrada ?? 0} tokens de entrada,{" "}
                {paso.tokens?.cache_lectura ?? 0} desde caché · {paso.ms} ms
              </span>
            )}
            {paso.tipo === "revision" && (
              <span className="tenue">
                Control de cumplimiento: {paso.aprobada === false ? "corregida" : "aprobada"}
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
