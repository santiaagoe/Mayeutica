from mcp.server.mcpserver import MCPServer
from estado import SesionTarea, MOMENTOS
from ejecutor import correr_pytest, ResultadoTests

mcp = MCPServer("mayeutica")
sesion: SesionTarea | None = None


# ---------------------------------------------------------------------------
# Funciones auxiliares (no son herramientas MCP)

def formatear_momento(nombre: str) -> str:
    """Arma el texto con las instrucciones de un momento para entregárselo al tutor.

    No es una herramienta MCP: la usan las herramientas para armar su respuesta.
    Formato sugerido (los tests solo exigen que aparezcan el nombre y los dos
    textos, no este formato exacto):

        Momento: <nombre>
        Permitido: <MOMENTOS[nombre]["permitido"]>
        Prohibido: <MOMENTOS[nombre]["prohibido"]>

    Args:
        nombre: Una clave de MOMENTOS (por ejemplo, "teoria").

    Returns:
        El texto con el nombre del momento y sus instrucciones.

    Raises:
        KeyError: Si nombre no es una clave de MOMENTOS. Es un error de
            programación, no del estudiante, así que no se convierte en texto.
    """
    if nombre not in MOMENTOS:
        raise KeyError(f"La clave '{nombre}' no existe en MOMENTOS.")
    permitido = MOMENTOS[nombre]["permitido"]
    prohibido = MOMENTOS[nombre]["prohibido"]
    return f"Momento: {nombre}\nPermitido: {permitido}\nProhibido: {prohibido}"


def instrucciones_revision(subobjetivo_id: str) -> str | None:
    """Devuelve las instrucciones de revisión según los intentos fallidos.

    No es una herramienta MCP. La usan pedir_ayuda y ejecutar_tests, así las
    dos aplican la misma regla y no hay que mantenerla en dos lugares.

    Pasos:
        1. Pide el momento a sesion.momento_revision.
        2. Si es None, devuelve None.
        3. Si es "rescate", lo confirma con sesion.puede_rescatar. Si lo
           autoriza, lo anota con sesion.registrar_rescate y devuelve las
           instrucciones de "rescate". Si no lo autoriza (no debería pasar si
           las dos reglas de estado.py están alineadas), devuelve las de
           "revision_explicita": nunca se entrega código sin autorización.
        4. En cualquier otro caso, devuelve las instrucciones de ese momento.

    Supone que hay sesión cargada y que el id existe: eso lo revisa quien la
    llama.

    Args:
        subobjetivo_id: Id del subobjetivo.

    Returns:
        El texto de formatear_momento para el momento que corresponda, o None
        si no hay nada que revisar (sin fallos o subobjetivo completado).
    """
    momento = sesion.momento_revision(subobjetivo_id)
    if momento is None:
        return None
        
    if momento == "rescate":
        permitido, motivo = sesion.puede_rescatar(subobjetivo_id)
        if permitido:
            sesion.registrar_rescate(subobjetivo_id)
            return formatear_momento("rescate")
        else:
            return formatear_momento("revision_explicita")       
    return formatear_momento(momento)


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
def registrar_diagnostico(subobjetivo_id: str, maneja_teoria: bool,
                          maneja_codigo: bool) -> str:
    """Guarda las respuestas del estudiante a la encuesta inicial de un subobjetivo.

    Úsala después de preguntarle al estudiante si maneja la teoría y si sabe
    implementarlo en código. Confía en lo que responda.
    Si vuelve a responder la encuesta, las respuestas nuevas reemplazan a las
    anteriores.

    Args:
        subobjetivo_id: Id del subobjetivo.
        maneja_teoria: True si el estudiante dice que maneja la teoría.
        maneja_codigo: True si el estudiante dice que sabe implementarlo.

    Returns:
        Las instrucciones del momento por el que empieza el ciclo
        (formatear_momento de sesion.momento_inicial), o un mensaje si no hay
        tarea cargada o el id no existe.
    """
    if (sesion is None):
        return "No hay tarea cargada"
    if (subobjetivo_id not in sesion.subobjetivos):
        return f"No existe el subobjetivo {subobjetivo_id}"
    subobjetivo = sesion.subobjetivos[subobjetivo_id]
    subobjetivo.maneja_teoria = maneja_teoria
    subobjetivo.maneja_codigo = maneja_codigo
    momento_inicial = sesion.momento_inicial(subobjetivo_id)
    instrucciones = formatear_momento(momento_inicial)
    return f"El momento por el que empieza el ciclo es {momento_inicial} y las instrucciones son: {instrucciones}"




