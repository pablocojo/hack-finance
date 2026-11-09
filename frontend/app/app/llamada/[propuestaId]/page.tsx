"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Llamada from "@/components/Llamada";
import { CLAVE_USUARIO } from "@/lib/sesion";

export default function PantallaLlamada() {
  const { propuestaId } = useParams<{ propuestaId: string }>();
  const [usuarioId, setUsuarioId] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setUsuarioId(window.sessionStorage.getItem(CLAVE_USUARIO));
  }, []);

  if (usuarioId === undefined) return <div className="movil" aria-busy="true" />;
  if (!usuarioId) {
    return (
      <div className="movil">
        <p className="banda">Primero activa Meisam en la app para poder abrir un aviso.</p>
        <Link href="/app">Ir a la app</Link>
      </div>
    );
  }
  return <Llamada propuestaId={decodeURIComponent(propuestaId)} usuarioId={usuarioId} />;
}
