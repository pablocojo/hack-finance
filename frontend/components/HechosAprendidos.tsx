"use client";

import { useCallback, useEffect, useState } from "react";
import { aprendido, borrarAmigo, borrarConversacionesCaso, borrarHecho, casos, editarHecho, olvidarTodo } from "@/lib/api";
import type { AprendidoRespuesta, CasoResumen } from "@/lib/api";
import { eur, fechaLarga, nombreVisible, textoVisible } from "@/lib/formato";

const ORIGEN: Record<string, string> = {
  feedback: "Por tus respuestas",
  preferencia: "Por tus preferencias",
  amigos: "Sobre tus amigos",
  voz: "De una llamada",
  ajustes: "De tus ajustes",
  perfil: "De tu perfil",
};
const AMBITO: Record<string, string> = { tipo: "Tipo de aviso", comercio: "Comercio", contacto: "Persona" };
const ESTADO_AMIGO: Record<string, string> = {
  detectado: "Detectada",
  pedido: "Pedida por Bizum",
  saldado: "Saldada",
  olvidado: "Olvidada",
  caducado: "Caducada",
};

const mensaje = (fallo: unknown) => (fallo instanceof Error ? fallo.message : String(fallo));

export default function HechosAprendidos({ usuarioId }: { usuarioId: string }) {
  const [datos, setDatos] = useState<AprendidoRespuesta | null>(null);
  const [listaCasos, setListaCasos] = useState<CasoResumen[]>([]);
  const [cargado, setCargado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmarTodo, setConfirmarTodo] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setDatos(await aprendido(usuarioId));
    } catch (fallo) {
      setError(mensaje(fallo));
    }
    // Las conversaciones de los casos todavía no tienen ruta: sin ella, la lista queda vacía.
    setListaCasos(await casos(usuarioId).catch(() => []));
    setCargado(true);
  }, [usuarioId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function ejecutar(tarea: () => Promise<unknown>, textoError?: string) {
    setOcupado(true);
    setError(null);
    try {
      await tarea();
      await cargar();
      return true;
    } catch (fallo) {
      setError(textoError ?? mensaje(fallo));
      return false;
    } finally {
      setOcupado(false);
    }
  }

  if (!cargado) {
    return (
      <p className="tenue" role="status">
        Cargando lo que he aprendido…
      </p>
    );
  }

  const conConversacion = listaCasos.filter((c) => c.conversaciones.length > 0);
  const hechos = datos?.hechos ?? [];
  const silencios = datos?.silencios ?? [];
  const amigos = datos?.amigos ?? [];
  const todoVacio = hechos.length + silencios.length + amigos.length + conConversacion.length === 0;

  return (
    <>
      {error && (
        <p className="error banda" role="alert">
          {error}
        </p>
      )}

      <section className="bloque" aria-labelledby="t-hechos">
        <h2 id="t-hechos">Lo que he ido aprendiendo</h2>
        <p className="tenue pequeno">Cada cosa que Meisam recuerda de ti. Apágala para que no la use o bórrala para siempre.</p>
        {hechos.length === 0 ? (
          <p className="vacio-bandeja">Todavía no he aprendido nada. Cuando respondas a un aviso, aparecerá aquí.</p>
        ) : (
          <ul className="frases">
            {hechos.map((h) => (
              <li key={h.id} className={`frase${h.activo ? "" : " apagado"}`}>
                <p>{textoVisible(h.texto)}</p>
                <p className="pequeno tenue">
                  {ORIGEN[h.origen] ?? h.origen} · {fechaLarga(h.creado)}
                  {!h.activo && " · Apagado"}
                </p>
                <div className="fila-botones">
                  <label className="interruptor-simple">
                    <input
                      type="checkbox"
                      checked={h.activo}
                      disabled={ocupado}
                      onChange={(e) => ejecutar(() => editarHecho(usuarioId, h.id, { activo: e.target.checked }))}
                    />
                    <span>Usar esto</span>
                    <span className="solo-lectores">: {textoVisible(h.texto)}</span>
                  </label>
                  <button type="button" className="boton-texto peligro" disabled={ocupado} onClick={() => ejecutar(() => borrarHecho(usuarioId, h.id))}>
                    Borrar<span className="solo-lectores">: {textoVisible(h.texto)}</span>
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bloque" aria-labelledby="t-silencios">
        <h2 id="t-silencios">Avisos que has silenciado</h2>
        {silencios.length === 0 ? (
          <p className="vacio-bandeja">No has silenciado nada.</p>
        ) : (
          <ul className="frases">
            {silencios.map((s, i) => (
              <li key={`${s.ambito}-${s.valor}-${i}`} className="frase">
                <p>
                  {AMBITO[s.ambito] ?? s.ambito}: <strong>{nombreVisible(s.valor)}</strong>
                </p>
                <p className="pequeno tenue">Desde {fechaLarga(s.desde)}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bloque" aria-labelledby="t-amigos">
        <h2 id="t-amigos">Lo que guardo sobre tus amigos</h2>
        <p className="tenue pequeno">Solo nombre abreviado, importe y estado. Nunca guardo los conceptos de tus Bizums.</p>
        {amigos.length === 0 ? (
          <p className="vacio-bandeja">No guardo nada sobre amigos.</p>
        ) : (
          <ul className="frases">
            {amigos.map((a) => (
              <li key={`${a.contraparte}-${a.creado}`} className="frase">
                <p>
                  <strong>{nombreVisible(a.contraparte)}</strong> · {eur(a.saldo)} · {ESTADO_AMIGO[a.estado] ?? a.estado}
                </p>
                <p className="pequeno tenue">Desde {fechaLarga(a.creado)}</p>
                <div className="fila-botones">
                  <button
                    type="button"
                    className="boton-texto peligro"
                    disabled={ocupado}
                    onClick={() =>
                      ejecutar(
                        () => borrarAmigo(usuarioId, a.contraparte),
                        "Todavía no se puede borrar a una persona suelta. Con «Olvidar todo» se borra todo lo guardado.",
                      )
                    }
                  >
                    Borrar<span className="solo-lectores"> a {nombreVisible(a.contraparte)}</span>
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bloque" aria-labelledby="t-conversaciones">
        <h2 id="t-conversaciones">Conversaciones de tus casos</h2>
        <p className="tenue pequeno">Resumen de lo que hablaste con Meisam sobre cada deuda, con los datos de terceros abreviados.</p>
        {conConversacion.length === 0 ? (
          <p className="vacio-bandeja">No guardo ninguna conversación.</p>
        ) : (
          <ul className="frases">
            {conConversacion.map((c) => (
              <li key={c.id} className="frase">
                <p className="pequeno tenue">
                  Caso del {fechaLarga(c.creado)} con {c.deudores.map((d) => nombreVisible(d.contraparte)).join(", ") || "tus amigos"}
                </p>
                <ul className="resumenes">
                  {c.conversaciones.map((t, i) => (
                    <li key={i}>{textoVisible(t)}</li>
                  ))}
                </ul>
                <div className="fila-botones">
                  <button
                    type="button"
                    className="boton-texto peligro"
                    disabled={ocupado}
                    onClick={() => ejecutar(() => borrarConversacionesCaso(usuarioId, c.id))}
                  >
                    Borrar estas conversaciones
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bloque zona-peligro" aria-labelledby="t-olvidar">
        <h2 id="t-olvidar">Olvidar todo</h2>
        <p className="tenue pequeno">Meisam borra todo lo aprendido y empieza de cero. Seguirás con los módulos que tengas activados.</p>
        {confirmarTodo ? (
          <>
            <p role="alert">Se borra todo lo aprendido, sin poder deshacerlo. ¿Seguro?</p>
            <div className="fila-botones">
              <button
                type="button"
                className="boton-secundario peligro"
                disabled={ocupado}
                onClick={async () => {
                  if (await ejecutar(() => olvidarTodo(usuarioId))) setConfirmarTodo(false);
                }}
              >
                Sí, olvidar todo
              </button>
              <button type="button" className="boton-secundario" onClick={() => setConfirmarTodo(false)}>
                No
              </button>
            </div>
          </>
        ) : (
          <button type="button" className="boton-secundario peligro" disabled={ocupado || todoVacio} onClick={() => setConfirmarTodo(true)}>
            Olvidar todo
          </button>
        )}
      </section>
    </>
  );
}
