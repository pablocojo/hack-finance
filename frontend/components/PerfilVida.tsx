"use client";

import { useCallback, useEffect, useState } from "react";
import { borrarCampoPerfil, borrarPerfil, editarPerfil, perfil as pedirPerfil } from "@/lib/api";
import type { FrasePerfil, PerfilRespuesta } from "@/lib/api";
import { importeDeTexto, textoVisible } from "@/lib/formato";

type Campo = { etiqueta: string; ayuda: string; modo: "entero" | "euros"; valor: (r: PerfilRespuesta) => string };

// Los campos que se editan desde aquí (el servidor valida los rangos y su mensaje se muestra tal cual).
const EDITABLES: Record<string, Campo> = {
  dia_cobro_nomina: {
    etiqueta: "Día del mes en que cobras la nómina",
    ayuda: "Un número del 1 al 31.",
    modo: "entero",
    valor: (r) => String(r.perfil?.dia_cobro_nomina ?? ""),
  },
  umbral_relevante_eur: {
    etiqueta: "Importe a partir del cual quieres que te avise (€)",
    ayuda: "Por debajo de esto, Meisam no te interrumpe.",
    modo: "euros",
    valor: (r) => (r.perfil?.umbral_relevante_eur ?? "").replace(".", ","),
  },
  ingreso_mensual_tipico: {
    etiqueta: "Ingreso mensual típico (€)",
    ayuda: "Lo que te suele entrar cada mes.",
    modo: "euros",
    valor: (r) => (r.perfil?.ingreso_mensual_tipico ?? "").replace(".", ","),
  },
};

const mensaje = (fallo: unknown) => (fallo instanceof Error ? fallo.message : String(fallo));

export default function PerfilVida({ usuarioId }: { usuarioId: string }) {
  const [datos, setDatos] = useState<PerfilRespuesta | null>(null);
  const [cargado, setCargado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editando, setEditando] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [errorCampo, setErrorCampo] = useState<string | null>(null);
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setDatos(await pedirPerfil(usuarioId));
    } catch (fallo) {
      setError(mensaje(fallo));
    } finally {
      setCargado(true);
    }
  }, [usuarioId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function ejecutar(tarea: () => Promise<PerfilRespuesta>) {
    setOcupado(true);
    setError(null);
    try {
      setDatos(await tarea());
      return true;
    } catch (fallo) {
      setError(mensaje(fallo));
      return false;
    } finally {
      setOcupado(false);
    }
  }

  function empezarEdicion(frase: FrasePerfil) {
    if (!datos) return;
    setEditando(frase.campo);
    setTexto(EDITABLES[frase.campo].valor(datos));
    setErrorCampo(null);
  }

  async function guardar(campo: string) {
    const def = EDITABLES[campo];
    let valor: number | string;
    if (def.modo === "entero") {
      const n = Number(texto.trim());
      if (!/^\d{1,2}$/.test(texto.trim()) || n < 1 || n > 31) {
        setErrorCampo("Escribe un número del 1 al 31.");
        return;
      }
      valor = n;
    } else {
      const importe = importeDeTexto(texto);
      if (importe === null) {
        setErrorCampo("Escribe un importe válido, por ejemplo 25,00.");
        return;
      }
      valor = importe;
    }
    setErrorCampo(null);
    if (await ejecutar(() => editarPerfil(usuarioId, campo, valor))) setEditando(null);
  }

  if (!cargado) {
    return (
      <p className="tenue" role="status">
        Cargando lo que sé de ti…
      </p>
    );
  }

  return (
    <section className="bloque" aria-labelledby="t-perfil">
      <h2 id="t-perfil">Cómo es tu vida financiera</h2>
      <p className="tenue pequeno">
        Esto es lo que Meisam ha deducido de tus movimientos para avisarte solo cuando compensa. Lo puedes corregir o borrar.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {datos && !datos.usar_perfil && (
        <div className="nota-bloque">
          <p>Has apagado tu perfil: Meisam funciona sin conocerte, con umbrales generales.</p>
          <button
            type="button"
            className="boton-secundario grande"
            disabled={ocupado}
            onClick={() => ejecutar(() => editarPerfil(usuarioId, "usar_perfil", true))}
          >
            Volver a usar mi perfil
          </button>
        </div>
      )}

      {datos?.usar_perfil && datos.frases.length === 0 && (
        <p className="vacio-bandeja">
          {datos.perfil
            ? "No queda nada guardado en tu perfil."
            : "Todavía no hay perfil: Meisam necesita unas cuatro semanas de movimientos para conocer tu mes."}
        </p>
      )}

      {datos?.usar_perfil && datos.frases.length > 0 && (
        <ul className="frases">
          {datos.frases.map((f) => {
            const def = EDITABLES[f.campo];
            const fijado = datos.perfil?.campos_fijados.includes(f.campo);
            const idCampo = `campo-${f.campo}`;
            return (
              <li key={f.campo} className="frase">
                {editando === f.campo && def ? (
                  <form
                    noValidate
                    className="campo-etiquetado"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void guardar(f.campo);
                    }}
                  >
                    <label htmlFor={idCampo}>{def.etiqueta}</label>
                    <input
                      id={idCampo}
                      className="campo"
                      inputMode={def.modo === "entero" ? "numeric" : "decimal"}
                      autoComplete="off"
                      autoFocus
                      value={texto}
                      onChange={(e) => setTexto(e.target.value)}
                      aria-invalid={Boolean(errorCampo)}
                      aria-describedby={`${idCampo}-ayuda`}
                    />
                    <small id={`${idCampo}-ayuda`} className={errorCampo ? "error" : "tenue"}>
                      {errorCampo ?? def.ayuda}
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
                    <p>
                      {textoVisible(f.texto)}
                      {fijado && <span className="etiqueta-fijado">Fijado por ti</span>}
                    </p>
                    <div className="fila-botones">
                      {f.editable && def && (
                        <button type="button" className="boton-texto" disabled={ocupado} onClick={() => empezarEdicion(f)}>
                          Editar<span className="solo-lectores">: {def.etiqueta}</span>
                        </button>
                      )}
                      {f.borrable && (
                        <button
                          type="button"
                          className="boton-texto peligro"
                          disabled={ocupado}
                          onClick={() => ejecutar(() => borrarCampoPerfil(usuarioId, f.campo))}
                        >
                          Borrar<span className="solo-lectores">: {textoVisible(f.texto)}</span>
                        </button>
                      )}
                    </div>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {datos?.usar_perfil && (
        <div className="zona-peligro">
          {confirmarBorrado ? (
            <>
              <p role="alert">Se borra todo tu perfil y Meisam deja de usarlo hasta que lo reactives. ¿Seguro?</p>
              <div className="fila-botones">
                <button
                  type="button"
                  className="boton-secundario peligro"
                  disabled={ocupado}
                  onClick={async () => {
                    if (await ejecutar(() => borrarPerfil(usuarioId))) setConfirmarBorrado(false);
                  }}
                >
                  Sí, borrar mi perfil
                </button>
                <button type="button" className="boton-secundario" onClick={() => setConfirmarBorrado(false)}>
                  No
                </button>
              </div>
            </>
          ) : (
            <button type="button" className="boton-secundario peligro" disabled={ocupado} onClick={() => setConfirmarBorrado(true)}>
              Borrar mi perfil
            </button>
          )}
        </div>
      )}
    </section>
  );
}
