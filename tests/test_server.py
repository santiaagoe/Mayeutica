"""Tests de server.py.

Prueban las herramientas MCP llamándolas como funciones normales de Python:
el decorador @mcp.tool() devuelve la función original, así que no hace falta
levantar el servidor. Para trabajar una herramienta a la vez:

    pytest tests/test_server.py -k instrucciones_servidor
    pytest tests/test_server.py -k formatear
    pytest tests/test_server.py -k revision
    pytest tests/test_server.py -k diagnostico
    pytest tests/test_server.py -k ayuda
    pytest tests/test_server.py -k ver_ejemplo
    pytest tests/test_server.py -k ejecutar
    pytest tests/test_server.py -k leer
    pytest tests/test_server.py -k entorno
    pytest tests/test_server.py -k leer_fuente
    pytest tests/test_server.py -k crear

Los tests no exigen frases exactas: revisan que la respuesta sea texto, que no
se lance una excepción y que el estado de la sesión cambie (o no) como debe.
"""

import asyncio
import json
import os

import pytest

import server
from estado import FALLOS_PARA_RESCATE, MOMENTOS, SesionTarea


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


def fallar(sesion, subobjetivo_id, veces=1):
    """Registra intentos fallidos directo en la sesión, sin correr pytest."""
    for _ in range(veces):
        sesion.registrar_intento(subobjetivo_id, "x = 1", "1 failed", paso=False)


def es_momento(respuesta, nombre):
    """True si la respuesta trae las instrucciones del momento indicado."""
    return (MOMENTOS[nombre]["permitido"] in respuesta
            and MOMENTOS[nombre]["prohibido"] in respuesta)


def momentos_en(respuesta):
    """Los momentos cuyas instrucciones aparecen en la respuesta."""
    return {n for n in MOMENTOS if MOMENTOS[n]["permitido"] in respuesta}


# ---------------------------------------------------------------------------
# Registro en el servidor MCP
# ---------------------------------------------------------------------------

def test_herramientas_registradas_en_el_servidor():
    herramientas = asyncio.run(server.mcp.list_tools())
    nombres = {h.name for h in herramientas}
    assert {"cargar_tarea", "registrar_intento", "registrar_diagnostico",
            "pedir_ayuda", "ver_ejemplo", "marcar_completado",
            "ejecutar_tests"} <= nombres


def test_pedir_pista_ya_no_existe():
    """pedir_ayuda la reemplaza: si quedan las dos, el LLM puede usar la vieja."""
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "pedir_pista" not in nombres


def test_auxiliares_no_son_herramientas():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "formatear_momento" not in nombres
    assert "instrucciones_revision" not in nombres


def test_herramientas_tienen_descripcion():
    """El docstring es lo que lee el LLM para decidir cuándo usar cada herramienta."""
    for h in asyncio.run(server.mcp.list_tools()):
        assert h.description, f"{h.name} no tiene descripción"


# ---------------------------------------------------------------------------
# Instrucciones generales del servidor (INSTRUCCIONES)
# ---------------------------------------------------------------------------

def test_instrucciones_servidor_son_texto():
    assert isinstance(server.INSTRUCCIONES, str)
    assert server.INSTRUCCIONES.strip() != ""


def test_instrucciones_servidor_se_entregan_al_cliente():
    """No basta con que exista la constante: el servidor tiene que entregarla."""
    assert server.mcp.instructions == server.INSTRUCCIONES


def test_instrucciones_servidor_nombran_todas_las_herramientas():
    """Si se agrega una herramienta, las instrucciones tienen que decir cuándo usarla."""
    for h in asyncio.run(server.mcp.list_tools()):
        assert h.name in server.INSTRUCCIONES, f"Las instrucciones no nombran {h.name}"


def test_instrucciones_servidor_no_nombran_herramientas_que_no_existen():
    assert "pedir_pista" not in server.INSTRUCCIONES


def test_instrucciones_servidor_mencionan_el_rescate():
    """El rescate es la única excepción a no escribir la solución."""
    assert "rescate" in server.INSTRUCCIONES


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


def test_cargar_sin_reanudar_empieza_de_cero(con_tarea, ruta_tarea):
    """Antes de la recarga se llamaba test_cargar_otra_tarea_empieza_de_cero."""
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    server.cargar_tarea(ruta_tarea, reanudar=False)
    assert server.sesion is not con_tarea
    assert server.sesion.subobjetivos["sigmoide"].intentos == []


def test_cargar_expande_la_virgulilla(tmp_path, monkeypatch):
    """Una ruta como '~/tarea.json' apunta a la carpeta personal."""
    monkeypatch.setenv("HOME", str(tmp_path))
    escribir_tarea(tmp_path / "tarea.json", SUBOBJETIVOS)
    server.cargar_tarea("~/tarea.json")
    assert isinstance(server.sesion, SesionTarea)


def test_cargar_ignora_espacios_alrededor_de_la_ruta(ruta_tarea):
    """El LLM a veces manda la ruta con espacios o un salto de línea."""
    server.cargar_tarea(f"  {ruta_tarea}\n")
    assert isinstance(server.sesion, SesionTarea)


def test_cargar_virgulilla_con_espacios(tmp_path, monkeypatch):
    """Espacios y '~' juntos: el '~' solo se expande si queda al inicio."""
    monkeypatch.setenv("HOME", str(tmp_path))
    escribir_tarea(tmp_path / "tarea.json", SUBOBJETIVOS)
    server.cargar_tarea("  ~/tarea.json\n")
    assert isinstance(server.sesion, SesionTarea)


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


def test_completar_despues_no_hay_revision(con_tarea):
    fallar(con_tarea, "sigmoide")
    server.marcar_completado("sigmoide")
    respuesta = server.pedir_ayuda("sigmoide")
    assert not es_momento(respuesta, "revision_conceptual")


