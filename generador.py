"""Convertir una fuente (por ahora, un notebook) en una tarea de Mayéutica.

Es la parte 2 de leer la tarea desde un notebook. Hay tres pasos con dueños
distintos:

    1. Sacar el contenido:        fuentes/ (FuenteNotebook.leer -> bloques).
    2. Partirlo en subobjetivos:  el LLM, a partir de lo que devuelve
                                  formatear_bloques. El estudiante confirma la
                                  lista en el chat antes del paso 3.
    3. Validar y guardar:         este módulo (validar_subobjetivos,
                                  escribir_tarea).

El resultado es un JSON de tarea común y corriente, para que cargar_tarea, el
árbitro, el estado y la recarga funcionen sin cambios. No sabe nada de MCP:
las herramientas leer_fuente y crear_tarea de server.py lo usan.

Decisiones (5 nov):
    - El JSON queda junto al notebook y se llama como él:
      'lab7.ipynb' -> 'lab7.tarea.json'. No 'tarea.json' a secas: dos
      notebooks en la misma carpeta se pisarían. Su estado queda en
      'lab7.tarea.estado.json' (ruta_estado no cambia).
    - Cada subobjetivo propuesto solo puede traer "id", "descripcion" y
      "celdas" (opcional: ids de las celdas donde el estudiante escribe;
      varias si una pregunta y su respuesta están en celdas separadas).
      "tests" y "ejemplo" se rechazan: un test escrito por el LLM no está
      verificado y un ejemplo inventado pasaría por oficial.
    - "celdas" se guarda en el JSON aunque SesionTarea todavía no lo use
      (ignora las claves que no conoce). Queda listo para la rama de
      leer_mi_codigo que busca la celda por id.
    - validar_subobjetivos devuelve TODOS los problemas de una vez, no solo
      el primero: así el LLM corrige la lista en un solo intento.

Tests: pytest tests/test_generador.py -k formatear / -k ruta / -k validar /
-k escribir
"""

from pathlib import Path
from fuentes import Bloque
import json
# Lo que se agrega al nombre del notebook para formar el de la tarea.
SUFIJO_TAREA = ".tarea.json"

# Claves que puede traer cada subobjetivo propuesto por el LLM.
CAMPOS_PERMITIDOS = ("id", "descripcion", "celdas")

# Texto que reemplaza a la ubicación cuando un bloque no tiene una.
SIN_UBICACION = "sin ubicación"

def es_texto_valido(valor) -> bool:
    """Verifica si un valor es un string y no está vacío tras quitar espacios."""
    if (valor is None):
        return False
    if (not isinstance(valor, str)):
        return False
    if (not valor.strip()):
        return False
    return True


def formatear_bloques(bloques: list[Bloque]) -> str:
    """Arma el texto con los bloques de una fuente para entregárselo al LLM.

    Cada bloque va en orden, con una línea de encabezado y después su
    contenido completo (sin recortar). Formato sugerido (los tests solo
    exigen que aparezcan el número, el tipo, la ubicación y el contenido, en
    orden, no este formato exacto):

        [1] texto · celda a1b2
        # Lab 7
        ...

        [2] codigo_por_completar · celda c3d4
        # TU CÓDIGO AQUÍ

    El número empieza en 1 y es la posición en la lista, no el número de
    celda del notebook (las celdas descartadas no tienen bloque). Si el
    bloque no tiene ubicación, en su lugar va SIN_UBICACION: así el LLM sabe
    que no puede usarlo en "celdas".

    Args:
        bloques: Lo que devuelve Fuente.leer().

    Returns:
        El texto. Si la lista está vacía, un mensaje que lo dice (nunca un
        string vacío).
    """
    devolver = ""
    if (len(bloques) == 0): #es vacio
        devolver = "El notebook no contiene bloques válidos para procesar."
    else:
        partes = []
        posicion = 1
        for bloque in bloques:
            ubicacion = bloque.ubicacion
            if (ubicacion is None):
                ubicacion = SIN_UBICACION
            encabezado = "[" + str(posicion) + "] " + bloque.tipo + " · celda " + str(ubicacion)
            texto_bloque = encabezado + "\n" + bloque.contenido
            partes.append(texto_bloque)
            posicion += 1
            
        devolver = "\n\n".join(partes)
        
    return devolver


def ruta_tarea_generada(ruta_notebook: str) -> str:
    """Devuelve la ruta del JSON de tarea que se genera desde un notebook.

    Queda en la misma carpeta, con el nombre del notebook y SUFIJO_TAREA:
    '/a/b/lab7.ipynb' -> '/a/b/lab7.tarea.json'.

    Args:
        ruta_notebook: Ruta del notebook (ya limpia).

    Returns:
        La ruta del JSON, como string.
    """
    ruta_obj = Path(ruta_notebook)
    ruta_nueva = ruta_obj.with_suffix(SUFIJO_TAREA)
    devolver = str(ruta_nueva)
    return devolver


