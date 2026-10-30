"""Una neurona con activación sigmoide.

Este es el archivo del estudiante para la tarea de ejemplo. Completa cada
función reemplazando el `pass`. Los tests de cada subobjetivo están en
test_sigmoide.py, test_derivada.py y test_forward.py.
"""
import numpy as np


def sigmoide(z):
    """Calcula la función sigmoide: 1 / (1 + e^(-z)).

    Args:
        z: Un número o un arreglo de numpy.

    Returns:
        Un valor entre 0 y 1 con la misma forma que z. Si z es un arreglo,
        la sigmoide se aplica elemento por elemento.
    """
    return 1 / (1 + np.exp(-z))


def derivada_sigmoide(z):
    """Calcula la derivada de la sigmoide evaluada en z.

    Args:
        z: Un número o un arreglo de numpy (la entrada de la sigmoide, no su
            salida).

    Returns:
        La derivada en z, con la misma forma que z.
    """
    s = sigmoide(z)
    return s * (1 - s)


def forward(x, w, b):
    """Calcula la salida de una neurona: la sigmoide del producto punto más el sesgo.

    Args:
        x: Vector de entradas (lista o arreglo de numpy).
        w: Vector de pesos, del mismo largo que x.
        b: Sesgo (un número).

    Returns:
        La activación de la neurona, un número entre 0 y 1.
    """
    z = np.dot(w, x) + b
    return sigmoide(z)
