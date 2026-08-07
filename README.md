# Astolfo Design

Aplicación de escritorio para diseñar e imprimir etiquetas utilizando
dimensiones reales en centímetros. Está desarrollada con Python y PyQt6 para
Windows.

## Funciones

- Diseños con ancho y largo configurables en centímetros.
- Inserción, movimiento y escalado de textos e imágenes.
- Códigos de barras Code 128 vectoriales generados con Zint.
- Edición de textos y códigos de barras existentes.
- Guardado de diseños en archivos `.astolfo`.
- Tema claro y oscuro.
- Detección de impresoras instaladas.
- Impresión individual e incremental.
- Pegado automático de campos `Nombre:` y `PosCode:` desde el portapapeles.
- Asociación de archivos `.astolfo` mediante el instalador.

## Requisitos de desarrollo

- Windows 10 u 11 de 64 bits.
- Python 3.10 o compatible.

Instala las dependencias:

```powershell
python -m pip install -r requirements.txt
```

Ejecuta la aplicación:

```powershell
python app.py
```

También puedes utilizar `iniciar_astolfo_design.bat`.

## Formato `.astolfo`

Los diseños se guardan como JSON legible con la extensión `.astolfo`. Contienen
las dimensiones de la etiqueta y las propiedades de cada elemento. Las imágenes
se referencian mediante su ruta local.

## Crear el ejecutable

Instala las dependencias de desarrollo:

```powershell
python -m pip install -r requirements-dev.txt
python -m PyInstaller --clean --noconfirm AstolfoDesign.spec
```

El ejecutable se genera en `dist\AstolfoDesign.exe`.

## Crear el instalador

El instalador utiliza [Inno Setup 6](https://jrsoftware.org/isinfo.php). Primero
genera el ejecutable dentro de `Instalador\App`:

```powershell
python -m PyInstaller --clean --noconfirm --distpath "Instalador\App" AstolfoDesign.spec
```

Después abre o compila `Instalador\AstolfoDesign.iss` con Inno Setup. Los
ejecutables, archivos BIN, ZIP y carpetas de compilación se excluyen del
repositorio mediante `.gitignore`.

## Estructura principal

```text
app.py                         Aplicación PyQt6
AstolfoDesign.spec             Configuración de PyInstaller
requirements.txt               Dependencias de ejecución
requirements-dev.txt           Dependencias para compilar
Logo.ico / Logo.png            Iconos de la aplicación
Instalador/AstolfoDesign.iss   Configuración de Inno Setup
Instalador/archivo.ico         Icono de archivos .astolfo
Instalador/instalador.ico      Icono del instalador
```

## Seguridad

Astolfo Design funciona localmente y no realiza conexiones a internet. Abre
solamente diseños e imágenes provenientes de fuentes confiables.
