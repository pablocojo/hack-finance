import { redirect } from "next/navigation";

// La demo empieza directamente en la app del cliente. Las demás pantallas siguen en /banco, /jurado y /kit.
export default function Portada() {
  redirect("/app");
}
