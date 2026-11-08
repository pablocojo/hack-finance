"use client";

import { useEffect, useState } from "react";
import { resumen as pedirResumen } from "@/lib/api";
import type { Resumen } from "@/lib/api";
import { eur, mesCorto, nombreCategoria, pct } from "@/lib/formato";

type Props = { sesionId: string | null; version: number };

export default function PanelGastos({ sesionId, version }: Props) {
  const [datos, setDatos] = useState<Resumen | null>(null);
  const [meses, setMeses] = useState(3);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sesionId) {
      setDatos(null);
      return;
    }
    let vigente = true;
    pedirResumen(sesionId, meses)
      .then((respuesta) => {
        if (vigente) {
          setDatos(respuesta);
          setError(null);
        }
      })
      .catch((fallo: unknown) => {
        if (vigente) setError(fallo instanceof Error ? fallo.message : String(fallo));
      });
    return () => {
      vigente = false;
    };
  }, [sesionId, meses, version]);

  if (error) return <section className="tarjeta"><p className="error">{error}</p></section>;
  if (!datos || datos.vacio) {
    return (
      <section className="tarjeta">
        <h2>Tus gastos</h2>
        <p className="tenue">Carga datos de ejemplo o sube el CSV de tu banco para ver el resumen.</p>
      </section>
    );
  }

  const categorias = (datos.por_categoria ?? []).slice(0, 8);
  const maximo = Math.max(1, ...categorias.map((c) => c.importe));
  const porMes = datos.por_mes ?? [];
  const maximoMes = Math.max(1, ...porMes.map((m) => Math.max(m.ingresos, m.gastos)));

  return (
    <section className="tarjeta" aria-label="Resumen de gastos">
      <div className="cabecera-tarjeta">
        <h2>Tus gastos</h2>
        <select value={meses} onChange={(e) => setMeses(Number(e.target.value))} aria-label="Periodo">
          <option value={1}>Este mes</option>
          <option value={3}>3 meses</option>
          <option value={6}>6 meses</option>
        </select>
      </div>

      <div className="kpis">
        <div className="kpi"><span>Ingresos</span><strong>{eur(datos.ingresos)}</strong></div>
        <div className="kpi"><span>Gastos</span><strong>{eur(datos.gastos)}</strong></div>
        <div className="kpi">
          <span>Ahorro</span>
          <strong className={(datos.ahorro ?? 0) < 0 ? "negativo" : "positivo"}>{eur(datos.ahorro)}</strong>
        </div>
        <div className="kpi"><span>Tasa de ahorro</span><strong>{pct(datos.tasa_ahorro_pct)}</strong></div>
      </div>

      <h3>Por categoría</h3>
      <ul className="barras">
        {categorias.map((c) => (
          <li key={c.categoria}>
            <span className="barra-nombre">{nombreCategoria(c.categoria)}</span>
            <span className="barra-pista">
              <span className="barra" style={{ width: `${(100 * c.importe) / maximo}%` }} />
            </span>
            <span className="barra-valor">{eur(c.importe)}</span>
          </li>
        ))}
      </ul>

      {porMes.length > 1 && (
        <>
          <h3>Mes a mes</h3>
          <div className="meses" role="img" aria-label="Ingresos y gastos por mes">
            {porMes.map((m) => (
              <div key={m.mes} className="mes" title={`${mesCorto(m.mes)}: ingresos ${eur(m.ingresos)}, gastos ${eur(m.gastos)}`}>
                <div className="mes-barras">
                  <span className="mes-ingresos" style={{ height: `${(100 * m.ingresos) / maximoMes}%` }} />
                  <span className="mes-gastos" style={{ height: `${(100 * m.gastos) / maximoMes}%` }} />
                </div>
                <span className="mes-nombre">{mesCorto(m.mes)}</span>
              </div>
            ))}
          </div>
          <p className="leyenda">
            <span className="punto ingresos" /> Ingresos <span className="punto gastos" /> Gastos
          </p>
        </>
      )}
      {datos.nota && <p className="tenue pequeno">{datos.nota}</p>}
    </section>
  );
}
