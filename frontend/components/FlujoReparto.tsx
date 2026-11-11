"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { rutaNoDisponible } from "@/lib/api";
import type { CasoResumen, ContactoResumen } from "@/lib/api";
import { centimosAbs, comoEuros, nombreContacto, nombreEscenario, RELACION } from "@/lib/cuentas";
import type { PagoRepartible } from "@/lib/cuentas";
import { contactos as pedirContactos, crearCaso } from "@/lib/cuentasApi";
import { eur, fechaLarga, importeDeTexto, nombreVisible, textoVisible } from "@/lib/formato";

// Reglas de Bizum para una solicitud (docs/diseno/deudas-casos.md): de 0,50 a 1.000 € por persona.
const MIN = 50;
const MAX = 100000;

const coma = (centimos: number) => comoEuros(centimos).replace(".", ",");
const mensaje = (fallo: unknown) => (fallo instanceof Error ? fallo.message : String(fallo));

function diasHasta(desde: string, hasta: string): number {
  const [a1, m1, d1] = desde.slice(0, 10).split("-").map(Number);
  const [a2, m2, d2] = hasta.slice(0, 10).split("-").map(Number);
  return Math.round((Date.UTC(a2, m2 - 1, d2) - Date.UTC(a1, m1 - 1, d1)) / 86400000);
}

type Props = {
  usuarioId: string;
  pago: PagoRepartible;
  alCerrar: () => void;
  alCreado?: (caso: CasoResumen) => void;
  // Personas ya marcadas al abrir (la sugerencia de Meisam en el nivel 2); se pueden quitar.
  elegidosIniciales?: string[];
};

