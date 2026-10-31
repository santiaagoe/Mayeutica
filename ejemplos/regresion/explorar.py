"""Resultados del modelo de regresion.py, para el momento "resultados" del tutor.

Entrena el modelo sobre datos inventados de departamentos (precio según metros
cuadrados y distancia al metro) e imprime lo que sale: los parámetros
aprendidos comparados con los reales, cómo baja el error con las épocas y qué
pasa con distintas tasas de aprendizaje. No interpreta nada: interpretar es
trabajo del estudiante, guiado por el tutor.

Los datos se generan con una regla conocida más ruido:
    precio (millones) = 0.9 · m² - 6 · km_al_metro + 40 + ruido
Las variables se estandarizan (media 0, desviación 1) antes de entrenar.

Uso:  python explorar.py
"""
import numpy as np

from regresion import entrenar, error_cuadratico_medio, predecir

PESOS_REALES = np.array([0.9, -6.0])   # millones por m², millones por km
SESGO_REAL = 40.0
RUIDO = 8.0                            # desviación del ruido, en millones


def generar_datos(n=200, semilla=0):
    """Departamentos inventados: X en unidades originales (m², km) e y en millones."""
    rng = np.random.default_rng(semilla)
    m2 = rng.uniform(30, 120, size=n)
    km = rng.uniform(0.1, 3.0, size=n)
    X = np.column_stack([m2, km])
    y = X @ PESOS_REALES + SESGO_REAL + rng.normal(0, RUIDO, size=n)
    return X, y


def estandarizar(X):
    """Devuelve X estandarizada por columna, junto con la media y la desviación usadas."""
    media = X.mean(axis=0)
    desviacion = X.std(axis=0)
    return (X - media) / desviacion, media, desviacion


def a_unidades_originales(w, b, media, desviacion):
    """Convierte pesos aprendidos sobre X estandarizada a pesos sobre X original."""
    w_original = w / desviacion
    b_original = b - np.sum(w * media / desviacion)
    return w_original, b_original


def main():
    X, y = generar_datos()
    Xs, media, desviacion = estandarizar(X)
    print(f"Datos: {len(y)} departamentos, precio promedio {y.mean():.1f} millones\n")

    # 1. Parámetros aprendidos
    w, b = entrenar(Xs, y, tasa=0.1, epocas=1000)
    w_orig, b_orig = a_unidades_originales(w, b, media, desviacion)
    print("1. Parámetros (tasa 0.1, 1000 épocas)")
    print(f"   {'':22}{'real':>10}{'aprendido':>12}")
    print(f"   {'millones por m²':22}{PESOS_REALES[0]:>10.3f}{w_orig[0]:>12.3f}")
    print(f"   {'millones por km':22}{PESOS_REALES[1]:>10.3f}{w_orig[1]:>12.3f}")
    print(f"   {'sesgo (millones)':22}{SESGO_REAL:>10.3f}{b_orig:>12.3f}")
    print(f"   Pesos sobre X estandarizada: {np.round(w, 3)}, sesgo {b:.3f}")
    mse = error_cuadratico_medio(y, predecir(Xs, w, b))
    print(f"   MSE final: {mse:.2f}   (raíz: {np.sqrt(mse):.2f} millones; ruido usado: {RUIDO})\n")

    # 2. Error según épocas
    print("2. MSE según épocas (tasa 0.1)")
    for epocas in [0, 1, 5, 20, 100, 1000]:
        w_e, b_e = entrenar(Xs, y, tasa=0.1, epocas=epocas)
        print(f"   {epocas:>5} épocas: {error_cuadratico_medio(y, predecir(Xs, w_e, b_e)):>12.2f}")
    print()

    # 3. Error según la tasa de aprendizaje
    print("3. MSE después de 100 épocas, según la tasa")
    with np.errstate(over="ignore", invalid="ignore"):
        for tasa in [0.001, 0.01, 0.1, 0.5, 1.1]:
            w_t, b_t = entrenar(Xs, y, tasa=tasa, epocas=100)
            print(f"   tasa {tasa:<6}: {error_cuadratico_medio(y, predecir(Xs, w_t, b_t)):>14.4g}")
    print()

    # 4. Sin estandarizar
    print("4. Mismo entrenamiento sin estandarizar X (tasa 0.1, 100 épocas)")
    with np.errstate(over="ignore", invalid="ignore"):
        w_c, b_c = entrenar(X, y, tasa=0.1, epocas=100)
        print(f"   pesos: {w_c}, sesgo: {b_c:.4g}")
        print(f"   MSE: {error_cuadratico_medio(y, predecir(X, w_c, b_c)):.4g}\n")

    # 5. Una predicción
    nuevo = np.array([[70.0, 0.5]])
    precio = predecir((nuevo - media) / desviacion, w, b)[0]
    print(f"5. Departamento de 70 m² a 0.5 km del metro: {precio:.1f} millones predichos")
    print(f"   (la regla sin ruido da {(nuevo @ PESOS_REALES + SESGO_REAL)[0]:.1f})")


if __name__ == "__main__":
    main()
