"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Llamada from "@/components/Llamada";
import { pagoDeCaso, preguntaDeCaso } from "@/lib/cuentas";
import { casos as pedirCasos } from "@/lib/cuentasApi";
import { CLAVE_USUARIO } from "@/lib/sesion";

// «Hablar con Meisam»: la misma pantalla de la llamada, sin aviso. Se abre desde la home y desde «Mis cuentas».
// Con `?caso=<id>` es el «Otra respuesta» de una pregunta del Resumen: se enfoca en ese caso y se recuerda la pregunta.
export default function PantallaHablar() {
  const [usuarioId, setUsuarioId] = useState<string | null | undefined>(undefined);
  const [casoId, setCasoId] = useState<string | null>(null);
  const [pregunta, setPregunta] = useState<string | null>(null);

  useEffect(() => {
    const id = window.sessionStorage.getItem(CLAVE_USUARIO);
    const caso = new URLSearchParams(window.location.search).get("caso");
    setCasoId(caso);
    setUsuarioId(id);
    if (!id || !caso) return;
    pedirCasos(id)
      .then((lista) => {
        const k = lista.find((x) => x.id === caso);
        if (k) setPregunta(preguntaDeCaso(k, pagoDeCaso(k)));
      })
      .catch(() => undefined); // sin el texto, la conversación sigue igual: el servidor ya la enfoca en el caso
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
  return <Llamada propuestaId={null} usuarioId={usuarioId} casoId={casoId} pregunta={pregunta} />;
}
