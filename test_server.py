"""Tests de server.py.

Prueban las herramientas MCP llamándolas como funciones normales de Python:
el decorador @mcp.tool() devuelve la función original, así que no hace falta
levantar el servidor. Para trabajar una herramienta a la vez:

    pytest test_server.py -k cargar
    pytest test_server.py -k registrar
    pytest test_server.py -k pista

Los tests no exigen frases exactas: revisan que la respuesta sea texto, que no
se lance una excepción y que el estado de la sesión cambie (o no) como debe.
"""

import asyncio
import json

import pytest

import server
from estado import SesionTarea


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

SUBOBJETIVOS = [
    {"id": "sigmoide", "descripcion": "Implementar la función sigmoide"},
    {"id": "derivada", "descripcion": "Implementar la derivada de la sigmoide"},
]


def escribir_tarea(ruta, subobjetivos):
    """Escribe un JSON de tarea en la ruta dada y devuelve la ruta como texto."""
    contenido = {"titulo": "Tarea de prueba", "subobjetivos": subobjetivos}
    ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    return str(ruta)


@pytest.fixture(autouse=True)
def sin_sesion(monkeypatch):
    """Cada test parte sin tarea cargada.

    server.sesion es una variable global del módulo: sin este fixture, la sesión
    que carga un test seguiría viva en el siguiente.
    """
    monkeypatch.setattr(server, "sesion", None)


@pytest.fixture
def ruta_tarea(tmp_path):
    """Ruta a un JSON de tarea válido con 'sigmoide' y 'derivada'."""
    return escribir_tarea(tmp_path / "tarea.json", SUBOBJETIVOS)


@pytest.fixture
def con_tarea(ruta_tarea):
    """Deja una tarea cargada a través de la herramienta, como lo haría el LLM."""
    server.cargar_tarea(ruta_tarea)
    return server.sesion


# ---------------------------------------------------------------------------
# Registro en el servidor MCP
# ---------------------------------------------------------------------------

def test_herramientas_registradas_en_el_servidor():
    herramientas = asyncio.run(server.mcp.list_tools())
    nombres = {h.name for h in herramientas}
    assert {"cargar_tarea", "registrar_intento", "pedir_pista"} <= nombres


def test_herramientas_tienen_descripcion():
    """El docstring es lo que lee el LLM para decidir cuándo usar cada herramienta."""
    for h in asyncio.run(server.mcp.list_tools()):
        assert h.description, f"{h.name} no tiene descripción"


# ---------------------------------------------------------------------------
# cargar_tarea
# ---------------------------------------------------------------------------

def test_cargar_devuelve_texto(ruta_tarea):
    assert isinstance(server.cargar_tarea(ruta_tarea), str)


def test_cargar_muestra_ids_y_descripciones(ruta_tarea):
    respuesta = server.cargar_tarea(ruta_tarea)
    for s in SUBOBJETIVOS:
        assert s["id"] in respuesta
        assert s["descripcion"] in respuesta


def test_cargar_deja_la_sesion_activa(ruta_tarea):
    server.cargar_tarea(ruta_tarea)
    assert isinstance(server.sesion, SesionTarea)
    assert set(server.sesion.subobjetivos) == {"sigmoide", "derivada"}


def test_cargar_archivo_inexistente_no_lanza_error(tmp_path):
    respuesta = server.cargar_tarea(str(tmp_path / "no_existe.json"))
    assert isinstance(respuesta, str)
    assert server.sesion is None


def test_cargar_ids_duplicados_no_lanza_error(tmp_path):
    ruta = escribir_tarea(tmp_path / "dup.json", [SUBOBJETIVOS[0], SUBOBJETIVOS[0]])
    respuesta = server.cargar_tarea(ruta)
    assert isinstance(respuesta, str)
    assert "sigmoide" in respuesta  # el mensaje dice cuál id está repetido
    assert server.sesion is None


def test_cargar_fallida_no_borra_la_sesion_anterior(con_tarea, tmp_path):
    server.cargar_tarea(str(tmp_path / "no_existe.json"))
    assert server.sesion is con_tarea


def test_cargar_otra_tarea_empieza_de_cero(con_tarea, ruta_tarea):
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    server.cargar_tarea(ruta_tarea)
    assert server.sesion is not con_tarea
    assert server.sesion.subobjetivos["sigmoide"].intentos == []


# ---------------------------------------------------------------------------
# registrar_intento
# ---------------------------------------------------------------------------

