// Micrófono en SVG (hereda el color del texto). Con `apagado` lleva una barra: micrófono silenciado.
export default function IconoMicro({ apagado = false, tamano = 22 }: { apagado?: boolean; tamano?: number }) {
  return (
    <svg
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3" />
      {apagado && <path d="M4 4l16 16" />}
    </svg>
  );
}
