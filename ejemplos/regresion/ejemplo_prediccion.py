"""Ejemplo oficial para el subobjetivo 'prediccion': notas finales de un curso.

No es la solución de la tarea. Es otro cálculo con la misma forma: una matriz
de notas (una fila por estudiante, una columna por evaluación) multiplicada por
un vector de ponderaciones, más unas décimas extra que reciben todos. Tu
trabajo es reconocer esa misma forma en el modelo lineal.

Qué mirar:
    - notas @ ponderaciones multiplica cada fila por el vector y suma: el
      resultado tiene un valor por estudiante, forma (n,). np.dot hace lo mismo.
    - Las décimas son un solo número y numpy las suma a todos los elementos del
      vector (broadcasting). No hace falta un for ni repetir el número n veces.
    - El operador @ no funciona con listas de Python; np.asarray convierte la
      entrada en arreglo (y no copia nada si ya lo era).

Para probarlo:  python ejemplo_prediccion.py
"""
import numpy as np


def notas_finales(notas, ponderaciones, decimas):
    """Calcula la nota final de cada estudiante.

    Args:
        notas: Matriz de forma (n, k): n estudiantes, k evaluaciones.
        ponderaciones: Vector de largo k (suelen sumar 1).
        decimas: Puntaje extra que reciben todos (un número).

    Returns:
        Un arreglo de forma (n,) con la nota final de cada estudiante.
    """
    notas = np.asarray(notas)
    ponderaciones = np.asarray(ponderaciones)
    return notas @ ponderaciones + decimas


if __name__ == "__main__":
    notas = [[5.0, 6.0, 4.0],    # estudiante 1
             [7.0, 6.5, 6.0]]    # estudiante 2
    ponderaciones = [0.3, 0.3, 0.4]
    print(np.asarray(notas) @ np.asarray(ponderaciones))  # [4.9 6.45]
    print(notas_finales(notas, ponderaciones, 0.2))       # [5.1  6.65]
    print(notas_finales(notas, ponderaciones, 0.2).shape) # (2,)
