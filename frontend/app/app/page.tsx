"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import Activacion from "@/components/Activacion";
import Bandeja from "@/components/Bandeja";
import InsigniaIA from "@/components/InsigniaIA";
import RelojDemo from "@/components/RelojDemo";
import { activar, avanzarReloj, cargarDemo, estadoUsuario, notificaciones } from "@/lib/api";
import type { EstadoUsuario, EventoReloj, Notificacion } from "@/lib/api";
import { eur } from "@/lib/formato";

const ESCENARIO = "cena-lucia";

export default function PantallaCliente() {
  const [usuarioId, setUsuarioId] = useState<string | null>(null);
  const [hoy, setHoy] = useState<string | null>(null);
  const [saldo, setSaldo] = useState<string | null>(null);
  const [estado, setEstado] = useState<EstadoUsuario | null>(null);
  const [ahora, setAhora] = useState<Notificacion[]>([]);
  const [resumen, setResumen] = useState<Notificacion[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refrescar = useCallback(async (id: string) => {
    const [e, a, r] = await Promise.all([estadoUsuario(id), notificaciones(id, "ahora"), notificaciones(id, "resumen")]);
    setEstado(e);
    setHoy(e.hoy);
    setSaldo(e.saldo);
    setAhora(a);
    setResumen(r);
  }, []);

  async function ejecutar(tarea: () => Promise<void>) {
    setOcupado(true);
    setError(null);
    try {
      await tarea();
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : String(fallo));
    } finally {
      setOcupado(false);
    }
  }

  const activarMeisam = (modulos: string[]) =>
    ejecutar(async () => {
      const demo = await cargarDemo(ESCENARIO);
      await activar(demo.usuario_id, modulos, { copiloto: true, memoria: true });
      setUsuarioId(demo.usuario_id);
      await refrescar(demo.usuario_id);
    });

  const avanzar = () =>
    ejecutar(async () => {
      if (!usuarioId) return;
      await avanzarReloj(usuarioId, 1);
      await refrescar(usuarioId);
    });

  const reiniciar = () => {
    setUsuarioId(null);
    setEstado(null);
    setHoy(null);
    setSaldo(null);
    setAhora([]);
    setResumen([]);
  };

  const alEventoReloj = (e: EventoReloj) => {
    if (e.tipo === "dia") {
      setHoy(e.datos.fecha);
      if (e.datos.saldo !== null) setSaldo(e.datos.saldo);
    } else if (e.tipo === "decision" && usuarioId) {
      void refrescar(usuarioId).catch(() => undefined);
    }
  };
  const alPararReloj = () => {
    if (usuarioId) void refrescar(usuarioId).catch(() => undefined);
  };

  const c = estado?.contadores;
  const contadas = c ? c.ahora + c.resumen : 0;

  return (
    <div className="movil">
      <header className="banco-cab">
        <div>
          <p className="banco-nombre">Banco Aurora</p>
          <p className="banco-saludo">{usuarioId ? "Hola, Lucía" : "Tu app del banco"}</p>
        </div>
        <Link href="/" className="banco-salir">
          Inicio
        </Link>
      </header>

      {error && (
        <p className="error banda" role="alert">
          {error}
        </p>
      )}

      {!usuarioId ? (
        <Activacion ocupado={ocupado} alActivar={activarMeisam} />
      ) : (
        <>
          <section className="saldo" aria-label="Cuenta">
            <p className="tenue pequeno">Cuenta corriente</p>
            <p className="saldo-importe">{eur(saldo)}</p>
          </section>

          <RelojDemo
            usuarioId={usuarioId}
            hoy={hoy}
            deshabilitado={ocupado}
            alEvento={alEventoReloj}
            alParar={alPararReloj}
            alAvanzarUno={avanzar}
          />

          {c && c.momentos > 0 && (
            <p className="silenciadas" role="status">
              Han pasado {c.momentos} {c.momentos === 1 ? "cosa" : "cosas"}. Solo{" "}
              {contadas === 1 ? "ha contado una" : `han contado ${contadas}`}
              {c.silenciadas > 0 && ` (${c.silenciadas} silenciadas por no compensar)`}.
            </p>
          )}

          <Bandeja ahora={ahora} resumen={resumen} />

          <button type="button" className="boton-secundario" onClick={reiniciar}>
            Reiniciar escenario
          </button>
        </>
      )}

      <footer className="aviso-ia-fijo">
        <InsigniaIA texto="IA" />
        <span>
          Meisam es un asistente de inteligencia artificial. La información es orientativa y no es asesoramiento
          financiero. Datos sintéticos.
        </span>
      </footer>
    </div>
  );
}
