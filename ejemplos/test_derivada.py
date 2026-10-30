"""Tests del subobjetivo 'derivada'."""
import numpy as np
import pytest

from neurona import derivada_sigmoide


def test_en_cero_vale_un_cuarto():
    assert derivada_sigmoide(0) == pytest.approx(0.25)


def test_valores_conocidos():
    assert derivada_sigmoide(1) == pytest.approx(0.19661193324148185)
    assert derivada_sigmoide(-2.5) == pytest.approx(0.07010371654510815)


def test_es_simetrica():
    for z in [0.5, 2.0, 5.0]:
        d = derivada_sigmoide(z)
        assert d is not None and d > 0
        assert d == pytest.approx(derivada_sigmoide(-z))


def test_maximo_en_cero():
    z = np.linspace(-6, 6, 121)
    d = derivada_sigmoide(z)
    assert z[np.argmax(d)] == pytest.approx(0.0)


def test_coincide_con_derivada_numerica():
    # Compara contra (σ(z+h) - σ(z-h)) / 2h, calculado aquí sin usar tu sigmoide.
    def sig(z):
        return 1 / (1 + np.exp(-z))

    h = 1e-5
    for z in [-3.0, -0.7, 0.0, 1.3, 4.0]:
        numerica = (sig(z + h) - sig(z - h)) / (2 * h)
        assert derivada_sigmoide(z) == pytest.approx(numerica, rel=1e-6)


def test_funciona_con_arreglos():
    z = np.array([-1.0, 0.0, 1.0])
    d = derivada_sigmoide(z)
    assert isinstance(d, np.ndarray)
    assert d.shape == z.shape
    assert d[1] == pytest.approx(0.25)


def test_casi_cero_lejos_del_origen():
    d = derivada_sigmoide(np.array([-50.0, 50.0]))
    assert np.all(d >= 0)
    assert np.all(d < 1e-10)
