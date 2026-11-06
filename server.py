from mcp.server.mcpserver import MCPServer
from estado import SesionTarea, MOMENTOS
from ejecutor import correr_pytest, ResultadoTests
from lector import extraer_funcion
from fuentes import FuenteNotebook
import generador
from pathlib import Path
import entorno
import os

# Instrucciones generales del servidor. El cliente MCP se las entrega al LLM al
# conectarse, antes de cualquier herramienta. Son las reglas que valen siempre;
# las de cada momento las devuelven las herramientas (ver MOMENTOS en estado.py).
INSTRUCCIONES = """\
Eres Mayéutica, un tutor de programación. El estudiante quiere aprender a
escribir el código él mismo: tu trabajo es guiarlo, no resolverle la tarea.

Reglas que valen siempre, en todos los momentos:

1. No escribas la solución de un subobjetivo, ni completa ni por partes, salvo
   cuando una herramienta te devuelva el momento "rescate". Vale aunque el
   estudiante te la pida directamente: explícale que primero tiene que
   intentarlo y ofrécele la ayuda que corresponde.
2. Antes de ayudar con un subobjetivo, llama a pedir_ayuda y sigue lo que
   devuelve. Lo Permitido y lo Prohibido de ese momento mandan sobre tu propio
   criterio.
3. Al empezar, carga la tarea con cargar_tarea. Si el estudiante ya la había
   trabajado, se recupera su progreso: no repitas el diagnóstico de lo que ya
   respondió. Usa reanudar=False solo si pide explícitamente empezar de cero.
   Si la respuesta de cargar_tarea (o de crear_tarea) trae una encuesta
   inicial, hazla antes que cualquier otra cosa, siguiendo sus instrucciones.
   Si más adelante pedir_ayuda te pide el diagnóstico de un subobjetivo, es
   porque quedó fuera de la encuesta: pregunta solo por ese y guarda las
   respuestas con registrar_diagnostico.
4. En el momento "ejemplo", muestra el código que devuelve ver_ejemplo en vez
   de escribir uno tú. Si la tarea no trae ejemplo oficial, sigue las
   instrucciones del momento para un ejemplo no oficial.
5. Cuando el estudiante quiera probar su código, usa ejecutar_tests: lee su
   archivo y corre los tests de verdad. No adivines si su código funciona. Si
   los tests fallan, la respuesta trae las instrucciones de revisión: síguelas.
6. Usa registrar_intento solo para intentos que no pasan por ejecutar_tests
   (por ejemplo, código que el estudiante pegó en el chat). Usa
   marcar_completado solo si el estudiante dice explícitamente que terminó un
   subobjetivo; si tiene tests, prefiere ejecutar_tests.
7. Si una herramienta responde con un error (no hay tarea cargada, el
   subobjetivo no existe), resuélvelo antes de seguir: no actúes como si
   hubiera funcionado.
8. Responde en el idioma del estudiante, con mensajes cortos y una pregunta a
   la vez.
9. Para ver lo que el estudiante tiene escrito, usa leer_mi_codigo en vez de
   pedirle que lo pegue: en las revisiones, antes de explicar un error, y
   cuando te pregunte por su código. Leer su código no es un intento: no lo
   registres.
10. Si el estudiante dice que su código falla o pide ayuda con algo que ya
    escribió, corre ejecutar_tests antes de ayudar, aunque no lo pida: así el
    fallo queda registrado y la respuesta trae el momento de revisión que
    corresponde. Sin un fallo registrado no estás en revisión: aunque veas el
    error con leer_mi_codigo, no señales la línea ni compares su código con
    el ejemplo; sigue lo que devuelve pedir_ayuda.
11. Si el estudiante tiene una duda sobre sus herramientas (terminal, git y
    GitHub, VS Code, el entorno de Python, cargar datos) y no sobre cómo
    programar un subobjetivo, usa ayuda_entorno. No respondas esas preguntas de
    memoria: la herramienta comprueba que no sea una pregunta de la tarea
    disfrazada y te dice cómo responder.
12. Si el estudiante te da un notebook (.ipynb) en vez de una tarea JSON,
    léelo con leer_fuente y propón subobjetivos pequeños: uno por cada bloque
    por completar, con los ids de sus celdas. Si una pregunta y la celda donde
    se responde están separadas, júntalas en un solo subobjetivo con las dos
    celdas. Muéstrale la lista y espera a que la confirme o la corrija; recién
    entonces llama a crear_tarea. No propongas tests ni ejemplos. Si
    crear_tarea dice que la tarea de ese notebook ya existe, cárgala con
    cargar_tarea en vez de crearla de nuevo.
13. En un subobjetivo que viene de un notebook, leer_mi_codigo y
    ejecutar_tests todavía no sirven: usa leer_fuente para ver lo que el
    estudiante escribió. Las respuestas escritas (texto_por_completar) no
    tienen tests: guarda cada respuesta con registrar_intento y usa
    marcar_completado cuando el estudiante diga que terminó.
"""

