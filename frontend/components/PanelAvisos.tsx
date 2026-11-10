"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useState } from "react";
import type { CasoResumen } from "@/lib/api";
import { casoDeResumen, casoSilencioso, esAhora, esResumen, FILTROS, pasaFiltro } from "@/lib/avisos";
import type { FiltroAvisos } from "@/lib/avisos";
import { casoAbierto, nombreEscenario, pagoDeCaso, preguntaDeCaso } from "@/lib/cuentas";
import { casos as pedirCasos } from "@/lib/cuentasApi";
import { eur, fechaLarga, textoVisible } from "@/lib/formato";
import { useAvisos } from "./AvisosProvider";
import EntradaAviso from "./EntradaAviso";
import InsigniaIA from "./InsigniaIA";

// Historial de avisos: ahora (nuevas, vistas y resueltas), resumen y, aparte y sin contador, los casos silenciosos
// que merecen una línea. Todo lo que se ve ya viene decidido por el backend.
export default function PanelAvisos({ usuarioId }: { usuarioId: string }) {
  const { lista, cargado, sinVer, refrescar, permiso, navegadorActivo, activarNavegador, cambiarNavegadorActivo } = useAvisos();
  const [filtro, setFiltro] = useState<FiltroAvisos>("todas");
  const [casos, setCasos] = useState<CasoResumen[]>([]);
  const idAviso = useId();

  const cargarCasos = useCallback(() => {
    pedirCasos(usuarioId)
      .then((c) => setCasos(c.filter((k) => casoAbierto(k) && k.deudores.length === 0 && (casoSilencioso(k) || casoDeResumen(k)))))
      .catch(() => setCasos([])); // sin la ruta de casos, el panel sigue con las notificaciones
  }, [usuarioId]);
  useEffect(() => {
    cargarCasos();
  }, [cargarCasos, lista]);

  const alCambiar = useCallback(() => {
    void refrescar();
    cargarCasos();
  }, [refrescar, cargarCasos]);

  const ahora = lista.filter((n) => esAhora(n) && pasaFiltro(n, filtro));
  const resumen = lista.filter((n) => esResumen(n) && pasaFiltro(n, filtro));
  // Los casos solo están abiertos: no aparecen en «Resueltas».
  const enResumen = filtro === "resueltas" ? [] : casos.filter(casoDeResumen);
  const silenciosos = filtro === "resueltas" ? [] : casos.filter(casoSilencioso);
  const hayAlgo = ahora.length + resumen.length + enResumen.length + silenciosos.length > 0;

  return (
    <div className="panel-avisos">
      <p className="pequeno tenue">
        Aquí queda todo lo que Meisam te ha contado. Solo te llega una notificación cuando algo ahorra o protege; el resto lo ves al entrar.
      </p>

      <section className="bloque avisos-navegador" aria-labelledby={`${idAviso}-nav`}>
        <h2 id={`${idAviso}-nav`}>Avisos del navegador</h2>
        {permiso === "no_soportado" && <p className="pequeno tenue">Este navegador no admite notificaciones. Seguirás viendo los avisos aquí y en la campana.</p>}
        {permiso === "por_pedir" && (
          <>
            <p className="pequeno tenue">
              Si quieres, Meisam puede avisarte con una notificación del navegador cuando llegue algo importante y tengas la app abierta. Nunca se pide solo.
            </p>
            <button type="button" className="boton-secundario grande" onClick={() => void activarNavegador()}>
              Activar avisos del navegador
            </button>
          </>
        )}
        {permiso === "denegado" && (
          <p className="pequeno tenue">
            Los avisos del navegador están bloqueados. Puedes permitirlos desde los ajustes del sitio en tu navegador; mientras tanto verás los avisos aquí.
          </p>
        )}
        {permiso === "concedido" && (
          <label className="interruptor-simple">
            <input type="checkbox" checked={navegadorActivo} onChange={(e) => cambiarNavegadorActivo(e.target.checked)} />
            Enviar avisos al navegador
          </label>
        )}
      </section>

      <div className="filtros-avisos" role="group" aria-label="Filtrar avisos">
        {FILTROS.map((f) => (
          <button key={f.id} type="button" className={`chip filtro${filtro === f.id ? " activo" : ""}`} aria-pressed={filtro === f.id} onClick={() => setFiltro(f.id)}>
            {f.texto}
          </button>
        ))}
      </div>

      {!cargado && <p className="vacio-bandeja" role="status">Cargando avisos…</p>}
      {cargado && !hayAlgo && (
        <p className="vacio-bandeja">
          {filtro === "resueltas"
            ? "Todavía no has resuelto ningún aviso."
            : filtro === "pendientes"
              ? "No tienes nada pendiente. Meisam solo te avisa cuando ahorra o protege."
              : "Todavía no hay avisos. Meisam solo te avisa cuando ahorra o protege."}
        </p>
      )}

      {ahora.length > 0 && (
        <section className="seccion-avisos" aria-labelledby={`${idAviso}-ahora`}>
          <h2 id={`${idAviso}-ahora`}>
            Avisos de ahora{" "}
            {sinVer > 0 && <span className="pequeno tenue">({sinVer === 1 ? "1 sin ver" : `${sinVer} sin ver`})</span>}
          </h2>
          {ahora.map((n) => (
            <EntradaAviso key={n.propuesta.id} usuarioId={usuarioId} notificacion={n} alCambiar={alCambiar} />
          ))}
        </section>
      )}

      {resumen.length + enResumen.length > 0 && (
        <section className="seccion-avisos" aria-labelledby={`${idAviso}-resumen`}>
          <h2 id={`${idAviso}-resumen`}>En el resumen</h2>
          {enResumen.map((k) => (
            <LineaCaso key={k.id} caso={k} />
          ))}
          {resumen.map((n) => (
            <EntradaAviso key={n.propuesta.id} usuarioId={usuarioId} notificacion={n} alCambiar={alCambiar} />
          ))}
        </section>
      )}

      {silenciosos.length > 0 && (
        <section className="seccion-avisos" aria-labelledby={`${idAviso}-calma`}>
          <h2 id={`${idAviso}-calma`}>Para revisar con calma</h2>
          <p className="pequeno tenue">Sin aviso ni contador: Meisam no te molesta por esto. Míralo cuando quieras.</p>
          {silenciosos.map((k) => (
            <LineaCaso key={k.id} caso={k} />
          ))}
        </section>
      )}

      <p className="pequeno tenue">
        <InsigniaIA /> Meisam decide qué te cuenta y te explica por qué; tú puedes corregirlo en «Ver todos los motivos» o en{" "}
        <Link href="/app/aprendido">Lo que he aprendido de ti</Link>.
      </p>
    </div>
  );
}

// Una línea para un caso de deuda dudoso («Quizá fuiste con alguien»): lleva a «Mis cuentas», donde se aclara.
function LineaCaso({ caso }: { caso: CasoResumen }) {
  const pago = pagoDeCaso(caso);
  return (
    <article className="pregunta-tarjeta linea-caso">
      <p className="aviso-marca">{nombreEscenario(caso.escenario)}</p>
      <h3>{textoVisible(preguntaDeCaso(caso, pago))}</h3>
      {pago && (pago.importe || pago.fecha) && (
        <p className="pequeno tenue">
          {pago.importe && eur(pago.importe)}
          {pago.importe && pago.fecha && " · "}
          {pago.fecha && fechaLarga(pago.fecha)}
        </p>
      )}
      <Link href="/app/cuentas" className="boton-texto">
        Aclararlo en Mis cuentas
      </Link>
    </article>
  );
}