# ---------------------------------------------------------------------------
# ejecutar_tests
# ---------------------------------------------------------------------------

CODIGO_BIEN = "import math\n\ndef sigmoide(x):\n    return 1 / (1 + math.exp(-x))\n"
CODIGO_MAL = "def sigmoide(x):\n    return x\n"
TESTS_SIGMOIDE = "from sigmoide import sigmoide\n\ndef test_cero():\n    assert sigmoide(0) == 0.5\n"


@pytest.fixture
def tarea_con_tests(tmp_path):
    """Carga una tarea donde 'sigmoide' tiene archivo y tests, y 'derivada' no.

    Devuelve la ruta del archivo del estudiante para que cada test escriba en
    él el código que necesita. Empieza con código que no pasa.
    """
    (tmp_path / "test_sigmoide.py").write_text(TESTS_SIGMOIDE, encoding="utf-8")
    archivo = tmp_path / "sigmoide.py"
    archivo.write_text(CODIGO_MAL, encoding="utf-8")
    ruta = escribir_tarea(tmp_path / "tarea.json", [
        {"id": "sigmoide", "descripcion": "Implementar la sigmoide",
         "archivo": "sigmoide.py", "tests": "test_sigmoide.py"},
        {"id": "derivada", "descripcion": "Implementar la derivada"},
    ])
    server.cargar_tarea(ruta)
    return archivo


def test_ejecutar_esta_registrada_en_el_servidor():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "ejecutar_tests" in nombres


def test_ejecutar_sin_tarea_no_lanza_error():
    respuesta = server.ejecutar_tests("sigmoide")
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_ejecutar_id_inexistente_no_lanza_error(tarea_con_tests):
    respuesta = server.ejecutar_tests("no_existe")
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_ejecutar_sin_tests_configurados_no_registra_intento(tarea_con_tests):
    respuesta = server.ejecutar_tests("derivada")
    assert isinstance(respuesta, str)
    assert server.sesion.subobjetivos["derivada"].intentos == []


def test_ejecutar_archivo_del_estudiante_inexistente(tarea_con_tests):
    tarea_con_tests.unlink()
    respuesta = server.ejecutar_tests("sigmoide")
    assert isinstance(respuesta, str)
    assert server.sesion.subobjetivos["sigmoide"].intentos == []


def test_ejecutar_registra_el_codigo_real_como_intento(tarea_con_tests):
    server.ejecutar_tests("sigmoide")
    intentos = server.sesion.subobjetivos["sigmoide"].intentos
    assert len(intentos) == 1
    assert intentos[0].codigo == CODIGO_MAL


def test_ejecutar_guarda_la_salida_real_de_pytest(tarea_con_tests):
    server.ejecutar_tests("sigmoide")
    resultado = server.sesion.subobjetivos["sigmoide"].intentos[0].resultado_tests
    assert resultado is not None
    assert "failed" in resultado


def test_ejecutar_falla_no_completa_y_muestra_la_salida(tarea_con_tests):
    respuesta = server.ejecutar_tests("sigmoide")
    assert "failed" in respuesta  # el estudiante necesita ver qué falló
    assert server.sesion.subobjetivos["sigmoide"].completado is False


def test_ejecutar_pasa_y_completa(tarea_con_tests):
    tarea_con_tests.write_text(CODIGO_BIEN, encoding="utf-8")
    respuesta = server.ejecutar_tests("sigmoide")
    assert isinstance(respuesta, str)
    assert server.sesion.subobjetivos["sigmoide"].completado is True
    assert server.sesion.subobjetivos["derivada"].completado is False


def test_ejecutar_lee_el_archivo_cada_vez(tarea_con_tests):
    """Si el estudiante edita su archivo, la siguiente ejecución usa la versión nueva."""
    server.ejecutar_tests("sigmoide")
    tarea_con_tests.write_text(CODIGO_BIEN, encoding="utf-8")
    server.ejecutar_tests("sigmoide")
    intentos = server.sesion.subobjetivos["sigmoide"].intentos
    assert [i.codigo for i in intentos] == [CODIGO_MAL, CODIGO_BIEN]
    assert server.sesion.subobjetivos["sigmoide"].completado is True


def test_ejecutar_registra_si_paso(tarea_con_tests):
    server.ejecutar_tests("sigmoide")
    tarea_con_tests.write_text(CODIGO_BIEN, encoding="utf-8")
    server.ejecutar_tests("sigmoide")
    intentos = server.sesion.subobjetivos["sigmoide"].intentos
    assert [i.paso for i in intentos] == [False, True]


def test_ejecutar_falla_cuenta_como_fallo(tarea_con_tests):
    server.ejecutar_tests("sigmoide")
    assert server.sesion.subobjetivos["sigmoide"].intentos_fallidos() == 1


def test_ejecutar_falla_trae_revision_segun_los_fallos(tarea_con_tests):
    """Cada fallo sube un escalón: conceptual, explícita, rescate."""
    esperados = ["revision_conceptual", "revision_explicita", "rescate"]
    for nombre in esperados:
        respuesta = server.ejecutar_tests("sigmoide")
        assert es_momento(respuesta, nombre), f"esperaba {nombre}"
        assert "failed" in respuesta  # la salida de pytest sigue apareciendo


def test_ejecutar_tercer_fallo_registra_rescate(tarea_con_tests):
    sub = server.sesion.subobjetivos["sigmoide"]
    for _ in range(FALLOS_PARA_RESCATE - 1):
        server.ejecutar_tests("sigmoide")
    assert sub.rescatado is False
    server.ejecutar_tests("sigmoide")
    assert sub.rescatado is True


def test_ejecutar_pasa_no_trae_instrucciones_de_revision(tarea_con_tests):
    server.ejecutar_tests("sigmoide")              # un fallo antes
    tarea_con_tests.write_text(CODIGO_BIEN, encoding="utf-8")
    respuesta = server.ejecutar_tests("sigmoide")
    assert momentos_en(respuesta) == set()


