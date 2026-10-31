"""Tests del subobjetivo 'entrenamiento'."""
import numpy as np
import pytest

from regresion import entrenar


def datos_sinteticos(ruido=0.0, semilla=4):
    """y = 2·x1 - 3·x2 + 5, con ruido opcional."""
    rng = np.random.default_rng(semilla)
    X = rng.normal(size=(100, 2))
    y = X @ np.array([2.0, -3.0]) + 5.0 + ruido * rng.normal(size=100)
    return X, y


def mse_referencia(X, y, w, b):
    return np.mean((X @ w + b - y) ** 2)


def test_devuelve_w_y_b():
    X, y = datos_sinteticos()
    resultado = entrenar(X, y, tasa=0.1, epocas=10)
    assert isinstance(resultado, tuple) and len(resultado) == 2
    w, b = resultado
    assert isinstance(w, np.ndarray) and w.shape == (2,)
    assert np.ndim(b) == 0


def test_cero_epocas_deja_los_valores_iniciales():
    X, y = datos_sinteticos()
    w, b = entrenar(X, y, tasa=0.1, epocas=0)
    assert w == pytest.approx([0.0, 0.0])
    assert b == pytest.approx(0.0)


def test_recupera_los_parametros_sin_ruido():
    X, y = datos_sinteticos()
    w, b = entrenar(X, y, tasa=0.1, epocas=1000)
    assert w == pytest.approx([2.0, -3.0], abs=1e-3)
    assert b == pytest.approx(5.0, abs=1e-3)


def test_con_ruido_se_acerca():
    X, y = datos_sinteticos(ruido=0.5)
    w, b = entrenar(X, y, tasa=0.1, epocas=1000)
    assert w == pytest.approx([2.0, -3.0], abs=0.2)
    assert b == pytest.approx(5.0, abs=0.2)


def test_mas_epocas_dan_menor_error():
    X, y = datos_sinteticos(ruido=0.5)
    costos = []
    for epocas in [1, 5, 20, 100]:
        w, b = entrenar(X, y, tasa=0.05, epocas=epocas)
        costos.append(mse_referencia(X, y, w, b))
    assert all(a > c for a, c in zip(costos, costos[1:]))


def test_un_paso_va_en_contra_del_gradiente():
    # Desde w = 0, b = 0 el primer paso es -tasa · gradiente.
    # Aquí: ŷ = 0, ŷ - y = [-1, -2]  ->  dw = -5, db = -3  ->  w = 0.5, b = 0.3
    X = np.array([[1.0], [2.0]])
    y = np.array([1.0, 2.0])
    w, b = entrenar(X, y, tasa=0.1, epocas=1)
    assert w == pytest.approx([0.5])
    assert b == pytest.approx(0.3)


def test_no_modifica_los_datos():
    X, y = datos_sinteticos()
    X_original, y_original = X.copy(), y.copy()
    resultado = entrenar(X, y, tasa=0.1, epocas=50)
    assert resultado is not None
    assert np.array_equal(X, X_original)
    assert np.array_equal(y, y_original)
