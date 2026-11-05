"""Fuente para notebooks de Jupyter (.ipynb).

Un .ipynb es un JSON. Lo que importa está en la lista "cells"; cada celda
trae, entre otros campos:

    {
      "cell_type": "markdown" | "code" | "raw",
      "id": "a3f9c2e1",               # desde el formato 4.5 (Colab lo
                                      # guarda en metadata["id"])
      "metadata": {...},              # libre, cada herramienta pone lo suyo
      "source": ["línea 1\\n", "línea 2"]  # o un solo string
      "outputs": [...]                # solo en las de código
    }

Python puro, sin MCP ni LLM (como estado.py).

Para trabajarlo paso a paso:

    pytest tests/test_fuentes.py -k source
    pytest tests/test_fuentes.py -k identificador
    pytest tests/test_fuentes.py -k tipo
    pytest tests/test_fuentes.py -k leer
"""

from pathlib import Path
from fuentes.base import Bloque, Fuente
import re
import unicodedata
import json

# Frases que marcan una celda como "por completar". Ya vienen en minúsculas y
# sin tildes, porque tipo_de_celda compara así. Se pueden expandir cuando
# aparezca una tarea con otra marca, pero ojo: una marca muy amplia ("aqui",
# "pass", "...") convierte en hueco código que ya viene dado (lo mostró el
# Auxiliar 6: "# Aqui tambien se podria usar .view(-1)").
#
# Marcas de código (solo se buscan en celdas "code"). "your code here" es la
# de nbgrader. "Escribe tu código aquí" ya calza con "tu codigo aqui".
MARCAS_CODIGO = ("tu codigo aqui", "your code here")

# Marcas de respuesta escrita (solo se buscan en celdas "markdown" y "raw").
# Llevan los dos puntos porque "respuesta" sola aparece en enunciados que no
# son huecos (Lab 7: "agregando sus respuestas", "la respuesta a la pregunta
# 4"). Las dos formas cubren "**Respuesta:**" y "**Respuesta**:".
MARCAS_TEXTO = ("respuesta:", "respuesta**:")


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

def id_de_celda(celda: dict) -> str | None:
    """Devuelve el identificador de una celda, buscándolo donde puede estar.

    Orden:
        1. El campo "id" de la celda (formato 4.5 en adelante).
        2. Si no está, metadata["id"] (Colab exporta formato 4.0 y guarda
           ahí su id).
        3. Si tampoco, None.

    Solo cuenta como id un string no vacío. Cualquier otra cosa (None, "",
    un número, una lista) se trata como si no estuviera y se pasa al
    siguiente lugar. Si "metadata" no existe o no es un diccionario,
    tampoco se cae: no hay id ahí.

    Ojo: esta función ve una sola celda, así que no puede saber si el id se
    repite en otra. Eso lo revisa FuenteNotebook.leer.

    Ejemplos:
        {"id": "a1", "metadata": {}}                    -> "a1"
        {"metadata": {"id": "VKjn5mmw"}}                -> "VKjn5mmw"
        {"id": "a1", "metadata": {"id": "otro"}}        -> "a1"
        {"id": "", "metadata": {"id": "m1"}}            -> "m1"
        {"metadata": {"id": 7}}                         -> None
        {"metadata": {}}                                -> None

    Args:
        celda: Una celda del notebook, como diccionario.

    Returns:
        El id como string, o None si no hay uno válido.
    """
    id_celda = celda.get("id")
    if(isinstance(id_celda, str)):
        sin_espacio = id_celda.strip()
        if(sin_espacio):
            return id_celda
    metadata = celda.get("metadata")
    if (isinstance(metadata, dict)):       
        metadata_id = metadata.get("id")
        if(isinstance(metadata_id, str)):
            sin_espacio = metadata_id.strip()
            if(sin_espacio):
                return metadata_id
    return None

