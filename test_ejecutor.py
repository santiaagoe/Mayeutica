"""Tests de ejecutor.py.

Cada test arma en una carpeta temporal un "código del estudiante" y su archivo
de tests, y revisa lo que devuelve correr_pytest. Son más lentos que los otros
porque cada uno lanza pytest en un proceso aparte.

    pytest test_ejecutor.py
"""

import time

from ejecutor import ResultadoTests, correr_pytest


def preparar(carpeta, codigo, tests):
    """Escribe mi_codigo.py y test_mi_codigo.py y devuelve la ruta de los tests."""
    (carpeta / "mi_codigo.py").write_text(codigo, encoding="utf-8")
    ruta = carpeta / "test_mi_codigo.py"
    ruta.write_text(tests, encoding="utf-8")
    return str(ruta)


CODIGO_BIEN = "def doble(x):\n    return 2 * x\n"
CODIGO_MAL = "def doble(x):\n    return x\n"
TESTS = "from mi_codigo import doble\n\ndef test_doble():\n    assert doble(3) == 6\n"


def test_devuelve_resultado_tests(tmp_path):
    resultado = correr_pytest(preparar(tmp_path, CODIGO_BIEN, TESTS))
    assert isinstance(resultado, ResultadoTests)
    assert isinstance(resultado.salida, str)


def test_codigo_correcto_pasa(tmp_path):
    resultado = correr_pytest(preparar(tmp_path, CODIGO_BIEN, TESTS))
    assert resultado.paso is True
    assert "passed" in resultado.salida


def test_codigo_incorrecto_no_pasa(tmp_path):
    resultado = correr_pytest(preparar(tmp_path, CODIGO_MAL, TESTS))
    assert resultado.paso is False
    assert "failed" in resultado.salida


def test_error_de_sintaxis_no_pasa(tmp_path):
    resultado = correr_pytest(preparar(tmp_path, "def doble(x)\n    return 2 * x\n", TESTS))
    assert resultado.paso is False
    assert resultado.salida


def test_archivo_sin_tests_no_pasa(tmp_path):
    """Si no se corrió ningún test, no hay nada que demuestre que el código funciona."""
    resultado = correr_pytest(preparar(tmp_path, CODIGO_BIEN, "from mi_codigo import doble\n"))
    assert resultado.paso is False


def test_archivo_inexistente_no_lanza_error(tmp_path):
    resultado = correr_pytest(str(tmp_path / "no_existe.py"))
    assert resultado.paso is False
    assert resultado.salida


def test_no_depende_del_directorio_actual(tmp_path, monkeypatch):
    """Claude Desktop lanza el servidor desde cualquier carpeta."""
    carpeta = tmp_path / "tarea"
    carpeta.mkdir()
    ruta = preparar(carpeta, CODIGO_BIEN, TESTS)
    otra = tmp_path / "otra"
    otra.mkdir()
    monkeypatch.chdir(otra)
    assert correr_pytest(ruta).paso is True


def test_loop_infinito_se_corta(tmp_path):
    codigo = "def doble(x):\n    while True:\n        pass\n"
    inicio = time.monotonic()
    resultado = correr_pytest(preparar(tmp_path, codigo, TESTS), timeout=2)
    assert time.monotonic() - inicio < 10
    assert resultado.paso is False
    assert resultado.salida
