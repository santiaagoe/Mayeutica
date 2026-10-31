"""Ejemplo oficial para el subobjetivo 'entrenamiento': descenso de gradiente.

No es la solución de la tarea. Aquí no hay datos ni modelo: se busca el mínimo
de una función conocida de dos variables,
    f(p) = (p[0] - 1)² + 10 · (p[1] + 2)²
cuyo mínimo está en p = (1, -2). Su gradiente es (2·(p[0] - 1), 20·(p[1] + 2)).
Tu tarea usa el mismo ciclo, pero el gradiente sale de tu función gradientes y
hay dos parámetros que actualizar (w y b).

Qué mirar:
    - Se parte de un punto inicial (ceros) creado dentro de la función, con la
      forma correcta: np.zeros(2).
    - Cada época hace siempre lo mismo: calcular el gradiente donde estás y dar
      un paso en la dirección contraria, multiplicado por la tasa.
    - p = p - tasa * g crea un arreglo nuevo. Así no se modifica nada que haya
      venido de afuera.
    - Si la tasa es muy grande el ciclo se descontrola; prueba con tasa=0.11.

Para probarlo:  python ejemplo_entrenamiento.py
"""
import numpy as np


def gradiente_f(p):
    """Gradiente de f(p) = (p[0] - 1)² + 10 · (p[1] + 2)²."""
    return np.array([2 * (p[0] - 1), 20 * (p[1] + 2)])


def descenso_de_gradiente(tasa=0.05, epocas=200):
    """Busca el mínimo de f con descenso de gradiente partiendo de (0, 0).

    Args:
        tasa: Tamaño del paso.
        epocas: Cantidad de pasos.

    Returns:
        El punto p (arreglo de forma (2,)) al que se llega.
    """
    p = np.zeros(2)
    for _ in range(epocas):
        g = gradiente_f(p)
        p = p - tasa * g
    return p


if __name__ == "__main__":
    print(descenso_de_gradiente(epocas=0))    # [0. 0.]
    print(descenso_de_gradiente(epocas=1))    # [ 0.1 -2. ]
    print(descenso_de_gradiente(epocas=200))  # [ 1. -2.] (redondeado)
    print(descenso_de_gradiente(tasa=0.11, epocas=50))  # diverge: números enormes
