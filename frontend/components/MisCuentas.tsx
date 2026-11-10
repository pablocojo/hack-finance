"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { rutaNoDisponible } from "@/lib/api";
import type { CasoResumen, ContactoResumen, DeudorCaso, Relacion } from "@/lib/api";
import {
  casoAbierto,
  centimosAbs,
  comoEuros,
  ESTADO_DEUDOR,
  idMovimientoOrigen,
  nombreContacto,
  nombreEscenario,
  RELACION,
  RELACIONES,
  VIA_SALDADO,
  deudorAbierto,
} from "@/lib/cuentas";
import { casos as pedirCasos, contactos as pedirContactos, editarContacto, esMaqueta } from "@/lib/cuentasApi";
import { eur, fechaLarga, nombreVisible, textoVisible } from "@/lib/formato";
import AccionesDeudor from "./AccionesDeudor";
import PreguntaConAlguien from "./PreguntaConAlguien";

const mensaje = (fallo: unknown) => (fallo instanceof Error ? fallo.message : String(fallo));

type Linea = { caso: CasoResumen; deudor: DeudorCaso };
type Persona = { contacto: ContactoResumen; lineas: Linea[] };

const AVISO_SUTIL: Record<string, string> = {
  silencioso: "Solo lo ves aquí, no te aviso",
  resumen: "Va a tu resumen, sin notificación",
};

function fraseSaldo(saldo: string): string {
  const c = centimosAbs(saldo);
  return saldo.trim().startsWith("-") ? `Le debes ${eur(comoEuros(c))}` : c > 0 ? `Te debe ${eur(comoEuros(c))}` : "Cuentas al día";
}

function comercioDe(caso: CasoResumen): string | null {
  const o = caso.movimiento_origen;
  return o && typeof o === "object" && (o.comercio || o.concepto) ? nombreVisible(o.comercio || o.concepto) : null;
}
function totalDe(caso: CasoResumen): string | null {
  const o = caso.movimiento_origen;
  return o && typeof o === "object" && o.importe ? o.importe.replace("-", "") : null;
}

