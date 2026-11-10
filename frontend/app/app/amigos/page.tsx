"use client";

import PantallaMovil, { SinUsuario } from "@/components/PantallaMovil";
import SaldosAmigos from "@/components/SaldosAmigos";
import { useUsuarioDemo } from "@/lib/usuarioDemo";

export default function PantallaAmigos() {
  const usuarioId = useUsuarioDemo();
  return (
    <PantallaMovil titulo="Cuentas con amigos">
      {usuarioId === undefined ? (
        <div aria-busy="true" />
      ) : !usuarioId ? (
        <SinUsuario />
      ) : (
        <SaldosAmigos usuarioId={usuarioId} />
      )}
    </PantallaMovil>
  );
}
