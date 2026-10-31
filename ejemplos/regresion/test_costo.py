"""Tests del subobjetivo 'costo'."""
import numpy as np
import pytest

from regresion import error_cuadratico_medio


def test_cero_si_las_predicciones_son_exactas():
    y = np.array([1.0, -2.0, 3.5])
    assert error_cuadratico_medio(y, y.copy()) == pytest.approx(0.0)


def test_valor_conocido():
    # Errores: 1, 0, 2  ->  (1 + 0 + 4) / 3
    y = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([2.0, 2.0, 5.0])
    assert error_cuadratico_medio(y, y_pred) == pytest.approx(5 / 3)


def test_es_un_promedio_y_no_una_suma():
    # Repetir los mismos datos no cambia el promedio.
    y = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([2.0, 2.0, 5.0])
    doble = error_cuadratico_medio(np.tile(y, 2), np.tile(y_pred, 2))
    assert doble is not None
    assert doble == pytest.approx(5 / 3)


def test_errores_negativos_no_se_cancelan():
    # Un error de +1 y otro de -1 no suman cero: se elevan al cuadrado.
    assert error_cuadratico_medio([0.0, 0.0], [1.0, -1.0]) == pytest.approx(1.0)


def test_castiga_mas_los_errores_grandes():
    # El doble de error da el cuádruple de costo.
    y = np.zeros(4)
    uno = error_cuadratico_medio(y, np.full(4, 1.0))
    dos = error_cuadratico_medio(y, np.full(4, 2.0))
    assert dos == pytest.approx(4 * uno)


def test_es_simetrico():
    y = np.array([0.5, 1.5, -2.0])
    y_pred = np.array([1.0, 1.0, 0.0])
    ida = error_cuadratico_medio(y, y_pred)
    assert ida is not None and ida > 0
    assert ida == pytest.approx(error_cuadratico_medio(y_pred, y))


def test_acepta_listas_y_devuelve_un_numero():
    costo = error_cuadratico_medio([1.0, 2.0, 3.0], [2.0, 2.0, 5.0])
    assert costo is not None
    assert np.ndim(costo) == 0
    assert float(costo) == pytest.approx(5 / 3)
