"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { notificaciones } from "@/lib/api";
import type { Notificacion } from "@/lib/api";
import { sinVer, textoNavegador } from "@/lib/avisos";
import { CLAVE_USUARIO } from "@/lib/sesion";
import ToastAviso from "./ToastAviso";
import type { AvisoToast } from "./ToastAviso";

export type PermisoNavegador = "no_soportado" | "por_pedir" | "concedido" | "denegado";

type Contexto = {
  usuarioId: string | null;
  lista: Notificacion[]; // todas las notificaciones del backend, la más reciente primero
  cargado: boolean;
  sinVer: number; // avisos de ahora en estado `nueva`: lo que cuenta la campana
  permiso: PermisoNavegador;
  navegadorActivo: boolean; // preferencia local; solo tiene efecto con el permiso concedido
  refrescar: () => Promise<void>;
  activarNavegador: () => Promise<void>;
  cambiarNavegadorActivo: (activo: boolean) => void;
};

const VACIO: Contexto = {
  usuarioId: null,
  lista: [],
  cargado: false,
  sinVer: 0,
  permiso: "no_soportado",
  navegadorActivo: true,
  refrescar: async () => undefined,
  activarNavegador: async () => undefined,
  cambiarNavegadorActivo: () => undefined,
};
const Avisos = createContext<Contexto>(VACIO);
export const useAvisos = () => useContext(Avisos);

const SONDEO_MS = 5000;
const CLAVE_PREFERENCIA = "meisam-avisos-navegador";

const leerPermiso = (): PermisoNavegador => {
  if (typeof window === "undefined" || !("Notification" in window)) return "no_soportado";
  return Notification.permission === "granted" ? "concedido" : Notification.permission === "denied" ? "denegado" : "por_pedir";
};

