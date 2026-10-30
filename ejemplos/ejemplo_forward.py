"""Ejemplo oficial para el subobjetivo 'forward': una neurona con activación gaussiana.

No es la solución de la tarea: la neurona de la tarea usa la sigmoide. Una
neurona hace siempre dos pasos, y aquí se ven separados:
    1. Combinación lineal: z = w · x + b (producto punto más el sesgo).
    2. Activación: la salida es f(z).

Qué mirar:
    - np.dot(w, x) multiplica elemento por elemento y suma: w[0]*x[0] + w[1]*x[1] + ...
      Funciona con listas o con arreglos de numpy, y w y x deben tener el mismo largo.
    - El sesgo b se suma después del producto punto, una sola vez.
    - La activación recibe z, que es un solo número.

Para probarlo:  python ejemplo_forward.py
"""
import numpy as np

from ejemplo_sigmoide import gaussiana


def forward_gaussiana(x, w, b):
    """Calcula la salida de una neurona con activación gaussiana.

    Args:
        x: Vector de entradas (lista o arreglo de numpy).
        w: Vector de pesos, del mismo largo que x.
        b: Sesgo (un número).

    Returns:
        La activación de la neurona, un número entre 0 y 1.
    """
    z = np.dot(w, x) + b
    return gaussiana(z)


if __name__ == "__main__":
    x = [1.0, 2.0]
    w = [0.5, -0.25]
    print(np.dot(w, x))                    # 0.0  -> 0.5*1 + (-0.25)*2
    print(forward_gaussiana(x, w, 0.0))    # 1.0
    print(forward_gaussiana(x, w, 1.0))    # 0.36787944117144233