def test_ejecutar_despues_del_rescate_igual_hay_que_pasar(tarea_con_tests):
    """El rescate no completa: el estudiante tiene que pasar los tests."""
    for _ in range(FALLOS_PARA_RESCATE):
        server.ejecutar_tests("sigmoide")
    sub = server.sesion.subobjetivos["sigmoide"]
    assert sub.completado is False
    tarea_con_tests.write_text(CODIGO_BIEN, encoding="utf-8")
    server.ejecutar_tests("sigmoide")
    assert sub.completado is True
    assert sub.rescatado is True                   # queda anotado para repasar


def test_ejecutar_otra_vez_ya_completado_no_lanza_error(tarea_con_tests):
    tarea_con_tests.write_text(CODIGO_BIEN, encoding="utf-8")
    server.ejecutar_tests("sigmoide")
    respuesta = server.ejecutar_tests("sigmoide")
    assert isinstance(respuesta, str)
    assert server.sesion.subobjetivos["sigmoide"].completado is True


# ---------------------------------------------------------------------------
# formatear_momento
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre", list(MOMENTOS))
def test_formatear_trae_nombre_y_textos(nombre):
    texto = server.formatear_momento(nombre)
    assert isinstance(texto, str)
    assert nombre in texto
    assert es_momento(texto, nombre)


def test_formatear_no_mezcla_momentos():
    assert momentos_en(server.formatear_momento("teoria")) == {"teoria"}


def test_formatear_nombre_inexistente_lanza_keyerror():
    with pytest.raises(KeyError):
        server.formatear_momento("no_existe")


# ---------------------------------------------------------------------------
# instrucciones_revision
# ---------------------------------------------------------------------------

def test_revision_sin_fallos_es_none(con_tarea):
    assert server.instrucciones_revision("sigmoide") is None


def test_revision_intento_sin_tests_no_cuenta(con_tarea):
    """Un intento con paso=None (registrar_intento) no es un fallo."""
    server.registrar_intento("sigmoide", "x = 1")
    assert server.instrucciones_revision("sigmoide") is None


@pytest.mark.parametrize("fallos, nombre", [
    (1, "revision_conceptual"),
    (2, "revision_explicita"),
    (FALLOS_PARA_RESCATE, "rescate"),
    (FALLOS_PARA_RESCATE + 2, "rescate"),
])
def test_revision_segun_fallos(con_tarea, fallos, nombre):
    fallar(con_tarea, "sigmoide", fallos)
    texto = server.instrucciones_revision("sigmoide")
    assert momentos_en(texto) == {nombre}


def test_revision_completado_es_none(con_tarea):
    fallar(con_tarea, "sigmoide", 2)
    con_tarea.marcar_completado("sigmoide")
    assert server.instrucciones_revision("sigmoide") is None


def test_revision_rescate_queda_registrado(con_tarea):
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE)
    server.instrucciones_revision("sigmoide")
    assert con_tarea.subobjetivos["sigmoide"].rescatado is True


def test_revision_antes_del_rescate_no_registra(con_tarea):
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE - 1)
    server.instrucciones_revision("sigmoide")
    assert con_tarea.subobjetivos["sigmoide"].rescatado is False


def test_revision_rescate_no_autorizado_no_entrega(con_tarea, monkeypatch):
    """Si puede_rescatar dice que no, se baja a revision_explicita sin anotar.

    Con las reglas actuales de estado.py esto no pasa; el test simula que las
    dos reglas se desalinean (por ejemplo, si alguien cambia una y no la otra).
    """
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE)
    monkeypatch.setattr(con_tarea, "puede_rescatar", lambda _id: (False, "no"))
    texto = server.instrucciones_revision("sigmoide")
    assert momentos_en(texto) == {"revision_explicita"}
    assert con_tarea.subobjetivos["sigmoide"].rescatado is False


def test_revision_es_por_subobjetivo(con_tarea):
    fallar(con_tarea, "sigmoide", 2)
    assert server.instrucciones_revision("derivada") is None


# ---------------------------------------------------------------------------
# registrar_diagnostico
# ---------------------------------------------------------------------------

def test_diagnostico_sin_tarea_no_lanza_error():
    respuesta = server.registrar_diagnostico("sigmoide", True, True)
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_diagnostico_id_inexistente_no_lanza_error(con_tarea):
    respuesta = server.registrar_diagnostico("no_existe", True, True)
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_diagnostico_guarda_en_la_sesion(con_tarea):
    server.registrar_diagnostico("sigmoide", True, False)
    sub = con_tarea.subobjetivos["sigmoide"]
    assert sub.maneja_teoria is True
    assert sub.maneja_codigo is False


def test_diagnostico_no_afecta_a_otro_subobjetivo(con_tarea):
    server.registrar_diagnostico("sigmoide", True, True)
    assert con_tarea.subobjetivos["derivada"].maneja_teoria is None


@pytest.mark.parametrize("teoria, codigo, nombre", [
    (False, False, "teoria"),
    (False, True, "teoria"),
    (True, False, "ejemplo"),
    (True, True, "duda_especifica"),
])
def test_diagnostico_devuelve_el_momento_inicial(con_tarea, teoria, codigo, nombre):
    respuesta = server.registrar_diagnostico("sigmoide", teoria, codigo)
    assert momentos_en(respuesta) == {nombre}


def test_diagnostico_de_nuevo_reemplaza(con_tarea):
    server.registrar_diagnostico("sigmoide", False, False)
    respuesta = server.registrar_diagnostico("sigmoide", True, True)
    assert con_tarea.subobjetivos["sigmoide"].maneja_teoria is True
    assert momentos_en(respuesta) == {"duda_especifica"}


