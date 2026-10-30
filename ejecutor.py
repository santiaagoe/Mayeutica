"""Ejecución de los tests de un subobjetivo.

Corre pytest en un proceso aparte y devuelve el resultado. No sabe nada de
sesiones, intentos ni MCP: solo recibe una ruta y entrega qué pasó. Así el
servidor puede comprobar los tests por su cuenta, en vez de creerle al LLM.
"""
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass

TIMEOUT_POR_DEFECTO = 30  # segundos


@dataclass
class ResultadoTests:
    """Lo que pasó al correr los tests.

    Attributes:
        paso: True solo si pytest terminó sin fallos y corrió al menos un test.
        salida: Lo que pytest imprimió (o una explicación si no se pudo correr),
            para mostrárselo al estudiante y guardarlo en el intento.
    """
    paso: bool
    salida: str


def correr_pytest(ruta_tests: str, timeout: float = TIMEOUT_POR_DEFECTO) -> ResultadoTests:
    """Corre pytest sobre un archivo de tests en un proceso aparte.

    El proceso se ejecuta con la carpeta del archivo de tests como directorio
    de trabajo, para que los tests puedan importar el código del estudiante que
    está junto a ellos, sin importar desde dónde se lanzó el servidor.

    Nunca lanza excepciones por problemas del código del estudiante o de los
    tests: cualquier falla se devuelve como ResultadoTests(paso=False, ...).

    Args:
        ruta_tests: Ruta al archivo de tests.
        timeout: Segundos máximos de ejecución. Si se exceden, el proceso se
            detiene y la salida dice que se agotó el tiempo.

    Returns:
        paso es True solo si todos los tests pasaron y se corrió al menos uno.
        Un archivo sin tests, un error de sintaxis, un archivo inexistente o un
        timeout cuentan como paso=False.
    """
    ruta = Path(ruta_tests)
    
    if not ruta.exists():
        return ResultadoTests(False, f"Error: No se encontró el archivo de tests en {ruta_tests}")

    directorio_trabajo = ruta.parent

    try:
        proceso = subprocess.run(
            [sys.executable, "-m", "pytest", ruta.name],
            cwd=directorio_trabajo,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        paso = (proceso.returncode == 0)
        salida = proceso.stdout
        if proceso.stderr:
            salida += f"\nErrores estándar:\n{proceso.stderr}"
            
        return ResultadoTests(paso, salida)
        
    except subprocess.TimeoutExpired:
        return ResultadoTests(
            False, 
            f"Se agotó el tiempo máximo de ejecución ({timeout} segundos). Es posible que el código tenga un ciclo infinito."
        )
    except Exception as e:
        return ResultadoTests(False, f"Error interno al intentar ejecutar pytest: {e}")