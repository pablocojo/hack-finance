"use client";

import { useState } from "react";
import type { CasoResumen, Movimiento } from "@/lib/api";
import { centimosAbs, comoEuros, pagoDeCaso, preguntaDeCaso } from "@/lib/cuentas";
import { eur, fechaLarga, nombreVisible } from "@/lib/formato";
import { tipoPregunta } from "@/lib/preguntas";
import type { TipoPregunta } from "@/lib/preguntas";
import { aplicarRespuesta } from "@/lib/respuestasCaso";
import FlujoReparto from "./FlujoReparto";
import PreguntaMeisam from "./PreguntaMeisam";
import type { RespuestaFija } from "./PreguntaMeisam";

type Props = {
  usuarioId: string;
  caso: CasoResumen;
  // Movimientos ya conocidos, por si `movimiento_origen` solo trae el id.
  movimientos?: Movimiento[];
  // Si se pasa, aparece «Ahora no» (el Resumen lo usa; «Mis cuentas» no lo necesita).
  alAhoraNo?: () => void;
  alCambiar: () => void;
  // Se contestó con una respuesta fija / se deshizo (el Resumen conserva la tarjeta para mostrar el «Deshacer»).
  alResponder?: () => void;
  alDeshacer?: () => void;
};

// «Fuiste con Laura y Marcos» a partir de la sugerencia (claves de personas -> nombres de pila).
function listaDeNombres(claves: string[]): string {
  const n = claves.map((c) => nombreVisible(c).split(" ")[0]);
  return n.length <= 1 ? (n[0] ?? "") : `${n.slice(0, -1).join(", ")} y ${n[n.length - 1]}`;
}

// Cuotas iguales -> un solo importe por persona para `con_personas`; si no son iguales, no se puede decir con una acción.
function cuotaUnica(cuotas: Record<string, string> | undefined, claves: string[]): number | null | "desigual" {
  const valores = claves.map((c) => cuotas?.[c]).filter((v): v is string => !!v);
  if (valores.length === 0) return null; // nivel 2: las pone el servidor (a partes iguales)
  const centimos = valores.map(centimosAbs);
  return valores.length === claves.length && centimos.every((c) => c === centimos[0]) ? Number(comoEuros(centimos[0])) : "desigual";
}

// Pregunta del Resumen sobre un caso: «¿Fuiste con alguien?» (nivel 1), «¿Fuiste con Laura y Marcos?» (nivel 2) o la
// duda pendiente de un caso dudoso. Cada una con 2-4 respuestas fijas y «Otra respuesta» (el chat con ese caso como contexto).
export default function PreguntaConAlguien({ usuarioId, caso, movimientos, alAhoraNo, alCambiar, alResponder, alDeshacer }: Props) {
  const [reparto, setReparto] = useState(false);
  const pago = pagoDeCaso(caso, movimientos);
  const tipo: TipoPregunta = tipoPregunta(caso) ?? (caso.estado === "dudoso" ? "duda" : "individual");
  const sugerencia = tipo === "sugerida" ? caso.sugerencia : null;

  const accion = (id: string, etiqueta: string, a: Parameters<typeof aplicarRespuesta>[2], campos: Parameters<typeof aplicarRespuesta>[3], principal = false): RespuestaFija => ({
    id,
    etiqueta,
    principal,
    alElegir: () => aplicarRespuesta(usuarioId, caso.id, a, campos),
  });
  const abrirReparto: RespuestaFija = { id: "con", etiqueta: tipo === "sugerida" ? "Otros" : "Sí, con…", principal: tipo !== "sugerida", alElegir: async () => (setReparto(true), null) };
  const ibaSolo = accion("solo", "Iba solo", "iba_solo", {});
  const nadie = accion("nadie", "Nadie me debe", "nadie_me_debe", {});

  let respuestas: RespuestaFija[];
  if (tipo === "duda") {
    respuestas = [accion("si", "Sí", "responder_duda", { respuesta: "si" }, true), accion("no", "No", "responder_duda", { respuesta: "no" })];
  } else if (sugerencia) {
    const cuota = cuotaUnica(sugerencia.cuotas, sugerencia.personas);
    const si: RespuestaFija =
      cuota === "desigual"
        ? { id: "si", etiqueta: "Sí", principal: true, alElegir: async () => (setReparto(true), null) } // cuotas distintas: se revisan en el reparto
        : accion("si", "Sí", "con_personas", { persona: sugerencia.personas.map(nombreVisible).join(", "), ...(cuota ? { importe: cuota } : {}) }, true);
    respuestas = [si, abrirReparto, ibaSolo, nadie];
  } else {
    respuestas = [abrirReparto, ibaSolo, nadie];
  }

  const detalle = pago && (pago.importe || pago.fecha) ? [pago.importe && eur(pago.importe), pago.fecha && fechaLarga(pago.fecha)].filter(Boolean).join(" · ") : null;
  const pregunta = sugerencia ? `¿Fuiste con ${listaDeNombres(sugerencia.personas)}?` : preguntaDeCaso(caso, pago);

  return (
    <PreguntaMeisam
      pregunta={pregunta}
      detalle={sugerencia && pago ? [pago.comercio !== "este pago" && nombreVisible(pago.comercio), detalle].filter(Boolean).join(" · ") : detalle}
      respuestas={respuestas}
      otraRespuestaHref={`/app/hablar?caso=${encodeURIComponent(caso.id)}`}
      flujo={
        reparto && pago ? (
          <FlujoReparto
            usuarioId={usuarioId}
            pago={pago}
            elegidosIniciales={sugerencia?.personas}
            alCerrar={() => {
              setReparto(false);
              alCambiar();
            }}
          />
        ) : undefined
      }
      alAhoraNo={alAhoraNo}
      // Con `alResponder` (el Resumen) la tarjeta se conserva con su «Deshacer» y se refrescan saldos y resumen.
      // Sin él («Mis cuentas») la lista se actualiza en la próxima carga, como siempre.
      alResponder={() => {
        if (!alResponder) return;
        alResponder();
        alCambiar();
      }}
      alDeshacer={() => {
        alDeshacer?.();
        if (alResponder) alCambiar();
      }}
    />
  );
}
