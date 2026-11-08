"""Categorías de movimientos, reglas por palabras clave y grupos de la regla 50/30/20."""

from __future__ import annotations

import re
import unicodedata

CATEGORIAS = {
    "ingresos": "Nóminas, becas, cobros de facturas y cualquier importe positivo",
    "vivienda": "Alquiler, hipoteca, comunidad e IBI",
    "suministros": "Luz, agua, gas, internet y móvil",
    "supermercado": "Alimentación y droguería",
    "restaurantes": "Bares, restaurantes y comida a domicilio",
    "transporte": "Transporte público, combustible, taxis, aparcamiento y taller",
    "suscripciones": "Servicios de pago periódico: streaming, música, software, nube",
    "salud": "Farmacia, médicos, dentista y óptica",
    "seguros": "Seguros de hogar, coche, vida o salud",
    "educacion": "Colegio, universidad, academias, cursos y libros",
    "ocio": "Cine, deporte, gimnasio, viajes y entradas",
    "compras": "Ropa, tecnología, hogar y compras online",
    "impuestos": "Hacienda, Seguridad Social, tasas y cuota de autónomos",
    "trabajo": "Gastos profesionales: coworking, gestoría, material",
    "transferencias": "Transferencias y Bizum a otras personas",
    "efectivo": "Retiradas en cajero",
    "otros": "Lo que no encaja en ninguna categoría",
}

# El orden importa: la primera regla que encaja gana.
REGLAS: list[tuple[str, str]] = [
    (r"AMAZON PRIME|PRIME VIDEO|NETFLIX|SPOTIFY|HBO|DISNEY|YOUTUBE PREMIUM|APPLE\.COM|ICLOUD|GOOGLE ONE|"
     r"GOOGLE WORKSPACE|DROPBOX|ADOBE|MICROSOFT 365|FILMIN|DAZN|AUDIBLE", "suscripciones"),
    (r"SEGURIDAD SOCIAL|TGSS|AEAT|AGENCIA TRIBUTARIA|HACIENDA|MODELO \d{3}|IBI |TASA |AYUNTAMIENTO|"
     r"CUOTA AUTONOMOS", "impuestos"),
    (r"ALQUILER|HIPOTECA|COMUNIDAD DE PROPIETARIOS|COMUNIDAD PROP", "vivienda"),
    (r"IBERDROLA|ENDESA|NATURGY|HOLALUZ|REPSOL LUZ|TOTALENERGIES|CANAL DE ISABEL|AGUAS DE|EMASESA|"
     r"MOVISTAR|VODAFONE|ORANGE|DIGI|MASMOVIL|LOWI|O2 |FIBRA|SIMYO|PEPEPHONE", "suministros"),
    (r"MERCADONA|CARREFOUR|LIDL|ALDI|\bDIA\b|EROSKI|ALCAMPO|CONSUM|HIPERCOR|SUPERMERCADO|BONPREU|"
     r"AHORRAMAS|GADIS|FROIZ|MAS Y MAS", "supermercado"),
    (r"RESTAURANTE|\bBAR\b|CAFETERIA|CAFE |GLOVO|JUST EAT|UBER ?EATS|TELEPIZZA|BURGER|MCDONALD|"
     r"TABERNA|PIZZERIA|SUSHI|KEBAB|CERVECERIA", "restaurantes"),
    (r"RENFE|METRO |EMT |CONSORCIO TRANSPORTES|ABONO TRANSPORTE|CABIFY|\bUBER\b|BLABLACAR|GASOLINERA|"
     r"REPSOL|CEPSA|GALP|\bBP\b|SHELL|PARKING|APARCAMIENTO|BICIMAD|TAXI|TALLER|ITV|PEAJE", "transporte"),
    (r"FARMACIA|CLINICA|DENTISTA|DENTAL|HOSPITAL|OPTICA|FISIOTERAPIA|MEDICO", "salud"),
    (r"SEGURO|MAPFRE|MUTUA|\bAXA\b|LINEA DIRECTA|ALLIANZ|SANITAS|ADESLAS|GENERALI|ZURICH", "seguros"),
    (r"COLEGIO|UNIVERSIDAD|ACADEMIA|MATRICULA|LIBRERIA|CURSO|COMEDOR ESCOLAR|EXTRAESCOLAR", "educacion"),
    (r"COWORKING|GESTORIA|ASESORIA|MATERIAL OFICINA|DOMINIO|HOSTING", "trabajo"),
    (r"CINE|TEATRO|CONCIERTO|ENTRADAS|TICKETMASTER|GIMNASIO|\bGYM\b|DECATHLON|HOTEL|BOOKING|AIRBNB|"
     r"RYANAIR|VUELING|IBERIA|VIAJES|MUSEO|STEAM|PLAYSTATION|NINTENDO", "ocio"),
    (r"AMAZON|ZARA|CORTE INGLES|PRIMARK|MEDIAMARKT|MEDIA MARKT|FNAC|IKEA|LEROY|ALIEXPRESS|SHEIN|"
     r"PCCOMPONENTES|MANGO|H&M|TIENDA|COMPRA ONLINE", "compras"),
    (r"CAJERO|RETIRADA EFECTIVO|REINTEGRO", "efectivo"),
    (r"TRANSFERENCIA|BIZUM|TRASPASO", "transferencias"),
]
_REGLAS_COMPILADAS = [(re.compile(patron), categoria) for patron, categoria in REGLAS]

# Regla 50/30/20: necesidades, deseos y ahorro.
NECESIDADES = {"vivienda", "suministros", "supermercado", "transporte", "salud", "seguros",
               "educacion", "impuestos", "trabajo"}
DESEOS = {"restaurantes", "suscripciones", "ocio", "compras"}


def normalizar(texto: str) -> str:
    """Mayúsculas y sin tildes, para comparar conceptos de distintos bancos."""
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes.upper()).strip()


def categorizar_por_reglas(concepto: str, importe: float) -> str | None:
    """Categoría por palabras clave, o None si ninguna regla encaja."""
    if importe > 0:
        return "ingresos"
    texto = normalizar(concepto)
    for patron, categoria in _REGLAS_COMPILADAS:
        if patron.search(texto):
            return categoria
    return None


def grupo_50_30_20(categoria: str | None) -> str | None:
    if categoria in NECESIDADES:
        return "necesidades"
    if categoria in DESEOS:
        return "deseos"
    return None
