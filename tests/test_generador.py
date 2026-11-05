"""Tests de generador.py (de notebook a tarea, sin MCP).

Para trabajar una función a la vez:

    pytest tests/test_generador.py -k formatear
    pytest tests/test_generador.py -k ruta
    pytest tests/test_generador.py -k validar
    pytest tests/test_generador.py -k escribir

Los de formatear no exigen un formato exacto: revisan que estén el número,
el tipo, la ubicación y el contenido de cada bloque, y el orden.
"""

import json
from pathlib import Path

import pytest

import generador
from estado import SesionTarea
from fuentes import Bloque


UBICACIONES = {"c1", "c2", "c3"}


def sub(id_sub="p1", descripcion="Responder la pregunta 1", **extra):
    """Un subobjetivo propuesto válido, con claves extra si se piden."""
    return {"id": id_sub, "descripcion": descripcion, **extra}


def algun_problema_menciona(problemas, texto):
    return any(texto in p for p in problemas)


# ---------------------------------------------------------------------------
# formatear_bloques
# ---------------------------------------------------------------------------

def test_formatear_devuelve_texto():
    assert isinstance(generador.formatear_bloques([Bloque("texto", "Hola", "c1")]), str)


def test_formatear_incluye_tipo_ubicacion_y_contenido():
    texto = generador.formatear_bloques(
        [Bloque("codigo_por_completar", "# TU CÓDIGO AQUÍ", "abc123")])
    assert "codigo_por_completar" in texto
    assert "abc123" in texto
    assert "# TU CÓDIGO AQUÍ" in texto


def test_formatear_contenido_completo_sin_recortar():
    largo = "x = 1\n" * 500
    assert largo in generador.formatear_bloques([Bloque("codigo", largo, "c1")])


def test_formatear_respeta_el_orden():
    texto = generador.formatear_bloques([
        Bloque("texto", "PRIMERO", "c1"),
        Bloque("texto_por_completar", "SEGUNDO", "c2"),
        Bloque("codigo", "TERCERO", "c3"),
    ])
    assert texto.index("PRIMERO") < texto.index("SEGUNDO") < texto.index("TERCERO")


def test_formatear_numera_desde_uno():
    texto = generador.formatear_bloques([
        Bloque("texto", "PRIMERO", "uno"),
        Bloque("texto", "SEGUNDO", "dos"),
    ])
    assert "1" in texto[: texto.index("PRIMERO")]
    assert "2" in texto[texto.index("PRIMERO"): texto.index("SEGUNDO")]


def test_formatear_cada_bloque_con_su_ubicacion():
    """La ubicación de cada bloque va antes de su contenido, no de otro."""
    texto = generador.formatear_bloques([
        Bloque("texto", "PRIMERO", "id_uno"),
        Bloque("texto", "SEGUNDO", "id_dos"),
    ])
    assert texto.index("id_uno") < texto.index("PRIMERO") < texto.index("id_dos")


def test_formatear_bloque_sin_ubicacion():
    texto = generador.formatear_bloques([Bloque("texto", "Hola", None)])
    assert generador.SIN_UBICACION in texto
    assert "None" not in texto


def test_formatear_lista_vacia_no_es_texto_vacio():
    texto = generador.formatear_bloques([])
    assert isinstance(texto, str)
    assert texto.strip() != ""


# ---------------------------------------------------------------------------
# ruta_tarea_generada
# ---------------------------------------------------------------------------

def test_ruta_mismo_nombre_y_carpeta():
    assert generador.ruta_tarea_generada("/a/b/lab7.ipynb") == "/a/b/lab7.tarea.json"


def test_ruta_devuelve_string():
    assert isinstance(generador.ruta_tarea_generada("/a/lab7.ipynb"), str)


def test_ruta_con_puntos_en_el_nombre():
    assert (generador.ruta_tarea_generada("/a/lab.7.ipynb")
            == "/a/lab.7.tarea.json")


def test_ruta_usa_el_sufijo():
    assert generador.ruta_tarea_generada("/a/x.ipynb").endswith(generador.SUFIJO_TAREA)


# ---------------------------------------------------------------------------
# validar_subobjetivos
# ---------------------------------------------------------------------------

def test_validar_lista_valida_sin_problemas():
    lista = [sub("p1", celdas=["c1"]), sub("p2", celdas=["c2", "c3"])]
    assert generador.validar_subobjetivos(lista, UBICACIONES) == []


def test_validar_sin_celdas_es_valido():
    assert generador.validar_subobjetivos([sub()], UBICACIONES) == []


def test_validar_celdas_vacias_es_valido():
    assert generador.validar_subobjetivos([sub(celdas=[])], UBICACIONES) == []


def test_validar_devuelve_lista_de_strings():
    problemas = generador.validar_subobjetivos([sub(tests="t.py")], UBICACIONES)
    assert isinstance(problemas, list)
    assert problemas and all(isinstance(p, str) for p in problemas)


def test_validar_lista_vacia():
    assert generador.validar_subobjetivos([], UBICACIONES) != []


def test_validar_elemento_que_no_es_diccionario():
    assert generador.validar_subobjetivos(["p1"], UBICACIONES) != []


