# Astolfo Design

Aplicación de escritorio para diseñar e imprimir etiquetas

## Funciones

- Diseños con ancho y largo configurables en centímetros.
- Inserción, movimiento y escalado de textos e imágenes.
- Códigos de barras Code 128 vectoriales generados con Zint.
- Edición de textos y códigos de barras existentes.
- Guardado de diseños en archivos `.astolfo`.
- Tema claro y oscuro.
- Detección de impresoras instaladas.
- Impresión individual e incremental.
- Impresión genérica mediante el controlador instalado en Windows.
- Selección entre el tamaño de papel configurado en el controlador y un tamaño
  personalizado solicitado por Astolfo.
- Diagnóstico previo de tamaño solicitado y aplicado, DPI, orientación, área
  imprimible y escalado.
- Pegado automático de campos `Nombre:` y `PosCode:` desde el portapapeles.
- Asociación de archivos `.astolfo` mediante el instalador.

## Requisitos

- Windows 10 u 11 de 64 bits
- Python 3.10

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

Los diseños se guardan como JSON legible con la extensión `.astolfo`. Las
dimensiones se almacenan internamente en milímetros y la interfaz las muestra en
centímetros. El cargador mantiene compatibilidad con los documentos antiguos que
guardaban `width_cm` y `height_cm`. Las imágenes se referencian mediante su ruta
local.

## Impresión

Astolfo imprime mediante `QPrinter` y el controlador de Windows, sin depender de
Zebra, ZPL ni una marca concreta. Antes de enviar un trabajo muestra las medidas
solicitadas, las aceptadas por el controlador, el DPI, la orientación, el área
imprimible y el escalado aplicado.

El modo **Usar tamaño configurado en la impresora** es el predeterminado y suele
ser el más compatible. El modo **Solicitar tamaño desde Astolfo** intenta aplicar
las dimensiones del diseño y avisa si el controlador conserva otro tamaño. El
DPI puede dejarse a cargo del controlador o elegirse manualmente.

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

## Seguridad

Astolfo Design funciona localmente y no realiza conexiones a internet
