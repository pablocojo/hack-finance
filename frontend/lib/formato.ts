const euros = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

// Acepta las cadenas decimales de la API ("24.00"): Intl las formatea tal cual, sin pasar por float.
export function eur(valor: number | string | null | undefined): string {
  return valor === null || valor === undefined || valor === "" ? "—" : euros.format(valor as number);
}

export function fechaLarga(iso: string): string {
  const [anio, mes, dia] = iso.slice(0, 10).split("-");
  return `${Number(dia)} ${MESES[Number(mes) - 1] ?? mes} ${anio}`;
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

// Siglas que se dejan en mayúsculas al convertir claves del motor en nombres legibles.
const SIGLAS = new Set(["IA", "ES", "IBAN", "SEPA", "PSD2", "BBVA", "DNI", "EUR", "UE", "IVA", "SA", "SL", "ATM"]);
const MINUSCULAS = new Set(["de", "del", "la", "las", "el", "los", "y", "en", "a"]);

// Solo para mostrar: «MARCOS R» -> «Marcos R.», «LA TASCA» -> «La Tasca». La clave original no se toca.
export function nombreVisible(clave: string | null | undefined): string {
  if (!clave) return "";
  const limpia = clave.trim().replace(/\s+/g, " ");
  if (limpia !== limpia.toUpperCase() || !/[A-ZÁÉÍÓÚÜÑ]/.test(limpia)) return limpia;
  const palabras = limpia.split(" ");
  return palabras
    .map((palabra, i) => {
      if (SIGLAS.has(palabra)) return palabra;
      if (palabra.length === 1 && i === palabras.length - 1 && i > 0) return `${palabra}.`;
      const minuscula = palabra.toLowerCase();
      if (i > 0 && MINUSCULAS.has(minuscula)) return minuscula;
      return minuscula.charAt(0).toUpperCase() + minuscula.slice(1);
    })
    .join(" ");
}

// Igual, pero dentro de una frase: busca tramos de palabras en mayúsculas («en LA TASCA», «a MARCOS R»).
const TRAMO = /\b[A-ZÁÉÍÓÚÜÑ]{2,}(?:\s+(?:[A-ZÁÉÍÓÚÜÑ]{2,}|[A-ZÁÉÍÓÚÜÑ]\b))*/g;
export function textoVisible(texto: string | null | undefined): string {
  if (!texto) return "";
  return texto.replace(TRAMO, (tramo, posicion: number, entero: string) => {
    const visible = nombreVisible(tramo);
    // Si la frase ya trae el punto de la inicial («MARCOS R.»), no se duplica.
    return visible.endsWith(".") && !tramo.endsWith(".") && entero[posicion + tramo.length] === "." ? visible.slice(0, -1) : visible;
  });
}

// Lo que escribe el usuario («12,5», «1.000,00», «12.50 €») pasa a cadena decimal con 2 decimales («12.50»),
// sin convertir a float. Devuelve null si no es un importe.
export function importeDeTexto(texto: string): string | null {
  let t = texto.replace(/[€\s]/g, "");
  if (!/^[\d.,]+$/.test(t)) return null;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if ((t.match(/\./g) ?? []).length > 1 || /^\d{1,3}\.\d{3}$/.test(t)) t = t.replace(/\./g, "");
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(t);
  if (!m) return null;
  return `${m[1].replace(/^0+(?=\d)/, "")}.${(m[2] ?? "").padEnd(2, "0")}`;
}

// Compara dos importes en céntimos (enteros), sin floats.
export function centimos(importe: string): number {
  const [e, d = "0"] = importe.split(".");
  return Number(e) * 100 + Number(d.padEnd(2, "0").slice(0, 2));
}
