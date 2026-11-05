"""Tests de fuentes/ (Bloque, Fuente y FuenteNotebook).

Una función a la vez:

    pytest tests/test_fuentes.py -k bloque    (ya pasan: Bloque y Fuente vienen hechos)
    pytest tests/test_fuentes.py -k source
    pytest tests/test_fuentes.py -k identificador
    pytest tests/test_fuentes.py -k tipo
    pytest tests/test_fuentes.py -k leer

Ojo con -k: filtra por subcadena del nombre. Cada grupo lleva su palabra y
ningún test de otro grupo la lleva.
"""

import dataclasses
import json

import pytest

from fuentes import TIPOS, Bloque, Fuente, FuenteNotebook
from fuentes.notebook import (
    MARCAS_CODIGO,
    MARCAS_TEXTO,
    id_de_celda,
    texto_de_source,
    tipo_de_celda,
)


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

def test_bloque_ubicacion_es_none_por_defecto():
    assert Bloque("texto", "hola").ubicacion is None


def test_bloque_archivo_es_none_por_defecto():
    assert Bloque("texto", "hola").archivo is None


def test_bloque_con_ubicacion_y_archivo():
    bloque = Bloque("codigo", "x = 1", "c1", "tarea.ipynb")
    assert bloque.ubicacion == "c1"
    assert bloque.archivo == "tarea.ipynb"


def test_bloque_distinto_archivo_no_es_igual():
    # Misma ubicación en dos notebooks distintos: son bloques distintos.
    assert Bloque("codigo", "x = 1", "c1", "a.ipynb") != Bloque("codigo", "x = 1", "c1", "b.ipynb")


def test_bloque_iguales_si_tienen_los_mismos_datos():
    assert Bloque("codigo", "x = 1", "c1") == Bloque("codigo", "x = 1", "c1")


def test_bloque_es_inmutable():
    bloque = Bloque("texto", "hola")
    with pytest.raises(dataclasses.FrozenInstanceError):
        bloque.contenido = "chao"


def test_bloque_valores_validos():
    assert TIPOS == ("texto", "codigo", "codigo_por_completar", "texto_por_completar")


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
# id_de_celda   (pytest -k identificador)
# ---------------------------------------------------------------------------

def test_identificador_campo_id():
    assert id_de_celda({"id": "a1", "metadata": {}}) == "a1"


def test_identificador_desde_metadata_como_colab():
    assert id_de_celda({"metadata": {"id": "VKjn5mmwZxst"}}) == "VKjn5mmwZxst"


def test_identificador_campo_id_gana_a_metadata():
    assert id_de_celda({"id": "a1", "metadata": {"id": "otro"}}) == "a1"


def test_identificador_ninguno_da_none():
    assert id_de_celda({"metadata": {}}) is None


def test_identificador_sin_metadata_da_none():
    assert id_de_celda({"cell_type": "code", "source": []}) is None


def test_identificador_metadata_que_no_es_dict_da_none():
    assert id_de_celda({"metadata": "hola"}) is None


def test_identificador_id_vacio_pasa_a_metadata():
    assert id_de_celda({"id": "", "metadata": {"id": "m1"}}) == "m1"


def test_identificador_id_none_pasa_a_metadata():
    assert id_de_celda({"id": None, "metadata": {"id": "m1"}}) == "m1"


def test_identificador_metadata_numero_da_none():
    assert id_de_celda({"metadata": {"id": 7}}) is None


def test_identificador_id_que_no_es_string_pasa_a_metadata():
    assert id_de_celda({"id": ["a"], "metadata": {"id": "m1"}}) == "m1"


def test_identificador_no_modifica_la_celda():
    celda = {"id": "", "metadata": {"id": "m1"}}
    id_de_celda(celda)
    assert celda == {"id": "", "metadata": {"id": "m1"}}


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


def test_tipo_codigo_vacio_es_codigo_por_completar():
    assert tipo_de_celda(celda_codigo("")) == "codigo_por_completar"


