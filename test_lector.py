"""Tests de lector.py.

    pytest test_lector.py
"""

import pytest

from lector import extraer_funcion


CODIGO = '''"""Módulo de prueba."""
import numpy as np


def predecir(X, w, b):
    """Predice."""
    return np.asarray(X) @ w + b


def error_cuadratico_medio(y, y_pred):
    """Calcula el MSE."""
    errores = np.asarray(y_pred) - np.asarray(y)

    # comentario dentro del cuerpo, después de una línea en blanco
    return np.mean(errores ** 2)


def gradientes(X, y, w, b):
    pass
'''


def test_devuelve_la_funcion_pedida():
    texto = extraer_funcion(CODIGO, "predecir")
    assert texto.startswith("def predecir(X, w, b):")
    assert "return np.asarray(X) @ w + b" in texto


def test_no_trae_otras_funciones():
    texto = extraer_funcion(CODIGO, "predecir")
    assert "error_cuadratico_medio" not in texto
    assert "import numpy" not in texto


def test_incluye_el_cuerpo_completo():
    """Las líneas en blanco y los comentarios dentro del cuerpo no la cortan."""
    texto = extraer_funcion(CODIGO, "error_cuadratico_medio")
    assert '"""Calcula el MSE."""' in texto
    assert "# comentario dentro del cuerpo" in texto
    assert texto.rstrip().endswith("return np.mean(errores ** 2)")
    assert "def gradientes" not in texto


def test_ultima_funcion_del_archivo():
    assert extraer_funcion(CODIGO, "gradientes").strip() == "def gradientes(X, y, w, b):\n    pass"


def test_respeta_el_texto_original():
    """Devuelve el código tal cual, no una versión reformateada."""
    codigo = "def f(x):\n    return   x+1   # raro pero válido\n"
    assert extraer_funcion(codigo, "f") == "def f(x):\n    return   x+1   # raro pero válido"


def test_funcion_inexistente_es_none():
    assert extraer_funcion(CODIGO, "entrenar") is None


def test_nombre_parecido_no_cuenta():
    """'predecir' no debe encontrar 'predecir_todo', ni al revés."""
    codigo = "def predecir_todo(x):\n    return x\n"
    assert extraer_funcion(codigo, "predecir") is None


def test_solo_nivel_superior():
    """Un método de una clase o una función anidada no cuentan."""
    codigo = (
        "class Modelo:\n"
        "    def predecir(self, x):\n"
        "        return x\n"
        "\n"
        "def externa():\n"
        "    def gradientes():\n"
        "        return 0\n"
        "    return gradientes()\n"
    )
    assert extraer_funcion(codigo, "predecir") is None
    assert extraer_funcion(codigo, "gradientes") is None


def test_incluye_decoradores():
    codigo = "import functools\n\n@functools.cache\ndef f(x):\n    return x\n"
    assert extraer_funcion(codigo, "f") == "@functools.cache\ndef f(x):\n    return x"


def test_codigo_invalido_lanza_syntaxerror():
    with pytest.raises(SyntaxError):
        extraer_funcion("def predecir(X, w, b:\n    return X\n", "predecir")