# ---------------------------------------------------------------------------
# pedir_ayuda
# ---------------------------------------------------------------------------

def test_ayuda_sin_tarea_no_lanza_error():
    respuesta = server.pedir_ayuda("sigmoide")
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_ayuda_id_inexistente_no_lanza_error(con_tarea):
    respuesta = server.pedir_ayuda("no_existe")
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_ayuda_sin_diagnostico_pide_diagnostico(con_tarea):
    assert momentos_en(server.pedir_ayuda("sigmoide")) == {"diagnostico"}


@pytest.mark.parametrize("teoria, codigo, nombre", [
    (False, True, "teoria"),
    (True, False, "ejemplo"),
    (True, True, "duda_especifica"),
])
def test_ayuda_sin_fallos_usa_el_momento_inicial(con_tarea, teoria, codigo, nombre):
    con_tarea.registrar_diagnostico("sigmoide", teoria, codigo)
    assert momentos_en(server.pedir_ayuda("sigmoide")) == {nombre}


def test_ayuda_con_fallos_usa_la_revision(con_tarea):
    """Los fallos mandan sobre el diagnóstico."""
    con_tarea.registrar_diagnostico("sigmoide", True, True)
    fallar(con_tarea, "sigmoide")
    assert momentos_en(server.pedir_ayuda("sigmoide")) == {"revision_conceptual"}


def test_ayuda_intento_sin_tests_no_cuenta_como_fallo(con_tarea):
    con_tarea.registrar_diagnostico("sigmoide", True, False)
    server.registrar_intento("sigmoide", "x = 1")
    assert momentos_en(server.pedir_ayuda("sigmoide")) == {"ejemplo"}


def test_ayuda_rescate_queda_registrado(con_tarea):
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE)
    respuesta = server.pedir_ayuda("sigmoide")
    assert momentos_en(respuesta) == {"rescate"}
    assert con_tarea.subobjetivos["sigmoide"].rescatado is True


def test_ayuda_antes_del_rescate_no_entrega(con_tarea):
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE - 1)
    respuesta = server.pedir_ayuda("sigmoide")
    assert "rescate" not in momentos_en(respuesta)
    assert con_tarea.subobjetivos["sigmoide"].rescatado is False


def test_ayuda_sobre_resultados(con_tarea):
    con_tarea.registrar_diagnostico("sigmoide", True, True)
    respuesta = server.pedir_ayuda("sigmoide", sobre_resultados=True)
    assert momentos_en(respuesta) == {"resultados"}


def test_ayuda_sobre_resultados_manda_sobre_los_fallos(con_tarea):
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE)
    respuesta = server.pedir_ayuda("sigmoide", sobre_resultados=True)
    assert momentos_en(respuesta) == {"resultados"}
    assert con_tarea.subobjetivos["sigmoide"].rescatado is False


def test_ayuda_sobre_resultados_funciona_completado(con_tarea):
    """Interpretar resultados suele venir después de resolver el subobjetivo."""
    con_tarea.marcar_completado("sigmoide")
    respuesta = server.pedir_ayuda("sigmoide", sobre_resultados=True)
    assert momentos_en(respuesta) == {"resultados"}


def test_ayuda_completado_no_da_instrucciones(con_tarea):
    con_tarea.registrar_diagnostico("sigmoide", True, True)
    con_tarea.marcar_completado("sigmoide")
    respuesta = server.pedir_ayuda("sigmoide")
    assert isinstance(respuesta, str)
    assert momentos_en(respuesta) == set()


def test_ayuda_no_registra_intentos(con_tarea):
    server.pedir_ayuda("sigmoide")
    assert con_tarea.subobjetivos["sigmoide"].intentos == []


def test_ayuda_es_por_subobjetivo(con_tarea):
    fallar(con_tarea, "sigmoide", 2)
    assert momentos_en(server.pedir_ayuda("derivada")) == {"diagnostico"}


# ---------------------------------------------------------------------------
# ver_ejemplo
# ---------------------------------------------------------------------------

CODIGO_EJEMPLO = "def relu(x):\n    return max(0.0, x)\n"


@pytest.fixture
def tarea_con_ejemplo(tmp_path):
    """'sigmoide' trae ejemplo oficial y 'derivada' no. Devuelve la ruta del ejemplo."""
    archivo = tmp_path / "ejemplo_relu.py"
    archivo.write_text(CODIGO_EJEMPLO, encoding="utf-8")
    ruta = escribir_tarea(tmp_path / "tarea.json", [
        {"id": "sigmoide", "descripcion": "Implementar la sigmoide",
         "ejemplo": "ejemplo_relu.py"},
        {"id": "derivada", "descripcion": "Implementar la derivada"},
    ])
    server.cargar_tarea(ruta)
    return archivo


def test_ver_ejemplo_sin_tarea_no_lanza_error():
    respuesta = server.ver_ejemplo("sigmoide")
    assert isinstance(respuesta, str)
    assert "tarea" in respuesta.lower()


def test_ver_ejemplo_id_inexistente_no_lanza_error(tarea_con_ejemplo):
    respuesta = server.ver_ejemplo("no_existe")
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_ver_ejemplo_devuelve_el_contenido(tarea_con_ejemplo):
    assert CODIGO_EJEMPLO in server.ver_ejemplo("sigmoide")


def test_ver_ejemplo_lee_el_archivo_cada_vez(tarea_con_ejemplo):
    nuevo = "def relu(x):\n    return x if x > 0 else 0.0\n"
    tarea_con_ejemplo.write_text(nuevo, encoding="utf-8")
    assert nuevo in server.ver_ejemplo("sigmoide")


def test_ver_ejemplo_sin_ejemplo_oficial_avisa(tarea_con_ejemplo):
    respuesta = server.ver_ejemplo("derivada")
    assert isinstance(respuesta, str)
    assert "oficial" in respuesta.lower()
    assert CODIGO_EJEMPLO not in respuesta