def test_tipo_codigo_solo_espacios_es_codigo_por_completar():
    assert tipo_de_celda(celda_codigo("  \n\n")) == "codigo_por_completar"


def test_tipo_marca_en_espanol_es_codigo_por_completar():
    assert tipo_de_celda(celda_codigo("# TU CÓDIGO AQUÍ\n")) == "codigo_por_completar"


def test_tipo_marca_sin_tildes_es_codigo_por_completar():
    assert tipo_de_celda(celda_codigo("# tu codigo aqui")) == "codigo_por_completar"


def test_tipo_marca_mayusculas_mezcladas_es_codigo_por_completar():
    assert tipo_de_celda(celda_codigo("# Tu Código Aquí")) == "codigo_por_completar"


def test_tipo_marca_de_nbgrader_es_codigo_por_completar():
    texto = "# YOUR CODE HERE\nraise NotImplementedError()"
    assert tipo_de_celda(celda_codigo(texto)) == "codigo_por_completar"


def test_tipo_marca_dentro_de_una_funcion_es_codigo_por_completar():
    texto = "def sigmoide(z):\n    # TU CÓDIGO AQUÍ\n    pass\n"
    assert tipo_de_celda(celda_codigo(texto)) == "codigo_por_completar"


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
    for marca in MARCAS_CODIGO + MARCAS_TEXTO:
        assert marca == marca.lower()
        assert marca.isascii()


def test_tipo_escribe_tu_codigo_aqui_del_auxiliar_6():
    # Variante real: no hace falta una marca nueva, contiene "tu codigo aqui".
    texto = "# Escribe tu código aquí\n# A = ...\n# B = ..."
    assert tipo_de_celda(celda_codigo(texto)) == "codigo_por_completar"


def test_tipo_comentario_con_aqui_suelto_es_codigo():
    # Caso real del Auxiliar 6: "aqui" sola no es una marca.
    texto = "t = t.flatten() # Aqui tambien se podria usar .view(-1)"
    assert tipo_de_celda(celda_codigo(texto)) == "codigo"


def test_tipo_respuesta_en_negrita_es_texto_por_completar():
    assert tipo_de_celda(celda_md("**Respuesta:** ....")) == "texto_por_completar"


def test_tipo_respuesta_con_dos_puntos_fuera_de_la_negrita():
    texto = "**Respuesta**:\n1. ...\n2. ..."
    assert tipo_de_celda(celda_md(texto)) == "texto_por_completar"


def test_tipo_respuesta_sin_negrita():
    assert tipo_de_celda(celda_md("Respuesta: escriba aquí")) == "texto_por_completar"


def test_tipo_respuesta_mayusculas():
    assert tipo_de_celda(celda_md("RESPUESTA:")) == "texto_por_completar"


def test_tipo_preguntas_y_respuesta_en_la_misma_celda():
    # Lab 7, celda 10: las preguntas y el hueco vienen juntos.
    texto = ("1. Explique el razonamiento detrás del tokenizador.\n"
             "2. ¿Qué problemas puede tener?\n\n"
             "**Respuesta**:\n1. ...\n2. ...")
    assert tipo_de_celda(celda_md(texto)) == "texto_por_completar"


def test_tipo_respuesta_ya_escrita_sigue_por_completar():
    # La Fuente dice dónde escribe el estudiante, no si ya terminó.
    texto = "**Respuesta:** Las stopwords no aportan al sentimiento."
    assert tipo_de_celda(celda_md(texto)) == "texto_por_completar"


def test_tipo_respuestas_en_las_instrucciones_es_texto():
    # Lab 7, celda 0: "respuesta" sin dos puntos no es un hueco.
    texto = "3. Modifique este archivo agregando sus respuestas donde corresponda."
    assert tipo_de_celda(celda_md(texto)) == "texto"


