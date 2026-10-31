"""Regresión lineal entrenada con descenso de gradiente.

Archivo del estudiante para la segunda tarea de ejemplo, ya resuelto: sirve
para probar el tutor, no para practicar. Para probar el ciclo de revisión,
rompe a propósito una función (por ejemplo, cambia np.mean por np.sum) y pide
ayuda con ese subobjetivo. Los tests de cada subobjetivo están en
test_prediccion.py, test_costo.py, test_gradiente.py y test_entrenamiento.py.
Para ver resultados del modelo entrenado: python explorar.py

Notación (la misma en todas las funciones):
    n: cantidad de muestras.
    d: cantidad de variables (columnas) de cada muestra.
    X: matriz de datos, forma (n, d). Cada fila es una muestra.
    y: valores reales, forma (n,).
    w: pesos, forma (d,).
    b: sesgo, un número.

El modelo predice ŷ = X · w + b para todas las muestras a la vez, y se entrena
minimizando el error cuadrático medio entre ŷ e y.
"""
import numpy as np


def predecir(X, w, b):
    """Calcula las predicciones del modelo lineal para todas las muestras.

    Args:
        X: Matriz de datos de forma (n, d) (lista de listas o arreglo de numpy).
        w: Vector de pesos de largo d.
        b: Sesgo (un número).

    Returns:
        Un arreglo de numpy de forma (n,): la predicción de cada muestra,
        ŷ_i = w · x_i + b.
    """
    return np.asarray(X, dtype=float) @ np.asarray(w, dtype=float) + b


def error_cuadratico_medio(y, y_pred):
    """Calcula el error cuadrático medio (MSE) entre valores reales y predichos.

    MSE = (1/n) · Σ (y_pred_i - y_i)²

    Args:
        y: Valores reales, largo n (lista o arreglo de numpy).
        y_pred: Valores predichos, largo n.

    Returns:
        Un número (no un arreglo): el promedio de los errores al cuadrado.
    """
    errores = np.asarray(y_pred, dtype=float) - np.asarray(y, dtype=float)
    return float(np.mean(errores ** 2))


def gradientes(X, y, w, b):
    """Calcula el gradiente del MSE respecto de los pesos y del sesgo.

    Con ŷ = X · w + b y MSE = (1/n) · Σ (ŷ_i - y_i)², las derivadas parciales son:
        ∂MSE/∂w = (2/n) · Xᵀ · (ŷ - y)        (un vector de largo d)
        ∂MSE/∂b = (2/n) · Σ (ŷ_i - y_i)       (un número)

    Args:
        X: Matriz de datos de forma (n, d).
        y: Valores reales, largo n.
        w: Pesos actuales, largo d.
        b: Sesgo actual.

    Returns:
        Una tupla (dw, db): dw es un arreglo de numpy de forma (d,) y db es un
        número.
    """
    X = np.asarray(X, dtype=float)
    n = X.shape[0]
    errores = predecir(X, w, b) - np.asarray(y, dtype=float)
    dw = (2 / n) * (X.T @ errores)
    db = (2 / n) * float(np.sum(errores))
    return dw, db


def entrenar(X, y, tasa=0.1, epocas=1000):
    """Entrena el modelo con descenso de gradiente y devuelve los parámetros.

    Parte con w en ceros y b = 0. En cada época calcula los gradientes con todos
    los datos y da un paso en la dirección contraria:
        w ← w - tasa · dw
        b ← b - tasa · db

    Args:
        X: Matriz de datos de forma (n, d).
        y: Valores reales, largo n.
        tasa: Tasa de aprendizaje (tamaño del paso).
        epocas: Cantidad de pasos de descenso de gradiente.

    Returns:
        Una tupla (w, b) con los parámetros entrenados: w de forma (d,) y b un
        número. No debe modificar X ni y.
    """
    X = np.asarray(X, dtype=float)
    w = np.zeros(X.shape[1])
    b = 0.0
    for _ in range(epocas):
        dw, db = gradientes(X, y, w, b)
        w = w - tasa * dw
        b = b - tasa * db
    return w, b
