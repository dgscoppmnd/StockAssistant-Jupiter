# StockAssistant-Jupiter

## Visión general

StockAssistant-Jupiter es un proyecto base orientado a la gestión de stock y cadenas de suministro, diseñado para combinar:

- generación de datos sintéticos,
- almacenamiento en PostgreSQL,
- exposición de servicios mediante FastAPI,
- análisis exploratorio en Jupyter.

Este proyecto sirve como punto de partida para un TFM, una demo técnica o una arquitectura inicial escalable.

---

## Estructura del proyecto

```text
StockAssistant-Jupiter/
├── docker/                      # Infraestructura de servicios
├── data/                        # Datos crudos, generados y procesados
├── src/                         # Código fuente principal
├── notebooks/                   # Análisis y exploración de datos
├── tests/                       # Pruebas unitarias e integración
├── scripts/                     # Scripts de ejecución útiles
├── requirements/                # Dependencias del proyecto
├── docs/                        # Documentación del proyecto
├── .env                         # Variables de entorno locales
├── .gitignore                   # Archivos ignorados por Git
├── Makefile                     # Comandos rápidos de uso
├── pyproject.toml               # Configuración del proyecto Python
└── README.md                    # Resumen inicial del proyecto
```

---

## Descripción de las carpetas

### 1. docker/
Carpeta destinada a la infraestructura del proyecto.

- contiene la configuración de Docker Compose,
- levanta servicios como PostgreSQL y pgAdmin,
- permite reproducir el entorno de forma sencilla en cualquier máquina.

### 2. data/
Espacio para almacenar los datos del proyecto.

- raw/: datos originales o crudos,
- generated/: archivos generados automáticamente,
- processed/: datos ya preparados para análisis o uso en IA.

Esta carpeta suele ser ignorada en Git para evitar subir datos pesados o sensibles.

### 3. src/
Es el corazón del proyecto, donde vive el código funcional.

#### src/generators/
Encargada de crear datos sintéticos.

- base_generator.py: clase base para los generadores.
- product_generator.py: generación de productos.
- supplier_generator.py: generación de proveedores.
- main_generator.py: orquestador principal para crear los datasets.

#### src/database/
Contiene todo lo relacionado con la persistencia de datos.

- connection.py: conexión a PostgreSQL.
- loader.py: carga de archivos CSV o datos a la base de datos.
- models.py: modelos de base de datos.

#### src/api/
Incluye la capa de servicios web del proyecto.

- main.py: aplicación FastAPI principal.
- routes/: endpoints organizados por dominio.
- schemas.py: modelos Pydantic para validación de datos.

#### src/utils/
Módulos auxiliares compartidos por varias partes del sistema.

- config.py: gestión de configuración.
- logger.py: utilidad de logging.

---

## notebooks/
Carpeta usada para análisis exploratorio y prototipos.

Aquí se pueden crear cuadernos Jupyter para:

- visualizar datos,
- validar calidad de datos,
- explorar patrones de negocio,
- preparar datasets para modelos de IA.

---

## tests/
Contiene las pruebas automáticas del proyecto.

Se recomienda utilizar esta carpeta para validar:

- generadores de datos,
- endpoints de la API,
- lógica de negocio básica.

---

## scripts/
Scripts ejecutables para tareas frecuentes.

- run_generator.py: genera los datos sintéticos.
- load_data.py: carga los datos a la base de datos.
- run_api.py: inicia la API FastAPI.

Estos scripts facilitan la ejecución del proyecto sin necesidad de escribir comandos largos cada vez.

---

## requirements/
Contiene los archivos con dependencias del proyecto.

- dev.txt: herramientas y paquetes para desarrollo.
- prod.txt: dependencias para producción o despliegue.

Esto ayuda a mantener el entorno reproducible.

---

## Configuración y entorno

El proyecto usa un archivo .env para guardar variables sensibles o configurables, como:

- nombre de la base de datos,
- usuario de PostgreSQL,
- contraseña,
- puerto y host.

Esto evita hardcodear valores en el código fuente.

---

## Flujo de trabajo recomendado

1. Levantar la infraestructura con Docker.
2. Generar los datos sintéticos.
3. Cargar los datos a PostgreSQL.
4. Ejecutar la API FastAPI.
5. Explorar el proyecto desde Jupyter.

---

## Comandos útiles

```bash
make build
make up
make generate
make load
make api
```

Estos comandos permiten acelerar el trabajo diario y mantener consistencia en los entornos.

---

## Objetivo del proyecto

StockAssistant-Jupiter pretende servir como base tecnológica para un sistema de apoyo a decisiones en stock y supply chain, con una arquitectura limpia que pueda evolucionar hacia:

- IA para predicción de demanda,
- análisis de inventario,
- alertas automáticas,
- dashboards y visualización.

---

## Notas finales

Este proyecto está pensado para crecer de forma modular.

Cada componente tiene una responsabilidad concreta:

- generar datos,
- almacenar datos,
- exponer servicios,
- documentar y analizar.

Eso facilita tanto el desarrollo inicial como futuras ampliaciones.
