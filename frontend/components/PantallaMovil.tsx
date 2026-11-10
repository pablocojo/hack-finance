import Link from "next/link";
import type { ReactNode } from "react";
import InsigniaIA from "./InsigniaIA";

// Marco común de las pantallas secundarias del cliente: cabecera del banco, contenido y aviso de IA siempre visible.
export default function PantallaMovil({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="movil">
      <header className="banco-cab">
        <div>
          <p className="banco-nombre">Banco Aurora</p>
          <h1 className="banco-saludo">{titulo}</h1>
        </div>
        <Link href="/app" className="banco-salir">
          Volver
        </Link>
      </header>
      {children}
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

export function SinUsuario() {
  return (
    <p className="vacio-bandeja">
      Primero activa Meisam desde <Link href="/app">tu app del banco</Link>.
    </p>
  );
}
