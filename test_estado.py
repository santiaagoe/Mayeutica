"""Tests de estado.py.

Cada grupo de tests corresponde a un paso del plan. Para trabajar un paso a la vez,
corre solo sus tests con -k, por ejemplo:

    pytest -k intento          # paso 1 y 4
    pytest -k regla_2          # paso 5, regla 2

Al principio casi todos van a fallar: eso es lo esperado. Tu trabajo es
implementar estado.py hasta que pasen.
"""

import json
from datetime import datetime

import pytest

from estado import INTENTOS_PREV_NECESARIOS, NIVEL_MAXIMO, Intento, SesionTarea


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

def escribir_tarea(ruta, subobjetivos):
    """Escribe un JSON de tarea en la ruta dada.

    Si tu tarea_ejemplo.json usa otro formato, ajusta solo esta función.
    """
    contenido = {"titulo": "Tarea de prueba", "subobjetivos": subobjetivos}
    ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sesion(tmp_path):
    """Una sesión con dos subobjetivos: 'sigmoide' y 'derivada'.

    tmp_path es una carpeta temporal que pytest crea y borra sola.
    """
    ruta = tmp_path / "tarea.json"
    escribir_tarea(ruta, [
        {"id": "sigmoide", "descripcion": "Implementar la función sigmoide"},
        {"id": "derivada", "descripcion": "Implementar la derivada de la sigmoide"},
    ])
    return SesionTarea(str(ruta))


def con_intentos(sesion, subobjetivo_id, cantidad=INTENTOS_PREV_NECESARIOS):
    """Registra la cantidad de intentos indicada y devuelve la sesión."""
    for i in range(cantidad):
        sesion.registrar_intento(subobjetivo_id, f"intento {i}")
    return sesion


# ---------------------------------------------------------------------------
# Paso 3: cargar la tarea
# ---------------------------------------------------------------------------

def test_carga_crea_un_subobjetivo_por_entrada(sesion):
    assert set(sesion.subobjetivos.keys()) == {"sigmoide", "derivada"}


def test_carga_guarda_la_descripcion(sesion):
    assert sesion.subobjetivos["derivada"].descripcion == "Implementar la derivada de la sigmoide"


def test_subobjetivo_nuevo_parte_vacio(sesion):
    sub = sesion.subobjetivos["sigmoide"]
    assert sub.intentos == []
    assert sub.nivel_pista_desbloqueado == 0
    assert sub.completado is False


def test_subobjetivos_no_comparten_lista_de_intentos(sesion):
    sesion.registrar_intento("sigmoide", "x = 1")
    assert sesion.subobjetivos["derivada"].intentos == []


def test_carga_archivo_inexistente_lanza_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        SesionTarea(str(tmp_path / "no_existe.json"))


def test_carga_ids_duplicados_lanza_error(tmp_path):
    ruta = tmp_path / "tarea.json"
    escribir_tarea(ruta, [
        {"id": "sigmoide", "descripcion": "Una"},
        {"id": "sigmoide", "descripcion": "Otra"},
    ])
    with pytest.raises(ValueError):
        SesionTarea(str(ruta))


# ---------------------------------------------------------------------------
# Pasos 1 y 4: Intento y registrar_intento
# ---------------------------------------------------------------------------

def test_intento_se_crea_con_fecha_automatica():
    intento = Intento(subobjetivo_id="sigmoide", codigo="x = 1", resultado_tests=None)
    assert isinstance(intento.fecha, datetime)


def test_registrar_intento_devuelve_el_intento(sesion):
    intento = sesion.registrar_intento("sigmoide", "def sigmoide(x): ...", "1 test falló")
    assert isinstance(intento, Intento)
    assert intento.subobjetivo_id == "sigmoide"
    assert intento.codigo == "def sigmoide(x): ..."
    assert intento.resultado_tests == "1 test falló"


def test_registrar_intento_sin_tests_deja_none(sesion):
    intento = sesion.registrar_intento("sigmoide", "x = 1")
    assert intento.resultado_tests is None


def test_registrar_intento_lo_guarda_en_su_subobjetivo(sesion):
    intento = sesion.registrar_intento("sigmoide", "x = 1")
    assert sesion.subobjetivos["sigmoide"].intentos == [intento]


def test_registrar_intento_mantiene_el_orden(sesion):
    primero = sesion.registrar_intento("sigmoide", "x = 1")
    segundo = sesion.registrar_intento("sigmoide", "x = 2")
    assert sesion.subobjetivos["sigmoide"].intentos == [primero, segundo]