def test_ver_ejemplo_archivo_inexistente_no_lanza_error(tarea_con_ejemplo):
    tarea_con_ejemplo.unlink()
    respuesta = server.ver_ejemplo("sigmoide")
    assert isinstance(respuesta, str)


def test_ver_ejemplo_no_cambia_el_estado(tarea_con_ejemplo):
    server.ver_ejemplo("sigmoide")
    sub = server.sesion.subobjetivos["sigmoide"]
    assert sub.intentos == []
    assert sub.rescatado is False


# ---------------------------------------------------------------------------
# leer_mi_codigo
# ---------------------------------------------------------------------------

CODIGO_DOS_FUNCIONES = (
    "import numpy as np\n"
    "\n"
    "\n"
    "def predecir(X, w, b):\n"
    "    return np.asarray(X) @ w + b\n"
    "\n"
    "\n"
    "def error_cuadratico_medio(y, y_pred):\n"
    "    return np.sum((y_pred - y) ** 2)\n"
)


@pytest.fixture
def tarea_con_archivo(tmp_path):
    """Carga una tarea con varios subobjetivos que comparten regresion.py.

    - 'prediccion' y 'costo': archivo y función.
    - 'entrenamiento': archivo y una función que todavía no existe en él.
    - 'todo': archivo sin función (se muestra completo).
    - 'sin_archivo': ni archivo ni función.
    Devuelve la ruta del archivo del estudiante.
    """
    archivo = tmp_path / "regresion.py"
    archivo.write_text(CODIGO_DOS_FUNCIONES, encoding="utf-8")
    ruta = escribir_tarea(tmp_path / "tarea.json", [
        {"id": "prediccion", "descripcion": "x", "archivo": "regresion.py",
         "funcion": "predecir"},
        {"id": "costo", "descripcion": "x", "archivo": "regresion.py",
         "funcion": "error_cuadratico_medio"},
        {"id": "entrenamiento", "descripcion": "x", "archivo": "regresion.py",
         "funcion": "entrenar"},
        {"id": "todo", "descripcion": "x", "archivo": "regresion.py"},
        {"id": "sin_archivo", "descripcion": "x"},
    ])
    server.cargar_tarea(ruta)
    return archivo


def test_leer_esta_registrada_en_el_servidor():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "leer_mi_codigo" in nombres


def test_leer_sin_tarea_no_lanza_error():
    respuesta = server.leer_mi_codigo("costo")
    assert isinstance(respuesta, str) and respuesta.strip()


def test_leer_id_inexistente_no_lanza_error(tarea_con_archivo):
    respuesta = server.leer_mi_codigo("no_existe")
    assert isinstance(respuesta, str)
    assert "no_existe" in respuesta


def test_leer_sin_archivo_configurado_no_lanza_error(tarea_con_archivo):
    respuesta = server.leer_mi_codigo("sin_archivo")
    assert isinstance(respuesta, str) and respuesta.strip()
    assert "def " not in respuesta


def test_leer_archivo_inexistente_no_lanza_error(tarea_con_archivo):
    tarea_con_archivo.unlink()
    respuesta = server.leer_mi_codigo("costo")
    assert isinstance(respuesta, str)
    assert str(tarea_con_archivo) in respuesta


def test_leer_con_funcion_muestra_solo_esa(tarea_con_archivo):
    respuesta = server.leer_mi_codigo("costo")
    assert "def error_cuadratico_medio(y, y_pred):" in respuesta
    assert "np.sum((y_pred - y) ** 2)" in respuesta
    assert "def predecir" not in respuesta


def test_leer_dice_de_que_archivo_viene(tarea_con_archivo):
    assert str(tarea_con_archivo) in server.leer_mi_codigo("costo")


def test_leer_sin_funcion_muestra_el_archivo_completo(tarea_con_archivo):
    respuesta = server.leer_mi_codigo("todo")
    assert "def predecir" in respuesta
    assert "def error_cuadratico_medio" in respuesta


def test_leer_funcion_que_no_esta_muestra_el_archivo_y_avisa(tarea_con_archivo):
    respuesta = server.leer_mi_codigo("entrenamiento")
    assert "def predecir" in respuesta
    assert "def error_cuadratico_medio" in respuesta
    assert "entrenar" in respuesta  # el aviso nombra la función que no encontró


def test_leer_error_de_sintaxis_muestra_el_archivo_y_avisa(tarea_con_archivo):
    roto = "def predecir(X, w, b:\n    return X\n"
    tarea_con_archivo.write_text(roto, encoding="utf-8")
    respuesta = server.leer_mi_codigo("prediccion")
    assert roto.strip() in respuesta
    assert "sintaxis" in respuesta.lower()


def test_leer_lee_el_archivo_cada_vez(tarea_con_archivo):
    server.leer_mi_codigo("costo")
    tarea_con_archivo.write_text(
        "def error_cuadratico_medio(y, y_pred):\n    return 42\n", encoding="utf-8")
    assert "return 42" in server.leer_mi_codigo("costo")


def test_leer_no_registra_intentos(tarea_con_archivo):
    server.leer_mi_codigo("costo")
    server.leer_mi_codigo("todo")
    for sub in server.sesion.subobjetivos.values():
        assert sub.intentos == []


# ---------------------------------------------------------------------------
# Guardado automático del estado
# ---------------------------------------------------------------------------

def leer_estado(ruta_tarea):
    """Lee el archivo de estado que corresponde a la tarea dada."""
    with open(server.ruta_estado(ruta_tarea), encoding="utf-8") as f:
        return json.load(f)


def test_ruta_estado_queda_junto_a_la_tarea():
    assert server.ruta_estado("/a/b/tarea.json") == "/a/b/tarea.estado.json"


def test_guardar_sesion_no_es_herramienta():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "guardar_sesion" not in nombres
    assert "ruta_estado" not in nombres


