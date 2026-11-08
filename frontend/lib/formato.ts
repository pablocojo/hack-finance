const euros = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

export function eur(valor: number | null | undefined): string {
  return valor === null || valor === undefined ? "—" : euros.format(valor);
}

export function pct(valor: number | null | undefined): string {
  return valor === null || valor === undefined
    ? "—"
    : `${valor.toLocaleString("es-ES", { maximumFractionDigits: 1 })} %`;
}

export function mesCorto(mes: string): string {
  const [anio, numero] = mes.split("-");
  return `${MESES[Number(numero) - 1] ?? numero} ${anio.slice(2)}`;
}

const CATEGORIAS: Record<string, string> = {
  ingresos: "Ingresos",
  vivienda: "Vivienda",
  suministros: "Suministros",
  supermercado: "Supermercado",
  restaurantes: "Restaurantes",
  transporte: "Transporte",
  suscripciones: "Suscripciones",
  salud: "Salud",
  seguros: "Seguros",
  educacion: "Educación",
  ocio: "Ocio",
  compras: "Compras",
  impuestos: "Impuestos",
  trabajo: "Trabajo",
  transferencias: "Transferencias",
  efectivo: "Efectivo",
  otros: "Otros",
  "sin categoría": "Sin categoría",
};

export function nombreCategoria(categoria: string): string {
  return CATEGORIAS[categoria] ?? categoria;
}

const HERRAMIENTAS: Record<string, string> = {
  resumen_gastos: "Resumen de gastos",
  buscar_movimientos: "Búsqueda de movimientos",
  detectar_anomalias: "Detección de anomalías",
  gastos_recurrentes: "Recibos y suscripciones",
  prevision_saldo: "Previsión de saldo",
  categorizar_movimientos: "Categorización",
  calcular_prestamo: "Calculadora de préstamos",
  interes_compuesto: "Interés compuesto",
  plan_ahorro: "Plan de ahorro",
  regla_50_30_20: "Regla 50/30/20",
  convertir_divisa: "Cambio de divisa",
  precio_accion: "Cotización",
  guardar_preferencia: "Memoria del perfil",
  leer_perfil: "Lectura del perfil",
  web_search: "Búsqueda web",
};

export function nombreHerramienta(nombre: string): string {
  return HERRAMIENTAS[nombre] ?? nombre;
}
