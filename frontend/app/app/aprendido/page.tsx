"use client";

import HechosAprendidos from "@/components/HechosAprendidos";
import PantallaMovil, { SinUsuario } from "@/components/PantallaMovil";
import PerfilVida from "@/components/PerfilVida";
import { useUsuarioDemo } from "@/lib/usuarioDemo";

export default function PantallaAprendido() {
  const usuarioId = useUsuarioDemo();
  return (
    <PantallaMovil titulo="Lo que he aprendido de ti">
      {usuarioId === undefined ? (
        <div aria-busy="true" />
      ) : !usuarioId ? (
        <SinUsuario />
      ) : (
        <>
          <PerfilVida usuarioId={usuarioId} />
          <HechosAprendidos usuarioId={usuarioId} />
        </>
      )}
    </PantallaMovil>
  );
}
