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

def test_sesion_recuerda_la_ruta_absoluta_de_la_tarea(sesion, tmp_path):
    """Hace falta para saber dónde guardar su estado."""
    assert sesion.ruta_tarea == str((tmp_path / "tarea.json").resolve())


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


# ---------------------------------------------------------------------------
# Carga de "funcion" (para leer_mi_codigo)
#   pytest -k funcion
# ---------------------------------------------------------------------------

def test_carga_sin_funcion_deja_none(sesion):
    assert sesion.subobjetivos["sigmoide"].funcion is None


def test_carga_guarda_la_funcion(tmp_path):
    ruta = tmp_path / "tarea.json"
    escribir_tarea(ruta, [{"id": "costo", "descripcion": "x",
                           "archivo": "regresion.py",
                           "funcion": "error_cuadratico_medio"}])
    sub = SesionTarea(str(ruta)).subobjetivos["costo"]
    assert sub.funcion == "error_cuadratico_medio"


def test_carga_funcion_no_se_trata_como_ruta(tmp_path):
    """La función es un nombre, no una ruta: no se le antepone la carpeta del JSON."""
    ruta = tmp_path / "tarea.json"
    escribir_tarea(ruta, [{"id": "costo", "descripcion": "x", "funcion": "gradientes"}])
    assert SesionTarea(str(ruta)).subobjetivos["costo"].funcion == "gradientes"


# ---------------------------------------------------------------------------
# Recargar el estado: Intento.desde_dict y cargar_estado
#
#     pytest tests/test_estado.py -k desde_dict
#     pytest tests/test_estado.py -k cargar_estado
# ---------------------------------------------------------------------------

def ida_y_vuelta(intento):
    """Pasa un Intento por el mismo camino que guardar: asdict + JSON con default=str."""
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(intento), default=str))


def escribir_estado(ruta, subobjetivos):
    """Escribe un archivo de estado a mano, con el formato de guardar."""
    ruta.write_text(json.dumps({"subobjetivos": subobjetivos}, ensure_ascii=False),
                    encoding="utf-8")


def recargar(sesion, tmp_path):
    """Guarda la sesión, crea una sesión nueva de la misma tarea y le carga el estado."""
    ruta_estado = tmp_path / "tarea.estado.json"
    sesion.guardar(str(ruta_estado))
    nueva = SesionTarea(str(tmp_path / "tarea.json"))
    nueva.cargar_estado(str(ruta_estado))
    return nueva


def test_desde_dict_devuelve_un_intento():
    datos = ida_y_vuelta(Intento("sigmoide", "x = 1"))
    assert isinstance(Intento.desde_dict(datos), Intento)


def test_desde_dict_ida_y_vuelta_da_el_mismo_intento():
    original = Intento("sigmoide", "x = 1", "1 failed", paso=False)
    assert Intento.desde_dict(ida_y_vuelta(original)) == original


def test_desde_dict_la_fecha_vuelve_como_datetime():
    datos = ida_y_vuelta(Intento("sigmoide", "x = 1"))
    assert isinstance(datos["fecha"], str)
    assert isinstance(Intento.desde_dict(datos).fecha, datetime)


def test_desde_dict_opcionales_ausentes_quedan_en_none():
    datos = {"subobjetivo_id": "sigmoide", "codigo": "x = 1",
             "fecha": "2026-11-02 20:13:05.123456"}
    intento = Intento.desde_dict(datos)
    assert intento.resultado_tests is None
    assert intento.paso is None


def test_desde_dict_sin_campo_obligatorio_lanza_keyerror():
    with pytest.raises(KeyError):
        Intento.desde_dict({"subobjetivo_id": "sigmoide", "fecha": "2026-11-02 20:13:05"})


def test_desde_dict_fecha_invalida_lanza_valueerror():
    with pytest.raises(ValueError):
        Intento.desde_dict({"subobjetivo_id": "sigmoide", "codigo": "x",
                            "fecha": "no es una fecha"})


def test_cargar_estado_recupera_los_intentos(sesion, tmp_path):
    sesion.registrar_intento("sigmoide", "x = 1", "1 failed", paso=False)
    sesion.registrar_intento("sigmoide", "x = 2", "ok", paso=True)
    nueva = recargar(sesion, tmp_path)
    assert nueva.subobjetivos["sigmoide"].intentos == sesion.subobjetivos["sigmoide"].intentos


def test_cargar_estado_los_intentos_son_objetos(sesion, tmp_path):
    sesion.registrar_intento("sigmoide", "x = 1")
    intento = recargar(sesion, tmp_path).subobjetivos["sigmoide"].intentos[0]
    assert isinstance(intento, Intento)
    assert isinstance(intento.fecha, datetime)


def test_cargar_estado_los_fallos_siguen_contando(sesion, tmp_path):
    """Si los intentos vuelven bien, el árbitro sigue funcionando sin cambios."""
    for _ in range(2):
        sesion.registrar_intento("sigmoide", "x = 1", "1 failed", paso=False)
    assert recargar(sesion, tmp_path).subobjetivos["sigmoide"].intentos_fallidos() == 2