// Elegir con quién se fue y cuánto pone cada uno. Solo apunta la deuda: Meisam no pide nada por Bizum sin el botón
// del usuario más adelante. Por defecto reparte a partes iguales entre las personas elegidas y tú.
export default function FlujoReparto({ usuarioId, pago, alCerrar, alCreado, elegidosIniciales }: Props) {
  const id = useId();
  const titulo = useRef<HTMLHeadingElement>(null);
  const [agenda, setAgenda] = useState<ContactoResumen[] | null>(null);
  const [errorAgenda, setErrorAgenda] = useState<string | null>(null);
  const [elegidos, setElegidos] = useState<string[]>(elegidosIniciales ?? []);
  const [escritos, setEscritos] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creado, setCreado] = useState<CasoResumen | null>(null);

  const total = pago.importe ? centimosAbs(pago.importe) : null;

  useEffect(() => {
    titulo.current?.focus();
    let vigente = true;
    pedirContactos(usuarioId)
      .then((c) => vigente && setAgenda(c))
      .catch((fallo) => {
        if (!vigente) return;
        setAgenda([]);
        setErrorAgenda(
          rutaNoDisponible(fallo) ? "La agenda de contactos todavía no está disponible." : `No se ha podido cargar la agenda: ${mensaje(fallo)}`,
        );
      });
    return () => {
      vigente = false;
    };
  }, [usuarioId]);

  // Sin editar, cada persona paga lo mismo: total entre las personas elegidas y tú (el resto del céntimo se queda en tu parte).
  const porDefecto = total !== null && elegidos.length > 0 ? coma(Math.floor(total / (elegidos.length + 1))) : "";
  const texto = (clave: string) => escritos[clave] ?? porDefecto;

  const filas = elegidos.map((clave) => {
    const importe = importeDeTexto(texto(clave));
    const c = importe === null ? null : centimosAbs(importe);
    let aviso: string | null = null;
    if (c === null) aviso = "Escribe un importe válido, por ejemplo 12,50.";
    else if (c < MIN || c > MAX) aviso = "Bizum admite solicitudes de 0,50 a 1.000 €.";
    return { clave, importe, centimos: c, aviso };
  });
  const suma = filas.reduce((s, f) => s + (f.centimos ?? 0), 0);
  const excede = total !== null && suma > total;
  const valido = filas.length > 0 && filas.every((f) => f.aviso === null) && !excede;

  const alternar = (clave: string) => {
    setElegidos((e) => (e.includes(clave) ? e.filter((x) => x !== clave) : [...e, clave]));
  };

  async function crear() {
    if (!valido) return;
    setEnviando(true);
    setError(null);
    try {
      const caso = await crearCaso(
        usuarioId,
        pago.id,
        filas.map((f) => ({ contraparte: f.clave, importe: f.importe as string })),
      );
      setCreado(caso);
      alCreado?.(caso);
    } catch (fallo) {
      setError(rutaNoDisponible(fallo) ? "Esta función todavía no está disponible en el servidor." : mensaje(fallo));
    } finally {
      setEnviando(false);
    }
  }

  const nombres = (claves: string[]) => claves.map((k) => nombreContacto(agenda?.find((c) => c.contraparte === k) ?? { contraparte: k })).join(", ");

  if (creado) {
    const dias = creado.avisar_desde ? Math.max(0, diasHasta(creado.creado, creado.avisar_desde)) : 2;
    const quien = creado.deudores.length === 1 ? `${nombres([creado.deudores[0].contraparte])} no te ha pagado` : "alguna de estas personas no te ha pagado";
    return (
      <section className="reparto" aria-labelledby={`${id}-t`}>
        <h3 id={`${id}-t`} ref={titulo} tabIndex={-1}>
          Hecho: {nombreEscenario(creado.escenario).toLowerCase()}
        </h3>
        <p role="status">
          Meisam estará atento. Si en {dias} {dias === 1 ? "día" : "días"} {quien}, te lo recordará a ti y podrás pedírselo
          por Bizum con un botón.
        </p>
        <p className="pequeno tenue">Esto solo lo apunta Meisam: no se envía ningún Bizum ni se mueve dinero.</p>
        <div className="fila-botones">
          <Link href="/app/cuentas" className="enlace-boton grande">
            Verlo en Mis cuentas
          </Link>
          <button type="button" className="boton-secundario grande" onClick={alCerrar}>
            Cerrar
          </button>
        </div>
      </section>
    );
  }

  return (
    <form
      className="reparto"
      aria-labelledby={`${id}-t`}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void crear();
      }}
    >
      <h3 id={`${id}-t`} ref={titulo} tabIndex={-1}>
        ¿Con quién fuiste?
      </h3>
      <p className="pequeno tenue">
        {nombreVisible(pago.comercio)}
        {pago.importe && ` · ${eur(pago.importe)}`}
        {pago.fecha && ` · ${fechaLarga(pago.fecha)}`}
      </p>

      <fieldset className="reparto-personas">
        <legend>Elige a las personas</legend>
        {agenda === null && (
          <p className="tenue" role="status">
            Cargando tu agenda…
          </p>
        )}
        {errorAgenda && (
          <p className="error" role="alert">
            {errorAgenda}
          </p>
        )}
        {agenda?.map((c) => (
          <label key={c.contraparte} className="contacto-opcion">
            <input type="checkbox" checked={elegidos.includes(c.contraparte)} onChange={() => alternar(c.contraparte)} />
            <span>
              <strong>{nombreContacto(c)}</strong>
              {c.relacion && <small>{RELACION[c.relacion]}</small>}
            </span>
          </label>
        ))}
      </fieldset>

      {filas.length > 0 && (
        <fieldset className="reparto-importes">
          <legend>Cuánto pone cada uno</legend>
          {filas.map((f) => {
            const nombre = nombres([f.clave]);
            return (
              <div key={f.clave} className="campo-etiquetado">
                <label htmlFor={`${id}-${f.clave}`}>Parte de {nombre} (euros)</label>
                <input
                  id={`${id}-${f.clave}`}
                  className="campo"
                  inputMode="decimal"
                  autoComplete="off"
                  value={texto(f.clave)}
                  onChange={(e) => setEscritos((x) => ({ ...x, [f.clave]: e.target.value }))}
                  aria-invalid={f.aviso !== null}
                  aria-describedby={f.aviso ? `${id}-${f.clave}-e` : undefined}
                />
                {f.aviso && (
                  <small id={`${id}-${f.clave}-e`} className="error">
                    {f.aviso}
                  </small>
                )}
              </div>
            );
          })}
          <p className="reparto-total" role="status">
            {total !== null ? (
              excede ? (
                <span className="error">
                  Las partes suman {eur(comoEuros(suma))}, más que el pago ({eur(comoEuros(total))}).
                </span>
              ) : (
                <>
                  Tu parte: <strong>{eur(comoEuros(total - suma))}</strong> · Te deben <strong>{eur(comoEuros(suma))}</strong>
                </>
              )
            ) : (
              <>
                Te deben <strong>{eur(comoEuros(suma))}</strong>
              </>
            )}
          </p>
        </fieldset>
      )}

      {error && (
        <p className="error" role="alert">
          {textoVisible(error)}
        </p>
      )}
      <div className="fila-botones">
        <button type="submit" className="boton-principal grande" disabled={!valido || enviando}>
          {enviando ? "Guardando…" : "Apuntar"}
        </button>
        <button type="button" className="boton-secundario grande" disabled={enviando} onClick={alCerrar}>
          Cancelar
        </button>
      </div>
      {elegidos.length === 0 && agenda && agenda.length > 0 && <p className="pequeno tenue">Elige al menos a una persona.</p>}
    </form>
  );
}
