"""Ejemplo oficial para el subobjetivo 'derivada': la derivada de la gaussiana.

No es la solución de la tarea. Muestra cómo escribir la derivada de una
activación reutilizando la propia activación. Para g(z) = e^(-z²), la regla de
la cadena da g'(z) = -2z · e^(-z²) = -2z · g(z). Tu trabajo es hacer lo mismo
con la sigmoide: encontrar su derivada y escribirla en función de σ(z).

Qué mirar:
    - La derivada recibe z (la entrada de la activación), no la salida.
    - Se calcula g(z) una sola vez, se guarda en una variable y se reutiliza.
    - Se puede comprobar con una derivada numérica: (g(z+h) - g(z-h)) / 2h.

Para probarlo:  python ejemplo_derivada.py
"""
import numpy as np

from ejemplo_sigmoide import gaussiana


def derivada_gaussiana(z):
    """Calcula la derivada de la gaussiana evaluada en z.

    Args:
        z: Un número o un arreglo de numpy (la entrada de la gaussiana, no su
            salida).

    Returns:
        La derivada en z, con la misma forma que z.
    """
    g = gaussiana(z)
    return -2 * z * g


if __name__ == "__main__":
    print(derivada_gaussiana(0))   # 0.0 (es el máximo de la gaussiana)
    print(derivada_gaussiana(1))   # -0.7357588823428847

    # Comprobación numérica: las dos columnas deberían coincidir.
    h = 1e-6
    for z in [-1.5, 0.3, 2.0]:
        numerica = (gaussiana(z + h) - gaussiana(z - h)) / (2 * h)
        print(z, derivada_gaussiana(z), numerica)
