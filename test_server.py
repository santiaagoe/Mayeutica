"""Tests de server.py.

Prueban las herramientas MCP llamándolas como funciones normales de Python:
el decorador @mcp.tool() devuelve la función original, así que no hace falta
levantar el servidor. Para trabajar una herramienta a la vez:

    pytest test_server.py -k instrucciones_servidor
    pytest test_server.py -k formatear
    pytest test_server.py -k revision
    pytest test_server.py -k diagnostico
    pytest test_server.py -k ayuda
    pytest test_server.py -k ver_ejemplo
    pytest test_server.py -k ejecutar

Los tests no exigen frases exactas: revisan que la respuesta sea texto, que no
se lance una excepción y que el estado de la sesión cambie (o no) como debe.
"""

import asyncio
import json

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
