"""Tests del rediseño pedagógico en estado.py: los momentos del ciclo.

Cada grupo corresponde a un paso. Para trabajar uno a la vez, corre solo sus
tests con -k:

    pytest test_momentos.py -k ejemplo       # paso A: campo "ejemplo" en la tarea
    pytest test_momentos.py -k fallidos      # paso B: intentos que pasan o fallan
    pytest test_momentos.py -k diagnostico   # paso C: encuesta inicial
    pytest test_momentos.py -k revision      # paso D: revisión que escala
    pytest test_momentos.py -k rescate       # paso E: rescate tras 3 fallos
    pytest test_momentos.py -k tabla         # paso F: el diccionario MOMENTOS

Al principio casi todos fallan: es lo esperado.

Se importa el módulo entero (import estado) en vez de los nombres sueltos, para
que la falta de MOMENTOS o FALLOS_PARA_RESCATE haga fallar solo los tests que
los usan, y no el archivo completo.
"""

import json

import pytest

import estado
from estado import SesionTarea


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

def escribir_tarea(ruta, subobjetivos):
    """Escribe un JSON de tarea en la ruta dada."""
    contenido = {"titulo": "Tarea de prueba", "subobjetivos": subobjetivos}
    ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sesion(tmp_path):
    """Una sesión con dos subobjetivos: 'sigmoide' y 'derivada'."""
    ruta = tmp_path / "tarea.json"
    escribir_tarea(ruta, [
        {"id": "sigmoide", "descripcion": "Implementar la función sigmoide"},
        {"id": "derivada", "descripcion": "Implementar la derivada de la sigmoide"},
    ])
    return SesionTarea(str(ruta))


def con_fallos(sesion, subobjetivo_id, cantidad):
    """Registra `cantidad` intentos con tests fallidos y devuelve la sesión."""
    for i in range(cantidad):
        sesion.registrar_intento(subobjetivo_id, f"intento {i}", "1 failed", paso=False)
    return sesion


