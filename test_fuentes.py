"""Tests de fuentes/ (Bloque, Fuente y FuenteNotebook).

Una función a la vez:

    pytest test_fuentes.py -k bloque    (ya pasan: Bloque y Fuente vienen hechos)
    pytest test_fuentes.py -k source
    pytest test_fuentes.py -k tipo
    pytest test_fuentes.py -k leer

Ojo con -k: filtra por subcadena del nombre. Cada grupo lleva su palabra y
ningún test de otro grupo la lleva.
"""

import dataclasses
import json

import pytest

from fuentes import TIPOS, Bloque, Fuente, FuenteNotebook
from fuentes.notebook import MARCAS_POR_COMPLETAR, texto_de_source, tipo_de_celda


# ---------------------------------------------------------------------------
# Auxiliares: arman celdas y notebooks como los que escribe Jupyter
# ---------------------------------------------------------------------------

def celda_md(texto, id_celda="md1"):
    return {
        "cell_type": "markdown",
        "id": id_celda,
        "metadata": {},
        "source": texto.splitlines(keepends=True),
    }


def celda_codigo(texto, id_celda="code1", outputs=None):
    return {
        "cell_type": "code",
        "id": id_celda,
        "metadata": {},
        "execution_count": None,
        "outputs": outputs or [],
        "source": texto.splitlines(keepends=True),
    }


def escribir_notebook(tmp_path, celdas, nombre="tarea.ipynb", minor=5):
    ruta = tmp_path / nombre
    notebook = {
        "cells": celdas,
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": minor,
    }
    ruta.write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
    return ruta


# ---------------------------------------------------------------------------
# Bloque y Fuente (vienen hechos; estos tests documentan cómo se usan)
# ---------------------------------------------------------------------------

def test_bloque_celda_es_none_por_defecto():
    assert Bloque("texto", "hola").celda is None


def test_bloque_iguales_si_tienen_los_mismos_datos():
    assert Bloque("codigo", "x = 1", "c1") == Bloque("codigo", "x = 1", "c1")


def test_bloque_es_inmutable():
    bloque = Bloque("texto", "hola")
    with pytest.raises(dataclasses.FrozenInstanceError):
        bloque.contenido = "chao"


def test_bloque_valores_validos():
    assert TIPOS == ("texto", "codigo", "por_completar")


def test_bloque_fuente_no_se_puede_instanciar():
    with pytest.raises(TypeError):
        Fuente()


def test_bloque_notebook_es_una_fuente():
    assert issubclass(FuenteNotebook, Fuente)


# ---------------------------------------------------------------------------
# texto_de_source
# ---------------------------------------------------------------------------

def test_source_lista_de_lineas_se_une():
    assert texto_de_source(["a = 1\n", "b = 2"]) == "a = 1\nb = 2"


def test_source_string_queda_igual():
    assert texto_de_source("a = 1\nb = 2") == "a = 1\nb = 2"


def test_source_lista_vacia():
    assert texto_de_source([]) == ""


def test_source_string_vacio():
    assert texto_de_source("") == ""


def test_source_no_agrega_saltos_de_linea():
    # Las líneas ya traen su "\n": unirlas con "\n" los duplicaría.
    assert texto_de_source(["a\n", "b\n", "c"]) == "a\nb\nc"


# ---------------------------------------------------------------------------
# tipo_de_celda
# ---------------------------------------------------------------------------

def test_tipo_markdown_es_texto():
    assert tipo_de_celda(celda_md("# Tarea 1\nImplementa la sigmoide.")) == "texto"


def test_tipo_markdown_vacio_se_descarta():
    assert tipo_de_celda(celda_md("")) is None


def test_tipo_markdown_solo_espacios_se_descarta():
    assert tipo_de_celda(celda_md("   \n\n  ")) is None


def test_tipo_raw_es_texto():
    celda = {"cell_type": "raw", "metadata": {}, "source": ["Entrega: viernes"]}
    assert tipo_de_celda(celda) == "texto"


