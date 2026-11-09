"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import Bandeja from "@/components/Bandeja";
import InsigniaIA from "@/components/InsigniaIA";
import { activar, avanzarReloj, cargarDemo, estadoUsuario, notificaciones } from "@/lib/api";
import type { EstadoUsuario, Notificacion } from "@/lib/api";
import { eur, fechaLarga } from "@/lib/formato";

const ESCENARIO = "cena-lucia";
const MODULOS = ["cena_compartida"];

export default function PantallaCliente() {
  const [usuarioId, setUsuarioId] = useState<string | null>(null);
  const [activado, setActivado] = useState(false);
  const [hoy, setHoy] = useState<string | null>(null);
  const [estado, setEstado] = useState<EstadoUsuario | null>(null);
  const [ahora, setAhora] = useState<Notificacion[]>([]);
  const [resumen, setResumen] = useState<Notificacion[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refrescar = useCallback(async (id: string) => {
    const [e, a, r] = await Promise.all([
      estadoUsuario(id),
      notificaciones(id, "ahora"),
      notificaciones(id, "resumen"),
    ]);
    setEstado(e);
    setHoy(e.hoy);
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

  const cargarYActivar = () =>
    ejecutar(async () => {
      const demo = await cargarDemo(ESCENARIO);
      await activar(demo.usuario_id, MODULOS, { copiloto: true, memoria: true });
      setUsuarioId(demo.usuario_id);
      setActivado(true);
      await refrescar(demo.usuario_id);
    });

  const avanzar = () =>
    ejecutar(async () => {
      if (!usuarioId) return;
      const respuesta = await avanzarReloj(usuarioId, 1);
      setHoy(respuesta.hoy);
      await refrescar(usuarioId);
    });

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

      <section className="saldo" aria-label="Cuenta">
        <p className="tenue pequeno">Cuenta corriente</p>
        <p className="saldo-importe">{estado ? eur(estado.saldo) : "—"}</p>
        <p className="pequeno tenue" aria-live="polite">
          {hoy ? `Hoy (simulado): ${fechaLarga(hoy)}` : "Carga el escenario para empezar"}
        </p>
      </section>

      <section className="controles-demo" aria-label="Controles de la demostración">
        <button className="boton-principal" onClick={cargarYActivar} disabled={ocupado}>
          {activado ? "Reiniciar escenario" : "Cargar cena de Lucía y activar Meisam"}
        </button>
        <button className="boton-secundario" onClick={avanzar} disabled={ocupado || !activado}>
          Avanzar un día
        </button>
      </section>

      {error && (
        <p className="error banda" role="alert">
          {error}
        </p>
      )}

      {activado ? (
        <Bandeja ahora={ahora} resumen={resumen} />
      ) : (
        <p className="vacio-bandeja">
          Meisam vigila tus movimientos y te avisa solo cuando hay algo que resolver. Actívalo para ver tus avisos.
        </p>
      )}

      {estado && activado && (
        <p className="pequeno tenue">
          Silenciadas por no compensar: {estado.contadores.silenciadas}
        </p>
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
