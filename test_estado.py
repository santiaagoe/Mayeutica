"""Tests de estado.py.

Cada grupo de tests corresponde a un paso del plan. Para trabajar un paso a la vez,
corre solo sus tests con -k, por ejemplo:

    pytest -k intento          # paso 1 y 4
    pytest -k completar        # marcar_completado

Las reglas de los momentos del ciclo (diagnóstico, revisión, rescate) están en
test_momentos.py.

Al principio casi todos van a fallar: eso es lo esperado. Tu trabajo es
implementar estado.py hasta que pasen.
"""

import json
from datetime import datetime

import pytest

from estado import Intento, SesionTarea


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


def con_intentos(sesion, subobjetivo_id, cantidad=1):
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
# Paso 6: guardar
# ---------------------------------------------------------------------------

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


def test_completar_no_borra_intentos(sesion):
    con_intentos(sesion, "sigmoide", 2)
    sesion.marcar_completado("sigmoide")
    assert len(sesion.subobjetivos["sigmoide"].intentos) == 2


def test_completar_se_guarda_en_disco(sesion, tmp_path):
    sesion.marcar_completado("sigmoide")
    ruta = tmp_path / "estado.json"
    sesion.guardar(str(ruta))
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["subobjetivos"]["sigmoide"]["completado"] is True
    assert datos["subobjetivos"]["derivada"]["completado"] is False


# ---------------------------------------------------------------------------
# Carga de "archivo" y "tests" (para ejecutar_tests)
# ---------------------------------------------------------------------------

def test_carga_sin_archivo_ni_tests_deja_none(sesion):
    sub = sesion.subobjetivos["sigmoide"]
    assert sub.archivo is None
    assert sub.tests is None


def test_carga_rutas_relativas_desde_la_carpeta_del_json(tmp_path, monkeypatch):
    carpeta = tmp_path / "tarea"
    carpeta.mkdir()
    ruta = carpeta / "tarea.json"
    escribir_tarea(ruta, [{"id": "sigmoide", "descripcion": "x",
                           "archivo": "sigmoide.py", "tests": "test_sigmoide.py"}])
    monkeypatch.chdir(tmp_path)  # el directorio actual NO es la carpeta del JSON
    sub = SesionTarea(str(ruta)).subobjetivos["sigmoide"]
    assert sub.archivo == str(carpeta / "sigmoide.py")
    assert sub.tests == str(carpeta / "test_sigmoide.py")


def test_carga_rutas_absolutas_se_respetan(tmp_path):
    otra = tmp_path / "otra" / "sigmoide.py"
    ruta = tmp_path / "tarea.json"
    escribir_tarea(ruta, [{"id": "sigmoide", "descripcion": "x", "archivo": str(otra)}])
    sub = SesionTarea(str(ruta)).subobjetivos["sigmoide"]
    assert sub.archivo == str(otra)
    assert sub.tests is None