def test_tipo_codigo_con_contenido_es_codigo():
    assert tipo_de_celda(celda_codigo("import numpy as np")) == "codigo"


def test_tipo_codigo_vacio_es_por_completar():
    assert tipo_de_celda(celda_codigo("")) == "por_completar"


def test_tipo_codigo_solo_espacios_es_por_completar():
    assert tipo_de_celda(celda_codigo("  \n\n")) == "por_completar"


def test_tipo_marca_en_espanol_es_por_completar():
    assert tipo_de_celda(celda_codigo("# TU CÓDIGO AQUÍ\n")) == "por_completar"


def test_tipo_marca_sin_tildes_es_por_completar():
    assert tipo_de_celda(celda_codigo("# tu codigo aqui")) == "por_completar"


def test_tipo_marca_mayusculas_mezcladas_es_por_completar():
    assert tipo_de_celda(celda_codigo("# Tu Código Aquí")) == "por_completar"


def test_tipo_marca_de_nbgrader_es_por_completar():
    texto = "# YOUR CODE HERE\nraise NotImplementedError()"
    assert tipo_de_celda(celda_codigo(texto)) == "por_completar"


def test_tipo_marca_dentro_de_una_funcion_es_por_completar():
    texto = "def sigmoide(z):\n    # TU CÓDIGO AQUÍ\n    pass\n"
    assert tipo_de_celda(celda_codigo(texto)) == "por_completar"


def test_tipo_codigo_parecido_a_la_marca_es_codigo():
    # "código" sola no es la marca.
    assert tipo_de_celda(celda_codigo("# Este código carga los datos\nx = 1")) == "codigo"


def test_tipo_texto_en_un_solo_string():
    celda = {"cell_type": "code", "metadata": {}, "outputs": [], "source": "x = 1"}
    assert tipo_de_celda(celda) == "codigo"


def test_tipo_desconocido_se_descarta():
    celda = {"cell_type": "otra_cosa", "metadata": {}, "source": ["hola"]}
    assert tipo_de_celda(celda) is None


def test_tipo_marcas_vienen_normalizadas():
    # Si alguien agrega una marca, tiene que venir en minúsculas y sin tildes.
    for marca in MARCAS_POR_COMPLETAR:
        assert marca == marca.lower()
        assert marca.isascii()


# ---------------------------------------------------------------------------
# FuenteNotebook.leer
# ---------------------------------------------------------------------------

def test_leer_devuelve_una_lista(tmp_path):
    ruta = escribir_notebook(tmp_path, [celda_md("# Tarea")])
    resultado = FuenteNotebook(ruta).leer()
    assert isinstance(resultado, list)
    assert all(isinstance(b, Bloque) for b in resultado)


def test_leer_una_entrada_por_celda(tmp_path):
    ruta = escribir_notebook(tmp_path, [
        celda_md("# Tarea 1", "a"),
        celda_codigo("import numpy as np", "b"),
        celda_codigo("# TU CÓDIGO AQUÍ", "c"),
    ])
    assert FuenteNotebook(ruta).leer() == [
        Bloque("texto", "# Tarea 1", "a"),
        Bloque("codigo", "import numpy as np", "b"),
        Bloque("por_completar", "# TU CÓDIGO AQUÍ", "c"),
    ]


def test_leer_respeta_el_orden(tmp_path):
    ruta = escribir_notebook(tmp_path, [
        celda_codigo("x = 1", "primera"),
        celda_md("Explicación", "segunda"),
        celda_codigo("y = 2", "tercera"),
    ])
    ids = [b.celda for b in FuenteNotebook(ruta).leer()]
    assert ids == ["primera", "segunda", "tercera"]


def test_leer_conserva_el_contenido_completo(tmp_path):
    # La marca no se quita: el LLM la necesita para entender qué se pide.
    texto = "def sigmoide(z):\n    # TU CÓDIGO AQUÍ\n    pass\n"
    ruta = escribir_notebook(tmp_path, [celda_codigo(texto, "s")])
    assert FuenteNotebook(ruta).leer() == [Bloque("por_completar", texto, "s")]


