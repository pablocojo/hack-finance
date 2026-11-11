"use client";

import { useEffect, useRef } from "react";
import IconoMicro from "./IconoMicro";

type Props = {
  titulo?: string;
  general?: boolean; // conversación sin aviso («Hablar con Meisam»)
  alContestar: () => void;
  alEscribir: () => void;
};

// Pantalla previa a la llamada: «Meisam te llama». Contestar es un gesto del usuario (el navegador lo exige para
// el micrófono y el audio) y Prefiero escribir abre el mismo agente en chat, sin gastar minutos de voz.
export default function PreLlamada({ titulo, general = false, alContestar, alEscribir }: Props) {
  const contestar = useRef<HTMLButtonElement>(null);
  useEffect(() => contestar.current?.focus(), []);

  return (
    <section className="pre-llamada" aria-labelledby="pre-llamada-titulo">
      <div className="pre-llamada-avatar" aria-hidden="true">
        <span>M</span>
      </div>
      <h1 id="pre-llamada-titulo">{general ? "Habla con Meisam" : "Meisam te llama"}</h1>
      {titulo && <p className="pre-llamada-tema">{titulo}</p>}
      <p className="pequeno tenue">
        {general
          ? "Pregúntale por tus cuentas con amigos o pídele cambios, hablando o por escrito. Todo lo que se hace aquí es simulado."
          : "Se resuelve en menos de un minuto, hablando o por escrito. Todo lo que se hace aquí es simulado."}
      </p>
      <div className="pre-llamada-botones">
        <button ref={contestar} type="button" className="boton-contestar grande" onClick={alContestar}>
          <IconoMicro />
          {general ? "Hablar por voz" : "Contestar por voz"}
        </button>
        <button type="button" className="boton-secundario grande" onClick={alEscribir}>
          Prefiero escribir
        </button>
      </div>
    </section>
  );
}
