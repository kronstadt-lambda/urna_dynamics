#!/bin/bash

# 1. Obtener la ruta del venv de Poetry
VENV_PATH=$(poetry env info --path)

# 2. Ruta de paquetes
PYTHON_PACKAGES="$VENV_PATH/lib/python3.13/site-packages"

# 3. Raíz del proyecto (Ejecutas desde la raíz)
PROJECT_ROOT=$(pwd)

# 4. Exportar PYTHONPATH
export PYTHONPATH="$PYTHON_PACKAGES:$PROJECT_ROOT/src"

# 5. Ejecutar Blender
blender -b -P "$PROJECT_ROOT/src/simulations/ejecutar_experimento.py"