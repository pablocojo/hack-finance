import Link from "next/link";

const SUPERFICIES = [
  { href: "/app", titulo: "App del cliente", texto: "Banco Aurora con Meisam dentro: avisos solo cuando ahorran o protegen." },
  { href: "/banco", titulo: "Consola del banco", texto: "Módulos sin código, prueba en seco y aprobación." },
  { href: "/jurado", titulo: "Panel del jurado", texto: "Precisión, molestias evitadas y curva de aprendizaje." },
  { href: "/kit", titulo: "Chat del kit", texto: "El asistente conversacional de finanzas personales." },
];

export default function Portada() {
  return (
    <div className="pagina portada">
      <header className="portada-cab">
        <h1>Meisam</h1>
        <p className="portada-lema">Tu banco te avisa solo cuando hay dinero que ahorrar o proteger.</p>
        <p className="insignia-ia">Asistente con IA · información orientativa, no es asesoramiento</p>
      </header>
      <nav aria-label="Superficies del producto">
        <ul className="portada-lista">
          {SUPERFICIES.map((s) => (
            <li key={s.href}>
              <Link href={s.href} className="portada-enlace">
                <strong>{s.titulo}</strong>
                <span>{s.texto}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <footer className="pie-pagina">Demostración con datos sintéticos de un banco ficticio (Banco Aurora).</footer>
    </div>
  );
}
