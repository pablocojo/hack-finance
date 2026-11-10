"use client";

import { useEffect, useState } from "react";
import { CLAVE_USUARIO } from "./sesion";

// El usuario de la demo vive en sessionStorage (lo guarda /app al activar). `undefined` = aún sin leer.
export function useUsuarioDemo(): string | null | undefined {
  const [usuarioId, setUsuarioId] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    setUsuarioId(window.sessionStorage.getItem(CLAVE_USUARIO));
  }, []);
  return usuarioId;
}