def test_registrar_intento_id_inexistente_lanza_error(sesion):
    with pytest.raises(KeyError):
        sesion.registrar_intento("no_existe", "x = 1")


# ---------------------------------------------------------------------------
# Paso 5, regla 1: niveles entre 1 y NIVEL_MAXIMO, sin saltarse ninguno
# ---------------------------------------------------------------------------

def test_regla_1_nivel_cero_no_permitido(sesion):
    con_intentos(sesion, "sigmoide")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 0)
    assert permitido is False


def test_regla_1_nivel_sobre_el_maximo_no_permitido(sesion):
    con_intentos(sesion, "sigmoide")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", NIVEL_MAXIMO + 1)
    assert permitido is False


def test_regla_1_no_se_puede_saltar_un_nivel(sesion):
    con_intentos(sesion, "sigmoide")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 2)
    assert permitido is False


def test_regla_1_no_se_puede_repetir_un_nivel_entregado(sesion):
    con_intentos(sesion, "sigmoide")
    sesion.registrar_pista_entregada("sigmoide", 1)
    sesion.registrar_intento("sigmoide", "otro intento")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 1)
    assert permitido is False


# ---------------------------------------------------------------------------
# Paso 5, regla 2: el nivel 1 exige intentos previos
# ---------------------------------------------------------------------------

def test_regla_2_sin_intentos_no_hay_pista_1(sesion):
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 1)
    assert permitido is False


def test_regla_2_con_intentos_suficientes_hay_pista_1(sesion):
    con_intentos(sesion, "sigmoide")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 1)
    assert permitido is True


def test_regla_2_intentos_de_otro_subobjetivo_no_cuentan(sesion):
    con_intentos(sesion, "derivada")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 1)
    assert permitido is False


# ---------------------------------------------------------------------------
# Paso 5, regla 3: entre una pista y la siguiente tiene que haber un intento
# ---------------------------------------------------------------------------

def test_regla_3_sin_intento_nuevo_no_hay_siguiente_pista(sesion):
    con_intentos(sesion, "sigmoide")
    sesion.registrar_pista_entregada("sigmoide", 1)
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 2)
    assert permitido is False


def test_regla_3_intentos_anteriores_a_la_pista_no_cuentan(sesion):
    con_intentos(sesion, "sigmoide", cantidad=3)
    sesion.registrar_pista_entregada("sigmoide", 1)
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 2)
    assert permitido is False


def test_regla_3_con_intento_nuevo_hay_siguiente_pista(sesion):
    con_intentos(sesion, "sigmoide")
    sesion.registrar_pista_entregada("sigmoide", 1)
    sesion.registrar_intento("sigmoide", "intento después de la pista 1")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 2)
    assert permitido is True


def test_regla_3_recorrido_completo_hasta_el_maximo(sesion):
    con_intentos(sesion, "sigmoide")
    for nivel in range(1, NIVEL_MAXIMO + 1):
        permitido, mensaje = sesion.puede_pedir_pista("sigmoide", nivel)
        assert permitido is True, f"nivel {nivel}: {mensaje}"
        sesion.registrar_pista_entregada("sigmoide", nivel)
        sesion.registrar_intento("sigmoide", f"intento después de la pista {nivel}")
    permitido, _ = sesion.puede_pedir_pista("sigmoide", NIVEL_MAXIMO + 1)
    assert permitido is False


# ---------------------------------------------------------------------------
# Paso 5, regla 4: un subobjetivo completado no da más pistas
# ---------------------------------------------------------------------------

def test_regla_4_completado_no_da_pistas(sesion):
    con_intentos(sesion, "sigmoide")
    sesion.subobjetivos["sigmoide"].completado = True
    permitido, _ = sesion.puede_pedir_pista("sigmoide", 1)
    assert permitido is False


def test_regla_4_completar_uno_no_afecta_a_otro(sesion):
    con_intentos(sesion, "derivada")
    sesion.subobjetivos["sigmoide"].completado = True
    permitido, _ = sesion.puede_pedir_pista("derivada", 1)
    assert permitido is True


# ---------------------------------------------------------------------------
# Paso 5, regla 5: toda negativa trae un mensaje que explica por qué
# ---------------------------------------------------------------------------

def _sin_intentos(s):
    return s, 1


def _nivel_saltado(s):
    return con_intentos(s, "sigmoide"), 3


def _sin_intento_nuevo(s):
    con_intentos(s, "sigmoide")
    s.registrar_pista_entregada("sigmoide", 1)
    return s, 2


def _completado(s):
    con_intentos(s, "sigmoide")
    s.subobjetivos["sigmoide"].completado = True
    return s, 1