@mcp.tool()
def pedir_ayuda(subobjetivo_id: str, sobre_resultados: bool = False) -> str:
    """Dice qué tipo de ayuda puedes darle al estudiante ahora en un subobjetivo.

    Llámala siempre antes de ayudar con un subobjetivo y sigue las instrucciones
    que devuelve (qué está permitido y qué está prohibido). Pon
    sobre_resultados=True solo cuando el estudiante pregunte cómo interpretar lo
    que le dio su código o su modelo (números, gráficos, métricas), no cuando
    pregunte cómo escribirlo.

    Reglas, en este orden:
        1. Sin tarea cargada o id inexistente -> mensaje de error.
        2. sobre_resultados=True -> momento "resultados" (aunque el subobjetivo
           esté completado o tenga fallos).
        3. Subobjetivo completado -> mensaje de que ya está resuelto, sin
           instrucciones de ningún momento.
        4. Si instrucciones_revision devuelve texto (hay fallos) -> ese texto.
        5. Si no -> instrucciones de sesion.momento_inicial.

    No registra intentos: pedir ayuda no cuenta como fallo.

    Args:
        subobjetivo_id: Id del subobjetivo.
        sobre_resultados: True si la pregunta es sobre interpretar resultados.

    Returns:
        Las instrucciones del momento que corresponde, o un mensaje (sin tarea,
        id inexistente o subobjetivo ya completado).
    """
    if sesion is None:
        return "Error: No hay ninguna tarea cargada."    
    if subobjetivo_id not in sesion.subobjetivos:
        return f"Error: No existe el subobjetivo con id '{subobjetivo_id}'."   
    if sobre_resultados:
        return formatear_momento("resultados")
    if sesion.subobjetivos[subobjetivo_id].completado:
        return f"El subobjetivo {subobjetivo_id} ya está completado."  
    revision = instrucciones_revision(subobjetivo_id)
    if revision is not None:
        return revision
    return formatear_momento(sesion.momento_inicial(subobjetivo_id))


@mcp.tool()
def ver_ejemplo(subobjetivo_id: str) -> str:
    """Devuelve la implementación oficial de ejemplo de un subobjetivo.

    Úsala en el momento "ejemplo", para mostrarle al estudiante código
    verificado en vez de escribirlo tú. Si la tarea no trae ejemplo, la
    respuesta lo dice: en ese caso sigue las instrucciones del momento
    "ejemplo" para un ejemplo no oficial.

    Args:
        subobjetivo_id: Id del subobjetivo.

    Returns:
        El contenido del archivo de ejemplo. O un mensaje si no hay tarea
        cargada, el id no existe, el subobjetivo no tiene ejemplo oficial, o el
        archivo de ejemplo no se encuentra.
    """
    if sesion is None:
        return "No hay tarea cargada."
    if subobjetivo_id not in sesion.subobjetivos:
        return f"No existe el subobjetivo {subobjetivo_id}."  
    subobjetivo = sesion.subobjetivos[subobjetivo_id]
    if not subobjetivo.ejemplo:
        return f"El subobjetivo {subobjetivo_id} no tiene un ejemplo oficial."
    try:
        with open(subobjetivo.ejemplo, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"No se encontró el archivo de ejemplo oficial en la ruta indicada: {subobjetivo.ejemplo}"


@mcp.tool()
def marcar_completado(subobjetivo_id: str) -> str:
    """Marca un subobjetivo como completado cuando el estudiante declara que lo resolvió.

    Úsala solo cuando el estudiante diga explícitamente que terminó ese paso.
    Después de esto pedir_ayuda ya no da revisiones para ese subobjetivo.

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
    
        
@mcp.tool()
def ejecutar_tests(subobjetivo_id: str) -> str:
    """Corre los tests de un subobjetivo sobre el código que el estudiante tiene en su archivo.

    Úsala cuando el estudiante diga que quiere probar su código. Lee el archivo
    real del estudiante (no recibe código como texto) y corre sus tests en el
    servidor. Cada ejecución se registra como un intento, con la salida real de
    pytest y si pasó o no (paso=resultado.paso), así los fallos cuentan para la
    revisión y el rescate. Si todos los tests pasan, el subobjetivo queda
    completado.

    Si los tests fallan, la respuesta trae además las instrucciones de
    revisión que corresponden (instrucciones_revision): síguelas para decidir
    qué tan explícito ser, sin llamar a pedir_ayuda.

    Returns:
        Si pasaron o no, y la salida de pytest para que el estudiante vea qué
        falló; si fallaron, también las instrucciones de revisión. O un mensaje
        si no hay tarea cargada, el id no existe, el subobjetivo no tiene
        archivo o tests configurados, o el archivo del estudiante no existe.
    """
    if sesion is None:
        return "No hay tarea cargada"
        
    if subobjetivo_id not in sesion.subobjetivos:
        return f"No existe el subobjetivo: {subobjetivo_id}"
        
    subobjetivo = sesion.subobjetivos[subobjetivo_id]
    
    if not subobjetivo.archivo or not subobjetivo.tests:
        return f"El subobjetivo '{subobjetivo_id}' no tiene archivo o tests configurados."
        
    try:
        with open(subobjetivo.archivo, "r", encoding="utf-8") as f:
            codigo = f.read()
    except FileNotFoundError:
        return f"No se encontró el archivo del estudiante en la ruta esperada: {subobjetivo.archivo}"
        
    resultado = correr_pytest(subobjetivo.tests)
    sesion.registrar_intento(subobjetivo_id, codigo, resultado.salida, paso= resultado.paso)
    if resultado.paso:
        sesion.marcar_completado(subobjetivo_id)
        return (f"Los tests del subobjetivo {subobjetivo_id} fueron aprobados.\n\n"
            f"Salida de pytest:\n\n{resultado.salida}")
    else:
        mensaje_fallo = ( f"Los tests del subobjetivo {subobjetivo_id} fallaron.\n\n"
            f"Salida de pytest:\n\n{resultado.salida}")
        revision = instrucciones_revision(subobjetivo_id)
        if revision:
            mensaje_fallo += f"\n\nInstrucciones de revisión aplicables:\n{revision}"
        return mensaje_fallo    



if __name__ == "__main__":
    mcp.run()