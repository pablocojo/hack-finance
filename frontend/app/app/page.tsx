"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Activacion from "@/components/Activacion";
import Bandeja from "@/components/Bandeja";
import { useAvisos } from "@/components/AvisosProvider";
import Campana from "@/components/Campana";
import IconoMicro from "@/components/IconoMicro";
import InsigniaIA from "@/components/InsigniaIA";
import RelojDemo from "@/components/RelojDemo";
import { activar, avanzarReloj, cargarDemo, estadoUsuario, notificaciones } from "@/lib/api";
import type { EstadoUsuario, EventoReloj, Notificacion } from "@/lib/api";
import { eur } from "@/lib/formato";
import { CLAVE_USUARIO } from "@/lib/sesion";

// Demo de Pablo (2/11-15/11): el cine de Kinepolis y las pizzas notifican; la cena del viernes la apunta él.
const ESCENARIO = "demo-pablo";

export default function PantallaCliente() {
  const [usuarioId, setUsuarioId] = useState<string | null>(null);
  const [hoy, setHoy] = useState<string | null>(null);
  const [saldo, setSaldo] = useState<string | null>(null);
  const [estado, setEstado] = useState<EstadoUsuario | null>(null);
  const [ahora, setAhora] = useState<Notificacion[]>([]);
  const [resumen, setResumen] = useState<Notificacion[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // El proveedor de /app/layout.tsx sondea los avisos; aquí solo se le pide que mire ya cuando el reloj o la activación cambian algo.
  const { refrescar: refrescarAvisos } = useAvisos();

  const refrescar = useCallback(async (id: string) => {
    const [e, a, r] = await Promise.all([estadoUsuario(id), notificaciones(id, "ahora"), notificaciones(id, "resumen")]);
    setEstado(e);
    setHoy(e.hoy);
    setSaldo(e.saldo);
    setAhora(a);
    setResumen(r);
    void refrescarAvisos();
  }, [refrescarAvisos]);

  // Al volver de la llamada se recupera al usuario de esta pestaña, sin volver a activar.
  useEffect(() => {
    const guardado = window.sessionStorage.getItem(CLAVE_USUARIO);
    if (!guardado) return;
    setUsuarioId(guardado);
    refrescar(guardado).catch(() => {
      window.sessionStorage.removeItem(CLAVE_USUARIO);
      setUsuarioId(null);
    });
  }, [refrescar]);

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
      window.sessionStorage.setItem(CLAVE_USUARIO, demo.usuario_id);
      setUsuarioId(demo.usuario_id);
      await refrescar(demo.usuario_id);
    });

  const avanzar = (dias = 1) =>
    ejecutar(async () => {
      if (!usuarioId) return;
      await avanzarReloj(usuarioId, dias);
      await refrescar(usuarioId);
    });

  const reiniciar = () => {
    window.sessionStorage.removeItem(CLAVE_USUARIO);
    setUsuarioId(null);
    setEstado(null);
    setHoy(null);
    setSaldo(null);
    setAhora([]);
    setResumen([]);
    void refrescarAvisos();
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
          <p className="banco-saludo">{usuarioId ? `Hola, ${usuarioId.charAt(0).toUpperCase()}${usuarioId.slice(1)}` : "Tu app del banco"}</p>
        </div>
        <div className="banco-acciones">
          <Campana />
          <Link href="/" className="banco-salir">
            Inicio
          </Link>
        </div>
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
            alAvanzarUno={() => avanzar(1)}
            alAvanzarDias={(dias) => avanzar(dias)}
          />

          {c && c.momentos > 0 && (
            <p className="silenciadas" role="status">
              Han pasado {c.momentos} {c.momentos === 1 ? "cosa" : "cosas"}. Solo{" "}
              {contadas === 1 ? "ha contado una" : `han contado ${contadas}`}
              {c.silenciadas > 0 && ` (${c.silenciadas} silenciadas por no compensar)`}.
            </p>
          )}

          <Bandeja
            usuarioId={usuarioId}
            ahora={ahora}
            resumen={resumen}
            hoy={hoy}
            alResolver={() => void refrescar(usuarioId).catch(() => undefined)}
          />

          <Link href="/app/hablar" className="enlace-boton grande" style={{ gap: 8 }}>
            <IconoMicro tamano={18} />
            Hablar con Meisam
          </Link>

          <nav className="atajos" aria-label="Más de Meisam">
            <Link href="/app/notificaciones" className="atajo">
              Todos los avisos
            </Link>
            <Link href="/app/cuentas" className="atajo">
              Mis cuentas
            </Link>
            <Link href="/app/movimientos" className="atajo">
              Movimientos
            </Link>
            <Link href="/app/aprendido" className="atajo">
              Lo que he aprendido de ti
            </Link>
          </nav>

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
