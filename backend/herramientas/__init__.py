"""
Herramientas del agente. Importar este paquete las registra todas.

Para añadir una: crea la función con @herramienta en el módulo que toque (o en uno nuevo
importado aquí), con tipos, docstring y sección Args. Después, test en tests/ y un caso
en evals/casos.yaml. La skill /herramienta lo hace por ti.
"""

from . import calculos, gastos, mercados, perfil  # noqa: F401
