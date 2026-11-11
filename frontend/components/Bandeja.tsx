"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { amigos as pedirAmigos, prepararAccion } from "@/lib/api";
import type { Amigo, CasoResumen, Notificacion, TarjetaConfirmacion } from "@/lib/api";
import { casoAbierto } from "@/lib/cuentas";
import { casos as pedirCasos, esMaqueta } from "@/lib/cuentasApi";
import { esPregunta, fraseResumen, resumenSemanal } from "@/lib/preguntas";
import { eur, nombreVisible, textoVisible } from "@/lib/formato";
import InsigniaIA from "./InsigniaIA";
import PorQue from "./PorQue";
import PreguntaConAlguien from "./PreguntaConAlguien";
import ResumenSemanal from "./ResumenSemanal";
import SelectorPedir from "./SelectorPedir";
import TarjetaAccion from "./TarjetaAccion";

type Pestana = "ahora" | "resumen";
// `hoy`: fecha del reloj simulado, para «quién te pagó esta semana».
type Props = { usuarioId: string; ahora: Notificacion[]; resumen: Notificacion[]; hoy?: string | null; alResolver?: () => void };

const URGENCIA: Record<string, string> = { alta: "Urgente", media: "Importante", baja: "Sin prisa" };

const CLAVE_AHORA_NO = "meisam-preguntas-ahora-no";
const leerAhoraNo = (): string[] => {
  try {
    return JSON.parse(window.sessionStorage.getItem(CLAVE_AHORA_NO) ?? "[]") as string[];
  } catch {
    return [];
  }
};

function sin<T>(registro: Record<string, T>, clave: string): Record<string, T> {
  const copia = { ...registro };
  delete copia[clave];
  return copia;
}

