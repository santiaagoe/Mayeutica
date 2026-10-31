"""Ejemplo oficial para el subobjetivo 'costo': el error absoluto medio (MAE).

No es la solución de la tarea. El MAE es otra forma de medir qué tan lejos
están las predicciones: promedia el valor absoluto de cada error,
    MAE = (1/n) · Σ |y_pred_i - y_i|
Tu tarea pide el error cuadrático medio, que en vez del valor absoluto eleva
cada error al cuadrado.

Qué mirar:
    - y_pred - y resta elemento por elemento y da el vector de errores.
    - np.abs se aplica a cada elemento; np.mean promedia (divide por n, no
      solo suma), así que el resultado no depende de cuántos datos hay.
    - np.mean devuelve un solo número, no un arreglo.

Para probarlo:  python ejemplo_costo.py
"""
import numpy as np


def error_absoluto_medio(y, y_pred):
    """Calcula el error absoluto medio entre valores reales y predichos.

    Args:
        y: Valores reales, largo n.
        y_pred: Valores predichos, largo n.

    Returns:
        Un número: el promedio de los errores en valor absoluto.
    """
    errores = np.asarray(y_pred) - np.asarray(y)
    return np.mean(np.abs(errores))


if __name__ == "__main__":
    y = [1.0, 2.0, 3.0]
    y_pred = [2.0, 2.0, 5.0]
    print(np.asarray(y_pred) - np.asarray(y))  # [1. 0. 2.]
    print(error_absoluto_medio(y, y_pred))     # 1.0  ->  (1 + 0 + 2) / 3
    print(error_absoluto_medio([0.0, 0.0], [1.0, -1.0]))  # 1.0, los signos no se cancelan
