---
name: finanzas
description: Conocimiento financiero para el producto. Fórmulas (préstamos, TAE, interés compuesto, ahorro), contexto español (impuestos, autónomos, recibos), fuentes de datos y normativa (AI Act, RGPD, asesoramiento de inversión, PSD2). Cárgala al diseñar herramientas, revisar cifras, generar datos o escribir avisos.
user-invocable: false
---

# Finanzas para el agente

## Regla de cálculo
- Dinero exacto con `Decimal` y redondeo `ROUND_HALF_UP` a céntimos: cuotas, intereses, totales, impuestos.
- Análisis (medias, porcentajes, tendencias) con pandas y floats redondeados al final con `eur()`.
- Toda cifra que vea el usuario sale de una herramienta y lleva sus supuestos.

## Fórmulas
- **Préstamo, sistema francés**: cuota = C · i / (1 − (1 + i)^−n), con i = TIN / 12 y n = número de cuotas. Si i = 0, cuota = C / n. Interés del mes = pendiente · i.
- **TAE**: tipo efectivo anual de los flujos reales. Se busca el tipo mensual r con C − comisiones = Σ cuota_k / (1 + r)^k y TAE = (1 + r)^12 − 1. Sin comisiones, TAE = (1 + TIN/12)^12 − 1.
- **Interés compuesto con aportaciones** (al final de cada mes): VF = C · (1 + r)^m + A · ((1 + r)^m − 1) / r, con r = (1 + R)^(1/12) − 1.
- **Valor real**: VF / (1 + inflación)^años.
- **Aportación para un objetivo**: A = (F − S · (1 + r)^m) · r / ((1 + r)^m − 1); si r = 0, A = (F − S) / m.
- **Tasa de ahorro**: (ingresos − gastos) / ingresos.

## Reglas orientativas (siempre como orientación, nunca como norma)
- 50/30/20: necesidades, deseos y ahorro. Con alquileres altos, las necesidades suelen pasar del 50 %.
- Fondo de emergencia: de 3 a 6 meses de gastos esenciales.
- Endeudamiento: muchas entidades miran que las cuotas no pasen del 30-35 % de los ingresos netos. Explícalo como práctica habitual, nunca como decisión sobre el usuario.

## Contexto español
- Recibos típicos: hipoteca o alquiler, comunidad, luz, agua (a menudo bimestral), gas, internet y móvil, seguros, colegio, suscripciones. IBI anual o fraccionado.
- Autónomos: cuota mensual a la Seguridad Social (TGSS) según rendimientos; IVA trimestral (modelo 303) y pago fraccionado del IRPF (modelo 130) en abril, julio, octubre y enero.
- Extractos CSV: separador `;`, coma decimal, fechas dd/mm/aaaa, a veces columnas Cargo y Abono separadas.
- Pagos entre personas por Bizum.

## Fuentes de datos
| Fuente | Para qué | Notas |
|---|---|---|
| Datos sintéticos del kit | Demo y tests | `backend/datos/sinteticos.py`, tres perfiles |
| CSV del banco | Probar con datos propios | Nunca en la demo pública |
| Frankfurter | Tipos de cambio de referencia (BCE y otros bancos centrales) | Sin clave; con caché y respaldo sin conexión |
| Alpha Vantage | Cotizaciones | Clave gratuita, 25 consultas al día; servidor MCP oficial |
| Open banking | Cuentas reales | Requiere proveedor autorizado (PSD2); el acceso gratuito de GoCardless ya no admite altas. Lo simulamos |

## Normativa que afecta al diseño
- **AI Act, transparencia (art. 50)**: el usuario debe saber que habla con una IA. Aviso fijo en la interfaz y en la primera respuesta.
- **AI Act, alto riesgo (anexo III)**: evaluar la solvencia o puntuar el crédito de personas físicas es alto riesgo (la detección de fraude queda fuera). Las obligaciones de alto riesgo se aplazan al 2 de diciembre de 2027. No hacemos scoring; si el reto lo pide, simulación explicable con revisión humana.
- **RGPD**: minimización (pedir solo lo necesario), finalidad clara, datos sintéticos en la demo, enmascarado de IBAN, tarjetas, DNI, emails y teléfonos antes de enviarlos a Claude.
- **Asesoramiento de inversión (MiFID II)**: recomendar a una persona un instrumento concreto es un servicio regulado. El agente informa y educa sobre tipos de productos y riesgos, sin decir "compra X".
- **PSD2**: acceder a cuentas reales exige un proveedor autorizado.
- **Transparencia bancaria**: la TAE debe incluir las comisiones obligatorias; avisa de que una oferta real puede tener otros gastos (seguros vinculados).

## Avisos (redacción recomendada)
- IA: "Hablas con un asistente de inteligencia artificial. La información es orientativa y no constituye asesoramiento financiero, fiscal ni de inversión."
- Proyecciones: "Es una estimación con los supuestos indicados; los resultados reales pueden variar y no están garantizados."
- Anomalías: "Son señales para revisar, no prueba de fraude. Si no reconoces un cargo, contacta con tu banco."
