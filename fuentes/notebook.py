"""Fuente para notebooks de Jupyter (.ipynb).

Un .ipynb es un JSON. Lo que importa está en la lista "cells"; cada celda
trae, entre otros campos:

    {
      "cell_type": "markdown" | "code" | "raw",
      "id": "a3f9c2e1",               # desde el formato 4.5
      "metadata": {...},              # libre, cada herramienta pone lo suyo
      "source": ["línea 1\\n", "línea 2"]  # o un solo string
      "outputs": [...]                # solo en las de código
    }

Python puro, sin MCP ni LLM (como estado.py).

Para trabajarlo paso a paso:

    pytest tests/test_fuentes.py -k source
    pytest tests/test_fuentes.py -k tipo
    pytest tests/test_fuentes.py -k leer
"""

from pathlib import Path
from fuentes.base import Bloque, Fuente
import re
import unicodedata
import json

# Frases que marcan una celda de código como "por completar". Ya vienen en
# minúsculas y sin tildes, porque tipo_de_celda compara así. "your code here"
# es la que usa nbgrader, común en cursos que usan notebooks. Se puede
# expandir cuando aparezca una tarea con otra marca.
MARCAS_POR_COMPLETAR = ("tu codigo aqui", "your code here")


def texto_de_source(source: list[str] | str) -> str:
    """Une el campo "source" de una celda en un solo string.

    En el formato .ipynb, "source" puede venir de dos formas: como lista de
    líneas (cada una con su "\\n" al final, menos la última) o como un solo
    string. Las dos son válidas y Jupyter escribe una u otra.

    Ejemplos:
        texto_de_source(["a = 1\\n", "b = 2"])  -> "a = 1\\nb = 2"
        texto_de_source("a = 1\\nb = 2")        -> "a = 1\\nb = 2"
        texto_de_source([])                    -> ""

    Args:
        source: El valor del campo "source" de la celda.

    Returns:
        El texto completo, sin agregar ni quitar nada.
    """
    if isinstance(source,list):
        if (len(source) == 0):
            return ""
        else:
            return "".join(source)    

    else: #no es lista
        return source     

def tipo_de_celda(celda: dict) -> str | None:
    """Decide qué tipo de Bloque corresponde a una celda, o si se descarta.

    Reglas:
        - "markdown" y "raw" -> "texto". Pero si el texto está vacío o solo
          tiene espacios, se descarta (None): no aporta nada.
        - "code" -> "por_completar" si está vacía, si solo tiene espacios o
          si contiene alguna de MARCAS_POR_COMPLETAR. La comparación ignora
          mayúsculas y tildes, y la marca puede estar en cualquier parte de
          la celda (por ejemplo, dentro del cuerpo de una función).
          Si no, -> "codigo".
        - Cualquier otro cell_type -> None.

    Ejemplos:
        {"cell_type": "markdown", "source": ["# Tarea 1"]}       -> "texto"
        {"cell_type": "markdown", "source": ["  \\n"]}          -> None
        {"cell_type": "code", "source": ["import numpy"]}       -> "codigo"
        {"cell_type": "code", "source": []}                     -> "por_completar"
        {"cell_type": "code", "source": ["# TU CÓDIGO AQUÍ"]}   -> "por_completar"

    Args:
        celda: Una celda del notebook, como diccionario.

    Returns:
        Uno de fuentes.base.TIPOS, o None si la celda se descarta.
    """
    tipo = celda["cell_type"]
    devolver = None
    texto_source = texto_de_source(celda["source"])
    condicion = False
    sin_espacio = texto_source.strip()
    if (tipo == "raw" or tipo == "markdown"):
        if (sin_espacio): #aquí no es vacío
            devolver = "texto"
    if (tipo == "code"):
        if (not sin_espacio): #es vacio
            condicion = True
        else:
            lista_letras = list(unicodedata.normalize('NFD', texto_source))
            sin_tilde = ""
            for letra in lista_letras:
                if (unicodedata.category(letra) != "Mn"): #es tilde
                    sin_tilde += letra
            no_tilde_no_minusciula = sin_tilde.lower()
            for marca in MARCAS_POR_COMPLETAR:
                if (marca in no_tilde_no_minusciula):
                    condicion = True
        if (condicion):
            devolver = "por_completar" 
        else:
            devolver = "codigo"      

    return devolver        


class FuenteNotebook(Fuente):
    """Lee una tarea desde un archivo .ipynb.

    Igual que SesionTarea, asume que la ruta ya viene limpia (sin "~" ni
    espacios alrededor). La limpieza la hace server.py, que es la frontera
    con el LLM.
    """

    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)

    def leer(self) -> list[Bloque]:
        """Lee el notebook y devuelve un Bloque por cada celda que no se descarta.

        - El orden de los bloques es el de las celdas.
        - El contenido es el source completo de la celda (ver
          texto_de_source), sin quitar las marcas.
        - celda es el "id" de la celda, o None si no lo trae (notebooks de
          formato anterior a 4.5).
        - Los "outputs" de las celdas de código NO se incluyen: pueden ser
          enormes (imágenes, tablas) o mostrar el resultado esperado.
        - El archivo se lee como UTF-8.

        Returns:
            La lista de bloques. Vacía si el notebook no tiene celdas.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si el archivo no es JSON válido, o si no es un
                diccionario con una lista en "cells". Cuando el error viene de otra excepción, se
                encadena con "raise ... from e".
        """
        
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
        except ValueError as e:
            raise ValueError("El archivo está roto") from e
        bloques = []
        if (not isinstance(datos, dict)):
            raise ValueError("Los datos no son un diccionario") 
        if ("cells" not in datos.keys()):
            raise ValueError("cells no está en las llaves") 
        if(not isinstance(datos["cells"], list)):
            raise ValueError("cells no es una lista") 
        for celda_nb in  datos["cells"]:
            tipo = tipo_de_celda(celda_nb)
            if (tipo is not None):
                contenido = texto_de_source(celda_nb["source"])
                celda = celda_nb.get("id")
                bloque = Bloque(tipo, contenido, celda)
                bloques.append(bloque)
        return bloques