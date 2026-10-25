#  Plan de Trabajo - Fase de Generación de Datos

##  Fase 1: Diseño de la Base de Datos (Día 1-2) [[Fase 1 - Creación del modelo normalizado]]
- Análisis del dataset Kaggle: Identificar columnas, tipos de datos y claves
- Diseño del modelo relacional: Normalización (3FN), definición de tablas y relaciones
- Documentación: Diagrama ER y diccionario de datos

##  Fase 2: Infraestructura con Docker (Día 3) [[Fase 2- Infraestructura con Docker]]
- Creación del `docker-compose.yml` para PostgreSQL + pgAdmin
- Scripts de inicialización: Creación de tablas y constraints
- Verificación: Conexión y prueba de la estructura

##  Fase 3: Generación de Datos con Python/Faker (Día 4-6)
- Lectura del dataset Kaggle: Extraer valores únicos (IDs de proveedores, productos, etc.)
- Diseño de generadores por tabla: Productos, Proveedores, Clientes, Pedidos, Detalles de pedido, Inventario
- Mantenimiento de relaciones: Asegurar integridad referencial
- Exportación a CSV: Archivos por tabla listos para carga

##  Fase 4: Carga de Datos en PostgreSQL (Día 7)
- Script de carga: Uso de `COPY` o `pandas.to_sql()`
- Manejo de errores: Logging y validación de integridad
- Verificación: Queries de comprobación de relaciones

##  Fase 5: API con FastAPI (Día 8-10)
- Conexión a PostgreSQL: Configuración de base de datos con SQLAlchemy
- Modelos Pydantic: Definición de schemas para las entidades
- Endpoints básicos: CRUD para las tablas principales
- Endpoints analíticos: Consultas relevantes para la IA (ej. stock crítico, tendencias de ventas)