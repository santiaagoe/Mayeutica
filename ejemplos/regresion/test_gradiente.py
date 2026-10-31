"""Tests del subobjetivo 'gradiente'."""
import numpy as np
import pytest

from regresion import gradientes


def mse_referencia(X, y, w, b):
    """MSE calculado aquí, sin usar tus funciones."""
    return np.mean((X @ w + b - y) ** 2)


def test_devuelve_dw_y_db():
    X = np.ones((4, 3))
    resultado = gradientes(X, np.zeros(4), np.zeros(3), 0.0)
    assert isinstance(resultado, tuple) and len(resultado) == 2
    dw, db = resultado
    assert isinstance(dw, np.ndarray) and dw.shape == (3,)
    assert np.ndim(db) == 0


def test_valor_conocido():
    # X = [[1], [2]], y = [1, 2], w = [0], b = 0  ->  ŷ = [0, 0], ŷ - y = [-1, -2]
    # dw = (2/2) · (1·(-1) + 2·(-2)) = -5      db = (2/2) · (-1 - 2) = -3
    X = np.array([[1.0], [2.0]])
    y = np.array([1.0, 2.0])
    dw, db = gradientes(X, y, np.array([0.0]), 0.0)
    assert dw == pytest.approx([-5.0])
    assert db == pytest.approx(-3.0)


def test_cero_en_el_optimo():
    # Si y se generó exactamente con w y b, el error es mínimo y el gradiente es cero.
    rng = np.random.default_rng(2)
    X = rng.normal(size=(30, 3))
    w = np.array([1.0, -2.0, 0.5])
    b = 4.0
    dw, db = gradientes(X, X @ w + b, w, b)
    assert dw == pytest.approx(np.zeros(3), abs=1e-10)
    assert db == pytest.approx(0.0, abs=1e-10)


def test_signo_del_sesgo():
    # Si el modelo predice de más, bajar b reduce el error: db debe ser positivo.
    X = np.array([[1.0], [2.0], [3.0]])
    y = np.array([1.0, 2.0, 3.0])
    _, db = gradientes(X, y, np.array([1.0]), 10.0)
    assert db > 0


def test_coincide_con_gradiente_numerico():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(25, 4))
    y = rng.normal(size=25)
    w = rng.normal(size=4)
    b = rng.normal()
    dw, db = gradientes(X, y, w, b)

    h = 1e-6
    for j in range(4):
        paso = np.zeros(4)
        paso[j] = h
        numerica = (mse_referencia(X, y, w + paso, b) - mse_referencia(X, y, w - paso, b)) / (2 * h)
        assert dw[j] == pytest.approx(numerica, rel=1e-5)
    numerica_b = (mse_referencia(X, y, w, b + h) - mse_referencia(X, y, w, b - h)) / (2 * h)
    assert db == pytest.approx(numerica_b, rel=1e-5)


def test_es_un_promedio_y_no_una_suma():
    # Repetir los datos no cambia el gradiente.
    X = np.array([[1.0, 0.5], [2.0, -1.0], [0.0, 3.0]])
    y = np.array([1.0, 0.0, 2.0])
    w = np.array([0.3, 0.2])
    dw1, db1 = gradientes(X, y, w, 0.1)
    dw2, db2 = gradientes(np.vstack([X, X]), np.tile(y, 2), w, 0.1)
    assert dw2 == pytest.approx(dw1)
    assert db2 == pytest.approx(db1)
