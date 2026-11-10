"use client";

import { useEffect, useState } from "react";
import MisCuentas from "@/components/MisCuentas";
import PantallaMovil, { SinUsuario } from "@/components/PantallaMovil";
import { esMaqueta } from "@/lib/cuentasApi";
import { useUsuarioDemo } from "@/lib/usuarioDemo";

export default function PantallaCuentas() {
  const usuario = useUsuarioDemo();
  const [maqueta, setMaqueta] = useState(false);
  useEffect(() => setMaqueta(esMaqueta()), []);
  // Con la maqueta (?mock=1) la pantalla se enseña sin activar la demo.
  const usuarioId = usuario ?? (maqueta ? "maqueta" : usuario);
  return (
    <PantallaMovil titulo="Mis cuentas">
      {usuarioId === undefined ? <div aria-busy="true" /> : !usuarioId ? <SinUsuario /> : <MisCuentas usuarioId={usuarioId} />}
    </PantallaMovil>
  );
}
