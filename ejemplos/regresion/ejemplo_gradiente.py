"""Ejemplo oficial para el subobjetivo 'gradiente': el gradiente del MAE.

No es la solución de la tarea. Es el gradiente de otro costo, el error
absoluto medio, para el mismo modelo lineal ŷ = X · w + b. Con la regla de la
cadena, la derivada de |e| es signo(e), y queda:
    ∂MAE/∂w = (1/n) · Xᵀ · signo(ŷ - y)
    ∂MAE/∂b = (1/n) · Σ signo(ŷ_i - y_i)
Tu tarea pide el gradiente del MSE: la estructura es la misma, cambia lo que
multiplica a Xᵀ.

Qué mirar:
    - X.T @ v combina el error de cada muestra con sus variables: el resultado
      tiene un valor por columna de X, forma (d,), igual que w.
    - La derivada respecto de b no pasa por X: es el promedio del mismo vector.
    - Se devuelven las dos cosas juntas en una tupla.
    - Se comprueba con una derivada numérica, moviendo un parámetro a la vez.

Para probarlo:  python ejemplo_gradiente.py
"""
import numpy as np


def gradientes_mae(X, y, w, b):
    """Calcula el gradiente del error absoluto medio respecto de w y b.

    Args:
        X: Matriz de datos de forma (n, d).
        y: Valores reales, largo n.
        w: Pesos, largo d.
        b: Sesgo.

    Returns:
        Una tupla (dw, db): dw de forma (d,) y db un número.
    """
    X = np.asarray(X)
    n = X.shape[0]
    signos = np.sign(X @ w + b - y)
    dw = X.T @ signos / n
    db = np.sum(signos) / n
    return dw, db


if __name__ == "__main__":
    X = np.array([[1.0, 0.0], [2.0, 1.0], [0.0, 3.0]])
    y = np.array([1.0, 0.0, 2.0])
    w = np.array([0.5, 0.5])
    b = 0.25
    dw, db = gradientes_mae(X, y, w, b)
    print(dw, db)  # [ 0.33333333 -0.66666667] -0.3333333333333333

    # Comprobación numérica: las dos columnas deberían coincidir.
    def mae(w, b):
        return np.mean(np.abs(X @ w + b - y))

    h = 1e-6
    for j in range(2):
        paso = np.zeros(2)
        paso[j] = h
        print(dw[j], (mae(w + paso, b) - mae(w - paso, b)) / (2 * h))
    print(db, (mae(w, b + h) - mae(w, b - h)) / (2 * h))
