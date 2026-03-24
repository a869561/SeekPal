# /*******************************************************************************
# NOMBRE DEL DOCUMENTO: Dockerfile
# AUTOR: Adrián Nasarre
# FECHA DE CREACIÓN: 2026-03-24
# ÚLTIMA MODIFICACIÓN: 2026-03-24
# VERSIÓN: 1.0.0
#
# DESCRIPCIÓN:
# Define la imagen de ejecución para la API Node.js, instala dependencias de producción,
# copia el código fuente y expone el puerto de servicio para despliegue en contenedores.
# *******************************************************************************/
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY . .

EXPOSE 3000

CMD ["npm", "start"]

