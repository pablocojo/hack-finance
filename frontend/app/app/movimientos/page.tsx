"use client";

import { useEffect, useState } from "react";
import ListaMovimientos from "@/components/ListaMovimientos";
import PantallaMovil, { SinUsuario } from "@/components/PantallaMovil";
import { esMaqueta } from "@/lib/cuentasApi";
import { useUsuarioDemo } from "@/lib/usuarioDemo";

export default function PantallaMovimientos() {
  const usuario = useUsuarioDemo();
  const [maqueta, setMaqueta] = useState(false);
  useEffect(() => setMaqueta(esMaqueta()), []);
  // Con la maqueta (?mock=1) la pantalla se enseña sin activar la demo.
  const usuarioId = usuario ?? (maqueta ? "maqueta" : usuario);
  return (
    <PantallaMovil titulo="Movimientos">
      {usuarioId === undefined ? <div aria-busy="true" /> : !usuarioId ? <SinUsuario /> : <ListaMovimientos usuarioId={usuarioId} />}
    </PantallaMovil>
  );
}