def guardar_y_leer(sesion, tmp_path):
    """Guarda la sesión y devuelve el JSON leído como diccionario."""
    ruta = tmp_path / "estado.json"
    sesion.guardar(str(ruta))
    return json.loads(ruta.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Paso A: campo "ejemplo" (la implementación oficial viene en la tarea)
# ---------------------------------------------------------------------------

def test_ejemplo_ausente_deja_none(sesion):
    assert sesion.subobjetivos["sigmoide"].ejemplo is None


def test_ejemplo_ruta_relativa_desde_la_carpeta_del_json(tmp_path, monkeypatch):
    carpeta = tmp_path / "tarea"
    carpeta.mkdir()
    escribir_tarea(carpeta / "tarea.json", [
        {"id": "lstm", "descripcion": "Celda LSTM", "ejemplo": "referencia/lstm.py"},
    ])
    # Desde otra carpeta, para comprobar que no se resuelve desde el cwd.
    monkeypatch.chdir(tmp_path)
    s = SesionTarea(str(carpeta / "tarea.json"))
    assert s.subobjetivos["lstm"].ejemplo == str((carpeta / "referencia" / "lstm.py").resolve())


def test_ejemplo_ruta_absoluta_se_respeta(tmp_path):
    absoluta = str((tmp_path / "otra" / "lstm.py").resolve())
    escribir_tarea(tmp_path / "tarea.json", [
        {"id": "lstm", "descripcion": "Celda LSTM", "ejemplo": absoluta},
    ])
    s = SesionTarea(str(tmp_path / "tarea.json"))
    assert s.subobjetivos["lstm"].ejemplo == absoluta


# ---------------------------------------------------------------------------
# Paso B: intentos que pasan o fallan
# ---------------------------------------------------------------------------

def test_fallidos_intento_sin_paso_deja_none(sesion):
    intento = sesion.registrar_intento("sigmoide", "codigo")
    assert intento.paso is None


def test_fallidos_registrar_intento_guarda_paso(sesion):
    a = sesion.registrar_intento("sigmoide", "codigo", "1 failed", paso=False)
    b = sesion.registrar_intento("sigmoide", "codigo", "3 passed", paso=True)
    assert a.paso is False
    assert b.paso is True


def test_fallidos_subobjetivo_nuevo_tiene_cero(sesion):
    assert sesion.subobjetivos["sigmoide"].intentos_fallidos() == 0


def test_fallidos_cuenta_solo_los_que_fallaron(sesion):
    sesion.registrar_intento("sigmoide", "a", "1 failed", paso=False)
    sesion.registrar_intento("sigmoide", "b")                       # sin tests: no cuenta
    sesion.registrar_intento("sigmoide", "c", "3 passed", paso=True)  # aprobado: no cuenta
    sesion.registrar_intento("sigmoide", "d", "2 failed", paso=False)
    assert sesion.subobjetivos["sigmoide"].intentos_fallidos() == 2


def test_fallidos_son_de_cada_subobjetivo(sesion):
    con_fallos(sesion, "sigmoide", 2)
    assert sesion.subobjetivos["derivada"].intentos_fallidos() == 0


def test_fallidos_paso_se_guarda_en_disco(sesion, tmp_path):
    sesion.registrar_intento("sigmoide", "a", "1 failed", paso=False)
    datos = guardar_y_leer(sesion, tmp_path)
    assert datos["subobjetivos"]["sigmoide"]["intentos"][0]["paso"] is False


# ---------------------------------------------------------------------------
# Paso C: diagnóstico (encuesta inicial)
# ---------------------------------------------------------------------------

def test_diagnostico_subobjetivo_nuevo_sin_responder(sesion):
    sub = sesion.subobjetivos["sigmoide"]
    assert sub.maneja_teoria is None
    assert sub.maneja_codigo is None


def test_diagnostico_se_registra(sesion):
    sesion.registrar_diagnostico("sigmoide", maneja_teoria=True, maneja_codigo=False)
    sub = sesion.subobjetivos["sigmoide"]
    assert sub.maneja_teoria is True
    assert sub.maneja_codigo is False


def test_diagnostico_no_afecta_a_otro_subobjetivo(sesion):
    sesion.registrar_diagnostico("sigmoide", maneja_teoria=True, maneja_codigo=True)
    assert sesion.subobjetivos["derivada"].maneja_teoria is None


def test_diagnostico_id_inexistente_lanza_keyerror(sesion):
    with pytest.raises(KeyError):
        sesion.registrar_diagnostico("no_existe", maneja_teoria=True, maneja_codigo=True)


def test_diagnostico_sin_responder_el_momento_es_diagnostico(sesion):
    assert sesion.momento_inicial("sigmoide") == "diagnostico"


@pytest.mark.parametrize("teoria, codigo, esperado", [
    (False, False, "teoria"),
    (False, True, "teoria"),        # sin teoría, se parte por la teoría
    (True, False, "ejemplo"),
    (True, True, "duda_especifica"),
])
def test_diagnostico_decide_el_momento_inicial(sesion, teoria, codigo, esperado):
    sesion.registrar_diagnostico("sigmoide", maneja_teoria=teoria, maneja_codigo=codigo)
    assert sesion.momento_inicial("sigmoide") == esperado


def test_diagnostico_momento_inicial_id_inexistente_lanza_keyerror(sesion):
    with pytest.raises(KeyError):
        sesion.momento_inicial("no_existe")


def test_diagnostico_se_guarda_en_disco(sesion, tmp_path):
    sesion.registrar_diagnostico("sigmoide", maneja_teoria=True, maneja_codigo=False)
    datos = guardar_y_leer(sesion, tmp_path)
    assert datos["subobjetivos"]["sigmoide"]["maneja_teoria"] is True
    assert datos["subobjetivos"]["sigmoide"]["maneja_codigo"] is False


# ---------------------------------------------------------------------------
# Paso D: revisión que escala con los intentos fallidos
# ---------------------------------------------------------------------------

def test_revision_constante_de_rescate_es_3():
    assert estado.FALLOS_PARA_RESCATE == 3


def test_revision_sin_fallos_es_none(sesion):
    assert sesion.momento_revision("sigmoide") is None


@pytest.mark.parametrize("cantidad, esperado", [
    (1, "revision_conceptual"),
    (2, "revision_explicita"),
    (3, "rescate"),
    (5, "rescate"),
])
def test_revision_escala_con_los_fallos(sesion, cantidad, esperado):
    con_fallos(sesion, "sigmoide", cantidad)
    assert sesion.momento_revision("sigmoide") == esperado


def test_revision_usa_la_constante(sesion, monkeypatch):
    monkeypatch.setattr(estado, "FALLOS_PARA_RESCATE", 4)
    con_fallos(sesion, "sigmoide", 3)
    assert sesion.momento_revision("sigmoide") == "revision_explicita"
    con_fallos(sesion, "sigmoide", 1)
    assert sesion.momento_revision("sigmoide") == "rescate"


def test_revision_intentos_sin_fallar_no_suben_el_nivel(sesion):
    sesion.registrar_intento("sigmoide", "a")
    sesion.registrar_intento("sigmoide", "b", "3 passed", paso=True)
    assert sesion.momento_revision("sigmoide") is None


def test_revision_completado_es_none(sesion):
    con_fallos(sesion, "sigmoide", 2)
    sesion.marcar_completado("sigmoide")
    assert sesion.momento_revision("sigmoide") is None


def test_revision_es_de_cada_subobjetivo(sesion):
    con_fallos(sesion, "sigmoide", 3)
    assert sesion.momento_revision("derivada") is None


def test_revision_id_inexistente_lanza_keyerror(sesion):
    with pytest.raises(KeyError):
        sesion.momento_revision("no_existe")


# ---------------------------------------------------------------------------
# Paso E: rescate (entregar el código tras 3 fallos)
# ---------------------------------------------------------------------------

def test_rescate_subobjetivo_nuevo_no_rescatado(sesion):
    assert sesion.subobjetivos["sigmoide"].rescatado is False


def test_rescate_sin_fallos_suficientes_no_se_permite(sesion):
    con_fallos(sesion, "sigmoide", 2)
    permitido, motivo = sesion.puede_rescatar("sigmoide")
    assert permitido is False
    assert motivo.strip() != ""


def test_rescate_con_fallos_suficientes_se_permite(sesion):
    con_fallos(sesion, "sigmoide", 3)
    permitido, _ = sesion.puede_rescatar("sigmoide")
    assert permitido is True


def test_rescate_completado_no_se_permite(sesion):
    con_fallos(sesion, "sigmoide", 3)
    sesion.marcar_completado("sigmoide")
    permitido, motivo = sesion.puede_rescatar("sigmoide")
    assert permitido is False
    assert motivo.strip() != ""


def test_rescate_cada_motivo_tiene_su_propio_mensaje(sesion):
    con_fallos(sesion, "sigmoide", 1)
    _, por_pocos_fallos = sesion.puede_rescatar("sigmoide")
    con_fallos(sesion, "derivada", 3)
    sesion.marcar_completado("derivada")
    _, por_completado = sesion.puede_rescatar("derivada")
    assert por_pocos_fallos != por_completado


def test_rescate_puede_rescatar_id_inexistente_lanza_keyerror(sesion):
    with pytest.raises(KeyError):
        sesion.puede_rescatar("no_existe")


def test_rescate_registrar_marca_el_subobjetivo(sesion):
    con_fallos(sesion, "sigmoide", 3)
    sesion.registrar_rescate("sigmoide")
    assert sesion.subobjetivos["sigmoide"].rescatado is True


def test_rescate_no_completa_el_subobjetivo(sesion):
    # Rescatado no es lo mismo que completado: igual tiene que pasar los tests.
    con_fallos(sesion, "sigmoide", 3)
    sesion.registrar_rescate("sigmoide")
    assert sesion.subobjetivos["sigmoide"].completado is False


def test_rescate_no_afecta_a_otro_subobjetivo(sesion):
    con_fallos(sesion, "sigmoide", 3)
    sesion.registrar_rescate("sigmoide")
    assert sesion.subobjetivos["derivada"].rescatado is False


def test_rescate_se_conserva_al_completar(sesion):
    con_fallos(sesion, "sigmoide", 3)
    sesion.registrar_rescate("sigmoide")
    sesion.marcar_completado("sigmoide")
    sub = sesion.subobjetivos["sigmoide"]
    assert sub.completado is True
    assert sub.rescatado is True


def test_rescate_registrar_id_inexistente_lanza_keyerror(sesion):
    with pytest.raises(KeyError):
        sesion.registrar_rescate("no_existe")


def test_rescate_se_guarda_en_disco(sesion, tmp_path):
    con_fallos(sesion, "sigmoide", 3)
    sesion.registrar_rescate("sigmoide")
    datos = guardar_y_leer(sesion, tmp_path)
    assert datos["subobjetivos"]["sigmoide"]["rescatado"] is True


# ---------------------------------------------------------------------------
# Paso F: la tabla de momentos (MOMENTOS)
# ---------------------------------------------------------------------------

TODOS_LOS_MOMENTOS = {
    "diagnostico", "teoria", "ejemplo", "duda_especifica",
    "revision_conceptual", "revision_explicita", "rescate", "resultados",
}


def test_tabla_tiene_todos_los_momentos():
    assert set(estado.MOMENTOS.keys()) == TODOS_LOS_MOMENTOS


@pytest.mark.parametrize("momento", sorted(TODOS_LOS_MOMENTOS))
def test_tabla_cada_momento_tiene_permitido_y_prohibido(momento):
    fila = estado.MOMENTOS[momento]
    assert set(fila.keys()) == {"permitido", "prohibido"}
    assert isinstance(fila["permitido"], str) and fila["permitido"].strip()
    assert isinstance(fila["prohibido"], str) and fila["prohibido"].strip()


def test_tabla_los_momentos_que_devuelve_el_arbitro_existen(sesion):
    devueltos = {sesion.momento_inicial("sigmoide")}
    for teoria in (True, False):
        for codigo in (True, False):
            sesion.registrar_diagnostico("sigmoide", maneja_teoria=teoria, maneja_codigo=codigo)
            devueltos.add(sesion.momento_inicial("sigmoide"))
    for _ in range(3):
        con_fallos(sesion, "derivada", 1)
        devueltos.add(sesion.momento_revision("derivada"))
    assert devueltos <= set(estado.MOMENTOS.keys())
