# Especificación de Datos para Visualización de Grafo

**Endpoint**: `GET /api/graph-data`
**Autenticación**: Requerida (Token Bearer)

## Estructura de Respuesta

El endpoint retorna un objeto JSON con dos arrays principales: `nodes` y `edges`. Este formato está optimizado para librerías de visualización de grafos como **Vis.js** o **React Force Graph**.

### 1. Nodes (Nodos)
Representan las entidades del sistema.

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `id` | string | Identificador único compuesto (ej: `inv_1`, `wp_2`, `proj_10`). |
| `label` | string | Texto visible en el nodo (Nombre corto o truncado). |
| `group` | string | Categoría para agrupar y estilizar (`investigator`, `wp`, `nodo`, `project`). |
| `value` | number | Tamaño relativo del nodo, calculado en el backend basado en el número de conexiones. |
| `title` | string | Texto completo para mostrar en tooltip (hover). |
| `color` | string | Color HEX predefinido por el backend. |
| `shape` | string | (Opcional) Forma del nodo (ej: `circle`, `box`). |
| `data` | object | Metadatos adicionales (`type`, `nombre` completo) para uso en lógica de UI (ej: modales). |

#### Grupos y Estilos (Definidos en Backend)
- **investigator** (Investigadores)
  - Color: `#e2e8f0` (Gris claro)
  - Tamaño: Basado en conexiones.
- **wp** (Working Packages)
  - Color: `#818cf8` (Indigo)
  - Forma: `circle`
  - Fuente: Tamaño 18, Blanca.
- **nodo** (Nodos Temáticos)
  - Color: `#67e8f9` (Cyan)
  - Forma: `box`
- **project** (Proyectos)
  - Color: `#6ee7b7` (Verde esmeralda)
  - Tamaño: Doble peso por conexión.

### 2. Edges (Conexiones)
Representan las relaciones entre entidades.

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `from` | string | ID del nodo origen. |
| `to` | string | ID del nodo destino. |
| `color` | object | Configuración de color (`color`, `opacity`). |
| `width` | number | Grosor de la línea. `2` para Investigadores Responsables, `1` para otros. |
| `dashes` | boolean | `true` si es una relación punteada (ej: Proyecto -> Nodo Temático). |
| `hidden` | boolean | (Opcional) `true` si la arista debe estar oculta inicialmente (configuración actual para algunos investigadores). |

## Ejemplo de Respuesta JSON

```json
{
  "nodes": [
    {
      "id": "inv_15",
      "label": "Maria Gonzalez",
      "group": "investigator",
      "title": "Maria Gonzalez (Conexiones: 3)",
      "value": 3,
      "color": "#e2e8f0",
      "data": { "type": "Investigador", "nombre": "Maria Gonzalez" }
    },
    {
      "id": "wp_2",
      "label": "WP 2",
      "title": "Gobernanza de Datos",
      "group": "wp",
      "shape": "circle",
      "color": "#818cf8",
      "value": 10
    },
    {
      "id": "proj_101",
      "label": "Estudio de Impacto Ambiental...",
      "title": "Estudio de Impacto Ambiental en Zonas Costeras",
      "group": "project",
      "color": "#6ee7b7",
      "value": 4
    }
  ],
  "edges": [
    {
      "from": "proj_101",
      "to": "wp_2",
      "color": { "color": "#a5b4fc", "opacity": 0.5 },
      "width": 2
    },
    {
      "from": "proj_101",
      "to": "inv_15",
      "color": { "color": "#fca5a5", "opacity": 0.8 },
      "width": 2,
      "hidden": true
    }
  ]
}
```

## Recomendaciones de Implementación Frontend

1.  **Librería**: Los datos están formateados casi nativamente para **Vis.js**. Si usas otra librería (como React Flow o D3), necesitarás mapear `from`/`to` a `source`/`target`.
2.  **Interactividad**:
    *   Usa el campo `data` para mostrar detalles en un panel lateral o modal al hacer clic en un nodo.
    *   El campo `title` ya viene listo para ser usado como tooltip nativo del navegador o de la librería.
3.  **Filtrado**:
    *   Puedes filtrar nodos en el cliente usando la propiedad `group`.
    *   Las aristas tienen una propiedad `hidden` que el backend envía; asegúrate de respetarla o manejar la visibilidad de aristas en el cliente si quieres mostrar todo.