def test_guardar_sesion_sin_tarea_no_lanza_error():
    server.guardar_sesion()


def test_cargar_no_pisa_un_estado_guardado(con_tarea, ruta_tarea):
    """Cargar con reanudar=True (por defecto) no debe borrar el progreso."""
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    server.cargar_tarea(ruta_tarea)
    assert len(leer_estado(ruta_tarea)["subobjetivos"]["sigmoide"]["intentos"]) == 1


def test_registrar_intento_guarda(con_tarea, ruta_tarea):
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    assert len(leer_estado(ruta_tarea)["subobjetivos"]["sigmoide"]["intentos"]) == 1


def test_registrar_intento_fallido_no_crea_archivo(con_tarea, ruta_tarea):
    server.registrar_intento("no_existe", "x")
    assert not os.path.exists(server.ruta_estado(ruta_tarea))


def test_registrar_diagnostico_guarda(con_tarea, ruta_tarea):
    server.registrar_diagnostico("sigmoide", True, False)
    sub = leer_estado(ruta_tarea)["subobjetivos"]["sigmoide"]
    assert sub["maneja_teoria"] is True
    assert sub["maneja_codigo"] is False


def test_marcar_completado_guarda(con_tarea, ruta_tarea):
    server.marcar_completado("sigmoide")
    assert leer_estado(ruta_tarea)["subobjetivos"]["sigmoide"]["completado"] is True


def test_ejecutar_tests_guarda(tarea_con_tests, tmp_path):
    server.ejecutar_tests("sigmoide")
    estado = leer_estado(str(tmp_path / "tarea.json"))
    assert len(estado["subobjetivos"]["sigmoide"]["intentos"]) == 1


def test_pedir_ayuda_guarda_el_rescate(con_tarea, ruta_tarea):
    """El rescate se anota dentro de pedir_ayuda: también hay que guardarlo."""
    fallar(con_tarea, "sigmoide", FALLOS_PARA_RESCATE)
    server.pedir_ayuda("sigmoide")
    assert leer_estado(ruta_tarea)["subobjetivos"]["sigmoide"]["rescatado"] is True


# ---------------------------------------------------------------------------
# ayuda_entorno
# ---------------------------------------------------------------------------

def test_entorno_registrada_en_el_servidor():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert "ayuda_entorno" in nombres


def test_entorno_sin_tarea_responde_directo():
    """Sin tarea no hay subobjetivos con qué comparar: no es un error."""
    respuesta = server.ayuda_entorno("¿Cómo activo el entorno virtual?")
    assert server.INSTRUCCIONES_ENTORNO in respuesta


def test_entorno_pregunta_de_entorno_responde_directo(con_tarea):
    respuesta = server.ayuda_entorno("¿Cómo activo el entorno virtual?")
    assert server.INSTRUCCIONES_ENTORNO in respuesta


def test_entorno_pregunta_de_la_tarea_redirige(con_tarea):
    respuesta = server.ayuda_entorno("¿Cómo implemento la sigmoide con numpy?")
    assert server.INSTRUCCIONES_ENTORNO not in respuesta
    assert "sigmoide" in respuesta
    assert "pedir_ayuda" in respuesta


def test_entorno_redirige_al_subobjetivo_correcto(con_tarea):
    respuesta = server.ayuda_entorno("no me sale la derivada")
    assert "derivada" in respuesta
    assert server.INSTRUCCIONES_ENTORNO not in respuesta


def test_entorno_pregunta_vacia_no_lanza_error(con_tarea):
    respuesta = server.ayuda_entorno("   ")
    assert isinstance(respuesta, str)
    assert respuesta
    assert server.INSTRUCCIONES_ENTORNO not in respuesta


def test_entorno_no_cambia_el_estado(con_tarea, ruta_tarea):
    """Ni intentos, ni rescate, ni archivo de estado guardado."""
    server.ayuda_entorno("¿Cómo implemento la sigmoide?")
    server.ayuda_entorno("¿Cómo activo el entorno virtual?")
    for subobjetivo in con_tarea.subobjetivos.values():
        assert subobjetivo.intentos == []
        assert subobjetivo.rescatado is False
    assert not os.path.exists(server.ruta_estado(ruta_tarea))


def test_entorno_las_instrucciones_del_servidor_la_mencionan():
    assert "ayuda_entorno" in server.INSTRUCCIONES


# ---------------------------------------------------------------------------
# cargar_tarea: recargar el estado guardado
#
#     pytest tests/test_server.py -k reanud
# ---------------------------------------------------------------------------

def test_reanudar_es_parametro_de_la_herramienta():
    """El LLM solo puede usar reanudar=False si lo ve en el esquema."""
    h = next(h for h in asyncio.run(server.mcp.list_tools()) if h.name == "cargar_tarea")
    assert "reanudar" in h.input_schema["properties"]


def test_reanudar_recupera_los_intentos(con_tarea, ruta_tarea):
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    server.cargar_tarea(ruta_tarea)
    assert server.sesion is not con_tarea
    assert len(server.sesion.subobjetivos["sigmoide"].intentos) == 1


def test_reanudar_recupera_el_diagnostico(con_tarea, ruta_tarea):
    server.registrar_diagnostico("sigmoide", True, False)
    server.cargar_tarea(ruta_tarea)
    assert server.sesion.subobjetivos["sigmoide"].maneja_teoria is True


def test_reanudar_marca_los_completados(con_tarea, ruta_tarea):
    server.marcar_completado("sigmoide")
    respuesta = server.cargar_tarea(ruta_tarea)
    linea = next(l for l in respuesta.splitlines() if "sigmoide:" in l)
    assert "completado" in linea.lower()
    linea = next(l for l in respuesta.splitlines() if "derivada:" in l)
    assert "completado" not in linea.lower()


