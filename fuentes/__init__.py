"""Fuentes de tareas: cada una sabe leer un tipo de archivo y devuelve bloques.

Uso:
    from fuentes import FuenteNotebook
    bloques = FuenteNotebook("tarea.ipynb").leer()
"""

from fuentes.base import TIPOS, Bloque, Fuente
from fuentes.notebook import FuenteNotebook

__all__ = ["TIPOS", "Bloque", "Fuente", "FuenteNotebook"]
