
"""Estado de una sesión de tutoría de Mayéutica.

Este módulo lleva el registro de lo que el estudiante ha hecho en una tarea
(intentos y pistas recibidas) y decide qué pistas están permitidas. No sabe
nada de LLMs ni de MCP: es el "árbitro" que las herramientas consultan.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json

INTENTOS_PREV_NECESARIOS = 1 #cantidad de intentos minimos para dar una pista
NIVEL_MAXIMO = 4  # 1: pregunta, 2: concepto, 3: pseudocódigo, 4: firma.

@dataclass
class Intento:
    """Un intento del estudiante de resolver un subobjetivo.

    Es inmutable en la práctica: una vez registrado, un intento no se modifica.

    Attributes:
        subobjetivo_id: Id del subobjetivo al que pertenece (por ejemplo, "derivada").
        codigo: El código que el estudiante escribió en este intento.
        resultado_tests: Salida de los tests sobre este código, o None si no se
            ejecutaron.
        fecha: Momento en que se registró el intento. Se asigna automáticamente.
    """
    subobjetivo_id: str 
    codigo: str
    # Puede ser texto o None. Le damos None como valor por defecto.
    resultado_tests : str | None = None
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
    """    
    id : str
    descripcion: str
    nivel_pista_desbloqueado: int = 0 #parte sin pistas
    completado: bool = False #parte sin completar
    intentos_al_entregar_pista : int = 0
    intentos : list[Intento] = field(default_factory=list) #los intentos de este subobjetivo
    
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
            subobjetivos, cada uno con "id" y "descripcion".

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si dos subobjetivos tienen el mismo id.
        """
        with open(ruta_tarea, encoding="utf-8") as f:
            datos = json.load(f)
        subs = {} #los subobjetivos
        for s in datos["subobjetivos"]:    
            subobjetivo = Subobjetivo(s["id"],s["descripcion"])
            if (subobjetivo.id in subs):
                raise ValueError(f"El id: {subobjetivo.id} está repetido")
            subs[subobjetivo.id] = subobjetivo
        self.subobjetivos = subs   

    def registrar_intento(self, subobjetivo_id: str, codigo: str,
                          resultado_tests: str | None = None) -> Intento:
        """Guarda un nuevo intento del estudiante en el subobjetivo indicado.

        Args:
            subobjetivo_id: Id del subobjetivo que el estudiante está intentando.
            codigo: El código del intento.
            resultado_tests: Salida de los tests, si se ejecutaron.

        Returns:
            El intento creado.

        Raises:
            KeyError: Si no existe un subobjetivo con ese id.
        """
        
        if (subobjetivo_id not in self.subobjetivos):
            raise KeyError(f"No existe subobjetivo con el id: {subobjetivo_id}.")

        intento_creado = Intento(subobjetivo_id, codigo, resultado_tests)
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