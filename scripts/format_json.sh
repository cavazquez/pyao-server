#!/bin/bash

# Encuentra todos los archivos .json en el directorio map_data/
find map_data/ -name "*.json" | while read -r file; do
    echo "Formateando: $file"
    
    # Leer el archivo completo
    content=$(cat "$file")
    
    # Extraer el array principal (asumiendo que es el último elemento)
    array_content=$(echo "$content" | jq -c '.[-1]')
    
    # Reconstruir el archivo con el array formateado
    {
        # Imprimir todo excepto el último elemento
        echo "$content" | jq -c '.[:-1][]'
        # Imprimir el array formateado
        echo "$array_content" | jq -c '.[]'
        # Cerrar el array
        echo "]"
    } > "${file}.tmp"
    
    # Verificar si el archivo ya tiene el formato correcto
    if diff -q "$file" "${file}.tmp" > /dev/null; then
        echo "  Ya tiene el formato correcto"
        rm -f "${file}.tmp"
    else
        # Si el archivo no está vacío después de formatear, reemplazarlo
        if [ -s "${file}.tmp" ]; then
            mv "${file}.tmp" "$file"
            echo "  Formateado correctamente"
        else
            echo "  Error: El archivo está vacío después de formatear"
            rm -f "${file}.tmp"
        fi
    fi
done

echo "Proceso completado"