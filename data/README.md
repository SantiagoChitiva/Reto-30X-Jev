# Datos

Todo sale del Excel de ejemplo que compartió 30X (`perfiles-30x-anonimo.xlsx`): 697 personas que llegaron a 30X (298 con deal en el CRM y 399 leads), descritas solo con categorías. No hay nombres, correos ni empresas.

| Archivo | Qué es |
|---|---|
| `build_profiles.py` | Convierte el Excel en los dos JSON. Solo usa la librería estándar. |
| `perfiles_30x.json` | Los 697 perfiles. La simulación parte de ellos. |
| `labeled_set.json` | 200 perfiles con etiquetas de referencia: el examen de JEV. |
| `eval_results.json` | Lo genera `python -m app.evaluate`. Lo devuelve `GET /evaluation`. |

Para regenerarlos:

```bash
python data/build_profiles.py "ruta/a/perfiles-30x-anonimo.xlsx"
```

## Columnas

| Excel | Clave | Notas |
|---|---|---|
| Relación con 30X | `relation` | Lead (sin deal) o Deal en el CRM |
| Estado, Etapa en el CRM | `crm_status`, `crm_stage` | |
| Programa | `program` | Programa en el que está o con el que llegó |
| Rol | `role` | Solo existe para deals |
| País, Dolor principal, Objetivo principal | `country`, `pain`, `objective` | |
| Temas de interés | `interests` | Lista |
| Nivel de info, Información disponible | `info_level`, `info_available` | |
| Programa sugerido, Afinidad | `ref.suggested_program`, `ref.affinity` | **Nunca se le pasan a JEV**: son la respuesta del examen |

"Sin dato", "—" y "No declaró ningún dolor" se guardan como `null`.

## Etiquetas del set (`labeled_set.json`)

La muestra de 200 se reparte por programa sugerido y banda de afinidad, en la misma proporción que el Excel.

- `content_ref`: el **programa sugerido por 30X** (sin programa → `nutricion`). Es una etiqueta real.
- `sales_ready_ref`: afinidad ≥ 7. Es una aproximación: según 30X, la afinidad mide si la persona encaja con el perfil de cada programa (los perfiles están en 30x.com/programas), no si ya quiere hablar con ventas.
- `segment_ref`: **borrador por reglas** (rol + objetivo + dolor + temas, función `reference_segment`). Falta revisarlo a mano. Al revisar un caso, corrige la etiqueta si hace falta y pon `"revisado": true`.

Ojo: el JEV simulado usa reglas parecidas a `reference_segment`, así que su precisión en `segment` sale inflada. Esa cifra solo vale con JEV real y las etiquetas revisadas.

Según la hoja *Notas* del Excel, rol, dolor y objetivo coinciden con 220 perfiles clasificados a mano en un 81 %, 55 % y 55 %. Sirven para ver proporciones, no como dato exacto de cada persona.