export default function Bandeja({ usuarioId, ahora, resumen, hoy = null, alResolver }: Props) {
  const [pestana, setPestana] = useState<Pestana>("ahora");
  const [tarjetas, setTarjetas] = useState<Record<string, TarjetaConfirmacion>>({});
  const [preparando, setPreparando] = useState<string | null>(null);
  const [errores, setErrores] = useState<Record<string, string>>({});
  // Un aviso resuelto (el amigo pagó, lo saldaste o lo descartaste) no se queda con sus botones: baja al final como
  // «✓ Resuelto» y no cuenta en «Ahora». Sigue en la campana, en «Resueltas».
  const cerrado = (n: Notificacion) => n.estado === "resuelta" || n.estado === "rechazada";
  const ordenar = (ns: Notificacion[]) => [...ns.filter((n) => !cerrado(n)), ...ns.filter(cerrado)];

  // Preguntas de Meisam (¿fuiste con alguien?, ¿con Laura y Marcos?, dudas): casos con aviso `resumen`. Solo viven en esta
  // pestaña, nunca como notificación. Una pregunta ya contestada se conserva en pantalla (con su «Deshacer») hasta la
  // próxima visita aunque el caso ya esté cerrado.
  const [preguntas, setPreguntas] = useState<CasoResumen[]>([]);
  const [todosLosCasos, setTodosLosCasos] = useState<CasoResumen[]>([]);
  const [amigosLista, setAmigosLista] = useState<Amigo[] | null>(null);
  const [ahoraNo, setAhoraNo] = useState<string[]>([]);
  const [respondidas, setRespondidas] = useState<string[]>([]);
  const respondidasRef = useRef<string[]>([]);
  const cargarPreguntas = useCallback(() => {
    Promise.all([pedirCasos(usuarioId), esMaqueta() ? Promise.resolve(null) : pedirAmigos(usuarioId).catch(() => null)])
      .then(([c, a]) => {
        setTodosLosCasos(c);
        setAmigosLista(a);
        const abiertas = c.filter(esPregunta);
        setPreguntas((previas) => {
          const sigue = (id: string) => abiertas.find((k) => k.id === id) ?? (respondidasRef.current.includes(id) ? previas.find((p) => p.id === id) : undefined);
          const mantenidas = previas.map((p) => sigue(p.id)).filter((p): p is CasoResumen => !!p);
          return [...mantenidas, ...abiertas.filter((k) => !previas.some((p) => p.id === k.id))];
        });
      })
      .catch(() => {
        setPreguntas([]); // sin la ruta de casos, el Resumen sigue como antes
        setTodosLosCasos([]);
      });
  }, [usuarioId]);
  useEffect(() => {
    setAhoraNo(leerAhoraNo());
  }, []);
  useEffect(() => {
    cargarPreguntas();
  }, [cargarPreguntas, ahora, resumen, hoy]);
  const visibles = preguntas.filter((k) => !ahoraNo.includes(k.id));
  // Cuando su caso ya está cerrado (todos pagaron, lo saldaste o lo descartaste), el aviso sale de la bandeja: sigue en la
  // campana, en «Resueltas». Mientras el caso siga abierto (p. ej. Bizum pedido y aún sin pagar) se ve como «✓ Hecho».
  const casoDe = (n: Notificacion) =>
    todosLosCasos.find((c) => (c as { propuesta_id?: string | null }).propuesta_id === n.propuesta.id || n.propuesta.id === `prop-preg-${c.id}`);
  const casoCerrado = (n: Notificacion) => {
    const c = casoDe(n);
    return !!c && !casoAbierto(c);
  };
  const lista = ordenar((pestana === "ahora" ? ahora : resumen).filter((n) => !casoCerrado(n)));
  const abiertasAhora = ahora.filter((n) => !cerrado(n) && !casoCerrado(n)).length;
  const pendientes = visibles.filter((k) => !respondidas.includes(k.id));
  const marcarRespondida = (id: string, si: boolean) => {
    respondidasRef.current = si ? [...respondidasRef.current, id] : respondidasRef.current.filter((x) => x !== id);
    setRespondidas(respondidasRef.current);
  };
  const posponer = (id: string) => {
    const nuevo = [...ahoraNo, id];
    window.sessionStorage.setItem(CLAVE_AHORA_NO, JSON.stringify(nuevo));
    setAhoraNo(nuevo);
  };
  const datosResumen = resumenSemanal(amigosLista, todosLosCasos, hoy, pendientes.length);
  const hayResumen = fraseResumen(datosResumen).length > 0;

  // Acceso rápido: sin llamada, prepara la primera acción ofrecida y pinta la misma tarjeta de confirmación.
  // Un aviso con varias personas (p. ej. el cine: Rodrigo y Marta) trae un `pedir_bizum` por persona: un botón para cada
  // una, y se puede pedir a la segunda después de confirmar la primera.
  type Ofrecida = Notificacion["propuesta"]["acciones_ofrecidas"][number];
  const [elegidas, setElegidas] = useState<Record<string, Ofrecida>>({});
  const pedidosDe = (n: Notificacion) => n.propuesta.acciones_ofrecidas.filter((a) => a.accion_id === "pedir_bizum");

  async function accesoRapido({ propuesta }: Notificacion, elegida?: Ofrecida) {
    const accion = elegida ?? propuesta.acciones_ofrecidas[0];
    if (!accion) return;
    setElegidas((e) => ({ ...e, [propuesta.id]: accion }));
    setPreparando(propuesta.id);
    setErrores((e) => sin(e, propuesta.id));
    try {
      const t = await prepararAccion(usuarioId, propuesta.id, accion.accion_id, accion.parametros);
      setTarjetas((ts) => ({ ...ts, [propuesta.id]: t }));
    } catch (fallo) {
      const mensaje = fallo instanceof Error ? fallo.message : String(fallo);
      setErrores((e) => ({ ...e, [propuesta.id]: mensaje }));
    } finally {
      setPreparando(null);
    }
  }

  return (
    <section className="bandeja" aria-label="Avisos de Meisam">
      <div className="pestanas" role="tablist" aria-label="Bandeja">
        {(["ahora", "resumen"] as const).map((p) => (
          <button
            key={p}
            role="tab"
            id={`pestana-${p}`}
            aria-selected={pestana === p}
            aria-controls="panel-bandeja"
            className={`pestana${pestana === p ? " activa" : ""}`}
            onClick={() => setPestana(p)}
          >
            {p === "ahora" ? "Ahora" : "Resumen"}
            <span className="contador">{p === "ahora" ? abiertasAhora : resumen.length + pendientes.length}</span>
          </button>
        ))}
      </div>

      <div id="panel-bandeja" role="tabpanel" aria-live="polite" aria-labelledby={`pestana-${pestana}`} className="lista-avisos">
        {lista.length === 0 && (pestana === "ahora" || (visibles.length === 0 && !hayResumen)) && (
          <p className="vacio-bandeja">
            {pestana === "ahora"
              ? "Nada que resolver ahora. Meisam solo te avisa cuando ahorra o protege."
              : "Todavía no hay nada en el resumen."}
          </p>
        )}
        {pestana === "resumen" && <ResumenSemanal datos={datosResumen} />}
        {pestana === "resumen" &&
          visibles.map((caso) => (
            <PreguntaConAlguien
              key={caso.id}
              usuarioId={usuarioId}
              caso={caso}
              alAhoraNo={() => posponer(caso.id)}
              alResponder={() => marcarRespondida(caso.id, true)}
              alDeshacer={() => marcarRespondida(caso.id, false)}
              alCambiar={cargarPreguntas}
            />
          ))}
        {lista.map((notificacion) => {
          const { propuesta, decision, estado } = notificacion;
          const tarjeta = tarjetas[propuesta.id];
          const primera = propuesta.acciones_ofrecidas[0];
          if (cerrado(notificacion)) {
            return (
              <article key={propuesta.id} className="aviso-tarjeta aviso-cerrado">
                <p className="aviso-resuelto">
                  {estado === "resuelta" ? "✓ Hecho" : "Descartado"}
                  <span className="pequeno tenue">
                    {estado === "resuelta" ? " · lo sigues en Mis cuentas" : " · no hace falta hacer nada"}
                  </span>
                </p>
                <h3>{textoVisible(propuesta.titulo)}</h3>
              </article>
            );
          }
          return (
            <article key={propuesta.id} className={`aviso-tarjeta urgencia-${propuesta.urgencia}`}>
              <header className="aviso-cab">
                <span className="aviso-marca">
                  Meisam <InsigniaIA />
                </span>
                <span className={`urgencia urgencia-${propuesta.urgencia}`}>{URGENCIA[propuesta.urgencia]}</span>
              </header>
              <h3>{textoVisible(propuesta.titulo)}</h3>
              <p className="aviso-mensaje">{textoVisible(propuesta.mensaje_notificacion)}</p>
              {propuesta.valor_estimado_eur && (
                <p className="aviso-valor">
                  <strong>{eur(propuesta.valor_estimado_eur)}</strong>
                  <span> en juego</span>
                </p>
              )}
              {propuesta.contexto_personal && <p className="aviso-contexto">{textoVisible(propuesta.contexto_personal)}</p>}
              {decision.motivos[0] && <p className="aviso-motivo">Por qué te aviso: {textoVisible(decision.motivos[0])}</p>}
              <PorQue usuarioId={usuarioId} propuestaId={propuesta.id} />
              {estado !== "nueva" && <p className="pequeno tenue">Estado: {estado}</p>}
              {pedidosDe(notificacion).length > 1 ? (
                <>
                  <SelectorPedir usuarioId={usuarioId} notificacion={notificacion} alHecho={() => alResolver?.()} />
                  <div className="aviso-botones">
                    <Link href={`/app/llamada/${encodeURIComponent(propuesta.id)}`} className="enlace-boton grande">
                      Resolver hablando
                    </Link>
                  </div>
                </>
              ) : tarjeta ? (
                <TarjetaAccion
                  tarjeta={tarjeta}
                  usuarioId={usuarioId}
                  parametrosBase={(elegidas[propuesta.id] ?? primera)?.parametros}
                  alResultado={() => alResolver?.()}
                  alAhoraNo={() => setTarjetas((ts) => sin(ts, propuesta.id))}
                  alCambiarTarjeta={(t) => setTarjetas((ts) => ({ ...ts, [propuesta.id]: t }))}
                />
              ) : (
                <div className="aviso-botones">
                  <Link href={`/app/llamada/${encodeURIComponent(propuesta.id)}`} className="enlace-boton grande">
                    Resolver
                  </Link>
                  {primera && (
                    <button
                      type="button"
                      className="boton-secundario grande"
                      disabled={preparando === propuesta.id}
                      onClick={() => accesoRapido(notificacion)}
                    >
                      Hacerlo ya
                    </button>
                  )}
                </div>
              )}
              {errores[propuesta.id] && (
                <p className="error" role="alert">
                  {errores[propuesta.id]}
                </p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
