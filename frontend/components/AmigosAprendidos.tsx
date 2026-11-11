"use client";

import { useState } from "react";
import { borrarAmigoAprendido, borrarSitioAprendido, editarAmigoAprendido } from "@/lib/api";
import type { AprendidoRespuesta, CanalAmigo, FraseAmigos } from "@/lib/api";
import { nombreVisible, textoVisible } from "@/lib/formato";

const DIAS_MAX = 10; // el backend (aprende_amigos.PARAMETROS) no admite esperas mayores
const CANALES: { valor: CanalAmigo; etiqueta: string }[] = [
  { valor: "bizum", etiqueta: "Bizum" },
  { valor: "efectivo", etiqueta: "Efectivo" },
  { valor: "transferencia", etiqueta: "Transferencia" },
];

const mensaje = (fallo: unknown) => (fallo instanceof Error ? fallo.message : String(fallo));

type Props = {
  usuarioId: string;
  frases: FraseAmigos[];
  // Cada cambio devuelve el `aprendido` completo: el padre lo pinta tal cual.
  alActualizar: (datos: AprendidoRespuesta) => void;
};

export default function AmigosAprendidos({ usuarioId, frases, alActualizar }: Props) {
  const [editando, setEditando] = useState<string | null>(null);
  const [dias, setDias] = useState("");
  const [canal, setCanal] = useState("");
  const [errorCampo, setErrorCampo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const personas = frases.filter((f) => f.tipo === "persona");
  const sitios = frases.filter((f) => f.tipo === "sitio");

  async function borrar(tarea: () => Promise<AprendidoRespuesta>) {
    setOcupado(true);
    setError(null);
    try {
      alActualizar(await tarea());
      setEditando(null);
    } catch (fallo) {
      setError(mensaje(fallo));
    } finally {
      setOcupado(false);
    }
  }

  function empezar(f: FraseAmigos) {
    setEditando(f.clave);
    setDias("");
    setCanal("");
    setErrorCampo(null);
    setError(null);
  }

  async function guardar(f: FraseAmigos) {
    const limpio = dias.trim();
    let valorDias: number | null = null;
    if (limpio) {
      if (!/^\d+$/.test(limpio) || Number(limpio) > DIAS_MAX) {
        setErrorCampo(`Escribe los días como un número entero de 0 a ${DIAS_MAX}.`);
        return;
      }
      valorDias = Number(limpio);
    }
    if (valorDias === null && !canal) {
      setErrorCampo("Elige los días o el canal que quieres cambiar.");
      return;
    }
    setOcupado(true);
    setErrorCampo(null);
    try {
      let ultimo: AprendidoRespuesta | null = null;
      if (valorDias !== null) ultimo = await editarAmigoAprendido(usuarioId, f.clave, "retraso_dias", valorDias);
      if (canal) ultimo = await editarAmigoAprendido(usuarioId, f.clave, "canal", canal as CanalAmigo);
      if (ultimo) alActualizar(ultimo);
      setEditando(null);
    } catch (fallo) {
      setErrorCampo(mensaje(fallo));
    } finally {
      setOcupado(false);
    }
  }

  function fila(f: FraseAmigos) {
    const nombre = f.tipo === "persona" ? nombreVisible(f.clave) : textoVisible(f.texto);
    const idForm = `amigo-${f.tipo}-${f.clave.replace(/[^a-zA-Z0-9]/g, "-")}`;
    return (
      <li key={f.campo} className="frase">
        {editando === f.clave ? (
          <form
            noValidate
            className="campo-etiquetado"
            onSubmit={(e) => {
              e.preventDefault();
              void guardar(f);
            }}
          >
            <p>{textoVisible(f.texto)}</p>
            <label htmlFor={`${idForm}-dias`}>Días de espera antes de recordárselo a {nombre}</label>
            <input
              id={`${idForm}-dias`}
              className="campo"
              inputMode="numeric"
              autoComplete="off"
              autoFocus
              placeholder="Sin cambios"
              value={dias}
              onChange={(e) => setDias(e.target.value)}
              aria-invalid={Boolean(errorCampo)}
              aria-describedby={`${idForm}-ayuda`}
            />
            <label htmlFor={`${idForm}-canal`}>Cómo suele pagarte</label>
            <select id={`${idForm}-canal`} value={canal} onChange={(e) => setCanal(e.target.value)}>
              <option value="">Sin cambios</option>
              {CANALES.map((c) => (
                <option key={c.valor} value={c.valor}>
                  {c.etiqueta}
                </option>
              ))}
            </select>
            <small id={`${idForm}-ayuda`} className={errorCampo ? "error" : "tenue"}>
              {errorCampo ?? `De 0 a ${DIAS_MAX} días. Lo que pongas aquí no lo cambia lo que vaya aprendiendo.`}
            </small>
            <div className="fila-botones">
              <button type="submit" className="boton-principal" disabled={ocupado}>
                Guardar
              </button>
              <button type="button" className="boton-secundario" disabled={ocupado} onClick={() => setEditando(null)}>
                Cancelar
              </button>
            </div>
          </form>
        ) : (
          <>
            <p>{textoVisible(f.texto)}</p>
            <div className="fila-botones">
              {f.editable && f.tipo === "persona" && (
                <button type="button" className="boton-texto" disabled={ocupado} onClick={() => empezar(f)}>
                  Editar<span className="solo-lectores"> lo que sé de {nombre}</span>
                </button>
              )}
              {f.borrable && (
                <button
                  type="button"
                  className="boton-texto peligro"
                  disabled={ocupado}
                  onClick={() =>
                    borrar(() => (f.tipo === "persona" ? borrarAmigoAprendido(usuarioId, f.clave) : borrarSitioAprendido(usuarioId, f.clave)))
                  }
                >
                  Borrar<span className="solo-lectores">: {textoVisible(f.texto)}</span>
                </button>
              )}
            </div>
          </>
        )}
      </li>
    );
  }

  return (
    <section className="bloque" aria-labelledby="t-planes">
      <h2 id="t-planes">Tus amigos y tus planes</h2>
      <p className="tenue pequeno">Solo lo uso para tus recordatorios. No sale de aquí.</p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {frases.length === 0 ? (
        <p className="vacio-bandeja">Aún no he aprendido nada de tus planes.</p>
      ) : (
        <>
          {personas.length > 0 && (
            <>
              <h3 id="t-planes-personas">Personas</h3>
              <ul className="frases" aria-labelledby="t-planes-personas">
                {personas.map(fila)}
              </ul>
            </>
          )}
          {sitios.length > 0 && (
            <>
              <h3 id="t-planes-sitios">Sitios</h3>
              <ul className="frases" aria-labelledby="t-planes-sitios">
                {sitios.map(fila)}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