def test_leer_descarta_markdown_vacio(tmp_path):
    ruta = escribir_notebook(tmp_path, [
        celda_md("# Tarea", "a"),
        celda_md("", "vacia"),
        celda_md("Fin", "b"),
    ])
    ids = [b.celda for b in FuenteNotebook(ruta).leer()]
    assert ids == ["a", "b"]


def test_leer_incluye_celdas_de_codigo_vacias(tmp_path):
    ruta = escribir_notebook(tmp_path, [celda_codigo("", "vacia")])
    assert FuenteNotebook(ruta).leer() == [Bloque("por_completar", "", "vacia")]


def test_leer_no_incluye_outputs(tmp_path):
    salida = [{"output_type": "stream", "name": "stdout", "text": ["SALIDA_ESPERADA\n"]}]
    ruta = escribir_notebook(tmp_path, [celda_codigo("print(f(2))", "c", outputs=salida)])
    bloques = FuenteNotebook(ruta).leer()
    assert all("SALIDA_ESPERADA" not in b.contenido for b in bloques)


def test_leer_celda_sin_id_da_none(tmp_path):
    celda = celda_md("Notebook viejo")
    del celda["id"]
    ruta = escribir_notebook(tmp_path, [celda], minor=4)
    assert FuenteNotebook(ruta).leer() == [Bloque("texto", "Notebook viejo", None)]


def test_leer_texto_en_un_solo_string(tmp_path):
    celda = {"cell_type": "code", "id": "c", "metadata": {}, "outputs": [],
             "execution_count": None, "source": "a = 1\nb = 2"}
    ruta = escribir_notebook(tmp_path, [celda])
    assert FuenteNotebook(ruta).leer() == [Bloque("codigo", "a = 1\nb = 2", "c")]


def test_leer_tildes_y_enie(tmp_path):
    texto = "## Función sigmoide\nCalcula σ(z) para cada año."
    ruta = escribir_notebook(tmp_path, [celda_md(texto, "m")])
    assert FuenteNotebook(ruta).leer()[0].contenido == texto


def test_leer_notebook_sin_celdas(tmp_path):
    ruta = escribir_notebook(tmp_path, [])
    assert FuenteNotebook(ruta).leer() == []


def test_leer_acepta_ruta_como_string(tmp_path):
    ruta = escribir_notebook(tmp_path, [celda_md("# Tarea", "a")])
    assert FuenteNotebook(str(ruta)).leer() == [Bloque("texto", "# Tarea", "a")]


def test_leer_archivo_inexistente_lanza_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        FuenteNotebook(tmp_path / "no_existe.ipynb").leer()


def test_leer_json_invalido_lanza_valueerror(tmp_path):
    ruta = tmp_path / "roto.ipynb"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        FuenteNotebook(ruta).leer()


def test_leer_json_invalido_encadena_el_error_original(tmp_path):
    ruta = tmp_path / "roto.ipynb"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(ValueError) as info:
        FuenteNotebook(ruta).leer()
    assert info.value.__cause__ is not None


def test_leer_sin_lista_cells_lanza_valueerror(tmp_path):
    ruta = tmp_path / "raro.ipynb"
    ruta.write_text(json.dumps({"metadata": {}, "nbformat": 4}), encoding="utf-8")
    with pytest.raises(ValueError):
        FuenteNotebook(ruta).leer()


def test_leer_cells_que_no_es_lista_lanza_valueerror(tmp_path):
    ruta = tmp_path / "raro.ipynb"
    ruta.write_text(json.dumps({"cells": "hola"}), encoding="utf-8")
    with pytest.raises(ValueError):
        FuenteNotebook(ruta).leer()


def test_leer_json_que_no_es_diccionario_lanza_valueerror(tmp_path):
    ruta = tmp_path / "lista.ipynb"
    ruta.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError):
        FuenteNotebook(ruta).leer()
