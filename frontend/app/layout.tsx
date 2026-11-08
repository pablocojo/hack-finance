import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Finanzas IA",
  description: "Asistente de finanzas personales con IA: entiende tus gastos, ahorra y calcula con cifras exactas.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