def test_tipo_respuesta_en_medio_del_enunciado_es_texto():
    # Lab 7, celda 41.
    texto = "¿qué se puede concluir con respecto al mejor modelo de la respuesta a la pregunta 4?"
    assert tipo_de_celda(celda_md(texto)) == "texto"


def test_tipo_raw_con_respuesta_es_texto_por_completar():
    celda = {"cell_type": "raw", "metadata": {}, "source": ["Respuesta: "]}
    assert tipo_de_celda(celda) == "texto_por_completar"


def test_tipo_marca_de_texto_en_codigo_no_cuenta():
    texto = 'datos = {"respuesta:": 42}'
    assert tipo_de_celda(celda_codigo(texto)) == "codigo"


def test_tipo_marca_de_codigo_en_markdown_no_cuenta():
    texto = "Escribe tu código aquí abajo, en la celda siguiente."
    assert tipo_de_celda(celda_md(texto)) == "texto"


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
        celda_md("**Respuesta:** ...", "d"),
    ])
    archivo = str(ruta)
    assert FuenteNotebook(ruta).leer() == [
        Bloque("texto", "# Tarea 1", "a", archivo),
        Bloque("codigo", "import numpy as np", "b", archivo),
        Bloque("codigo_por_completar", "# TU CÓDIGO AQUÍ", "c", archivo),
        Bloque("texto_por_completar", "**Respuesta:** ...", "d", archivo),
    ]


def test_leer_respeta_el_orden(tmp_path):
    ruta = escribir_notebook(tmp_path, [
        celda_codigo("x = 1", "primera"),
        celda_md("Explicación", "segunda"),
        celda_codigo("y = 2", "tercera"),
    ])
    ids = [b.ubicacion for b in FuenteNotebook(ruta).leer()]
    assert ids == ["primera", "segunda", "tercera"]


def test_leer_conserva_el_contenido_completo(tmp_path):
    # La marca no se quita: el LLM la necesita para entender qué se pide.
    texto = "def sigmoide(z):\n    # TU CÓDIGO AQUÍ\n    pass\n"
    ruta = escribir_notebook(tmp_path, [celda_codigo(texto, "s")])
    assert FuenteNotebook(ruta).leer() == [Bloque("codigo_por_completar", texto, "s", str(ruta))]


def test_leer_descarta_markdown_vacio(tmp_path):
    ruta = escribir_notebook(tmp_path, [
        celda_md("# Tarea", "a"),
        celda_md("", "vacia"),
        celda_md("Fin", "b"),
    ])
    ids = [b.ubicacion for b in FuenteNotebook(ruta).leer()]
    assert ids == ["a", "b"]


def test_leer_incluye_celdas_de_codigo_vacias(tmp_path):
    ruta = escribir_notebook(tmp_path, [celda_codigo("", "vacia")])
    assert FuenteNotebook(ruta).leer() == [Bloque("codigo_por_completar", "", "vacia", str(ruta))]


def test_leer_no_incluye_outputs(tmp_path):
    salida = [{"output_type": "stream", "name": "stdout", "text": ["SALIDA_ESPERADA\n"]}]
    ruta = escribir_notebook(tmp_path, [celda_codigo("print(f(2))", "c", outputs=salida)])
    bloques = FuenteNotebook(ruta).leer()
    assert all("SALIDA_ESPERADA" not in b.contenido for b in bloques)


def test_leer_celda_sin_id_da_none(tmp_path):
    celda = celda_md("Notebook viejo")
    del celda["id"]
    ruta = escribir_notebook(tmp_path, [celda], minor=4)
    assert FuenteNotebook(ruta).leer() == [Bloque("texto", "Notebook viejo", None, str(ruta))]


def test_leer_id_desde_metadata_como_colab(tmp_path):
    celda = celda_md("# Laboratorio 7")
    del celda["id"]
    celda["metadata"] = {"id": "VKjn5mmwZxst"}
    ruta = escribir_notebook(tmp_path, [celda], minor=0)
    assert [b.ubicacion for b in FuenteNotebook(ruta).leer()] == ["VKjn5mmwZxst"]


