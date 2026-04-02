#!/bin/bash

# 1. Obtener la ruta del venv de Poetry
VENV_PATH=$(poetry env info --path)

# 2. Raíz del proyecto (Asume que ejecutas desde la raíz)
PROJECT_ROOT=$(pwd)

# 3. Exportar PYTHONPATH para que Python encuentre la carpeta src si es necesario
export PYTHONPATH="$PROJECT_ROOT/src"

echo "Iniciando cálculo de validacion de modelo..."

# 4. Ejecutar el script usando el Python del entorno virtual (sin Blender)
"$VENV_PATH/bin/python" "$PROJECT_ROOT/src/validation/ejecutar_analisis_forense.py"