def test_reanudar_sin_estado_guardado_no_crea_archivo(ruta_tarea):
    server.cargar_tarea(ruta_tarea)
    assert server.sesion is not None
    assert not os.path.exists(server.ruta_estado(ruta_tarea))


def test_reanudar_estado_danado_no_lanza_error(ruta_tarea):
    with open(server.ruta_estado(ruta_tarea), "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    respuesta = server.cargar_tarea(ruta_tarea)
    assert isinstance(respuesta, str)
    assert server.sesion is not None
    assert server.sesion.subobjetivos["sigmoide"].intentos == []
    assert "progreso" in respuesta.lower()


def test_reanudar_estado_danado_no_se_pisa_al_cargar(ruta_tarea):
    with open(server.ruta_estado(ruta_tarea), "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    server.cargar_tarea(ruta_tarea)
    with open(server.ruta_estado(ruta_tarea), encoding="utf-8") as f:
        assert f.read() == "{esto no es json"


def test_reanudar_avisa_los_ids_ignorados(ruta_tarea):
    with open(server.ruta_estado(ruta_tarea), "w", encoding="utf-8") as f:
        json.dump({"subobjetivos": {"viejo": {"intentos": []}}}, f)
    respuesta = server.cargar_tarea(ruta_tarea)
    assert "viejo" in respuesta
    assert "viejo" not in server.sesion.subobjetivos


def test_sin_reanudar_pisa_el_estado_guardado(con_tarea, ruta_tarea):
    """Empezar de cero tiene que ser de verdad: el progreso viejo no vuelve."""
    server.registrar_intento("sigmoide", "def sigmoide(x): pass")
    server.cargar_tarea(ruta_tarea, reanudar=False)
    assert leer_estado(ruta_tarea)["subobjetivos"]["sigmoide"]["intentos"] == []
    server.cargar_tarea(ruta_tarea)
    assert server.sesion.subobjetivos["sigmoide"].intentos == []


def test_cargar_un_subobjetivo_por_linea(ruta_tarea):
    """Sin nada completado, cada subobjetivo igual va en su propia línea."""
    respuesta = server.cargar_tarea(ruta_tarea)
    lineas = respuesta.splitlines()
    assert sum("sigmoide:" in l for l in lineas) == 1
    assert sum("derivada:" in l for l in lineas) == 1
    assert not any("sigmoide:" in l and "derivada:" in l for l in lineas)


# ---------------------------------------------------------------------------
# El servidor arranca al final (if __name__ == "__main__")
# ---------------------------------------------------------------------------

def test_main_va_al_final_de_server():
    """mcp.run() se queda corriendo: lo que esté definido después nunca se registra.

    Importar server (como hacen estos tests) no ejecuta el bloque, así que los
    demás tests no lo detectan. Hay que mirar el archivo.
    """
    import ast
    with open(server.__file__, encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    ultimo = arbol.body[-1]
    assert isinstance(ultimo, ast.If) and "__main__" in ast.unparse(ultimo.test), (
        "El bloque if __name__ == '__main__' tiene que ser lo último de server.py")


# ---------------------------------------------------------------------------
# leer_fuente y crear_tarea (notebook -> tarea)
# ---------------------------------------------------------------------------

def celda_nb(tipo, texto, id_celda):
    celda = {"cell_type": tipo, "id": id_celda, "metadata": {},
             "source": texto.splitlines(keepends=True)}
    if tipo == "code":
        celda["outputs"] = []
        celda["execution_count"] = None
    return celda


CELDAS_LAB = [
    celda_nb("markdown", "# Lab de prueba\nPregunta 1: ¿qué es TF-IDF?", "enunciado"),
    celda_nb("markdown", "**Respuesta:** ...", "resp1"),
    celda_nb("code", "import numpy as np", "imports"),
    celda_nb("code", "# TU CÓDIGO AQUÍ", "hueco"),
]

PROPUESTA = [
    {"id": "pregunta_1", "descripcion": "Explicar qué es TF-IDF",
     "celdas": ["enunciado", "resp1"]},
    {"id": "limpieza", "descripcion": "Implementar la limpieza", "celdas": ["hueco"]},
]


@pytest.fixture
def notebook(tmp_path):
    """Ruta (str) a un notebook con una pregunta abierta y un hueco de código."""
    ruta = tmp_path / "lab.ipynb"
    contenido = {"cells": CELDAS_LAB, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    return str(ruta)


def json_generado(notebook):
    return notebook[: -len(".ipynb")] + ".tarea.json"


def test_leer_fuente_y_crear_tarea_registradas():
    nombres = {h.name for h in asyncio.run(server.mcp.list_tools())}
    assert {"leer_fuente", "crear_tarea"} <= nombres


def test_leer_fuente_muestra_tipos_ubicaciones_y_contenido(notebook):
    respuesta = server.leer_fuente(notebook)
    for tipo in ("texto", "texto_por_completar", "codigo", "codigo_por_completar"):
        assert tipo in respuesta
    for id_celda in ("enunciado", "resp1", "imports", "hueco"):
        assert id_celda in respuesta
    assert "¿qué es TF-IDF?" in respuesta
    assert "# TU CÓDIGO AQUÍ" in respuesta


def test_leer_fuente_no_cambia_la_sesion(con_tarea, notebook):
    server.leer_fuente(notebook)
    assert server.sesion is con_tarea


def test_leer_fuente_sin_tarea_no_carga_nada(notebook):
    server.leer_fuente(notebook)
    assert server.sesion is None


def test_leer_fuente_trae_lo_ultimo_guardado(notebook):
    server.leer_fuente(notebook)
    with open(notebook, encoding="utf-8") as f:
        datos = json.load(f)
    datos["cells"][1]["source"] = ["**Respuesta:** pondera la frecuencia"]
    with open(notebook, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    assert "pondera la frecuencia" in server.leer_fuente(notebook)


def test_leer_fuente_archivo_inexistente_no_lanza_error(tmp_path):
    respuesta = server.leer_fuente(str(tmp_path / "no_existe.ipynb"))
    assert isinstance(respuesta, str) and respuesta.strip()


def test_leer_fuente_notebook_roto_no_lanza_error(tmp_path):
    ruta = tmp_path / "roto.ipynb"
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert isinstance(server.leer_fuente(str(ruta)), str)


def test_leer_fuente_extension_no_soportada(tmp_path):
    ruta = tmp_path / "enunciado.pdf"
    ruta.write_text("hola", encoding="utf-8")
    respuesta = server.leer_fuente(str(ruta))
    assert isinstance(respuesta, str)
    assert ".ipynb" in respuesta


def test_leer_fuente_virgulilla_y_espacios(notebook, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert "# TU CÓDIGO AQUÍ" in server.leer_fuente("  ~/lab.ipynb \n")


def test_crear_escribe_el_json_junto_al_notebook(notebook):
    server.crear_tarea(notebook, PROPUESTA)
    assert os.path.exists(json_generado(notebook))


def test_crear_carga_la_tarea(notebook):
    respuesta = server.crear_tarea(notebook, PROPUESTA)
    assert server.sesion is not None
    assert list(server.sesion.subobjetivos) == ["pregunta_1", "limpieza"]
    assert "pregunta_1" in respuesta and "limpieza" in respuesta


def test_crear_responde_la_ruta_del_json(notebook):
    assert json_generado(notebook) in server.crear_tarea(notebook, PROPUESTA)


def test_crear_guarda_las_celdas(notebook):
    server.crear_tarea(notebook, PROPUESTA)
    with open(json_generado(notebook), encoding="utf-8") as f:
        datos = json.load(f)
    assert datos["subobjetivos"][0]["celdas"] == ["enunciado", "resp1"]


def test_crear_se_puede_volver_a_cargar(notebook):
    server.crear_tarea(notebook, PROPUESTA)
    server.sesion = None
    server.cargar_tarea(json_generado(notebook))
    assert list(server.sesion.subobjetivos) == ["pregunta_1", "limpieza"]


def test_crear_virgulilla_y_espacios(notebook, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    server.crear_tarea("  ~/lab.ipynb\n", PROPUESTA)
    assert os.path.exists(json_generado(notebook))


@pytest.mark.parametrize("propuesta, culpable", [
    ([], None),
    ([{"id": "p1", "descripcion": "x", "celdas": ["inventada"]}], "inventada"),
    ([{"id": "p1", "descripcion": "x", "tests": "test_p1.py"}], "tests"),
    ([{"id": "p1", "descripcion": "x"}, {"id": "p1", "descripcion": "y"}], "p1"),
    ([{"descripcion": "sin id"}], "id"),
])
def test_crear_propuesta_invalida_no_escribe(notebook, con_tarea, propuesta, culpable):
    respuesta = server.crear_tarea(notebook, propuesta)
    assert isinstance(respuesta, str)
    if culpable:
        assert culpable in respuesta
    assert not os.path.exists(json_generado(notebook))
    assert server.sesion is con_tarea


def test_crear_notebook_inexistente_no_lanza_error(tmp_path, con_tarea):
    respuesta = server.crear_tarea(str(tmp_path / "no.ipynb"), PROPUESTA)
    assert isinstance(respuesta, str)
    assert server.sesion is con_tarea


def test_crear_extension_no_soportada(tmp_path):
    ruta = tmp_path / "tarea.json"
    ruta.write_text("{}", encoding="utf-8")
    respuesta = server.crear_tarea(str(ruta), PROPUESTA)
    assert ".ipynb" in respuesta
    assert ruta.read_text(encoding="utf-8") == "{}"


def test_crear_no_pisa_una_tarea_existente(notebook):
    server.crear_tarea(notebook, PROPUESTA)
    server.sesion = None
    otra = [{"id": "otra", "descripcion": "Otra cosa"}]
    respuesta = server.crear_tarea(notebook, otra)
    assert json_generado(notebook) in respuesta
    with open(json_generado(notebook), encoding="utf-8") as f:
        assert [s["id"] for s in json.load(f)["subobjetivos"]] == ["pregunta_1", "limpieza"]
    assert server.sesion is None


def test_crear_reemplazar_rehace_la_tarea(notebook):
    server.crear_tarea(notebook, PROPUESTA)
    otra = [{"id": "otra", "descripcion": "Otra cosa"}]
    server.crear_tarea(notebook, otra, reemplazar=True)
    assert list(server.sesion.subobjetivos) == ["otra"]


def test_crear_reemplazar_conserva_el_progreso_de_lo_que_sigue(notebook):
    server.crear_tarea(notebook, PROPUESTA)
    server.registrar_intento("pregunta_1", "Pondera la frecuencia por la rareza")
    nueva = PROPUESTA + [{"id": "extra", "descripcion": "Un paso más"}]
    server.crear_tarea(notebook, nueva, reemplazar=True)
    assert len(server.sesion.subobjetivos["pregunta_1"].intentos) == 1
    assert server.sesion.subobjetivos["extra"].intentos == []


def test_crear_pregunta_abierta_usa_el_ciclo_sin_tests(notebook):
    """Sin tests: registrar_intento no cuenta como fallo y no lleva a revisión."""
    server.crear_tarea(notebook, PROPUESTA)
    for _ in range(FALLOS_PARA_RESCATE):
        server.registrar_intento("pregunta_1", "Una respuesta")
    respuesta = server.pedir_ayuda("pregunta_1")
    assert not es_momento(respuesta, "rescate")
    assert isinstance(server.ejecutar_tests("pregunta_1"), str)
    server.marcar_completado("pregunta_1")
    assert server.sesion.subobjetivos["pregunta_1"].completado
