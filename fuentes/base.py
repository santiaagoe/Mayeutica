"""Interfaz común para leer una tarea, venga de donde venga.

Cada tipo de archivo tiene su Fuente (FuenteNotebook, después FuentePDF,
FuenteGitHub...). Todas devuelven lo mismo: una lista de Bloque, en el orden
en que aparecen en la tarea. El resto del sistema trabaja con esa lista y no
necesita saber de dónde vino.

Decisiones de diseño (4 nov):
    - La fuente devuelve TODO el contenido, incluidas las celdas que marcan
      dónde programar ("# TU CÓDIGO AQUÍ"), porque son las que dicen qué se
      pide en concreto.
    - Se devuelve una lista de bloques y no un solo string, para no
      perder la estructura del notebook. Un PDF, que no tiene celdas,
      devuelve solo bloques "texto".
    - Cada bloque guarda el id de su celda, para que después un subobjetivo
      pueda apuntar a la celda donde el estudiante escribe su código. El id 
      no cambia si se agregan celdas arriba; el número de celda sí.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

# Los tipos posibles de un bloque:
#   "texto"          enunciado, explicaciones (markdown en un notebook, todo
#                    el texto en un PDF).
#   "codigo"         código que ya viene dado: imports, datos, funciones de
#                    apoyo. Es contexto, no se pide programarlo.
#   "por_completar"  código que el estudiante tiene que escribir: celda vacía
#                    o con una marca como "# TU CÓDIGO AQUÍ".
TIPOS = ("texto", "codigo", "por_completar")


@dataclass(frozen=True)
class Bloque:
    """Un trozo de la tarea, con su tipo y su contenido.

    Es inmutable (frozen): una vez leída, la tarea no se modifica. Además, así
    dos bloques con los mismos datos son iguales (==), lo que simplifica los
    tests.

    Attributes:
        tipo: Uno de TIPOS.
        contenido: El texto del bloque, tal como viene en la fuente (sin
            recortar espacios ni quitar marcas).
        celda: El id de la celda en el notebook, o None si la fuente no
            tiene celdas (PDF) o el notebook es de un formato sin ids.
    """

    tipo: str
    contenido: str
    celda: str | None = None


class Fuente(ABC):
    """Lo que tiene que saber hacer toda fuente de tareas.

    Es abstracta: no se puede crear una Fuente directamente, solo una de sus
    subclases, que tiene que definir leer(). Cada subclase decide qué recibe
    en su constructor (una ruta local, una URL...).
    """

    @abstractmethod
    def leer(self) -> list[Bloque]:
        """Lee la tarea y la devuelve como bloques, en orden.

        Returns:
            La lista de bloques. Vacía si la tarea no tiene contenido.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si el archivo existe pero no se puede interpretar.
        """
