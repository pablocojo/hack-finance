"use client";

import { useState } from "react";
import { confirmarAccion, prepararAccion } from "@/lib/api";
import type { Notificacion } from "@/lib/api";
import { eur, nombreVisible } from "@/lib/formato";

type Ofrecida = Notificacion["propuesta"]["acciones_ofrecidas"][number];
type Resultado = { nombre: string; ok: boolean; mensaje: string };

// Un aviso con varias personas (el cine: Rodrigo y Marta) trae un `pedir_bizum` por persona. Marcas a quién y, con un
// solo botón, se prepara y se confirma una solicitud por persona, cada una con su token de un solo uso (simulado).
export default function SelectorPedir({
  usuarioId,
  notificacion,
  alHecho,
}: {
  usuarioId: string;
  notificacion: Notificacion;
  alHecho: () => void;
}) {
  const { propuesta } = notificacion;
  const pedidos = propuesta.acciones_ofrecidas.filter((a) => a.accion_id === "pedir_bizum");
  const clave = (a: Ofrecida) => String(a.parametros.contraparte ?? "");
  const [marcados, setMarcados] = useState<string[]>(pedidos.map(clave));
  const [enviando, setEnviando] = useState(false);
  const [resultados, setResultados] = useState<Resultado[] | null>(null);

  const elegidos = pedidos.filter((a) => marcados.includes(clave(a)));
  const totalCentimos = elegidos.reduce((s, a) => s + Math.round(Number(a.parametros.importe ?? 0) * 100), 0);
  const alternar = (c: string) => setMarcados((m) => (m.includes(c) ? m.filter((x) => x !== c) : [...m, c]));

  async function pedir() {
    setEnviando(true);
    const salida: Resultado[] = [];
    // Primero todas las tarjetas (tokens) y después las confirmaciones: así ninguna depende de cómo quede el aviso.
    const tarjetas = [];
    for (const a of elegidos) {
      const nombre = nombreVisible(clave(a));
      try {
        tarjetas.push({ nombre, tarjeta: await prepararAccion(usuarioId, propuesta.id, "pedir_bizum", a.parametros) });
      } catch (fallo) {
        salida.push({ nombre, ok: false, mensaje: fallo instanceof Error ? fallo.message : String(fallo) });
      }
    }
    for (const { nombre, tarjeta } of tarjetas) {
      try {
        const r = await confirmarAccion(usuarioId, tarjeta.token_confirmacion);
        salida.push({ nombre, ok: r.ok, mensaje: r.mensaje });
      } catch (fallo) {
        salida.push({ nombre, ok: false, mensaje: fallo instanceof Error ? fallo.message : String(fallo) });
      }
    }
    setResultados(salida);
    setEnviando(false);
  }

  if (resultados) {
    return (
      <div className="selector-pedir" role="status">
        {resultados.map((r) => (
          <p key={r.nombre} className={r.ok ? "selector-ok" : "error"}>
            {r.ok ? `✓ Bizum pedido a ${r.nombre}` : `${r.nombre}: ${r.mensaje}`}
          </p>
        ))}
        <p className="pequeno tenue">Simulado. Cuando paguen, Meisam cerrará el caso solo.</p>
        <button type="button" className="boton-secundario grande" onClick={alHecho}>
          Listo
        </button>
      </div>
    );
  }

  return (
    <fieldset className="selector-pedir">
      <legend>¿A quién le pides el Bizum?</legend>
      {pedidos.map((a) => (
        <label key={clave(a)} className="selector-persona">
          <input type="checkbox" checked={marcados.includes(clave(a))} onChange={() => alternar(clave(a))} />
          <span>
            {nombreVisible(clave(a))} · {eur(String(a.parametros.importe ?? ""))}
          </span>
        </label>
      ))}
      <button type="button" className="boton-principal grande" disabled={enviando || elegidos.length === 0} onClick={pedir}>
        {enviando
          ? "Pidiendo…"
          : elegidos.length === 0
            ? "Marca a alguien"
            : `Pedir Bizum a ${elegidos.length === 1 ? "1 persona" : `${elegidos.length} personas`} (${eur((totalCentimos / 100).toFixed(2))})`}
      </button>
      <p className="pequeno tenue">Simulado: se envía una solicitud de Bizum a cada persona marcada. No se mueve dinero hasta que pagan.</p>
    </fieldset>
  );
}
