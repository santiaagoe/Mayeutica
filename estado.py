
"""Estado de una sesión de tutoría de Mayéutica.

Este módulo lleva el registro de lo que el estudiante ha hecho en una tarea
(intentos y pistas recibidas) y decide qué pistas están permitidas. No sabe
nada de LLMs ni de MCP: es el "árbitro" que las herramientas consultan.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import json

INTENTOS_PREV_NECESARIOS = 1 #cantidad de intentos minimos para dar una pista
NIVEL_MAXIMO = 4  # 1: pregunta, 2: concepto, 3: pseudocódigo, 4: firma.

# Intentos fallidos en un mismo subobjetivo a partir de los cuales se permite
# entregar el código (momento "rescate").
FALLOS_PARA_RESCATE = 3

# Tabla de momentos del ciclo: qué debe y qué no puede hacer el tutor en cada
# uno. Es el texto que el servidor le entrega al LLM como instrucción. Las
# claves son fijas (las devuelven momento_inicial y momento_revision) y no
# llevan tildes; los textos sí, porque los lee una persona (o el LLM).
MOMENTOS: dict[str, dict[str, str]] = {
    "diagnostico": {
        "permitido": (
            "Hazle al estudiante dos preguntas rápidas de sí o no sobre este "
            "subobjetivo: si maneja la teoría y si sabe implementarlo en código. "
            "Confía en lo que responda y llama a registrar_diagnostico con sus "
            "respuestas."
        ),
        "prohibido": (
            "No expliques teoría ni muestres código antes de tener sus respuestas. "
            "No le tomes una prueba: la encuesta debe ser rápida."
        ),
    },
    "teoria": {
        "permitido": (
            "Explica brevemente la teoría que necesita este subobjetivo, con un "
            "ejemplo o una intuición si ayuda, y comprueba con una pregunta corta "
            "si quedó clara. Si el estudiante dijo que maneja la teoría, dala por "
            "sabida, pero explícala igual si pregunta o si se nota que le falta un "
            "concepto."
        ),
        "prohibido": (
            "No escribas código de la solución. No des una clase larga ni le "
            "impongas una explicación de algo que dijo saber si no la pide."
        ),
    },
    "ejemplo": {
        "permitido": (
            "Muestra la implementación oficial del ejemplo de este subobjetivo y "
            "explica brevemente cómo funciona y qué hace cada parte. Luego dile "
            "que su tarea es adaptarla a su propio caso. Si la tarea no trae un "
            "ejemplo, escribe tú uno, basado en la versión de la librería que el "
            "estudiante tiene instalada, y avísale antes de mostrarlo que no es "
            "oficial ni está verificado: puede tener errores o usar una API de "
            "otra versión. Sugiérele correrlo para comprobar que funciona."
        ),
        "prohibido": (
            "No adaptes el ejemplo al caso del estudiante: esa adaptación es su "
            "tarea. No presentes un ejemplo escrito por ti como si fuera oficial "
            "ni omitas el aviso de que no está verificado."
        ),
    },
    "duda_especifica": {
        "permitido": (
            "El estudiante dice manejar la teoría y el código. Pregúntale cuál es "
            "su duda concreta y ayúdalo solo en eso."
        ),
        "prohibido": (
            "No recorras el ciclo completo (teoría, ejemplo) si no lo pide. No "
            "escribas la solución."
        ),
    },
    "revision_conceptual": {
        "permitido": (
            "El estudiante falló una vez. Explica qué concepto o idea está "
            "fallando y por qué, a partir de la salida de los tests. Puedes "
            "hacerle una pregunta que lo lleve a encontrar el error."
        ),
        "prohibido": (
            "No digas en qué línea está el error. No escribas código, ni la "
            "corrección ni un fragmento de ella."
        ),
    },
    "revision_explicita": {
        "permitido": (
            "El estudiante ya falló más de una vez. Dile dónde está el error (la "
            "función o la línea) y qué está mal en concreto, comparando lo que "
            "hace su código con lo que debería hacer."
        ),
        "prohibido": (
            "No escribas la línea corregida ni la solución completa: el arreglo "
            "lo tiene que escribir él."
        ),
    },
    "rescate": {
        "permitido": (
            "El estudiante llegó al límite de intentos fallidos. Entrégale el "
            "código de este subobjetivo, explica qué hace cada parte y en qué "
            "estaba fallando su versión. Al final, hazle una pregunta breve de "
            "comprensión que pida explicar, por ejemplo: 'explica en una frase qué "
            "hace esta línea' o '¿qué pasaría si cambias X?'."
        ),
        "prohibido": (
            "No entregues el código sin explicarlo. No cierres con '¿entendiste?' "
            "ni con otra pregunta de sí o no. No marques el subobjetivo como "
            "completado: igual tiene que pasar los tests."
        ),
    },
    "resultados": {
        "permitido": (
            "El estudiante pregunta por los resultados (por ejemplo, de un modelo "
            "de ML). Guíalo con preguntas para que él mismo los interprete y saque "
            "la conclusión: qué esperaba, qué obtuvo y qué podría explicar la "
            "diferencia."
        ),
        "prohibido": (
            "No le des la conclusión ni la interpretación final. No cambies su "
            "código para mejorar los resultados."
        ),
    },
}

@dataclass
class Intento:
    """Un intento del estudiante de resolver un subobjetivo.

    Es inmutable en la práctica: una vez registrado, un intento no se modifica.

    Attributes:
        subobjetivo_id: Id del subobjetivo al que pertenece (por ejemplo, "derivada").
        codigo: El código que el estudiante escribió en este intento.
        resultado_tests: Salida de los tests sobre este código, o None si no se
            ejecutaron.
        paso: True si los tests pasaron, False si fallaron, None si no se
            ejecutaron. Los intentos con False son los que cuentan como fallidos.
        fecha: Momento en que se registró el intento. Se asigna automáticamente.
    """
    subobjetivo_id: str 
    codigo: str
    # Puede ser texto o None. Le damos None como valor por defecto.
    resultado_tests : str | None = None
    paso: bool | None = None   # True si pasaron los tests, False si fallaron, None si no se corrieron.
    fecha : datetime = field(default_factory=datetime.now)
    

@dataclass
class Subobjetivo:
    """Un paso pequeño de una tarea, con su propio historial de intentos y pistas.

    Cada subobjetivo avanza por los niveles de pista de forma independiente:
    se puede estar en la pista 3 de uno y no haber pedido ninguna en otro.

    Attributes:
        id: Identificador único dentro de la tarea (por ejemplo, "derivada").
        descripcion: Qué tiene que lograr el estudiante en este paso.
        nivel_pista_desbloqueado: Última pista entregada (0 si no ha recibido ninguna).
        completado: True si el estudiante ya resolvió este paso.
        intentos_al_entregar_pista: Cantidad de intentos que había cuando se entregó la última pista.
        intentos: Todos los intentos registrados, en orden cronológico.
        archivo: Ruta absoluta al archivo con el código del estudiante para este
            subobjetivo, o None si la tarea no la indica.
        tests: Ruta absoluta al archivo de tests de este subobjetivo, o None si
            la tarea no la indica.
        ejemplo: Ruta absoluta a la implementación oficial que el tutor muestra
            en el momento "ejemplo", o None si la tarea no la indica.
        maneja_teoria: Respuesta del diagnóstico sobre la teoría (None si
            todavía no se preguntó).
        maneja_codigo: Respuesta del diagnóstico sobre el código (None si
            todavía no se preguntó).
        rescatado: True si se le entregó el código al estudiante (momento
            "rescate"). Es independiente de completado.
    """    
    id : str
    descripcion: str
    nivel_pista_desbloqueado: int = 0 #parte sin pistas
    completado: bool = False #parte sin completar
    intentos_al_entregar_pista : int = 0
    intentos : list[Intento] = field(default_factory=list) #los intentos de este subobjetivo
    archivo: str | None = None
    tests: str | None = None
    ejemplo: str | None = None   # Ruta absoluta a la implementación oficial, o None.
    maneja_teoria: bool | None = None
    maneja_codigo: bool | None = None
    rescatado: bool = False

    
    def hay_intento_previo(self) -> bool:
        """Indica si el estudiante ha registrado al menos un intento.

        Returns:
            True si existe al menos un intento en este subobjetivo.
        """
        return (len(self.intentos) > 0)

    def hay_intento_desde_ultima_pista(self) -> bool:
        """Indica si hay un intento registrado después de la última pista entregada.

        Si todavía no se ha entregado ninguna pista, equivale a hay_intento_previo().

        Returns:
            True si el estudiante volvió a intentar después de recibir la última pista.
        """
        if (self.nivel_pista_desbloqueado <= 0):
            return self.hay_intento_previo()
        return len(self.intentos) > self.intentos_al_entregar_pista

    def intentos_fallidos(self) -> int:
        """Cuenta los intentos cuyos tests fallaron.

        Solo cuentan los intentos con paso False. Los aprobados (True) y los que
        no corrieron tests (None) no cuentan.

        Returns:
            Cantidad de intentos fallidos de este subobjetivo.
        """   
        fallos = 0
        for i in self.intentos:
            if (i.paso == False):
                fallos += 1
        return fallos        
        

class SesionTarea:
    """Una tarea en la que el estudiante está trabajando, de principio a fin.

    Es la puerta de entrada que usan las herramientas MCP: todas las consultas
    y cambios sobre intentos y pistas pasan por aquí.

    Attributes:
        subobjetivos: Diccionario que asocia el id de cada subobjetivo con su objeto.
    """

    def __init__(self, ruta_tarea: str):
        """Carga una tarea desde un archivo JSON y crea sus subobjetivos.

        Args:
            ruta_tarea: Ruta al JSON de la tarea. Debe contener una lista de
            subobjetivos, cada uno con "id" y "descripcion". Cada uno puede
            traer además "archivo", "tests" y "ejemplo" (opcionales). Si son rutas
            relativas, se interpretan desde la carpeta donde está el JSON, no
            desde el directorio actual, y se guardan como rutas absolutas.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si dos subobjetivos tienen el mismo id.
        """
        ruta_absoluta_json = Path(ruta_tarea).resolve()
        directorio_base = ruta_absoluta_json.parent
        with open(ruta_absoluta_json, encoding="utf-8") as f:
            datos = json.load(f)
        def resolver_ruta(ruta: str | None) -> str | None:
            if not ruta:
                return None
            p = Path(ruta)
            return str(p if p.is_absolute() else (directorio_base / p).resolve())

        subs = {}
        for s in datos["subobjetivos"]:
            archivo = resolver_ruta(s.get("archivo"))
            tests = resolver_ruta(s.get("tests"))
            ejemplo = resolver_ruta(s.get("ejemplo"))

            subobjetivo = Subobjetivo(
                id=s["id"],
                descripcion=s["descripcion"],
                archivo=archivo,
                tests=tests,
                ejemplo=ejemplo
            )
            
            if subobjetivo.id in subs:
                raise ValueError(f"El id: {subobjetivo.id} está repetido")
            subs[subobjetivo.id] = subobjetivo
            
        self.subobjetivos = subs

    def registrar_intento(self, subobjetivo_id: str, codigo: str,
                          resultado_tests: str | None = None,
                          paso : bool | None = None) -> Intento:
        """Guarda un nuevo intento del estudiante en el subobjetivo indicado.

        Args:
            subobjetivo_id: Id del subobjetivo que el estudiante está intentando.
            codigo: El código del intento.
            resultado_tests: Salida de los tests, si se ejecutaron.
            paso: True si los tests pasaron, False si fallaron, None si no se
                ejecutaron.

        Returns:
            El intento creado.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}.")

        intento_creado = Intento(subobjetivo_id, codigo, resultado_tests, paso)
        subobjetivo = self.subobjetivos[subobjetivo_id]
        subobjetivo.intentos.append(intento_creado)
        return intento_creado

    def puede_pedir_pista(self, subobjetivo_id: str, nivel: int) -> tuple[bool, str]:
        """Decide si el estudiante puede recibir una pista de cierto nivel.

        Reglas, en este orden:
            1. El nivel debe estar entre 1 y NIVEL_MAXIMO y ser exactamente el
               siguiente al último entregado (no se pueden saltar niveles).
            2. Para el nivel 1, debe haber al menos INTENTOS_PREV_NECESARIOS intentos.
            3. Para el nivel N+1, debe existir un intento posterior a la entrega
               de la pista N.
            4. Si el subobjetivo está completado, no se entregan más pistas.

        Args:
            subobjetivo_id: Id del subobjetivo.
            nivel: Nivel de pista solicitado.

        Returns:
            Una tupla (permitido, mensaje). Si permitido es False, el mensaje
            explica por qué, en un tono que el LLM pueda mostrar al estudiante.
        """
        subobjetivo = self.subobjetivos[subobjetivo_id]
        if (subobjetivo.completado): #4
            return (False, "El subobjetivo está completado")
        
        if ((nivel - subobjetivo.nivel_pista_desbloqueado) != 1 or nivel > NIVEL_MAXIMO ): #1
            return (False, "No se puede pedir pista porque se salta niveles o excede el nivel máximo")
        if (nivel == 1): #2
            if  (len(subobjetivo.intentos)< INTENTOS_PREV_NECESARIOS):
                return (False, "No tiene los intentos necesarios")
            else: 
                return (True, "")
        else:
            if(subobjetivo.hay_intento_desde_ultima_pista()):
                return (True, "")
            else: 
                return (False, "No hay intento previo desde la última pista")


    def registrar_pista_entregada(self, subobjetivo_id: str, nivel: int) -> None:
        """Anota que se entregó una pista, para que las reglas la tomen en cuenta.

        Se llama después de que puede_pedir_pista autorizó el nivel y la pista
        fue entregada. Sin este método, las reglas 1 y 3 no tendrían cómo saber
        qué pistas ya se dieron.

        Args:
            subobjetivo_id: Id del subobjetivo.
            nivel: Nivel de la pista entregada.
        """
        subobjetivo = self.subobjetivos[subobjetivo_id]
        subobjetivo.nivel_pista_desbloqueado = nivel
        subobjetivo.intentos_al_entregar_pista = len(subobjetivo.intentos)

    def marcar_completado(self, subobjetivo_id: str) -> bool:
        """Marca un subobjetivo como completado.

        Solo cambia el estado: no decide cuándo un subobjetivo cuenta como
        resuelto. Una vez completado, la regla 4 de puede_pedir_pista bloquea las
        pistas de ese subobjetivo.

        Args:
            subobjetivo_id: Id del subobjetivo.

        Returns:
            True si el subobjetivo pasó de no completado a completado; False si
            ya estaba completado (no es un error, pero quien llama puede avisarlo).

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        if (subobjetivo_id not in self.subobjetivos ):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}")
        subobjetivo = self.subobjetivos[subobjetivo_id]
        marcar = False
        if (subobjetivo.completado == False):
            marcar = True 
            subobjetivo.completado = True
        return marcar 
        


    def registrar_diagnostico(self, subobjetivo_id: str,
                              maneja_teoria: bool, maneja_codigo: bool) -> None:
        """Guarda lo que respondió el estudiante en la encuesta inicial.

        Se confía en la respuesta. Si después el tutor nota que no maneja un
        concepto, igual puede explicarlo (eso lo decide el tutor, no el árbitro).

        Args:
            subobjetivo_id: Id del subobjetivo.
            maneja_teoria: True si el estudiante dice que maneja la teoría.
            maneja_codigo: True si el estudiante dice que sabe implementarlo.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}")
        subobjetivo = self.subobjetivos[subobjetivo_id]
        subobjetivo.maneja_teoria = maneja_teoria
        subobjetivo.maneja_codigo = maneja_codigo
        
    def momento_inicial(self, subobjetivo_id: str) -> str:
        """Decide por dónde empieza el ciclo, según el diagnóstico.

        Reglas:
            - Sin diagnóstico (maneja_teoria es None) -> "diagnostico"
            - No maneja la teoría (sepa o no el código) -> "teoria"
            - Maneja la teoría pero no el código -> "ejemplo"
            - Maneja las dos cosas -> "duda_especifica"

        Args:
            subobjetivo_id: Id del subobjetivo.

        Returns:
            El nombre del momento; siempre es una clave de MOMENTOS.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}")
        subobjetivo = self.subobjetivos[subobjetivo_id]
        maneja_teo = subobjetivo.maneja_teoria 
        maneja_cod = subobjetivo.maneja_codigo
        devolver = ""
        if (maneja_teo is None):
            devolver = "diagnostico"
        elif (maneja_teo == False):
            devolver = "teoria"
        elif(maneja_cod == False):
            devolver = "ejemplo"
        else:
            devolver = "duda_especifica"
        return devolver    


    def momento_revision(self, subobjetivo_id: str) -> str | None:
        """Decide qué tan explícita debe ser la revisión, según los intentos fallidos.

        Reglas, en este orden:
            - Completado -> None (no hay nada que revisar)
            - 0 intentos fallidos -> None
            - FALLOS_PARA_RESCATE o más -> "rescate"
            - 1 fallo -> "revision_conceptual"
            - Desde 2 fallos hasta antes de FALLOS_PARA_RESCATE -> "revision_explicita"

        Args:
            subobjetivo_id: Id del subobjetivo.

        Returns:
            El nombre del momento (una clave de MOMENTOS), o None.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}")
        subobjetivo = self.subobjetivos[subobjetivo_id]
        if (subobjetivo.completado):
            return None
        fallidos = subobjetivo.intentos_fallidos()
        if (fallidos == 0):
            return None
        elif (fallidos == 1):
            return "revision_conceptual"
        elif (1 < fallidos < FALLOS_PARA_RESCATE):
            return "revision_explicita"
        else:
            return "rescate"

    def puede_rescatar(self, subobjetivo_id: str) -> tuple[bool, str]:
        """Decide si se puede entregar el código al estudiante.

        Reglas:
            1. Si el subobjetivo está completado, no se rescata.
            2. Debe tener al menos FALLOS_PARA_RESCATE intentos fallidos.

        Args:
            subobjetivo_id: Id del subobjetivo.

        Returns:
            Una tupla (permitido, mensaje). Si permitido es False, el mensaje
            explica por qué, y cada regla tiene su propio mensaje.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}")
        subobjetivo = self.subobjetivos[subobjetivo_id]
        if (subobjetivo.completado):
            return (False, f"El subobjetivo {subobjetivo_id} ya está completado")
        fallidos = subobjetivo.intentos_fallidos()
        if (fallidos < FALLOS_PARA_RESCATE):
            return (False, f"Debe tener al menos {FALLOS_PARA_RESCATE} fallos para el rescate")
        else:
            return (True, "")

        
    def registrar_rescate(self, subobjetivo_id: str) -> None:
        """Anota que se le entregó el código al estudiante.

        Se llama después de que puede_rescatar lo autorizó. No marca el
        subobjetivo como completado: el estudiante igual tiene que pasar los
        tests. Sirve para saber después qué subobjetivos conviene repasar.

        Args:
            subobjetivo_id: Id del subobjetivo.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}")
        subobjetivo = self.subobjetivos[subobjetivo_id]
        subobjetivo.rescatado = True
        
    def guardar(self, ruta: str) -> None:
        """Escribe el estado completo de la sesión en disco.

        Args:
            ruta: Archivo donde guardar el estado.
        """   
        subs_dict = {}
        for clave, subobjetivo in self.subobjetivos.items():
            subs_dict[clave] = asdict(subobjetivo)
            
        datos = {
            "subobjetivos": subs_dict
        }

        #default=str convierte a texto 
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2, default=str)