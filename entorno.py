"""Ayuda con el entorno: decide si una pregunta es de las herramientas o de la tarea.

Python puro, sin MCP ni LLM (como estado.py). La herramienta ayuda_entorno de
server.py usa subobjetivo_coincidente para cerrar el hueco de disfrazar una
pregunta de la tarea como pregunta de entorno: si la pregunta coincide con un
subobjetivo de la sesión, no se responde directo sino que se redirige a
pedir_ayuda.

Criterio de diseño: un falso positivo (redirigir una pregunta de entorno de
verdad) cuesta poco, porque el estudiante puede reformular. Un falso negativo
(responder directo una pregunta de la tarea) es justo el hueco que se quiere
cerrar. Ante la duda, coincidir.

Para trabajarlo paso a paso:

    pytest tests/test_entorno.py -k normalizar
    pytest tests/test_entorno.py -k coincide
"""

from estado import Subobjetivo
import unicodedata
import re

# Palabras que no distinguen un subobjetivo de otro ni una pregunta de otra.
# Se puede expandir cuando un test o una prueba real muestre un falso
# positivo por una palabra demasiado común. Ya vienen sin tildes, porque
# normalizar las quita antes de comparar.
PALABRAS_VACIAS = frozenset({
    "como", "que", "por", "para", "con", "una", "uno", "unos", "unas", "los",
    "las", "del", "mis", "esta", "este", "esto", "hay", "pero", "cual",
    "donde", "cuando", "puedo", "debo", "hago", "hacer", "quiero",
    "implementar", "calcular", "funcion", "codigo",
})

# Cuántas palabras de la descripción de un subobjetivo tienen que aparecer en
# la pregunta para contar como coincidencia. Con 1, "datos" bastaría para
# redirigir "¿cómo descargo el dataset?" al subobjetivo "normaliza los datos".
UMBRAL_DESCRIPCION = 2


def normalizar(texto: str) -> set[str]:
    """Convierte un texto en el conjunto de palabras que sirven para comparar.

    Pasos, en este orden:
        1. Minúsculas.
        2. Sin tildes ("función" -> "funcion").
        3. Separar en palabras por todo lo que no sea letra o dígito. El guion
           bajo separa: "derivada_sigmoide" da dos palabras.
        4. Descartar las palabras de menos de 3 letras.
        5. Descartar las que estén en PALABRAS_VACIAS.

    Ejemplos:
        normalizar("derivada_sigmoide")        -> {"derivada", "sigmoide"}
        normalizar("¿Cómo instalo NumPy?")     -> {"instalo", "numpy"}
        normalizar("la función de la a")       -> set()

    Limitación conocida: no reduce las palabras a su raíz, así que "normaliza"
    y "normalizo" cuentan como palabras distintas.

    Args:
        texto: Cualquier texto; puede estar vacío.

    Returns:
        Un conjunto de palabras (vacío si no queda ninguna).
    """
    en_minusc = texto.lower()
    lista_letras = list(unicodedata.normalize('NFD', en_minusc))
    sin_tilde = ""
    for letra in lista_letras:
        if (unicodedata.category(letra) != "Mn"): #es tilde
            sin_tilde += letra
    sin_espacio = re.findall(r'[a-z0-9]+', sin_tilde)
    palabra_a_devolver = set()
    for palabra in sin_espacio:
        if (len(palabra) >= 3 and palabra not in PALABRAS_VACIAS):
            palabra_a_devolver.add(palabra)
    return palabra_a_devolver 



    


def subobjetivo_coincidente(pregunta: str,
                            subobjetivos: list[Subobjetivo]) -> str | None:
    """Busca el primer subobjetivo con el que coincide una pregunta.

    Un subobjetivo coincide si se cumple cualquiera de estas dos señales:
        - Fuerte: alguna palabra de su id o de su funcion (si la tiene)
          aparece en la pregunta.
        - Débil: al menos UMBRAL_DESCRIPCION palabras de su descripción
          aparecen en la pregunta.

    Las palabras se comparan ya normalizadas (ver normalizar). Si coinciden
    varios, gana el que aparece primero en la lista.

    Args:
        pregunta: La duda del estudiante, con sus palabras.
        subobjetivos: Los subobjetivos de la sesión, en orden.

    Returns:
        El id del primer subobjetivo que coincide, o None si ninguno (también
        None si la lista está vacía).
    """
    if(len(subobjetivos) == 0):
        return None
    palabras = normalizar(pregunta)
    for subobjetivo in subobjetivos:
        descripcion = normalizar(subobjetivo.descripcion)
        palabras_aparecen = palabras & descripcion
        if (len(palabras_aparecen) >= UMBRAL_DESCRIPCION):
            return subobjetivo.id
        for palabra in palabras:
            id = normalizar(subobjetivo.id)
            if (palabra in id):
                return subobjetivo.id
            if (subobjetivo.funcion is not None):
                funcion = normalizar(subobjetivo.funcion)
                if ( palabra in funcion):
                    return subobjetivo.id    
    return None