# Cómo responder una pregunta de entorno. ayuda_entorno lo devuelve cuando la
# pregunta no coincide con ningún subobjetivo de la tarea.
INSTRUCCIONES_ENTORNO = """\
Esta pregunta es sobre las herramientas, no sobre lo que evalúa la tarea:
respóndela directo, sin pedir intentos previos y sin usar los momentos del
ciclo.

- Ve paso a paso: da los comandos de a uno y espera a que el estudiante cuente
  qué le salió antes de dar el siguiente.
- Di siempre qué debería aparecer si el comando funciona.
- Si no sabes su sistema operativo o su terminal, pregúntaselo antes de dar
  comandos.
- Si en medio de la respuesta aparece algo que sí es parte de un subobjetivo
  (por ejemplo, cómo normalizar los datos), no lo resuelvas: vuelve a
  pedir_ayuda.
"""

# La encuesta inicial (el paso 3 del plan: "encuesta de dos columnas"). Va al
# final de la respuesta de cargar_tarea si quedan subobjetivos sin diagnóstico
# (ver instrucciones_encuesta). Las dos columnas son las dos preguntas del
# diagnóstico; el momento "diagnostico" queda como respaldo para los que se
# salten la encuesta.
INSTRUCCIONES_ENCUESTA = """\
Encuesta inicial. Antes de empezar con cualquier subobjetivo, muéstrale al
estudiante una tabla con una fila por cada subobjetivo de la lista de abajo y
dos columnas: "¿Lo entiendes?" (la teoría) y "¿Sabes programarlo?" (el
código). Pídele que la responda entera de una vez, con sí o no en cada
casilla. Confía en lo que responda y llama a registrar_diagnostico una vez
por fila. Recién después, elige con él por dónde empezar y llama a
pedir_ayuda para ese subobjetivo.

No expliques teoría, no muestres código y no le tomes una prueba antes de
tener la tabla: la encuesta tiene que ser rápida. Si un subobjetivo es una
pregunta escrita (sin código), la segunda columna se refiere a si sabe
redactar la respuesta.
"""

mcp = MCPServer("mayeutica", instructions=INSTRUCCIONES)
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
            guardar_sesion()
            return formatear_momento("rescate")
        else:
            return formatear_momento("revision_explicita")       
    return formatear_momento(momento)


def instrucciones_encuesta() -> str | None:
    """Devuelve el bloque de la encuesta inicial, o None si no hace falta.

    No es una herramienta MCP. La usa cargar_tarea al final de su respuesta
    (y así también crear_tarea, que llama a cargar_tarea).

    Pasos:
        1. Si no hay sesión, devuelve None.
        2. Pide los ids con sesion.pendientes_de_encuesta(). Si no hay
           ninguno, devuelve None: la encuesta no se repite al retomar.
        3. Si hay, devuelve INSTRUCCIONES_ENCUESTA seguido de una línea con
           los ids pendientes separados por coma. Formato sugerido:

               <INSTRUCCIONES_ENCUESTA>
               Subobjetivos de la encuesta: sigmoide, derivada

           Solo los ids, sin descripción ni ":" (las descripciones ya están
           en la lista de cargar_tarea, y test_cargar_un_subobjetivo_por_linea
           cuenta las líneas con "id:").

    Returns:
        El texto de la encuesta, o None.
    """
    if(sesion is None):
        return None
    ids = sesion.pendientes_de_encuesta()
    if (ids == []): #vacio
        return None
    else:
        return f"{INSTRUCCIONES_ENCUESTA}\nSubobjetivos de la encuesta: {",".join(ids)}"


