"use client";

import PanelAvisos from "@/components/PanelAvisos";
import PantallaMovil, { SinUsuario } from "@/components/PantallaMovil";
import { useUsuarioDemo } from "@/lib/usuarioDemo";

export default function PantallaNotificaciones() {
  const usuarioId = useUsuarioDemo();
  return (
    <PantallaMovil titulo="Avisos">
      {usuarioId === undefined ? <div aria-busy="true" /> : !usuarioId ? <SinUsuario /> : <PanelAvisos usuarioId={usuarioId} />}
    </PantallaMovil>
  );
}