// Detecta los avisos nuevos con un sondeo suave de `GET /usuarios/{id}/notificaciones` (solo con la pestaña visible; el
// reloj de la demo también lo pide al instante). El tope de avisos lo decide el backend: aquí solo se muestran.
// No hay Web Push real ni service worker: la notificación del navegador solo sale con la app abierta.
export default function AvisosProvider({ children }: { children: ReactNode }) {
  const ruta = usePathname();
  const router = useRouter();
  const [usuarioId, setUsuarioId] = useState<string | null>(null);
  const [lista, setLista] = useState<Notificacion[]>([]);
  const [cargado, setCargado] = useState(false);
  const [toast, setToast] = useState<AvisoToast | null>(null);
  const [permiso, setPermiso] = useState<PermisoNavegador>("no_soportado");
  const [navegadorActivo, setNavegadorActivo] = useState(true);

  const usuarioRef = useRef<string | null>(null);
  const conocidos = useRef<Set<string> | null>(null); // null = aún no hemos visto la primera lista (no se anuncia nada)
  const enVuelo = useRef(false);
  const repetir = useRef(false);
  const estado = useRef({ ruta, permiso, navegadorActivo });
  estado.current = { ruta, permiso, navegadorActivo };
  const irA = useRef(router.push);
  irA.current = router.push;

  const anunciar = useCallback((nuevos: Notificacion[], volviendo: boolean) => {
    const { ruta: rutaActual, permiso: p, navegadorActivo: activo } = estado.current;
    const uno = nuevos.length === 1 ? nuevos[0] : null;
    const aviso = uno
      ? textoNavegador(uno)
      : { titulo: `Tienes ${nuevos.length} avisos nuevos`, cuerpo: "Ábrelos en Meisam para ver qué ha pasado." };
    // En plena llamada no se interrumpe con un toast, y en el propio panel ya se ve la lista: el aviso queda en la campana.
    if (!rutaActual.startsWith("/app/llamada") && !rutaActual.startsWith("/app/notificaciones")) {
      setToast({ clave: `${Date.now()}`, titulo: aviso.titulo, mensaje: aviso.cuerpo, propuestaId: uno?.propuesta.id ?? null, total: nuevos.length });
    }
    // Notificación del navegador: solo con permiso y preferencia, y no al volver a la pestaña (ya no es «nueva»).
    if (p === "concedido" && activo && !volviendo && document.visibilityState === "visible") {
      try {
        const n = new Notification(aviso.titulo, { body: aviso.cuerpo, tag: uno ? uno.propuesta.id : "meisam-varios" });
        n.onclick = () => {
          window.focus();
          irA.current("/app/notificaciones");
          n.close();
        };
      } catch {
        // algunos móviles solo admiten notificaciones desde un service worker; el toast ya ha avisado
      }
    }
  }, []);

  const refrescar = useCallback(
    async (volviendo = false) => {
      const id = window.sessionStorage.getItem(CLAVE_USUARIO);
      if (id !== usuarioRef.current) {
        usuarioRef.current = id;
        conocidos.current = null;
        setUsuarioId(id);
        setLista([]);
        setCargado(false);
        setToast(null);
      }
      if (!id) return;
      if (enVuelo.current) {
        repetir.current = true;
        return;
      }
      enVuelo.current = true;
      try {
        do {
          repetir.current = false;
          const todas = await notificaciones(id);
          if (usuarioRef.current !== id) break;
          const nuevos = conocidos.current ? todas.filter((n) => sinVer(n) && !conocidos.current?.has(n.propuesta.id)) : [];
          conocidos.current = new Set(todas.map((n) => n.propuesta.id));
          setLista(todas);
          setCargado(true);
          if (nuevos.length > 0) anunciar(nuevos, volviendo);
        } while (repetir.current);
      } catch {
        // sondeo suave: si falla una vez, el siguiente intento lo repite
      } finally {
        enVuelo.current = false;
      }
    },
    [anunciar],
  );

  // Sondeo mientras la pestaña está visible; al ocultarse se para, y al volver se refresca de inmediato.
  useEffect(() => {
    setPermiso(leerPermiso());
    setNavegadorActivo(window.localStorage.getItem(CLAVE_PREFERENCIA) !== "0");
    let temporizador: number | undefined;
    const parar = () => {
      if (temporizador !== undefined) window.clearInterval(temporizador);
      temporizador = undefined;
    };
    const empezar = () => {
      parar();
      temporizador = window.setInterval(() => void refrescar(), SONDEO_MS);
    };
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") {
        void refrescar(true);
        empezar();
      } else {
        parar();
      }
    };
    void refrescar();
    if (document.visibilityState === "visible") empezar();
    document.addEventListener("visibilitychange", alCambiarVisibilidad);
    return () => {
      parar();
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
    };
  }, [refrescar]);

  // Al cambiar de pantalla se vuelve a leer el usuario (p. ej. justo después de activar Meisam).
  useEffect(() => {
    void refrescar();
    if (ruta.startsWith("/app/notificaciones")) setToast(null);
  }, [ruta, refrescar]);

  // El permiso solo se pide con un botón explícito, nunca al cargar la app.
  const activarNavegador = useCallback(async () => {
    if (!("Notification" in window)) return;
    try {
      await Notification.requestPermission();
    } finally {
      setPermiso(leerPermiso());
      window.localStorage.removeItem(CLAVE_PREFERENCIA);
      setNavegadorActivo(true);
    }
  }, []);

  const cambiarNavegadorActivo = useCallback((activo: boolean) => {
    window.localStorage.setItem(CLAVE_PREFERENCIA, activo ? "1" : "0");
    setNavegadorActivo(activo);
  }, []);

  const valor = useMemo<Contexto>(
    () => ({
      usuarioId,
      lista,
      cargado,
      sinVer: lista.filter(sinVer).length,
      permiso,
      navegadorActivo,
      refrescar: () => refrescar(),
      activarNavegador,
      cambiarNavegadorActivo,
    }),
    [usuarioId, lista, cargado, permiso, navegadorActivo, refrescar, activarNavegador, cambiarNavegadorActivo],
  );

  return (
    <Avisos.Provider value={valor}>
      {children}
      <div className="toast-zona" aria-live="polite" aria-atomic="true">
        {toast && <ToastAviso key={toast.clave} toast={toast} alCerrar={() => setToast(null)} />}
      </div>
    </Avisos.Provider>
  );
}