def validar_subobjetivos(subobjetivos: list, ubicaciones: set[str]) -> list[str]:
    """Revisa la lista de subobjetivos que propone el LLM antes de guardarla.

    No modifica la lista ni lanza excepciones: junta los problemas en una
    lista de mensajes. Cada mensaje nombra lo que está mal (el id repetido,
    la clave no permitida, la celda que no existe...) para que el LLM pueda
    corregirlo. Reglas:

        - La lista no puede estar vacía.
        - Cada subobjetivo es un diccionario.
        - Solo trae claves de CAMPOS_PERMITIDOS. Cualquier otra ("tests",
          "ejemplo", "archivo"...) es un problema.
        - "id" y "descripcion" son obligatorios y son strings con texto (no
          vacíos ni solo espacios).
        - Los ids no se repiten.
        - "celdas" es opcional. Si viene, es una lista de strings, y cada uno
          está en ubicaciones. Una lista vacía es válida (un subobjetivo que
          no apunta a ninguna celda).

    Args:
        subobjetivos: Lo que mandó el LLM. Puede venir mal formado (por eso
            no es list[dict]).
        ubicaciones: Los ids de celda válidos: las ubicaciones (no None) de
            los bloques de la fuente.

    Returns:
        Los problemas encontrados, en orden. Vacía si la lista es válida.
    """
    problemas = []
    if (not isinstance(subobjetivos, list)):
        problemas.append("La entrada de subobjetivos debe ser una lista.")
        return problemas
    if (len(subobjetivos) == 0): #es vacio
        problemas.append("La lista de subobjetivos no puede estar vacía.")
        return problemas
    ids_vistos = set()
    for posicion, sub in enumerate(subobjetivos, start=1):
        if (not isinstance(sub, dict)):
            problemas.append("El subobjetivo en la posición " + str(posicion) + " no es un diccionario.")
            continue # Salta al siguiente y evita anidar todo en un else
        llaves = sub.keys()
        for clave in llaves: # Revisar claves no permitidas
            if (clave not in CAMPOS_PERMITIDOS):
                problemas.append("Clave no permitida '" + clave + "' en el subobjetivo " + str(posicion) + ".")         
        sub_id = sub.get("id")
        if (not es_texto_valido(sub_id)): # Usa la nueva función auxiliar
            problemas.append("El 'id' del subobjetivo " + str(posicion) + " debe ser un texto y no estar vacío.")
        else:
            if (sub_id in ids_vistos):
                problemas.append("El id '" + sub_id + "' está repetido en la lista.")
            else:
                ids_vistos.add(sub_id)
        desc = sub.get("descripcion")
        if (not es_texto_valido(desc)): # Usa la nueva función auxiliar
            problemas.append("La 'descripcion' del subobjetivo " + str(posicion) + " debe ser un texto y no estar vacía.")
        if ("celdas" in llaves) :# Revisar 'celdas' (opcional)
            celdas = sub["celdas"]
            if (not isinstance(celdas, list)):
                problemas.append("La clave 'celdas' del subobjetivo " + str(posicion) + " debe ser una lista.")
            else:
                idx_celda = 0
                for c in celdas:
                    if (not isinstance(c, str)):
                        problemas.append("El elemento " + str(idx_celda) + " de 'celdas' (subobjetivo " + str(posicion) + ") no es texto.")
                    else:
                        if (c not in ubicaciones):
                            problemas.append("La celda '" + c + "' referenciada en el subobjetivo " + str(posicion) + " no existe en la fuente.")
                    idx_celda += 1          
    return problemas

def escribir_tarea(ruta_json: str, ruta_notebook: str,
                   subobjetivos: list[dict]) -> None:
    """Escribe el JSON de la tarea generada a partir de un notebook.

    Supone que los subobjetivos ya pasaron por validar_subobjetivos: no los
    revisa de nuevo. Si el archivo existe, lo reemplaza (decidir si se puede
    reemplazar le toca a crear_tarea).

    El JSON tiene la misma forma que las tareas escritas a mano, más una
    clave "fuente":

        {
          "titulo": "lab7",                <- nombre del notebook sin extensión
          "fuente": "lab7.ipynb",          <- solo el nombre: queda en la misma
                                              carpeta (como "archivo" y "tests",
                                              que son relativas al JSON)
          "subobjetivos": [
            {"id": "...", "descripcion": "...", "celdas": ["..."]},
            ...
          ]
        }

    "celdas" se escribe solo en los subobjetivos que la traen. Se guarda en
    UTF-8 y con las tildes legibles (no como \\u00e9), con sangría para que
    una persona pueda abrirlo y revisarlo.

    Args:
        ruta_json: Dónde escribir (normalmente, ruta_tarea_generada).
        ruta_notebook: El notebook del que sale la tarea.
        subobjetivos: La lista ya validada.
    """
    notebook_path = Path(ruta_notebook)
    titulo_nb = notebook_path.stem
    fuente_nb = notebook_path.name
    
    datos = {}
    datos["titulo"] = titulo_nb
    datos["fuente"] = fuente_nb
    datos["subobjetivos"] = subobjetivos
    
    with open(ruta_json, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
