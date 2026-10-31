"""Lectura del código del estudiante para la herramienta leer_mi_codigo.

Python puro, sin MCP: recibe texto y devuelve texto, así se puede probar sin
levantar el servidor. Los tests están en test_lector.py.
"""
import ast

def extraer_funcion(codigo: str, nombre: str) -> str | None:
    """Devuelve el código fuente de una función de nivel superior.

    Busca en el código una función definida con `def nombre(...)` en el nivel
    superior del módulo (no dentro de una clase ni de otra función) y devuelve
    su texto exacto, desde la línea del `def` hasta la última línea de su
    cuerpo, incluido el docstring. Si la función tiene decoradores, el texto
    parte en el primer decorador.

    Pista de herramientas: el módulo estándar `ast` sabe leer código Python.
    Mira ast.parse, el atributo body del árbol, ast.FunctionDef y
    ast.get_source_segment.

    Args:
        codigo: El contenido completo de un archivo.py.
        nombre: El nombre de la función a buscar.

    Returns:
        El texto de la función, o None si no hay una función de nivel superior
        con ese nombre.

    Raises:
        SyntaxError: Si el código no es Python válido (por ejemplo, el
            estudiante dejó un paréntesis abierto). Quien llame decide qué
            hacer en ese caso.
    """
    texto = None
    arbol = ast.parse(codigo)
    lineas = codigo.splitlines()
    for elemento in arbol.body:
        if isinstance(elemento, ast.FunctionDef): #si es funcion
            nombre_funcion = elemento.name
            if(nombre_funcion == nombre): 
               if elemento.decorator_list:
                   inicio = elemento.decorator_list[0].lineno
               else:
                   inicio = elemento.lineno
               fin = elemento.end_lineno
               lineas_funcion = lineas[inicio - 1 : fin]   
               return "\n".join(lineas_funcion)
                   
    return texto
