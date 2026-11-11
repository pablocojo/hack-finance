"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Llamada from "@/components/Llamada";
import { CLAVE_USUARIO } from "@/lib/sesion";

// «Hablar con Meisam»: la misma pantalla de la llamada, sin aviso. Se abre desde la home y desde «Mis cuentas».
export default function PantallaHablar() {
  const [usuarioId, setUsuarioId] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setUsuarioId(window.sessionStorage.getItem(CLAVE_USUARIO));
  }, []);

  if (usuarioId === undefined) return <div className="movil" aria-busy="true" />;
  if (!usuarioId) {
    return (
      <div className="movil">
        <p className="banda">Primero activa Meisam en la app para poder hablar con él.</p>
        <Link href="/app">Ir a la app</Link>
      </div>
    );
  }
  return <Llamada propuestaId={null} usuarioId={usuarioId} />;
}
