"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { reproducir } from "@/lib/api";
import type { EventoReloj } from "@/lib/api";
import { fechaLarga } from "@/lib/formato";

const MS_POR_DIA = 1500;
const PAUSAR_EN = "gasto_compartido";

// Reproduce los días con el SSE de /reloj/reproducir, un día por petición: así «Pausa» detiene el reloj de verdad
// (si cortáramos un flujo largo, el servidor seguiría avanzando). Se para solo con el aviso de la cena.
export default function RelojDemo({
  usuarioId,
  hoy,
  deshabilitado,
  alEvento,
  alParar,
  alAvanzarUno,
}: {
  usuarioId: string;
  hoy: string | null;
  deshabilitado: boolean;
  alEvento: (e: EventoReloj) => void;
  alParar: () => void;
  alAvanzarUno: () => void;
}) {
  const [reproduciendo, setReproduciendo] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const activo = useRef(false);
  const control = useRef<AbortController | null>(null);
  const cb = useRef({ alEvento, alParar });
  cb.current = { alEvento, alParar };

  const parar = useCallback((texto?: string) => {
    activo.current = false;
    control.current?.abort();
    setReproduciendo(false);
    if (texto) setMensaje(texto);
    cb.current.alParar();
  }, []);

  useEffect(
    () => () => {
      activo.current = false;
      control.current?.abort();
    },
    [],
  );

  async function iniciar() {
    if (activo.current) return;
    activo.current = true;
    setReproduciendo(true);
    setMensaje(null);
    try {
      while (activo.current) {
        let pausado = false;
        control.current = new AbortController();
        await reproducir({
          usuarioId,
          dias: 1,
          msPorDia: 0,
          pausarEn: PAUSAR_EN,
          senal: control.current.signal,
          alEvento: (e) => {
            if (e.tipo === "fin") pausado = !!e.datos.pausado;
            if (e.tipo === "error") throw new Error(e.datos.mensaje);
            cb.current.alEvento(e);
          },
        });
        if (pausado) return parar("Reloj parado: ha llegado un aviso de Meisam.");
        await new Promise((r) => setTimeout(r, MS_POR_DIA));
      }
    } catch (fallo) {
      if (activo.current) parar(fallo instanceof Error ? fallo.message : String(fallo));
    }
  }

  return (
    <div className="reloj-demo">
      <p className="reloj-fecha" aria-live="polite">
        <span className="tenue pequeno">Fecha simulada</span>
        <strong>{hoy ? fechaLarga(hoy) : "—"}</strong>
      </p>
      <div className="reloj-botones">
        {reproduciendo ? (
          <button type="button" className="boton-principal" onClick={() => parar()} aria-label="Pausar el reloj">
            ⏸ Pausa
          </button>
        ) : (
          <button type="button" className="boton-principal" onClick={iniciar} disabled={deshabilitado} aria-label="Reproducir los días">
            ▶ Reproducir
          </button>
        )}
        <button type="button" className="boton-secundario" onClick={alAvanzarUno} disabled={deshabilitado || reproduciendo}>
          Avanzar un día
        </button>
      </div>
      {mensaje && (
        <p className="pequeno" role="status">
          {mensaje}
        </p>
      )}
    </div>
  );
}