def ruta_estado(ruta_tarea: str) -> str:
    """Devuelve la ruta del archivo de estado de una tarea.

    Queda junto al JSON de la tarea: '/a/b/tarea.json' -> '/a/b/tarea.estado.json'.
    """
    rt = Path(ruta_tarea)
    nuevo_rt = rt.with_suffix(".estado.json")
    return str(nuevo_rt)
    

def guardar_sesion() -> None:
    """Guarda la sesión activa en su archivo de estado.

    Si no hay tarea cargada, no hace nada. La llaman las herramientas que
    cambian la sesión, después del cambio y solo si el cambio ocurrió.
    """
    if (sesion is None):
        return None
    ruta = ruta_estado(sesion.ruta_tarea)
    if sesion:
        sesion.guardar(ruta) #guarda lo q actualizamos
        return None



@mcp.tool()
def cargar_tarea(ruta: str, reanudar: bool = True) -> str:
    """Carga una tarea desde un JSON y recupera el progreso guardado, si lo hay.

    Si existe el archivo de estado de la tarea (ver ruta_estado) y reanudar
    es True, el estudiante sigue donde quedó: intentos, diagnóstico,
    completados y rescates. Usa reanudar=False solo si el estudiante pide
    explícitamente empezar de cero.

    Comportamiento:
        - reanudar=True, sin archivo de estado: sesión nueva. No guarda nada.
        - reanudar=True, con estado válido: recupera el progreso
          (SesionTarea.cargar_estado). No guarda nada.
        - reanudar=True, con estado dañado: sesión nueva, avisando que no se
          pudo leer el progreso. No guarda (el archivo dañado queda hasta el
          primer cambio, por si alguien quiere revisarlo).
        - reanudar=False: sesión nueva y la guarda de inmediato, para que el
          progreso viejo no vuelva en la próxima carga.

    Args:
        ruta: Ruta al JSON de la tarea.
        reanudar: Si es True (por defecto), recupera el progreso guardado.

    Returns:
        Los subobjetivos (id y descripción); los completados se marcan con
        "(completado)" en su línea. Al final, si quedan subobjetivos sin
        diagnóstico, el bloque de instrucciones_encuesta (separado de la lista
        por una línea en blanco). Además, si
        corresponde: que se recuperó el progreso, que no se pudo leer (y se
        empieza de cero), o qué ids del estado se ignoraron porque ya no están
        en la tarea. O un mensaje claro si el archivo de la tarea no existe o
        tiene ids repetidos.
    """
    global sesion 
    try:
        #haciendo esto protegemos la sesión anterior
        ruta_sesion = os.path.expanduser(ruta.strip()) ## Pa encontrar -/tarea.json/n
        nueva_sesion = SesionTarea(ruta_sesion)
    except (FileNotFoundError, ValueError) as e:
        return f"Error al cargar la tarea: {e}"    
    aviso = ""
    try:
        existe_rutaEstado = os.path.exists(ruta_estado(nueva_sesion.ruta_tarea))
        rutaeEstado = ruta_estado(nueva_sesion.ruta_tarea)
        if (reanudar == True and existe_rutaEstado == True):
            ids_ignorados = nueva_sesion.cargar_estado(rutaeEstado) #no guarda nada
            aviso = "Se recuperó el progreso guardado.\n"
            if (len(ids_ignorados) > 0):
                aviso += f"Se ignoraron porque ya no están en la tarea {", ".join(ids_ignorados)}.\n"
    except (ValueError) as x:
        aviso =  "No se pudo leer el progreso guardado; se empieza de cero.\n"
    sesion = nueva_sesion
    if (reanudar == False):
            guardar_sesion() #sesióm mueva y se guarda de inmediato
    resultado = "Subobjetivos de la tarea:\n"
    for id_sub, subobjetivo in sesion.subobjetivos.items():
        marca = ""
        if (subobjetivo.completado):
            marca = "(completado)"
        resultado += f"- {id_sub}: {subobjetivo.descripcion} {marca} \n"
    instrucciones = instrucciones_encuesta()
    if (instrucciones is not None):
        resultado += instrucciones    
    return aviso + resultado

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
            guardar_sesion()
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
    if sesion is None:
        return "No hay tarea cargada"
    if subobjetivo_id not in sesion.subobjetivos:
        return f"No existe el subobjetivo {subobjetivo_id}"
    sesion.registrar_diagnostico(subobjetivo_id, maneja_teoria, maneja_codigo)
    momento_inicial = sesion.momento_inicial(subobjetivo_id)
    instrucciones = formatear_momento(momento_inicial)
    guardar_sesion()
    return f"El momento por el que empieza el ciclo es {momento_inicial} y las instrucciones son:\n{instrucciones}"


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
def leer_mi_codigo(subobjetivo_id: str) -> str:
    """Muestra el código que el estudiante tiene escrito para un subobjetivo.

    Úsala para ver su código real antes de revisarlo o de responder una
    pregunta sobre él, en vez de pedirle que lo pegue. Lee el archivo cada vez
    que se llama, así que siempre trae la versión guardada más reciente. No
    registra un intento ni cambia el estado de la sesión.

    Si la tarea indica la función del subobjetivo ("funcion" en el JSON),
    devuelve solo esa función, con extraer_funcion de lector.py, y dice de qué
    archivo viene. Devuelve el archivo completo, explicando por qué, cuando:
        - el subobjetivo no tiene "funcion",
        - la función no está en el archivo (quizá le cambió el nombre), o
        - el archivo tiene un error de sintaxis (SyntaxError), y por eso no se
          puede buscar la función. En este caso la respuesta lo dice, porque
          ese error es lo primero que hay que revisar.

    Args:
        subobjetivo_id: Id del subobjetivo.

    Returns:
        El código, con la ruta del archivo. O un mensaje si no hay tarea
        cargada, el id no existe, el subobjetivo no tiene archivo configurado,
        o el archivo no se encuentra.
    """
    if sesion is None:
        return "No hay tarea cargada."
    if subobjetivo_id not in sesion.subobjetivos:
        return f"No existe el subobjetivo {subobjetivo_id}." 
    subobjetivo = sesion.subobjetivos[subobjetivo_id]
    if not subobjetivo.archivo:
        return f"El subobjetivo {subobjetivo_id} no tiene un archivo configurado."
    try:
        with open(subobjetivo.archivo, "r", encoding="utf-8") as f:
            texto_archivo = f.read()
    except FileNotFoundError:
        return f"No se encontró el archivo en la ruta indicada: {subobjetivo.archivo}"
    if not subobjetivo.funcion:
        return f"El subobjetivo no especifica una función. Archivo completo de {subobjetivo.archivo}:\n\n{texto_archivo}"
    try:
        codigo_funcion = extraer_funcion(texto_archivo, subobjetivo.funcion)
        if codigo_funcion is None:
            return f"No se encontró la función '{subobjetivo.funcion}' en el archivo. Archivo completo de {subobjetivo.archivo}:\n\n{texto_archivo}"
        else:
            return f"Función '{subobjetivo.funcion}' del archivo {subobjetivo.archivo}:\n\n{codigo_funcion}"
    except SyntaxError:
        return f"El archivo {subobjetivo.archivo} tiene un error de sintaxis y no se pudo buscar la función. Archivo completo:\n\n{texto_archivo}"


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
        guardar_sesion()
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
        guardar_sesion()
        return (f"Los tests del subobjetivo {subobjetivo_id} fueron aprobados.\n\n"
            f"Salida de pytest:\n\n{resultado.salida}")
    else:
        mensaje_fallo = ( f"Los tests del subobjetivo {subobjetivo_id} fallaron.\n\n"
            f"Salida de pytest:\n\n{resultado.salida}")
        revision = instrucciones_revision(subobjetivo_id)
        if revision:
            mensaje_fallo += f"\n\nInstrucciones de revisión aplicables:\n{revision}"
        guardar_sesion()    
        return mensaje_fallo    



