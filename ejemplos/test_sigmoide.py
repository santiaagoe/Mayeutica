"""Tests del subobjetivo 'sigmoide'."""
import numpy as np
import pytest

from neurona import sigmoide


def test_en_cero_vale_un_medio():
    assert sigmoide(0) == pytest.approx(0.5)


def test_valores_conocidos():
    assert sigmoide(1) == pytest.approx(0.7310585786300049)
    assert sigmoide(2) == pytest.approx(0.8807970779778823)
    assert sigmoide(-1) == pytest.approx(0.2689414213699951)


def test_simetria():
    # σ(z) + σ(-z) = 1 para cualquier z
    for z in [0.3, 1.5, 4.0, 10.0]:
        assert sigmoide(z) + sigmoide(-z) == pytest.approx(1.0)


def test_queda_entre_cero_y_uno():
    z = np.linspace(-20, 20, 101)
    s = sigmoide(z)
    assert np.all(s >= 0) and np.all(s <= 1)


def test_es_creciente():
    z = np.linspace(-10, 10, 50)
    assert np.all(np.diff(sigmoide(z)) > 0)


def test_funciona_con_arreglos():
    z = np.array([[-1.0, 0.0], [1.0, 2.0]])
    s = sigmoide(z)
    assert isinstance(s, np.ndarray)
    assert s.shape == z.shape
    assert s[0, 1] == pytest.approx(0.5)
    assert s[1, 0] == pytest.approx(0.7310585786300049)


def test_valores_extremos_no_dan_nan():
    s = sigmoide(np.array([-1000.0, 1000.0]))
    assert not np.any(np.isnan(s))
    assert s[0] == pytest.approx(0.0, abs=1e-12)
    assert s[1] == pytest.approx(1.0)