@pytest.mark.parametrize("clave", ["tests", "ejemplo", "archivo", "funcion"])
def test_validar_clave_no_permitida(clave):
    problemas = generador.validar_subobjetivos([sub(**{clave: "x"})], UBICACIONES)
    assert algun_problema_menciona(problemas, clave)


@pytest.mark.parametrize("campo", ["id", "descripcion"])
def test_validar_falta_campo_obligatorio(campo):
    s = sub()
    del s[campo]
    assert algun_problema_menciona(
        generador.validar_subobjetivos([s], UBICACIONES), campo)


@pytest.mark.parametrize("valor", ["", "   ", None, 3])
def test_validar_id_sin_texto(valor):
    assert generador.validar_subobjetivos([sub(valor)], UBICACIONES) != []


@pytest.mark.parametrize("valor", ["", "  \n", None])
def test_validar_descripcion_sin_texto(valor):
    assert generador.validar_subobjetivos([sub("p1", valor)], UBICACIONES) != []


def test_validar_id_repetido():
    problemas = generador.validar_subobjetivos([sub("p1"), sub("p1")], UBICACIONES)
    assert algun_problema_menciona(problemas, "p1")


def test_validar_celda_que_no_existe():
    problemas = generador.validar_subobjetivos(
        [sub(celdas=["c1", "inventada"])], UBICACIONES)
    assert algun_problema_menciona(problemas, "inventada")


def test_validar_celdas_no_es_lista():
    """Un string suelto no es una lista de celdas (aunque "c1" exista)."""
    assert generador.validar_subobjetivos([sub(celdas="c1")], UBICACIONES) != []


def test_validar_celda_que_no_es_string():
    assert generador.validar_subobjetivos([sub(celdas=[1])], UBICACIONES) != []


def test_validar_junta_todos_los_problemas():
    """No se detiene en el primero: el LLM corrige todo en un intento."""
    lista = [sub("p1", tests="t.py"), sub("p2", celdas=["inventada"])]
    problemas = generador.validar_subobjetivos(lista, UBICACIONES)
    assert algun_problema_menciona(problemas, "tests")
    assert algun_problema_menciona(problemas, "inventada")


def test_validar_no_modifica_la_lista():
    lista = [sub("p1", celdas=["c1"]), sub("p1", tests="x")]
    copia = json.loads(json.dumps(lista))
    generador.validar_subobjetivos(lista, UBICACIONES)
    assert lista == copia


def test_validar_sin_ubicaciones_rechaza_cualquier_celda():
    assert generador.validar_subobjetivos([sub(celdas=["c1"])], set()) != []


# ---------------------------------------------------------------------------
# escribir_tarea
# ---------------------------------------------------------------------------

@pytest.fixture
def escrita(tmp_path):
    """Escribe una tarea con dos subobjetivos y devuelve (ruta_json, datos)."""
    notebook = tmp_path / "lab7.ipynb"
    ruta_json = tmp_path / "lab7.tarea.json"
    subobjetivos = [
        sub("p1", "Explicar qué es TF-IDF", celdas=["c1", "c2"]),
        sub("p2", "Implementar la limpieza"),
    ]
    generador.escribir_tarea(str(ruta_json), str(notebook), subobjetivos)
    return ruta_json, json.loads(ruta_json.read_text(encoding="utf-8"))


def test_escribir_crea_el_archivo(escrita):
    ruta_json, _ = escrita
    assert ruta_json.exists()


def test_escribir_titulo_y_fuente(escrita):
    _, datos = escrita
    assert datos["titulo"] == "lab7"
    assert datos["fuente"] == "lab7.ipynb"


def test_escribir_subobjetivos_en_orden(escrita):
    _, datos = escrita
    assert [s["id"] for s in datos["subobjetivos"]] == ["p1", "p2"]
    assert datos["subobjetivos"][0]["descripcion"] == "Explicar qué es TF-IDF"


def test_escribir_celdas_solo_si_vienen(escrita):
    _, datos = escrita
    assert datos["subobjetivos"][0]["celdas"] == ["c1", "c2"]
    assert "celdas" not in datos["subobjetivos"][1]


def test_escribir_tildes_legibles(escrita):
    ruta_json, _ = escrita
    texto = ruta_json.read_text(encoding="utf-8")
    assert "qué" in texto
    assert "\\u00e9" not in texto


def test_escribir_con_sangria(escrita):
    ruta_json, _ = escrita
    assert "\n" in ruta_json.read_text(encoding="utf-8").strip()


def test_escribir_la_carga_sesion_tarea(escrita):
    """Es un JSON de tarea normal: SesionTarea lo carga sin cambios."""
    ruta_json, _ = escrita
    sesion = SesionTarea(str(ruta_json))
    assert list(sesion.subobjetivos) == ["p1", "p2"]
    assert sesion.subobjetivos["p1"].tests is None
    assert sesion.subobjetivos["p1"].ejemplo is None


def test_escribir_reemplaza_si_existe(tmp_path):
    ruta_json = tmp_path / "lab7.tarea.json"
    ruta_json.write_text("viejo", encoding="utf-8")
    generador.escribir_tarea(str(ruta_json), str(tmp_path / "lab7.ipynb"), [sub()])
    assert json.loads(ruta_json.read_text(encoding="utf-8"))["subobjetivos"][0]["id"] == "p1"