@mcp.tool()
def leer_fuente(ruta: str) -> str:
    """Muestra el contenido de un notebook (.ipynb) como bloques, para partirlo en subobjetivos.

    Úsala cuando el estudiante te dé un notebook en vez de una tarea JSON, y
    después para ver lo que escribió en un subobjetivo que viene de un
    notebook. Lee el archivo cada vez que se llama (trae la versión guardada
    más reciente) y no cambia la sesión: no carga ni crea ninguna tarea.

    Cada bloque viene con su tipo y su ubicación (el id de la celda). Los
    tipos son: "texto" (enunciado), "codigo" (código ya dado),
    "codigo_por_completar" (donde el estudiante programa) y
    "texto_por_completar" (donde escribe una respuesta). Los ids son los que
    van en "celdas" al llamar a crear_tarea; un bloque "sin ubicación" no se
    puede usar ahí.

    Comportamiento:
        - Limpia la ruta como cargar_tarea (espacios alrededor y "~").
        - Solo acepta .ipynb; con otra extensión responde qué formatos hay.
        - Lee con FuenteNotebook y arma el texto con
          generador.formatear_bloques, precedido de la ruta del notebook.

    Args:
        ruta: Ruta al notebook.

    Returns:
        Los bloques del notebook, en orden. O un mensaje si la extensión no
        es .ipynb, el archivo no existe o no es un notebook válido.
    """
    ruta_limpia = os.path.expanduser(ruta.strip())
    if (not ruta_limpia.endswith(".ipynb")):
        return "Solo se aceptan archivos .ipynb"
    fuente = FuenteNotebook(ruta_limpia)
    try:
        bloques = fuente.leer()
    except (FileNotFoundError) as e:
        return f"El archivo no existe: {e}"
    except (ValueError) as e:
        return f"El archivo no es un notebook válido: {e}"
    texto_formateado = generador.formatear_bloques(bloques)
    devolver = "Ruta: " + ruta_limpia + "\n\n" + texto_formateado
    return devolver


