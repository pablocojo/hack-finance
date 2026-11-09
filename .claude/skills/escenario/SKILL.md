---
name: escenario
description: Crea un escenario sintético con la verdad etiquetada (movimientos, momentos que deben salir y cuándo, trampas que no deben disparar nada y, si hace falta, un usuario simulado). Es la base de los tests, las evals, /medir y la demo. Úsala antes de crear o arreglar un detector o un módulo.
argument-hint: "<historia en una frase, por ejemplo: cena de 120 € con 5 amigos y uno no paga>"
disable-model-invocation: true
---

# /escenario $ARGUMENTS

## 1. La historia
Escribe en 3-5 líneas quién es la persona, qué le pasa, qué momento debe detectar el sistema y en qué fecha. Añade al menos una **trampa**: algo parecido que NO debe disparar nada (por ejemplo, dos cafés iguales el mismo día no son un cobro duplicado).

## 2. El archivo (`ingeniero-deteccion`)
Usa el formato de `docs/diseno/motor.md` (sección de datos de prueba). Va en `backend/escenarios/`. Si el formato aún no existe, usa este:
```yaml
id: cena-falta-uno
descripcion: Pagas una cena de 120 € y te devuelven 3 de las 4 partes
base: {perfil: estudiante, meses: 3, semilla: 7}   # movimientos de fondo del kit
movimientos:                                       # fechas relativas al último día del escenario
  - {dia: -6, concepto: "COMPRA TARJETA RESTAURANTE LA TAGLIATELLA", comercio: "LA TAGLIATELLA", importe: -120.00, canal: tarjeta}
  - {dia: -6, concepto: "BIZUM RECIBIDO", contraparte: "Laura M", nota: "cena", importe: 24.00, canal: bizum}
  - {dia: -5, concepto: "BIZUM RECIBIDO", contraparte: "Dani R", nota: "🍝", importe: 24.00, canal: bizum}
  - {dia: -4, concepto: "BIZUM RECIBIDO", contraparte: "Sara P", nota: "cena viernes", importe: 24.00, canal: bizum}
esperado:
  - {tipo: gasto_compartido, desde: -4, hasta: -2, datos: {personas_estimadas: 5, faltan: 1, importe_pendiente: 24.00}}
no_esperado:
  - {tipo: posible_estafa, motivo: "los Bizums recibidos no son un riesgo"}
usuario_simulado: null   # o {preferencias ocultas} si el escenario mide la personalización
```
- Importes y conceptos realistas en España (`experto-banca` si hay dudas). Solo datos inventados.
- Semilla fija: el escenario tiene que dar siempre lo mismo.

## 3. Comprobar
- Carga el escenario en un test (`tests/test_escenarios.py`) y comprueba que el formato es válido.
- Si el detector ya existe, `/medir motor` debe contarlo. Si aún no existe, el test queda marcado como esperado que falle (`xfail`) hasta que `/detector` lo implemente.
- Commit: `test: escenario <id>`.