@pytest.mark.parametrize("preparar", [_sin_intentos, _nivel_saltado, _sin_intento_nuevo, _completado])
def test_regla_5_toda_negativa_explica_el_motivo(sesion, preparar):
    sesion, nivel = preparar(sesion)
    permitido, mensaje = sesion.puede_pedir_pista("sigmoide", nivel)
    assert permitido is False
    assert isinstance(mensaje, str) and mensaje.strip() != ""


@pytest.fixture
def fabrica_sesiones(tmp_path):
    """Devuelve una función que crea sesiones nuevas e independientes entre sí."""
    contador = {"n": 0}

    def crear():
        contador["n"] += 1
        ruta = tmp_path / f"tarea_{contador['n']}.json"
        escribir_tarea(ruta, [
            {"id": "sigmoide", "descripcion": "Implementar la función sigmoide"},
            {"id": "derivada", "descripcion": "Implementar la derivada de la sigmoide"},
        ])
        return SesionTarea(str(ruta))

    return crear


def test_regla_5_cada_motivo_tiene_su_propio_mensaje(fabrica_sesiones):
    """Cada regla da un mensaje distinto, para que el estudiante sepa qué hacer."""
    mensajes = set()
    for preparar in [_sin_intentos, _nivel_saltado, _sin_intento_nuevo, _completado]:
        sesion, nivel = preparar(fabrica_sesiones())
        _, mensaje = sesion.puede_pedir_pista("sigmoide", nivel)
        mensajes.add(mensaje)
    assert len(mensajes) == 4


# ---------------------------------------------------------------------------
# Paso 6: registrar_pista_entregada y guardar
# ---------------------------------------------------------------------------

def test_registrar_pista_actualiza_el_nivel(sesion):
    con_intentos(sesion, "sigmoide")
    sesion.registrar_pista_entregada("sigmoide", 1)
    assert sesion.subobjetivos["sigmoide"].nivel_pista_desbloqueado == 1


def test_registrar_pista_no_afecta_a_otro_subobjetivo(sesion):
    con_intentos(sesion, "sigmoide")
    sesion.registrar_pista_entregada("sigmoide", 1)
    assert sesion.subobjetivos["derivada"].nivel_pista_desbloqueado == 0


def test_guardar_crea_el_archivo_con_los_intentos(sesion, tmp_path):
    sesion.registrar_intento("sigmoide", "codigo_unico_123")
    ruta = tmp_path / "estado_guardado.json"
    sesion.guardar(str(ruta))
    assert ruta.exists()
    assert "codigo_unico_123" in ruta.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Completar subobjetivos: marcar_completado (pendiente 2)
# ---------------------------------------------------------------------------

def test_completar_marca_el_subobjetivo(sesion):
    sesion.marcar_completado("sigmoide")
    assert sesion.subobjetivos["sigmoide"].completado is True


def test_completar_no_afecta_a_otro_subobjetivo(sesion):
    sesion.marcar_completado("sigmoide")
    assert sesion.subobjetivos["derivada"].completado is False


def test_completar_devuelve_true_la_primera_vez(sesion):
    assert sesion.marcar_completado("sigmoide") is True


def test_completar_dos_veces_devuelve_false_y_sigue_completado(sesion):
    sesion.marcar_completado("sigmoide")
    assert sesion.marcar_completado("sigmoide") is False
    assert sesion.subobjetivos["sigmoide"].completado is True


def test_completar_id_inexistente_lanza_keyerror(sesion):
    with pytest.raises(KeyError):
        sesion.marcar_completado("no_existe")


def test_completar_bloquea_las_pistas(sesion):
    """Conecta el método nuevo con la regla 4, que ya está implementada."""
    con_intentos(sesion, "sigmoide")
    assert sesion.puede_pedir_pista("sigmoide", 1)[0] is True
    sesion.marcar_completado("sigmoide")
    assert sesion.puede_pedir_pista("sigmoide", 1)[0] is False


def test_completar_no_borra_intentos_ni_pistas(sesion):
    con_intentos(sesion, "sigmoide", 2)
    sesion.registrar_pista_entregada("sigmoide", 1)
    sesion.marcar_completado("sigmoide")
    sub = sesion.subobjetivos["sigmoide"]
    assert len(sub.intentos) == 2
    assert sub.nivel_pista_desbloqueado == 1


def test_completar_se_guarda_en_disco(sesion, tmp_path):
    sesion.marcar_completado("sigmoide")
    ruta = tmp_path / "estado.json"
    sesion.guardar(str(ruta))
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["subobjetivos"]["sigmoide"]["completado"] is True
    assert datos["subobjetivos"]["derivada"]["completado"] is False
