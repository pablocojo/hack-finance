"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { amigos as pedirAmigos, aprendido } from "@/lib/api";
import type { Amigo } from "@/lib/api";
import { eur, fechaLarga, nombreVisible } from "@/lib/formato";

const ESTADO: Record<string, string> = {
  detectado: "Detectada",
  pedido: "Pedida por Bizum",
  saldado: "Saldada",
  olvidado: "Olvidada",
  caducado: "Caducada",
};

// Maqueta para enseñar la pantalla sin backend: se activa con /app/amigos?mock=1 y nunca por defecto.
const MOCK: Amigo[] = [
  { contraparte: "Marcos R.", saldo: "18.50", propuesta_origen: "mock-1", estado: "pedido", creado: "2026-11-02", pedido: "2026-11-04" },
  { contraparte: "Lucía M.", saldo: "12.00", propuesta_origen: "mock-2", estado: "detectado", creado: "2026-11-08" },
  { contraparte: "Daniel S.", saldo: "0.00", propuesta_origen: "mock-3", estado: "saldado", creado: "2026-10-20", pedido: "2026-10-22", saldado: "2026-10-23" },
];

// El saldo es lo que te debe esa persona: positivo = te debe, negativo = le debes. Todo en céntimos enteros.
function centimosConSigno(saldo: string): number {
  const negativo = saldo.trim().startsWith("-");
  const [e, d = "0"] = saldo.replace("-", "").split(".");
  const c = Number(e) * 100 + Number(d.padEnd(2, "0").slice(0, 2));
  return negativo ? -c : c;
}
const comoEuros = (c: number) => `${c < 0 ? "-" : ""}${Math.floor(Math.abs(c) / 100)}.${String(Math.abs(c) % 100).padStart(2, "0")}`;

function fraseSaldo(saldo: string): string {
  const c = centimosConSigno(saldo);
  if (c > 0) return `Te debe ${eur(comoEuros(c))}`;
  if (c < 0) return `Le debes ${eur(comoEuros(-c))}`;
  return "Cuentas al día";
}

export default function SaldosAmigos({ usuarioId }: { usuarioId: string }) {
  const [lista, setLista] = useState<Amigo[] | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    async function cargar() {
      if (new URLSearchParams(window.location.search).get("mock") === "1") {
        setAviso("Datos de ejemplo (maqueta).");
        setLista(MOCK);
        return;
      }
      try {
        const r = await pedirAmigos(usuarioId);
        if (vigente) setLista(r);
        return;
      } catch {
        // La ruta /amigos puede no estar disponible todavía: se usa lo que ya devuelve «lo aprendido».
      }
      try {
        const r = await aprendido(usuarioId);
        if (vigente) setLista(r.amigos.map((a) => ({ ...a, propuesta_origen: "" })));
      } catch (fallo) {
        if (vigente) {
          setError(fallo instanceof Error ? fallo.message : String(fallo));
          setLista([]);
        }
      }
    }
    void cargar();
    return () => {
      vigente = false;
    };
  }, [usuarioId]);

  if (lista === null) {
    return (
      <p className="tenue" role="status">
        Cargando tus cuentas…
      </p>
    );
  }

  const pendientes = lista.filter((a) => (a.estado === "detectado" || a.estado === "pedido") && centimosConSigno(a.saldo) > 0);
  const totalPendiente = pendientes.reduce((suma, a) => suma + centimosConSigno(a.saldo), 0);

  return (
    <>
      {error && (
        <p className="error banda" role="alert">
          {error}
        </p>
      )}
      {aviso && <p className="nota-bloque pequeno">{aviso}</p>}

      <section className="bloque resumen-deudas" aria-labelledby="t-resumen-amigos">
        <h2 id="t-resumen-amigos">Quién te debe</h2>
        {pendientes.length > 0 ? (
          <p className="total-deuda">
            <strong>{eur(comoEuros(totalPendiente))}</strong>
            <span>
              {" "}
              pendientes entre {pendientes.length} {pendientes.length === 1 ? "persona" : "personas"}
            </span>
          </p>
        ) : (
          <p className="vacio-bandeja">Nadie te debe nada ahora mismo.</p>
        )}
      </section>

      <section className="bloque" aria-labelledby="t-cuentas">
        <h2 id="t-cuentas">Cómo van las cuentas</h2>
        {lista.length === 0 ? (
          <p className="vacio-bandeja">
            Aún no hay cuentas con tus amigos. Cuando Meisam detecte una cena o un gasto compartido, lo verás aquí con su
            estado.
          </p>
        ) : (
          <ul className="frases">
            {lista.map((a) => (
              <li key={`${a.contraparte}-${a.creado}-${a.propuesta_origen}`} className="frase fila-amigo">
                <div className="amigo-datos">
                  <p className="amigo-nombre">{nombreVisible(a.contraparte)}</p>
                  <p className="amigo-saldo">{fraseSaldo(a.saldo)}</p>
                </div>
                <div className="amigo-estado">
                  <span className={`estado-amigo estado-${a.estado}`}>{ESTADO[a.estado] ?? a.estado}</span>
                  <p className="pequeno tenue">
                    Detectada el {fechaLarga(a.creado)}
                    {a.pedido && ` · Pedida el ${fechaLarga(a.pedido)}`}
                    {a.saldado && ` · Saldada el ${fechaLarga(a.saldado)}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="pequeno tenue">
          Guardo solo el nombre abreviado, el importe y el estado. Puedes verlo y borrarlo en{" "}
          <Link href="/app/aprendido">Lo que he aprendido de ti</Link>.
        </p>
      </section>
    </>
  );
}
