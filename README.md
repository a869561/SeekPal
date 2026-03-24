## NOMBRE DEL DOCUMENTO: README.md
## AUTOR: Adrián Nasarre
## FECHA DE CREACIÓN: 2026-03-24
## ÚLTIMA MODIFICACIÓN: 2026-03-24
## VERSIÓN: 1.0.0
## DESCRIPCIÓN:
Documentación principal del proyecto. Describe objetivo, alcance técnico, estructura
de carpetas, comandos de ejecución local y en contenedores, endpoints base y próximos
pasos para evolucionar la solución hacia un buscador semántico empresarial completo.

# Buscador Inteligente Documental (Base MVC)

## Objetivo del proyecto
Base de arquitectura para una aplicacion web de busqueda inteligente sobre repositorios documentales empresariales.

Incluye:
- API Node.js + Express con MVC modular.
- Autenticacion JWT.
- Endpoints para busqueda semantica, filtros, historial y analitica.
- Capa de conectores (local, S3, Google Drive como placeholder).
- Cola de ingestion con Redis + BullMQ.
- Persistencia de documentos en S3 (o MinIO en local).

## Estructura
```text
src/
  app.js
  server.js
  config/
  controllers/
  jobs/
  middlewares/
  repositories/
  routes/
  services/
  utils/
docs/
  architecture.md
```

## Arranque local
1. Copiar `.env.example` a `.env` y completar variables.
2. Instalar dependencias:
   ```bash
   npm install
   ```
3. Ejecutar en desarrollo:
   ```bash
   npm run dev
   ```

## Arranque con Docker
```bash
docker compose up --build
```

## Endpoints base
- `GET /health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/search/query`
- `POST /api/search/ingest`
- `GET /api/history`
- `GET /api/analytics/summary`
- `GET /api/connectors`

## Siguientes pasos recomendados
1. Sustituir repositorios en memoria por base de datos (PostgreSQL o MongoDB).
2. Implementar un microservicio Python para embeddings con SentenceTransformers.
3. Integrar parser real de PDF/Word/HTML en el worker de ingestion.
4. Implementar frontend (React/Vue) consumiendo esta API.

