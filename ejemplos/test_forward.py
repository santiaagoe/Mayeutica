"""Tests del subobjetivo 'forward'."""
import numpy as np
import pytest

from neurona import forward


def test_entrada_neta_cero_da_un_medio():
    # 1*0.5 + 2*(-0.25) + 0 = 0  ->  σ(0) = 0.5
    assert forward(np.array([1.0, 2.0]), np.array([0.5, -0.25]), 0.0) == pytest.approx(0.5)


def test_valor_conocido():
    # 1*0.3 + 2*0.4 + 0.1 = 1.2  ->  σ(1.2)
    salida = forward(np.array([1.0, 2.0]), np.array([0.3, 0.4]), 0.1)
    assert salida == pytest.approx(0.7685247834990175)


def test_el_sesgo_importa():
    x = np.array([1.0, 1.0, 1.0])
    w = np.array([1.0, 1.0, 1.0])
    assert forward(x, w, -3.0) == pytest.approx(0.5)
    assert forward(x, w, 0.0) > forward(x, w, -3.0)


def test_acepta_listas():
    assert forward([1.0, 2.0], [0.3, 0.4], 0.1) == pytest.approx(0.7685247834990175)


def test_salida_entre_cero_y_uno():
    rng = np.random.default_rng(0)
    for _ in range(20):
        x = rng.normal(size=4)
        w = rng.normal(size=4)
        b = rng.normal()
        s = forward(x, w, b)
        assert 0 < s < 1


def test_devuelve_un_escalar():
    salida = forward(np.array([1.0, 2.0]), np.array([0.3, 0.4]), 0.1)
    assert salida is not None
    assert np.ndim(salida) == 0
    assert float(salida) == pytest.approx(0.7685247834990175)