def test_registrar_sin_tarea_no_lanza_error():
    respuesta = server.registrar_intento("sigmoide", "x = 1")
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_registrar_guarda_el_intento_en_la_sesion(con_tarea):
    server.registrar_intento("sigmoide", "def sigmoide(x): pass", "1 failed")
    intentos = con_tarea.subobjetivos["sigmoide"].intentos
    assert len(intentos) == 1
    assert intentos[0].codigo == "def sigmoide(x): pass"
    assert intentos[0].resultado_tests == "1 failed"


def test_registrar_sin_resultado_de_tests_deja_none(con_tarea):
    server.registrar_intento("sigmoide", "x = 1")
    assert con_tarea.subobjetivos["sigmoide"].intentos[0].resultado_tests is None


def test_registrar_informa_la_cantidad_de_intentos(con_tarea):
    server.registrar_intento("sigmoide", "intento 1")
    respuesta = server.registrar_intento("sigmoide", "intento 2")
    assert isinstance(respuesta, str)
    assert "2" in respuesta


def test_registrar_no_afecta_a_otro_subobjetivo(con_tarea):
    server.registrar_intento("sigmoide", "x = 1")
    assert con_tarea.subobjetivos["derivada"].intentos == []


def test_registrar_id_inexistente_no_lanza_error(con_tarea):
    respuesta = server.registrar_intento("no_existe", "x = 1")
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


# ---------------------------------------------------------------------------
# pedir_pista
# ---------------------------------------------------------------------------

def test_pista_sin_tarea_no_lanza_error():
    respuesta = server.pedir_pista("sigmoide", 1)
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_pista_id_inexistente_no_lanza_error(con_tarea):
    respuesta = server.pedir_pista("no_existe", 1)
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_pista_negada_muestra_el_motivo_del_arbitro(con_tarea):
    _, motivo = con_tarea.puede_pedir_pista("sigmoide", 1)  # sin intentos: negada
    respuesta = server.pedir_pista("sigmoide", 1)
    assert motivo in respuesta


def test_pista_negada_no_registra_nada(con_tarea):
    server.pedir_pista("sigmoide", 1)
    assert con_tarea.subobjetivos["sigmoide"].nivel_pista_desbloqueado == 0


def test_pista_permitida_menciona_el_nivel(con_tarea):
    server.registrar_intento("sigmoide", "x = 1")
    respuesta = server.pedir_pista("sigmoide", 1)
    assert isinstance(respuesta, str)
    assert "1" in respuesta


def test_pista_permitida_queda_registrada_en_la_misma_llamada(con_tarea):
    """La regla central: no depende de que el LLM haga una segunda llamada."""
    server.registrar_intento("sigmoide", "x = 1")
    server.pedir_pista("sigmoide", 1)
    assert con_tarea.subobjetivos["sigmoide"].nivel_pista_desbloqueado == 1


def test_pista_flujo_completo_exige_intento_entre_niveles(con_tarea):
    sub = con_tarea.subobjetivos["sigmoide"]
    server.registrar_intento("sigmoide", "intento 1")
    server.pedir_pista("sigmoide", 1)

    server.pedir_pista("sigmoide", 2)          # sin intento nuevo: negada
    assert sub.nivel_pista_desbloqueado == 1

    server.registrar_intento("sigmoide", "intento 2")
    server.pedir_pista("sigmoide", 2)          # ahora sí
    assert sub.nivel_pista_desbloqueado == 2


# ---------------------------------------------------------------------------
# marcar_completado
# ---------------------------------------------------------------------------

def test_completar_esta_registrada_en_el_servidor():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "marcar_completado" in nombres


def test_completar_sin_tarea_no_lanza_error():
    respuesta = server.marcar_completado("sigmoide")
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_completar_id_inexistente_no_lanza_error(con_tarea):
    respuesta = server.marcar_completado("no_existe")
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_completar_marca_en_la_sesion(con_tarea):
    respuesta = server.marcar_completado("sigmoide")
    assert isinstance(respuesta, str)
    assert con_tarea.subobjetivos["sigmoide"].completado is True
    assert con_tarea.subobjetivos["derivada"].completado is False


def test_completar_dos_veces_avisa_distinto(con_tarea):
    """La segunda vez no es un error, pero el mensaje no debería ser idéntico."""
    primera = server.marcar_completado("sigmoide")
    segunda = server.marcar_completado("sigmoide")
    assert isinstance(segunda, str)
    assert segunda != primera
    assert con_tarea.subobjetivos["sigmoide"].completado is True


def test_completar_despues_no_hay_pistas(con_tarea):
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    server.marcar_completado("sigmoide")
    server.pedir_pista("sigmoide", 1)
    assert con_tarea.subobjetivos["sigmoide"].nivel_pista_desbloqueado == 0
