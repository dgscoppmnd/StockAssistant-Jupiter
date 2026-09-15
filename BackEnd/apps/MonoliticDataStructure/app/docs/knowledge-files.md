# Archivos de conocimiento

La página **Base de conocimiento** permite adjuntar o sustituir un TXT, PDF o MD
al crear o editar un registro. Límite: 20 MB; TXT y MD deben usar UTF-8.
Los campos de título, contenido y fuente mantienen su obligatoriedad.

`public.knowledge_documents.archivo` contiene el nombre relativo del archivo,
con un prefijo UUID para evitar sobrescrituras. Los registros anteriores tienen
este campo a NULL. La inicialización del backend aplica automáticamente
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS archivo TEXT` a bases existentes.

Dockerfile crea `/app/data/knowledge` y declara el volumen. Docker Compose lo
monta desde `BackEnd/apps/MonoliticDataStructure/app/data/knowledge`, por lo que
los archivos persisten al recrear el contenedor y son accesibles desde Windows.
Se pueden copiar TXT, PDF y MD directamente a esa carpeta para una futura
ingesta. Copiar un archivo local no crea automáticamente un registro en SQL.

API autenticada (mismas credenciales que los maestros):

- `POST /api/master-data/knowledge-documents/with-file`
- `PUT /api/master-data/knowledge-documents/{id}/with-file`

Ambas reciben multipart con `values` (objeto JSON con los metadatos) y `file`
(opcional). Si una actualización no incluye archivo, conserva el anterior.
El nombre se asigna en el servidor. Los archivos anteriores se conservan al
sustituir la referencia o eliminar un registro, evitando borrar fuentes locales.
No se ejecuta indexación ni generación de embeddings al guardar.

Tras actualizar, recrear el backend con Docker Compose para aplicar la
declaración explícita del volumen. El montaje existente de `data` también
permite acceder a la misma carpeta sin recrearlo.