export default function MisCuentas({ usuarioId }: { usuarioId: string }) {
  const [listaCasos, setListaCasos] = useState<CasoResumen[] | null>(null);
  const [agenda, setAgenda] = useState<ContactoResumen[]>([]);
  const [noDisponible, setNoDisponible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [maqueta, setMaqueta] = useState(false);

  const cargar = useCallback(async () => {
    setMaqueta(esMaqueta());
    const [c, a] = await Promise.allSettled([pedirCasos(usuarioId), pedirContactos(usuarioId)]);
    const fallos = [c, a].filter((r): r is PromiseRejectedResult => r.status === "rejected").map((r) => r.reason);
    if (fallos.length > 0 && fallos.every(rutaNoDisponible)) setNoDisponible(true);
    else if (fallos.length > 0) setError(mensaje(fallos.find((f) => !rutaNoDisponible(f))));
    setListaCasos(c.status === "fulfilled" ? c.value : []);
    setAgenda(a.status === "fulfilled" ? a.value : []);
  }, [usuarioId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function cambiarRelacion(c: ContactoResumen, relacion: Relacion) {
    setError(null);
    try {
      await editarContacto(usuarioId, c.contraparte, relacion);
      setAviso(`Guardado: ${nombreContacto(c)} figura como «${RELACION[relacion].toLowerCase()}». Lo has dicho tú; Meisam no lo deduce.`);
      await cargar();
    } catch (fallo) {
      setError(rutaNoDisponible(fallo) ? "Todavía no se puede guardar la relación." : mensaje(fallo));
    }
  }

  const alHecho = (texto: string) => {
    setAviso(texto);
    void cargar();
  };

  if (listaCasos === null) {
    return (
      <p className="tenue" role="status">
        Cargando tus cuentas…
      </p>
    );
  }

  // Personas: la agenda más quien aparezca en algún caso sin estar en ella.
  const todos = listaCasos.flatMap((caso) => caso.deudores.map((deudor) => ({ caso, deudor })));
  const claves = new Set(agenda.map((c) => c.contraparte));
  const sueltos: ContactoResumen[] = [...new Set(todos.map((l) => l.deudor.contraparte))]
    .filter((k) => !claves.has(k))
    .map((k) => {
      const pend = todos.filter((l) => l.deudor.contraparte === k && deudorAbierto(l.deudor));
      return {
        contraparte: k,
        nombre: nombreVisible(k),
        relacion: null,
        saldo_total: comoEuros(pend.reduce((s, l) => s + centimosAbs(l.deudor.cuota), 0)),
        casos_abiertos: pend.length,
      };
    });
  const personas: Persona[] = [...agenda, ...sueltos]
    .map((contacto) => ({ contacto, lineas: todos.filter((l) => l.deudor.contraparte === contacto.contraparte) }))
    .sort(
      (a, b) =>
        centimosAbs(b.contacto.saldo_total) - centimosAbs(a.contacto.saldo_total) || b.lineas.length - a.lineas.length,
    );

  const quienDebe = personas.filter((p) => centimosAbs(p.contacto.saldo_total) > 0 && !p.contacto.saldo_total.startsWith("-"));
  const total = quienDebe.reduce((s, p) => s + centimosAbs(p.contacto.saldo_total), 0);
  const preguntas = listaCasos.filter((c) => c.escenario === "pago_individual" && c.deudores.length === 0 && casoAbierto(c));

  return (
    <>
      {error && (
        <p className="error banda" role="alert">
          {error}
        </p>
      )}
      {maqueta && <p className="nota-bloque pequeno">Datos de ejemplo (maqueta). Nada de esto viene del servidor.</p>}
      {noDisponible && (
        <p className="nota-bloque pequeno" role="status">
          Las cuentas con personas todavía no están disponibles en el servidor. Cuando lo estén, las verás aquí.
        </p>
      )}
      {aviso && (
        <p className="nota-bloque pequeno" role="status">
          {textoVisible(aviso)}
        </p>
      )}

      <section className="bloque resumen-deudas" aria-labelledby="t-quien-debe">
        <h2 id="t-quien-debe">Quién te debe</h2>
        {quienDebe.length > 0 ? (
          <p className="total-deuda">
            <strong>{eur(comoEuros(total))}</strong>
            <span>
              {" "}
              pendientes entre {quienDebe.length} {quienDebe.length === 1 ? "persona" : "personas"}
            </span>
          </p>
        ) : (
          <p className="vacio-bandeja">Nadie te debe nada ahora mismo.</p>
        )}
        <Link href="/app/movimientos" className="enlace-boton grande">
          He pagado por otra persona
        </Link>
      </section>

      {preguntas.length > 0 && (
        <section className="bloque" aria-labelledby="t-quiza">
          <h2 id="t-quiza">{nombreEscenario("pago_individual")}</h2>
          <p className="tenue pequeno">
            Pagos que podrían haber sido con otras personas. Meisam no avisa de esto: lo ves aquí o, a veces, en tu resumen.
          </p>
          {preguntas.map((caso) => (
            <div key={caso.id} className="caso-pregunta">
              {caso.aviso && AVISO_SUTIL[caso.aviso] && <p className="pequeno tenue">{AVISO_SUTIL[caso.aviso]}</p>}
              <PreguntaConAlguien usuarioId={usuarioId} caso={caso} alCambiar={() => void cargar()} />
            </div>
          ))}
        </section>
      )}

      <section className="bloque" aria-labelledby="t-personas">
        <h2 id="t-personas">Personas</h2>
        {personas.length === 0 ? (
          <p className="vacio-bandeja">
            Aún no hay cuentas con personas. Cuando Meisam detecte un gasto compartido, o tú apuntes un pago por otra persona, lo verás aquí.
          </p>
        ) : (
          <ul className="frases">
            {personas.map(({ contacto: c, lineas }) => {
              const nombre = nombreContacto(c);
              const ordenadas = [...lineas].sort(
                (a, b) => Number(deudorAbierto(b.deudor)) - Number(deudorAbierto(a.deudor)) || b.caso.creado.localeCompare(a.caso.creado),
              );
              return (
                <li key={c.contraparte} className="frase persona">
                  <div className="persona-cab">
                    <div>
                      <h3 className="amigo-nombre">{nombre}</h3>
                      {c.telefono && <p className="pequeno tenue">{c.telefono}</p>}
                    </div>
                    <p className="amigo-saldo persona-saldo">{fraseSaldo(c.saldo_total)}</p>
                  </div>
                  <div className="campo-etiquetado persona-relacion">
                    <label htmlFor={`rel-${c.contraparte}`}>Relación con {nombre}</label>
                    <select
                      id={`rel-${c.contraparte}`}
                      value={c.relacion ?? ""}
                      onChange={(e) => void cambiarRelacion(c, e.target.value as Relacion)}
                    >
                      <option value="" disabled>
                        Sin indicar
                      </option>
                      {RELACIONES.map((r) => (
                        <option key={r} value={r}>
                          {RELACION[r]}
                        </option>
                      ))}
                    </select>
                  </div>

                  {ordenadas.length === 0 ? (
                    <p className="pequeno tenue">Sin cuentas con {nombre}.</p>
                  ) : (
                    <ul className="casos-persona">
                      {ordenadas.map(({ caso, deudor }) => {
                        const comercio = comercioDe(caso);
                        const totalPago = totalDe(caso);
                        const abierto = deudorAbierto(deudor);
                        return (
                          <li key={`${caso.id}-${deudor.contraparte}`} className={`caso-fila${abierto ? "" : " cerrado"}`}>
                            <div className="caso-linea">
                              <p className="caso-titulo">{nombreEscenario(caso.escenario)}</p>
                              <span className={`estado-amigo estado-${deudor.estado}`}>{ESTADO_DEUDOR[deudor.estado] ?? deudor.estado}</span>
                            </div>
                            <p className="pequeno">
                              {comercio && <>{comercio} · </>}
                              {deudor.cuota && (
                                <>
                                  Su parte: <strong>{eur(deudor.cuota)}</strong>
                                  {totalPago && <> de {eur(totalPago)}</>}
                                </>
                              )}
                            </p>
                            <p className="pequeno tenue">
                              Desde el {fechaLarga(caso.creado)}
                              {deudor.pedida && ` · Pedida el ${fechaLarga(deudor.pedida)}`}
                              {deudor.saldada && ` · Saldada el ${fechaLarga(deudor.saldada)}`}
                              {abierto && caso.avisar_desde && caso.aviso === "notificar" && ` · Meisam avisa desde el ${fechaLarga(caso.avisar_desde)}`}
                            </p>
                            {abierto && caso.aviso && AVISO_SUTIL[caso.aviso] && <p className="pequeno tenue">{AVISO_SUTIL[caso.aviso]}</p>}
                            {deudor.estado === "saldada" && (
                              <p className="pequeno">
                                Saldada {deudor.via_saldado ? VIA_SALDADO[deudor.via_saldado] ?? "" : ""}
                                {deudor.motivo_saldado && <> · «{textoVisible(deudor.motivo_saldado)}»</>}
                              </p>
                            )}
                            {caso.acuerdos && caso.acuerdos.length > 0 && (
                              <p className="pequeno tenue">Acordado: {caso.acuerdos.map((a) => textoVisible(a)).join(" · ")}</p>
                            )}
                            <AccionesDeudor usuarioId={usuarioId} caso={caso} deudor={deudor} nombre={nombre} alHecho={alHecho} />
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <p className="pequeno tenue">
          Guardo solo el nombre abreviado, el importe y el estado. La relación la indicas tú. Puedes verlo y borrarlo en{" "}
          <Link href="/app/aprendido">Lo que he aprendido de ti</Link>.
        </p>
      </section>
    </>
  );
}
