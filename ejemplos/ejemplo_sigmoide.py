"""Ejemplo oficial para el subobjetivo 'sigmoide': la activación gaussiana.

No es la solución de la tarea. Es una función de activación distinta,
g(z) = e^(-z²), escrita igual que se escribe una activación con numpy. Tu
trabajo es adaptar la idea a la sigmoide, 1 / (1 + e^(-z)).

Qué mirar:
    - np.exp (no math.exp) funciona tanto con un número como con un arreglo, y
      aplica la operación elemento por elemento. math.exp falla con arreglos.
    - Las operaciones aritméticas (**, -, /) también son elemento por elemento,
      así que la función completa no necesita ningún for.
    - Con valores muy grandes, e^(-z²) se acerca a 0 sin dar nan.

Para probarlo:  python ejemplo_sigmoide.py
"""
import numpy as np


def gaussiana(z):
    """Calcula la activación gaussiana: e^(-z²).

    Args:
        z: Un número o un arreglo de numpy.

    Returns:
        Un valor entre 0 y 1 con la misma forma que z (1 cuando z = 0).
    """
    return np.exp(-z ** 2)


if __name__ == "__main__":
    print(gaussiana(0))                           # 1.0
    print(gaussiana(1))                           # 0.36787944117144233
    print(gaussiana(np.array([-2.0, 0.0, 2.0])))  # [0.01831564 1.         0.01831564]
    print(gaussiana(np.array([-1000.0, 1000.0]))) # [0. 0.]
