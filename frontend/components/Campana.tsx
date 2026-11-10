"use client";

import Link from "next/link";
import { useAvisos } from "./AvisosProvider";

// Campana de la cabecera: enlaza al historial y cuenta solo los avisos de ahora que aún no se han abierto.
export default function Campana() {
  const { usuarioId, sinVer } = useAvisos();
  if (!usuarioId) return null;
  const etiqueta = sinVer === 0 ? "Avisos: ninguno sin ver" : sinVer === 1 ? "Avisos: 1 sin ver" : `Avisos: ${sinVer} sin ver`;
  return (
    <Link href="/app/notificaciones" className="campana" aria-label={etiqueta}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </svg>
      {sinVer > 0 && (
        <span className="campana-contador" aria-hidden="true">
          {sinVer > 9 ? "9+" : sinVer}
        </span>
      )}
    </Link>
  );
}
