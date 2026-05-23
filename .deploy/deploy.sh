#!/bin/bash
# Despliegue automático de Asesora TS

PROJECT_DIR="/home/jota-server/projects/asesora-ts/asesora-ts/"

echo "Iniciando despliegue en $PROJECT_DIR"
cd "$PROJECT_DIR" || { echo "Error: No se encontro el directorio $PROJECT_DIR"; exit 1; }

echo "Bajando contenedores..."
docker compose down

echo "Obteniendo ultimos cambios de GitHub..."
git pull origin main

echo "Reconstruyendo y levantando contenedores..."
docker compose up -d --build

echo "Despliegue finalizado."