def test_cargar_estado_recupera_el_diagnostico(sesion, tmp_path):
    sesion.registrar_diagnostico("sigmoide", True, False)
    sub = recargar(sesion, tmp_path).subobjetivos["sigmoide"]
    assert sub.maneja_teoria is True
    assert sub.maneja_codigo is False


def test_cargar_estado_recupera_completado_y_rescatado(sesion, tmp_path):
    sesion.marcar_completado("sigmoide")
    sesion.subobjetivos["derivada"].rescatado = True
    nueva = recargar(sesion, tmp_path)
    assert nueva.subobjetivos["sigmoide"].completado is True
    assert nueva.subobjetivos["derivada"].rescatado is True


def test_cargar_estado_no_mezcla_subobjetivos(sesion, tmp_path):
    sesion.registrar_intento("sigmoide", "x = 1")
    nueva = recargar(sesion, tmp_path)
    assert nueva.subobjetivos["derivada"].intentos == []


def test_cargar_estado_la_tarea_manda_en_la_descripcion(sesion, tmp_path):
    """Si se corrige la tarea después de guardar, gana la versión nueva."""
    ruta_estado = tmp_path / "tarea.estado.json"
    sesion.guardar(str(ruta_estado))
    escribir_tarea(tmp_path / "tarea.json", [
        {"id": "sigmoide", "descripcion": "Descripción corregida"},
        {"id": "derivada", "descripcion": "Implementar la derivada de la sigmoide"},
    ])
    nueva = SesionTarea(str(tmp_path / "tarea.json"))
    nueva.cargar_estado(str(ruta_estado))
    assert nueva.subobjetivos["sigmoide"].descripcion == "Descripción corregida"


def test_cargar_estado_todos_calzan_devuelve_lista_vacia(sesion, tmp_path):
    ruta_estado = tmp_path / "tarea.estado.json"
    sesion.guardar(str(ruta_estado))
    assert sesion.cargar_estado(str(ruta_estado)) == []


def test_cargar_estado_ignora_ids_que_ya_no_estan(sesion, tmp_path):
    ruta_estado = tmp_path / "tarea.estado.json"
    escribir_estado(ruta_estado, {
        "viejo": {"intentos": [], "completado": True},
        "sigmoide": {"intentos": [], "completado": True},
    })
    assert sesion.cargar_estado(str(ruta_estado)) == ["viejo"]
    assert "viejo" not in sesion.subobjetivos
    assert sesion.subobjetivos["sigmoide"].completado is True


def test_cargar_estado_subobjetivo_nuevo_parte_de_cero(sesion, tmp_path):
    ruta_estado = tmp_path / "tarea.estado.json"
    escribir_estado(ruta_estado, {"sigmoide": {"intentos": [], "completado": True}})
    sesion.cargar_estado(str(ruta_estado))
    derivada = sesion.subobjetivos["derivada"]
    assert derivada.intentos == []
    assert derivada.completado is False
    assert derivada.maneja_teoria is None


def test_cargar_estado_campo_faltante_deja_el_valor_previo(sesion, tmp_path):
    """Un estado sin 'rescatado' (por ejemplo, de una versión vieja) no es un error."""
    ruta_estado = tmp_path / "tarea.estado.json"
    escribir_estado(ruta_estado, {"sigmoide": {"intentos": [], "completado": True}})
    sesion.cargar_estado(str(ruta_estado))
    assert sesion.subobjetivos["sigmoide"].rescatado is False


def test_cargar_estado_archivo_inexistente_lanza_error(sesion, tmp_path):
    with pytest.raises(FileNotFoundError):
        sesion.cargar_estado(str(tmp_path / "no_existe.json"))


def test_cargar_estado_json_invalido_lanza_valueerror(sesion, tmp_path):
    ruta_estado = tmp_path / "tarea.estado.json"
    ruta_estado.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        sesion.cargar_estado(str(ruta_estado))


def test_cargar_estado_sin_subobjetivos_lanza_valueerror(sesion, tmp_path):
    ruta_estado = tmp_path / "tarea.estado.json"
    ruta_estado.write_text(json.dumps({"otra_cosa": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        sesion.cargar_estado(str(ruta_estado))


def test_cargar_estado_intento_danado_lanza_valueerror(sesion, tmp_path):
    ruta_estado = tmp_path / "tarea.estado.json"
    escribir_estado(ruta_estado, {"sigmoide": {"intentos": [{"codigo": "x"}]}})
    with pytest.raises(ValueError):
        sesion.cargar_estado(str(ruta_estado))


def test_cargar_estado_danado_no_cambia_nada(sesion, tmp_path):
    """Todo o nada: 'sigmoide' está bien, pero 'derivada' está dañado."""
    ruta_estado = tmp_path / "tarea.estado.json"
    escribir_estado(ruta_estado, {
        "sigmoide": {"intentos": [], "completado": True, "maneja_teoria": True},
        "derivada": {"intentos": [{"subobjetivo_id": "derivada", "codigo": "x",
                                   "fecha": "no es una fecha"}]},
    })
    with pytest.raises(ValueError):
        sesion.cargar_estado(str(ruta_estado))
    assert sesion.subobjetivos["sigmoide"].completado is False
    assert sesion.subobjetivos["sigmoide"].maneja_teoria is None
