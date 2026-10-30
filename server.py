from mcp.server.mcpserver import MCPServer
from estado import SesionTarea

mcp = MCPServer("mayeutica")
sesion: SesionTarea | None = None


@mcp.tool()
def cargar_tarea(ruta: str) -> str:
    """Carga una tarea desde un JSON y empieza una sesión nueva.

    Args:
        ruta: Ruta al JSON de la tarea.

    Returns:
        Los subobjetivos (id y descripción) para que el tutor arme la encuesta,
        o un mensaje claro si el archivo no existe o tiene ids repetidos.
    """
    global sesion 
    try:
        #haciendo esto protegemos la sesión anterior
        nueva_sesion = SesionTarea(ruta)
    except (FileNotFoundError, ValueError) as e:
        return f"Error al cargar la tarea: {e}"    
   
    sesion = nueva_sesion
    resultado = "Subobjetivos de la tarea:\n"
    for id_sub, subobjetivo in sesion.subobjetivos.items():
        resultado += f"- {id_sub}: {subobjetivo.descripcion}\n"
        
    return resultado

@mcp.tool()
def registrar_intento(subobjetivo_id: str, codigo: str,
                      resultado_tests: str | None = None) -> str:
    """Registra un intento del estudiante en un subobjetivo.

    Returns:
        Confirmación con la cantidad de intentos de ese subobjetivo, o un
        mensaje si no hay tarea cargada o el id no existe.
    """
    if (sesion is None):
        return "No hay tarea cargada"
    else:
        if (subobjetivo_id not in sesion.subobjetivos):
            return f"No existe el subobjetivo {subobjetivo_id}"
        else:
            sesion.registrar_intento(subobjetivo_id,codigo, resultado_tests)
            intentos = len(sesion.subobjetivos[subobjetivo_id].intentos)
            return f"Intento registrado correctamente. El subobjetivo {subobjetivo_id} tiene {intentos} intentos"

@mcp.tool()
def pedir_pista(subobjetivo_id: str, nivel: int) -> str:
    """Pide una pista de cierto nivel. El árbitro decide si está permitida.

    Returns:
        Si se permite: el nivel autorizado y qué tipo de ayuda corresponde.
        Si no: el motivo que entrega puede_pedir_pista.
    """
    if (sesion is None):
        return "No hay tarea cargada"
    if (subobjetivo_id not in sesion.subobjetivos):
        return f"No existe el subobjetivo: {subobjetivo_id}"
    permitido , motivo = sesion.puede_pedir_pista(subobjetivo_id, nivel)
    if permitido:
        sesion.registrar_pista_entregada(subobjetivo_id, nivel)
        return f"El nivel autorizado es {nivel} y es ayuda para {subobjetivo_id}"
    else:
        return motivo        


@mcp.tool()
def marcar_completado(subobjetivo_id: str) -> str:
    """Marca un subobjetivo como completado cuando el estudiante declara que lo resolvió.

    Úsala solo cuando el estudiante diga explícitamente que terminó ese paso.
    Después de esto no se entregan más pistas para ese subobjetivo.

    Returns:
        Confirmación de que quedó completado, un aviso si ya lo estaba, o un
        mensaje si no hay tarea cargada o el id no existe.
    """
    if (sesion is None):
        return "No hay tarea cargada"
    if (subobjetivo_id not in sesion.subobjetivos ):
        return f"No existe subobjetivo con el id: {subobjetivo_id}"
    subobjetivo = sesion.subobjetivos[subobjetivo_id]
    if (subobjetivo.completado == False):
        sesion.marcar_completado(subobjetivo_id)
        return f"Se marcó como completado el subobjetivo {subobjetivo_id}"
    else:
        return f"El subobjetivo {subobjetivo_id} ya estaba completado"
    
        
if __name__ == "__main__":
    mcp.run()