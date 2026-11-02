"""Tests de entorno.py.

Una función a la vez:

    pytest test_entorno.py -k normalizar
    pytest test_entorno.py -k coincide

Ojo con -k: filtra por subcadena del nombre. Todos los tests de la segunda
función llevan "coincide" y ninguno de la primera lo lleva, para que no se
mezclen.
"""

import pytest

from entorno import normalizar, subobjetivo_coincidente
from estado import Subobjetivo


# ---------------------------------------------------------------------------
# normalizar
# ---------------------------------------------------------------------------

def test_normalizar_devuelve_un_conjunto():
    assert isinstance(normalizar("hola mundo"), set)


def test_normalizar_texto_vacio():
    assert normalizar("") == set()


def test_normalizar_minusculas():
    assert normalizar("SIGMOIDE") == {"sigmoide"}


def test_normalizar_quita_tildes():
    assert normalizar("Sigmóide derivación") == {"sigmoide", "derivacion"}


def test_normalizar_quita_signos():
    assert normalizar("¿Cómo instalo NumPy?") == {"instalo", "numpy"}


def test_normalizar_el_guion_bajo_separa():
    assert normalizar("derivada_sigmoide") == {"derivada", "sigmoide"}


def test_normalizar_descarta_palabras_cortas():
    assert normalizar("la a el de") == set()


def test_normalizar_descarta_palabras_vacias():
    assert normalizar("implementar la función") == set()


def test_normalizar_conserva_digitos():
    assert "python3" in normalizar("Instalar python3")


# ---------------------------------------------------------------------------
# subobjetivo_coincidente
# ---------------------------------------------------------------------------

@pytest.fixture
def subobjetivos():
    return [
        Subobjetivo(id="sigmoide", descripcion="Implementar la función sigmoide",
                    funcion="sigmoide"),
        Subobjetivo(id="forward",
                    descripcion="Calcular la salida de la neurona",
                    funcion="forward_pass"),
        Subobjetivo(id="perdida",
                    descripcion="Calcular la entropía cruzada entre predicción y etiquetas"),
        Subobjetivo(id="carga", descripcion="Cargar y normalizar los datos"),
    ]


def test_coincide_por_id(subobjetivos):
    assert subobjetivo_coincidente("¿Cómo derivo la sigmoide?", subobjetivos) == "sigmoide"


def test_coincide_por_funcion(subobjetivos):
    """El id es 'forward' y la función 'forward_pass': 'pass' solo está en la función."""
    assert subobjetivo_coincidente("no entiendo el pass", subobjetivos) == "forward"


def test_coincide_ignora_mayusculas_y_tildes(subobjetivos):
    assert subobjetivo_coincidente("SIGMÓIDE", subobjetivos) == "sigmoide"


def test_coincide_por_descripcion_con_dos_palabras(subobjetivos):
    pregunta = "¿cómo se calcula la entropía cruzada?"
    assert subobjetivo_coincidente(pregunta, subobjetivos) == "perdida"


def test_coincide_no_con_una_sola_palabra_de_la_descripcion(subobjetivos):
    assert subobjetivo_coincidente("¿cómo grafico la entropía?", subobjetivos) is None


def test_coincide_gana_el_primero_de_la_lista(subobjetivos):
    pregunta = "uso la sigmoide en el forward"
    assert subobjetivo_coincidente(pregunta, subobjetivos) == "sigmoide"


def test_coincide_sin_subobjetivos():
    assert subobjetivo_coincidente("¿cómo activo el entorno virtual?", []) is None


def test_coincide_funcion_ausente_no_rompe():
    solo_id = [Subobjetivo(id="carga", descripcion="Cargar los datos")]
    assert subobjetivo_coincidente("hola", solo_id) is None


@pytest.mark.parametrize("pregunta", [
    "¿Cómo activo el entorno virtual?",
    "¿Qué significa este error de zsh?",
    "¿Cómo deshago el último commit?",
    "¿Cómo elijo el intérprete de Python en VS Code?",
    "¿Cómo leo un CSV con pandas?",
    "¿Cómo instalo numpy?",
])
def test_coincide_no_con_preguntas_de_entorno(subobjetivos, pregunta):
    assert subobjetivo_coincidente(pregunta, subobjetivos) is None


@pytest.mark.xfail(reason="Sin raíz de palabras: 'normalizo' no coincide con 'normalizar'. "
                          "Debería pasar el día que se compare por raíz.")
def test_coincide_limitacion_conocida_sin_raiz(subobjetivos):
    assert subobjetivo_coincidente("¿cómo normalizo los datos?", subobjetivos) == "carga"
