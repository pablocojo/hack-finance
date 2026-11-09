// Aviso de IA: discreto y siempre visible (decisión de producto: insignia visual, no se dice en voz alta).
export default function InsigniaIA({ texto = "IA" }: { texto?: string }) {
  return (
    <span className="insignia-ia-mini" role="note" aria-label="Contenido generado por inteligencia artificial">
      <span aria-hidden="true" className="insignia-ia-punto" />
      {texto}
    </span>
  );
}
