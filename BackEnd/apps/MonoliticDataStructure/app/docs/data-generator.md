# Data Generator

## ¿Qué hace esta parte?

La funcionalidad de Data Generator se encarga de crear y preparar los datos sintéticos que alimentan el proyecto. Su objetivo es proporcionar un conjunto de archivos estructurados que puedan utilizarse para:

- probar la carga de datos,
- simular operaciones de stock y supply chain,
- trabajar con análisis exploratorio,
- alimentar la API o futuras fases de IA.

Este módulo permite generar datasets iniciales de forma reproducible sin depender únicamente de datos reales.

---

## ¿Cómo funciona?

El flujo general del data generator es el siguiente:

1. Se leen o se crean estructuras base de datos.
2. Se generan registros sintéticos para entidades como productos y proveedores.
3. Los datos se guardan en archivos CSV dentro de la carpeta de datos generados.
4. Posteriormente pueden cargarse en PostgreSQL o utilizarse directamente en notebooks.

En este proyecto, el punto de entrada principal es:

- [scripts/run_generator.py](scripts/run_generator.py)

Y la lógica de generación se encuentra en:

- [src/generators/main_generator.py](src/generators/main_generator.py)

---

## Componentes principales

### 1. Generadores

La carpeta [src/generators](src/generators) contiene los módulos encargados de crear los datos.

- [src/generators/base_generator.py](src/generators/base_generator.py): define la estructura base para todos los generadores.
- [src/generators/product_generator.py](src/generators/product_generator.py): genera datos de productos.
- [src/generators/supplier_generator.py](src/generators/supplier_generator.py): genera datos de proveedores.
- [src/generators/main_generator.py](src/generators/main_generator.py): coordina la generación y exportación de los archivos.

### 2. Salida de datos

Los archivos generados se guardan en la carpeta:

- [data/generated](data/generated)

Allí se pueden encontrar ficheros como:

- products.csv
- suppliers.csv

---

## Flujo recomendado de uso

### 1. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

### 2. Instalar dependencias

```bash
pip install pandas numpy faker tqdm python-dotenv
```

### 3. Colocar el archivo Kaggle

Debes dejar el dataset original en la ruta:

- [data/raw/Kaggle_Dataset.csv](data/raw/Kaggle_Dataset.csv)

> Si el archivo no existe, el flujo puede fallar o quedar incompleto según la implementación futura.

### 4. Generar datos

```bash
python scripts/run_generator.py
```

Este comando ejecuta la lógica principal del generador y produce los archivos CSV resultantes.

### 5. Verificar integridad

```bash
python scripts/verify_data.py
```

Este paso sirve para comprobar que los datos generados están bien formados y listos para su uso posterior.

---

## Buenas prácticas

- Mantén el entorno virtual aislado del sistema.
- Guarda los datasets originales en [data/raw](data/raw).
- No subas archivos grandes a Git.
- Usa la carpeta [data/generated](data/generated) para archivos intermedios o de salida.
- Verifica siempre los resultados antes de cargar datos en la base de datos.

---

## Objetivo

El Data Generator sirve como punto de partida para construir un flujo de datos limpio y reproducible dentro de StockAssistant-Jupiter, facilitando tanto el análisis como la integración con la base de datos y la API.