@mcp.tool()
def crear_tarea(ruta: str, subobjetivos: list[dict],
                reemplazar: bool = False) -> str:
    """Crea la tarea de un notebook con los subobjetivos confirmados y la carga.

    Llámala solo después de mostrarle al estudiante la lista de subobjetivos
    y que la confirme. Cada subobjetivo es un diccionario con:
        - "id": nombre corto, único, sin espacios (por ejemplo, "pregunta_1").
        - "descripcion": qué tiene que lograr el estudiante en ese paso.
        - "celdas" (opcional): lista con los ids de celda (de leer_fuente)
          donde el estudiante escribe ese paso.
    No se aceptan otras claves: ni "tests" ni "ejemplo".

    Pasos:
        1. Limpia la ruta (como cargar_tarea) y exige .ipynb.
        2. Lee el notebook con FuenteNotebook. Las ubicaciones válidas son
           las de sus bloques (sin los None).
        3. generador.validar_subobjetivos. Si hay problemas, responde con
           todos y no escribe nada.
        4. Si el JSON (generador.ruta_tarea_generada) ya existe y reemplazar
           es False, responde que ya existe, con su ruta, y no escribe nada:
           así no se pierde una tarea que el estudiante ya está trabajando.
        5. generador.escribir_tarea y después cargar_tarea con ese JSON
           (reanudar=True: si se reemplazó una tarea con progreso, los
           subobjetivos que siguen existiendo lo conservan).

    Si algo falla, la sesión anterior queda como estaba.

    Args:
        ruta: Ruta al notebook.
        subobjetivos: La lista confirmada por el estudiante.
        reemplazar: True solo si el estudiante pide rehacer los subobjetivos
            de un notebook que ya tenía tarea.

    Returns:
        La ruta del JSON creado y la respuesta de cargar_tarea (los
        subobjetivos). O un mensaje con lo que hay que corregir.
    """
    ruta_limpia = os.path.expanduser(ruta.strip())
    if (not ruta_limpia.endswith(".ipynb")):
        return "Solo se aceptan archivos .ipynb"
    fuente = FuenteNotebook(ruta_limpia)
    try:
        bloques = fuente.leer()
    except (FileNotFoundError) as e:
        return f"El archivo no existe: {e}"
    except (ValueError) as e:
        return f"El archivo no es un notebook válido: {e}"
    ubicaciones_validas = set()
    for bloque in bloques:
        if (bloque.ubicacion is not None):
            ubicaciones_validas.add(bloque.ubicacion)
    problemas = generador.validar_subobjetivos(subobjetivos, ubicaciones_validas)
    if (len(problemas) > 0):
        mensaje_problemas = "\n".join(problemas)
        return "Hay problemas con los subobjetivos:\n" + mensaje_problemas
    ruta_json = generador.ruta_tarea_generada(ruta_limpia)
    if (os.path.exists(ruta_json)):
        if (reemplazar == False):
            return (f"La tarea de este notebook ya existe en: {ruta_json}. "
                    "Para retomarla, cárgala con cargar_tarea usando esa ruta. "
                    "Usa reemplazar=True solo si el estudiante pide explícitamente "
                    "rehacer los subobjetivos.")
    generador.escribir_tarea(ruta_json, ruta_limpia, subobjetivos)
    respuesta_carga = cargar_tarea(ruta_json, reanudar=True)
    devolver = "Ruta del JSON creado: " + ruta_json + "\n\n" + respuesta_carga
    return devolver


