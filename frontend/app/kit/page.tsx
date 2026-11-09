"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Chat from "@/components/Chat";
import PanelGastos from "@/components/PanelGastos";
import SelectorDatos from "@/components/SelectorDatos";
import Traza from "@/components/Traza";
import { cargarEjemplo, salud } from "@/lib/api";
import type { DatosSesion, Final, Salud } from "@/lib/api";

const PERFIL_INICIAL = "familia";

export default function Kit() {
  const [estado, setEstado] = useState<Salud | null>(null);
  const [errorConexion, setErrorConexion] = useState<string | null>(null);
  const [sesionId, setSesionId] = useState<string | null>(null);
  const [datos, setDatos] = useState<DatosSesion | null>(null);
  const [version, setVersion] = useState(0);
  const [reinicio, setReinicio] = useState(0);
  const [ultima, setUltima] = useState<Final | null>(null);
  const iniciado = useRef(false);

  useEffect(() => {
    if (iniciado.current) return; // en desarrollo, React ejecuta los efectos dos veces
    iniciado.current = true;
    salud()
      .then(async (respuesta) => {
        setEstado(respuesta);
        const cargados = await cargarEjemplo(PERFIL_INICIAL);
        setSesionId(cargados.sesion_id);
        setDatos(cargados);
        setVersion((v) => v + 1);
      })
      .catch((fallo: unknown) => {
        setErrorConexion(fallo instanceof Error ? fallo.message : String(fallo));
      });
  }, []);

  function alCargar(nuevos: DatosSesion) {
    setSesionId(nuevos.sesion_id);
    setDatos(nuevos);
    setUltima(null);
    setVersion((v) => v + 1);
    setReinicio((r) => r + 1);
  }

  function alTerminar(final: Final) {
    setUltima(final);
    setVersion((v) => v + 1); // una herramienta puede haber cambiado categorías o el perfil
  }

  return (
    <div className="pagina">
      <header className="cabecera">
        <div>
          <h1>{estado?.producto ?? "Finanzas IA"}</h1>
          <p className="subtitulo"><Link href="/">Volver a la portada</Link></p>
          <p className="subtitulo">Tus gastos, tu ahorro y tus cálculos, con cifras exactas.</p>
        </div>
        <p className="insignia-ia">Asistente con IA · información orientativa, no es asesoramiento</p>
      </header>

      {errorConexion && (
        <p className="error banda">
          No hay conexión con el backend ({errorConexion}). Arráncalo con{" "}
          <code>uvicorn backend.api.main:app --reload</code> y recarga.
        </p>
      )}
      {estado?.aviso_configuracion && <p className="aviso banda">{estado.aviso_configuracion}</p>}

      <main className="rejilla">
        <Chat sesionId={sesionId} reinicio={reinicio} alCambiarSesion={setSesionId} alTerminar={alTerminar} />
        <aside className="lateral">
          <SelectorDatos sesionId={sesionId} perfiles={estado?.perfiles_ejemplo ?? {}} datos={datos} alCargar={alCargar} />
          <PanelGastos sesionId={sesionId} version={version} />
          <Traza final={ultima} />
        </aside>
      </main>

      <footer className="pie-pagina">
        {estado?.aviso_ia ??
          "Hablas con un asistente de inteligencia artificial. La información es orientativa y no constituye asesoramiento financiero."}{" "}
        Datos de ejemplo sintéticos; los datos personales se ocultan antes de enviarse a la IA.
      </footer>
    </div>
  );
}
