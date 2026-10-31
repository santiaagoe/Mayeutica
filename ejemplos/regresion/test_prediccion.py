"""Tests del subobjetivo 'prediccion'."""
import numpy as np
import pytest

from regresion import predecir


def test_valor_conocido():
    # Fila 1: 1*2 + 2*3 + 1 = 9.  Fila 2: 0*2 + (-1)*3 + 1 = -2.
    X = np.array([[1.0, 2.0], [0.0, -1.0]])
    w = np.array([2.0, 3.0])
    assert predecir(X, w, 1.0) == pytest.approx([9.0, -2.0])


def test_devuelve_una_prediccion_por_muestra():
    X = np.ones((5, 3))
    y_pred = predecir(X, np.zeros(3), 0.0)
    assert isinstance(y_pred, np.ndarray)
    assert y_pred.shape == (5,)


def test_pesos_cero_predicen_el_sesgo():
    X = np.array([[3.0, -1.0], [10.0, 4.0], [0.5, 0.5]])
    assert predecir(X, np.zeros(2), 7.0) == pytest.approx([7.0, 7.0, 7.0])


def test_el_sesgo_se_suma_a_todas_las_muestras():
    X = np.array([[1.0], [2.0], [3.0]])
    w = np.array([1.0])
    diferencia = predecir(X, w, 5.0) - predecir(X, w, 0.0)
    assert diferencia == pytest.approx([5.0, 5.0, 5.0])


def test_una_sola_muestra():
    X = np.array([[1.0, 2.0, 3.0]])
    y_pred = predecir(X, np.array([1.0, 1.0, 1.0]), 0.0)
    assert y_pred.shape == (1,)
    assert y_pred[0] == pytest.approx(6.0)


def test_acepta_listas():
    y_pred = predecir([[1.0, 2.0], [0.0, -1.0]], [2.0, 3.0], 1.0)
    assert y_pred == pytest.approx([9.0, -2.0])


def test_coincide_con_un_for():
    # Lo mismo calculado muestra por muestra, sin usar tu función.
    rng = np.random.default_rng(1)
    X = rng.normal(size=(20, 4))
    w = rng.normal(size=4)
    b = rng.normal()
    esperado = [sum(X[i, j] * w[j] for j in range(4)) + b for i in range(20)]
    assert predecir(X, w, b) == pytest.approx(esperado)