@mcp.tool()
def ayuda_entorno(pregunta: str) -> str:
    """Responde dudas sobre las herramientas de trabajo del estudiante, no sobre la tarea.

    Se usa para terminal, git y GitHub, VS Code, el entorno de Python (instalar
    paquetes, errores de import, versiones) y carga de datos (descargar un
    dataset, leer un CSV, rutas que no se encuentran). No exige intentos
    previos y no cambia el estado de la sesión.

    No se usa para dudas sobre cómo programar un subobjetivo: para eso está
    pedir_ayuda. Si se llama con una, la herramienta compara la pregunta con
    los subobjetivos de la tarea cargada y, si coincide con alguno, te
    redirige a pedir_ayuda en vez de dejarte responder.

    Args:
        pregunta: La duda del estudiante, con sus palabras.

    Returns:
        Las instrucciones para responderla directo y paso a paso, o un mensaje
        que nombra el subobjetivo con el que coincide y te manda a
        pedir_ayuda. Sin tarea cargada no hay con qué comparar, así que
        devuelve las instrucciones de respuesta directa. Una pregunta vacía
        devuelve un mensaje que la pide.
    """
    if (len(pregunta.strip()) == 0):
        return "Por favor, haz una pregunta" 
    if (sesion is None):
        return INSTRUCCIONES_ENTORNO
    subobjetivos = list(sesion.subobjetivos.values())
    coincide = entorno.subobjetivo_coincidente(pregunta , subobjetivos)
    if (coincide is not None):
        return f"Coincide con el subobjetivo {coincide}. Ve a pedir_ayuda"
    else:
        return INSTRUCCIONES_ENTORNO

# Ahora main va al final, de modo que todas las herramientas estén
# definidas antes de que el servidor empiece a escuchar.
if __name__ == "__main__":
    mcp.run()
