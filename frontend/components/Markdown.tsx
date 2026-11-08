import type { ReactNode } from "react";

// Markdown mínimo y seguro (sin HTML): párrafos, listas, títulos y **negritas**.
const VINETA = /^\s*([-*•]|\d+[.)])\s+/;

function enLinea(texto: string, clave: string): ReactNode[] {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((parte, indice) =>
    parte.startsWith("**") && parte.endsWith("**") && parte.length > 4 ? (
      <strong key={`${clave}-${indice}`}>{parte.slice(2, -2)}</strong>
    ) : (
      <span key={`${clave}-${indice}`}>{parte}</span>
    ),
  );
}

export default function Markdown({ texto }: { texto: string }) {
  const nodos: ReactNode[] = [];
  let lista: string[] = [];
  let parrafo: string[] = [];

  const cerrarLista = () => {
    if (lista.length === 0) return;
    const clave = `l${nodos.length}`;
    nodos.push(
      <ul key={clave}>
        {lista.map((elemento, i) => (
          <li key={`${clave}-${i}`}>{enLinea(elemento, `${clave}-${i}`)}</li>
        ))}
      </ul>,
    );
    lista = [];
  };
  const cerrarParrafo = () => {
    if (parrafo.length === 0) return;
    const clave = `p${nodos.length}`;
    nodos.push(
      <p key={clave}>
        {parrafo.map((linea, i) => (
          <span key={`${clave}-${i}`}>
            {enLinea(linea, `${clave}-${i}`)}
            {i < parrafo.length - 1 ? <br /> : null}
          </span>
        ))}
      </p>,
    );
    parrafo = [];
  };

  for (const linea of texto.split("\n")) {
    if (linea.trim() === "") {
      cerrarLista();
      cerrarParrafo();
    } else if (VINETA.test(linea)) {
      cerrarParrafo();
      lista.push(linea.replace(VINETA, ""));
    } else if (/^#{1,4}\s/.test(linea)) {
      cerrarLista();
      cerrarParrafo();
      nodos.push(
        <p key={`h${nodos.length}`} className="md-titulo">
          {enLinea(linea.replace(/^#{1,4}\s+/, ""), `h${nodos.length}`)}
        </p>,
      );
    } else {
      cerrarLista();
      parrafo.push(linea);
    }
  }
  cerrarLista();
  cerrarParrafo();
  return <div className="md">{nodos}</div>;
}
