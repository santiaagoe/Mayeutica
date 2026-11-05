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
    - Cada bloque guarda dónde está: el archivo del que viene y su ubicación
      dentro de él, para que después un subobjetivo pueda apuntar al lugar
      donde el estudiante escribe. En un notebook la ubicación es el id de
      la celda (no cambia si se agregan celdas arriba; el número de celda
      sí); en un .py será el nombre de la función.

Decisiones (4 nov, noche, después de probar notebooks reales):
    - "por completar" se divide en dos, porque el ciclo del tutor cambia
      según lo que hay que producir: código (se revisa con tests) o una
      respuesta escrita (no hay tests).
    - El archivo va en el bloque para poder juntar varias fuentes (PDF +
      notebook, PDF + repo) sin que se confundan ubicaciones repetidas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

# Los tipos posibles de un bloque:
#   "texto"                enunciado, explicaciones (markdown en un notebook,
#                          todo el texto en un PDF).
#   "codigo"               código que ya viene dado: imports, datos, funciones
#                          de apoyo. Es contexto, no se pide programarlo.
#   "codigo_por_completar" código que el estudiante tiene que escribir: celda
#                          vacía o con una marca como "# TU CÓDIGO AQUÍ".
#   "texto_por_completar"  respuesta escrita que el estudiante tiene que
#                          redactar: celda markdown con "**Respuesta:**".
TIPOS = ("texto", "codigo", "codigo_por_completar", "texto_por_completar")


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
        ubicacion: Dónde está el bloque dentro de su archivo: el id de la
            celda en un notebook (después, el nombre de la función en un
            .py). None si la fuente no tiene ubicaciones (PDF) o si no se
            pudo determinar una confiable.
        archivo: La ruta del archivo del que viene el bloque, como string,
            tal como se la dieron a la Fuente. None si no viene de un
            archivo.
    """

    tipo: str
    contenido: str
    ubicacion: str | None = None
    archivo: str | None = None


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
