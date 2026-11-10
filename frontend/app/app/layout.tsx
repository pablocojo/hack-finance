import type { ReactNode } from "react";
import AvisosProvider from "@/components/AvisosProvider";

// Un solo proveedor para todas las pantallas del cliente: sondea los avisos, cuenta las no vistas y lanza el toast.
export default function LayoutApp({ children }: { children: ReactNode }) {
  return <AvisosProvider>{children}</AvisosProvider>;
}
