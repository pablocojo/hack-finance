import Link from "next/link";

export default function Proximamente({ titulo }: { titulo: string }) {
  return (
    <div className="pagina portada">
      <header className="portada-cab">
        <h1>{titulo}</h1>
        <p className="portada-lema">Próximamente.</p>
        <p>
          <Link href="/">Volver a la portada</Link>
        </p>
      </header>
    </div>
  );
}