def test_leer_id_repetido_queda_en_none(tmp_path):
    ruta = escribir_notebook(tmp_path, [
        celda_md("Uno", "rep"),
        celda_codigo("x = 1", "unico"),
        celda_md("Dos", "rep"),
    ])
    ids = [b.ubicacion for b in FuenteNotebook(ruta).leer()]
    assert ids == [None, "unico", None]


def test_leer_id_repetido_entre_campo_id_y_metadata(tmp_path):
    # Lo que cuenta es el id que entrega id_de_celda, venga de donde venga.
    sin_id = celda_codigo("y = 2")
    del sin_id["id"]
    sin_id["metadata"] = {"id": "rep"}
    ruta = escribir_notebook(tmp_path, [celda_md("Uno", "rep"), sin_id])
    ids = [b.ubicacion for b in FuenteNotebook(ruta).leer()]
    assert ids == [None, None]


def test_leer_id_repetido_con_una_celda_descartada(tmp_path):
    # La celda vacía no da bloque, pero su id igual choca con el de la otra:
    # en el archivo hay dos celdas con ese id.
    ruta = escribir_notebook(tmp_path, [celda_md("", "rep"), celda_md("Texto", "rep")])
    assert FuenteNotebook(ruta).leer() == [Bloque("texto", "Texto", None, str(ruta))]


def test_leer_varias_celdas_sin_id_no_cuentan_como_repetidas(tmp_path):
    # None no es un id: que falte en dos celdas no es un choque.
    a = celda_md("Uno")
    b = celda_md("Dos")
    del a["id"], b["id"]
    ruta = escribir_notebook(tmp_path, [a, b, celda_md("Tres", "t")], minor=4)
    ids = [b.ubicacion for b in FuenteNotebook(ruta).leer()]
    assert ids == [None, None, "t"]


def test_leer_archivo_es_la_ruta_como_string(tmp_path):
    ruta = escribir_notebook(tmp_path, [celda_md("# Tarea", "a"), celda_codigo("x = 1", "b")])
    archivos = [b.archivo for b in FuenteNotebook(ruta).leer()]
    assert archivos == [str(ruta), str(ruta)]


def test_leer_dos_notebooks_no_se_confunden(tmp_path):
    ruta_a = escribir_notebook(tmp_path, [celda_codigo("x = 1", "c1")], nombre="a.ipynb")
    ruta_b = escribir_notebook(tmp_path, [celda_codigo("x = 1", "c1")], nombre="b.ipynb")
    assert FuenteNotebook(ruta_a).leer() != FuenteNotebook(ruta_b).leer()


def test_leer_texto_en_un_solo_string(tmp_path):
    celda = {"cell_type": "code", "id": "c", "metadata": {}, "outputs": [],
             "execution_count": None, "source": "a = 1\nb = 2"}
    ruta = escribir_notebook(tmp_path, [celda])
    assert FuenteNotebook(ruta).leer() == [Bloque("codigo", "a = 1\nb = 2", "c", str(ruta))]


def test_leer_tildes_y_enie(tmp_path):
    texto = "## Función sigmoide\nCalcula σ(z) para cada año."
    ruta = escribir_notebook(tmp_path, [celda_md(texto, "m")])
    assert FuenteNotebook(ruta).leer()[0].contenido == texto


def test_leer_notebook_sin_celdas(tmp_path):
    ruta = escribir_notebook(tmp_path, [])
    assert FuenteNotebook(ruta).leer() == []


def test_leer_acepta_ruta_como_string(tmp_path):
    ruta = escribir_notebook(tmp_path, [celda_md("# Tarea", "a")])
    assert FuenteNotebook(str(ruta)).leer() == [Bloque("texto", "# Tarea", "a", str(ruta))]


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