def tipo_de_celda(celda: dict) -> str | None:
    """Decide qué tipo de Bloque corresponde a una celda, o si se descarta.

    Reglas:
        - "markdown" y "raw":
            - vacía o solo espacios -> None (se descarta: no aporta nada).
            - contiene alguna de MARCAS_TEXTO -> "texto_por_completar".
            - si no -> "texto".
        - "code":
            - vacía o solo espacios -> "codigo_por_completar".
            - contiene alguna de MARCAS_CODIGO -> "codigo_por_completar".
            - si no -> "codigo".
        - Cualquier otro cell_type -> None.

    Cada lista de marcas se busca solo en su tipo de celda: una variable
    "respuesta:" en un dict de código no es un hueco de texto, y un markdown
    que dice "escribe tu código aquí abajo" no es una celda de código.

    La comparación ignora mayúsculas y tildes, y la marca puede estar en
    cualquier parte de la celda (dentro de una función, o después de las
    preguntas en el mismo markdown).

    Ejemplos:
        {"cell_type": "markdown", "source": ["# Tarea 1"]}         -> "texto"
        {"cell_type": "markdown", "source": ["  \\n"]}            -> None
        {"cell_type": "markdown", "source": ["**Respuesta:** ..."]} -> "texto_por_completar"
        {"cell_type": "code", "source": ["import numpy"]}         -> "codigo"
        {"cell_type": "code", "source": []}                       -> "codigo_por_completar"
        {"cell_type": "code", "source": ["# TU CÓDIGO AQUÍ"]}     -> "codigo_por_completar"

    Args:
        celda: Una celda del notebook, como diccionario.

    Returns:
        Uno de fuentes.base.TIPOS, o None si la celda se descarta.
    """
    tipo = celda["cell_type"]
    devolver = None
    texto_source = texto_de_source(celda["source"])
    condicion = False
    texto_a_completar = False
    sin_espacio = texto_source.strip()
    if (tipo == "raw" or tipo == "markdown"):
            if (sin_espacio): #aquí no es vacío
                lista_letras = list(unicodedata.normalize('NFD', texto_source))
                sin_tilde = ""
                for letra in lista_letras:
                    if (unicodedata.category(letra) != "Mn"): #es tilde
                        sin_tilde += letra
                no_tilde_no_minusciula = sin_tilde.lower()
                
                for marca in MARCAS_TEXTO:
                    if (marca in no_tilde_no_minusciula):
                        texto_a_completar = True
                        
                if (texto_a_completar):
                    devolver = "texto_por_completar"
                else:
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
            for marca in MARCAS_CODIGO:
                if (marca in no_tilde_no_minusciula):
                    condicion = True
        if (condicion):
            devolver = "codigo_por_completar" 
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
        - ubicacion es el id de la celda según id_de_celda. Si ese id se
                repite en otra celda del mismo notebook (contando también las
                que se descartan), no sirve para encontrar la celda después: en
                todas las celdas que lo comparten, ubicacion queda en None. Las
                demás conservan el suyo.
        - archivo es str(self.ruta), igual en todos los bloques.
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
        conteo_ids = {} #Contar cuántas veces aparece cada id en todo el notebook
        for celda_nb in datos["cells"]:
            id_celda = id_de_celda(celda_nb)
            if (id_celda is not None):
                if (id_celda in conteo_ids):
                    conteo_ids[id_celda] += 1
                else:
                    conteo_ids[id_celda] = 1
        for celda_nb in datos["cells"]:
            tipo = tipo_de_celda(celda_nb)
            if (tipo is not None):
                contenido = texto_de_source(celda_nb["source"])
                ubicacion = id_de_celda(celda_nb)
                if (ubicacion is not None):
                    if (conteo_ids[ubicacion] > 1):
                        ubicacion = None
                archivo = str(self.ruta)
                bloque = Bloque(tipo, contenido, ubicacion, archivo)
                bloques.append(bloque)
                
        return bloques