"use client";

import { useEffect, useRef } from "react";
import IconoMicro from "./IconoMicro";

type Props = {
  titulo?: string;
  alContestar: () => void;
  alEscribir: () => void;
};

// Pantalla previa a la llamada: «Meisam te llama». Contestar es un gesto del usuario (el navegador lo exige para
// el micrófono y el audio) y Prefiero escribir abre el mismo agente en chat, sin gastar minutos de voz.
export default function PreLlamada({ titulo, alContestar, alEscribir }: Props) {
  const contestar = useRef<HTMLButtonElement>(null);
  useEffect(() => contestar.current?.focus(), []);

  return (
    <section className="pre-llamada" aria-labelledby="pre-llamada-titulo">
      <div className="pre-llamada-avatar" aria-hidden="true">
        <span>M</span>
      </div>
      <h1 id="pre-llamada-titulo">Meisam te llama</h1>
      {titulo && <p className="pre-llamada-tema">{titulo}</p>}
      <p className="pequeno tenue">
        Se resuelve en menos de un minuto, hablando o por escrito. Todo lo que se hace aquí es simulado.
      </p>
      <div className="pre-llamada-botones">
        <button ref={contestar} type="button" className="boton-contestar grande" onClick={alContestar}>
          <IconoMicro />
          Contestar por voz
        </button>
        <button type="button" className="boton-secundario grande" onClick={alEscribir}>
          Prefiero escribir
        </button>
      </div>
    </section>
  );
}
