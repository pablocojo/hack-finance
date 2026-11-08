"use client";

import { useState } from "react";
import type { ChangeEvent } from "react";
import { cargarEjemplo, subirCsv } from "@/lib/api";
import type { DatosSesion } from "@/lib/api";

type Props = {
  sesionId: string | null;
  perfiles: Record<string, string>;
  datos: DatosSesion | null;
  alCargar: (datos: DatosSesion) => void;
};

const NOMBRES: Record<string, string> = { estudiante: "Estudiante", familia: "Familia", autonomo: "Autónomo" };

export default function SelectorDatos({ sesionId, perfiles, datos, alCargar }: Props) {
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ejecutar(tarea: () => Promise<DatosSesion>) {
    setCargando(true);
    setError(null);
    try {
      alCargar(await tarea());
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setCargando(false);
    }
  }

  function alElegirCsv(evento: ChangeEvent<HTMLInputElement>) {
    const archivo = evento.target.files?.[0];
    evento.target.value = "";
    if (archivo) void ejecutar(() => subirCsv(archivo, sesionId));
  }

  return (
    <section className="tarjeta" aria-label="Datos">
      <h2>Datos</h2>
      <div className="perfiles">
        {Object.entries(perfiles).map(([clave, descripcion]) => (
          <button key={clave} type="button" className="chip" title={descripcion} disabled={cargando}
            onClick={() => void ejecutar(() => cargarEjemplo(clave, sesionId))}>
            {NOMBRES[clave] ?? clave}
          </button>
        ))}
        <label className="chip">
          <input type="file" accept=".csv,text/csv" onChange={alElegirCsv} hidden />
          Subir CSV del banco
        </label>
      </div>
      {datos && (
        <p className="tenue pequeno">
          {datos.movimientos} movimientos{datos.desde ? ` del ${datos.desde} al ${datos.hasta}` : ""} · {datos.origen}
        </p>
      )}
      {datos?.informe && datos.informe.datos_personales_ocultados > 0 && (
        <p className="aviso-pequeno">Se han ocultado {datos.informe.datos_personales_ocultados} datos personales del CSV.</p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
