"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { rutaNoDisponible } from "@/lib/api";
import type { CasoResumen, Movimiento } from "@/lib/api";
import { idMovimientoOrigen, nombreContacto, nombreEscenario, pagoDeMovimiento } from "@/lib/cuentas";
import { casos as pedirCasos, esMaqueta, movimientos as pedirMovimientos } from "@/lib/cuentasApi";
import { eur, fechaLarga, nombreCategoria, nombreVisible } from "@/lib/formato";
import FlujoReparto from "./FlujoReparto";

const mensaje = (fallo: unknown) => (fallo instanceof Error ? fallo.message : String(fallo));
// Solo los cargos (importe negativo) pueden pagarse por otras personas; verificaciones y devoluciones no.
const esCargo = (m: Movimiento) => m.importe.trim().startsWith("-") && m.tipo_operacion !== "verificacion" && m.tipo_operacion !== "devolucion";

export default function ListaMovimientos({ usuarioId }: { usuarioId: string }) {
  const [lista, setLista] = useState<Movimiento[] | null>(null);
  const [casos, setCasos] = useState<CasoResumen[]>([]);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [sinRuta, setSinRuta] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [maqueta, setMaqueta] = useState(false);

  const cargar = useCallback(async () => {
    setMaqueta(esMaqueta());
    const [m, c] = await Promise.allSettled([pedirMovimientos(usuarioId), pedirCasos(usuarioId)]);
    if (m.status === "fulfilled") setLista(m.value);
    else {
      setLista([]);
      if (rutaNoDisponible(m.reason)) setSinRuta(true);
      else setError(mensaje(m.reason));
    }
    setCasos(c.status === "fulfilled" ? c.value : []);
  }, [usuarioId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  if (lista === null) {
    return (
      <p className="tenue" role="status">
        Cargando tus movimientos…
      </p>
    );
  }

  // Un pago ya apuntado (no el «quizá fuiste con alguien», que se puede convertir) muestra su estado en vez del botón.
  const apuntado = (m: Movimiento) => casos.find((c) => c.escenario !== "pago_individual" && idMovimientoOrigen(c.movimiento_origen) === m.id && c.deudores.length > 0);

  return (
    <>
      {error && (
        <p className="error banda" role="alert">
          {error}
        </p>
      )}
      {maqueta && <p className="nota-bloque pequeno">Datos de ejemplo (maqueta). Nada de esto viene del servidor.</p>}
      {sinRuta && (
        <p className="nota-bloque pequeno" role="status">
          La lista de movimientos todavía no está disponible en el servidor. Cuando lo esté, podrás apuntar aquí un pago hecho por otras personas.
        </p>
      )}

      <section className="bloque" aria-labelledby="t-movs">
        <h2 id="t-movs">Últimos movimientos</h2>
        <p className="tenue pequeno">
          Si pagaste algo por otra persona o con otras personas, apúntalo y Meisam se encarga de acordarse. Lo ves después en{" "}
          <Link href="/app/cuentas">Mis cuentas</Link>.
        </p>
        {lista.length === 0 && !sinRuta ? (
          <p className="vacio-bandeja">No hay movimientos que mostrar.</p>
        ) : (
          <ul className="frases">
            {lista.map((m) => {
              const caso = apuntado(m);
              const abierta = abierto === m.id;
              const titulo = nombreVisible(m.comercio || m.contraparte || m.concepto);
              return (
                <li key={m.id} className="frase movimiento">
                  <div className="movimiento-fila">
                    <div>
                      <p className="amigo-nombre">{titulo}</p>
                      <p className="pequeno tenue">
                        {fechaLarga(m.fecha)}
                        {m.categoria && ` · ${nombreCategoria(m.categoria)}`}
                      </p>
                    </div>
                    <p className={`movimiento-importe${esCargo(m) ? "" : " positivo"}`}>{eur(m.importe)}</p>
                  </div>
                  {caso ? (
                    <p className="pequeno">
                      <span className="estado-amigo">{nombreEscenario(caso.escenario)}</span>{" "}
                      con {caso.deudores.map((d) => nombreContacto({ contraparte: d.contraparte })).join(", ")}.{" "}
                      <Link href="/app/cuentas">Ver en Mis cuentas</Link>
                    </p>
                  ) : (
                    esCargo(m) &&
                    !abierta && (
                      <button type="button" className="boton-secundario" onClick={() => setAbierto(m.id)}>
                        He pagado por otra persona / con otras personas
                        <span className="solo-lectores">: {titulo}</span>
                      </button>
                    )
                  )}
                  {abierta && (
                    <FlujoReparto
                      usuarioId={usuarioId}
                      pago={pagoDeMovimiento(m)}
                      alCerrar={() => {
                        setAbierto(null);
                        void cargar();
                      }}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
