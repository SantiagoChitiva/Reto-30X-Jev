# Integración con HubSpot

30X usa HubSpot como CRM. Esta es la propuesta de cómo se conecta 30X Pulse. El código está en `backend/app/hubspot.py` y `backend/app/crm.py`.

```
HubSpot (contactos y deals)
   │  webhooks: contacto creado, propiedad cambiada, deal con etapa nueva
   ▼
POST /webhooks/hubspot  →  eventos de Pulse  →  JEV decide (solo categorías anónimas)
   │
   ▼
Propiedades pulse_* del contacto en HubSpot  →  workflows de HubSpot (avisar a ventas, enviar el programa)
```

## 1. ID único de cada persona

El **ID del contacto en HubSpot**: en Pulse la persona es `hs_<id>`. Es estable, no cambia si la persona cambia de correo y ya existe en cada evento de HubSpot.

**Ese ID nunca sale hacia JEV.** JEV solo recibe las categorías anónimas del perfil (rol, objetivo, dolor, intereses, etapa) y las señales ya calculadas en código. Sin nombre, correo, teléfono ni ID (`pipeline.build_state`; lo cubre un test).

## 2. Entrada: webhooks

| Evento de HubSpot | Lo que hace Pulse |
|---|---|
| `contact.creation` | `signup`: crea la persona con su perfil |
| `contact.propertyChange` de una propiedad del perfil | `profile_update` con ese campo |
| `contact.propertyChange` de `hs_email_last_open_date` | `email_open` |
| `contact.propertyChange` de `ultimo_evento_asistido_30x` | `attendance` (la llena la integración de Luma con HubSpot) |
| `deal.creation` o `deal.propertyChange` de `dealstage` | `profile_update` del contacto asociado: pasa a «Deal en el CRM» y toma la etapa |
| Cualquier otra propiedad | Se ignora |

- Si un contacto aparece por primera vez, Pulse lee su perfil con la API y lo da de alta.
- HubSpot reintenta los webhooks: los eventos repetidos (mismo `eventId`) se ignoran.
- Cada webhook se valida con la firma `X-HubSpot-Signature-v3` y se rechaza si tiene más de 5 minutos.

### Propiedades del perfil

Los nombres internos de abajo son una propuesta. Si en el HubSpot de 30X se llaman distinto, se cambian con `HUBSPOT_PROPERTY_MAP` en `.env`, sin tocar código.

| Propiedad de HubSpot | Campo en Pulse | Columna del Excel |
|---|---|---|
| `relacion_30x` | `relation` | Relación con 30X |
| `estado_crm_30x` | `crm_status` | Estado CRM |
| `etapa_crm_30x` | `crm_stage` | Etapa CRM |
| `programa_30x` | `program` | Programa |
| `rol_30x` | `role` | Rol |
| `country` | `country` | País |
| `dolor_30x` | `pain` | Dolor |
| `objetivo_30x` | `objective` | Objetivo |
| `intereses_30x` (casillas, separadas por `;`) | `interests` | Temas de interés |
| `nivel_info_30x` | `info_level` | Nivel de información |
| `info_disponible_30x` | `info_available` | Información disponible |

Las etapas del pipeline de deals se traducen con `HUBSPOT_DEAL_STAGES`, por ejemplo `{"123456": "Calificado"}`.

## 3. Salida: propiedades del contacto

Cada decisión automática, prudente o resuelta por una persona se escribe en el contacto (grupo **30X Pulse**). Las prudentes nunca marcan `pulse_lista_para_ventas`, así que ningún workflow avisa a ventas con un caso dudoso:

| Propiedad | Valor |
|---|---|
| `pulse_segmento` | `fundador_ventas`, `fundador_escala`, `lider_comercial`, `ejecutivo_ia`, `perfil_tecnico`, `explorador`, `otro` |
| `pulse_programa_sugerido` | `ai_sales`, `inmersion_ejecutiva`, `sales_machine`, `hardcore_ai`, `achievers`, `nutricion`, `otro` |
| `pulse_lista_para_ventas` | sí / no |
| `pulse_madurez_ia` | `baja`, `media`, `alta` |
| `pulse_confianza` | de 0 a 1 |
| `pulse_decidido_por` | `jev`, `jev_por_confirmar`, `humano` |
| `pulse_ultima_accion` | `notify_sales`, `send:<programa>` o vacío |
| `pulse_actualizado` | fecha y hora |

Solo se llama a HubSpot si cambió algo que ventas ve, para no gastar el límite de la API. Si HubSpot falla, la decisión igual queda en la tabla `crm_profiles`.

**Pulse no envía correos ni asigna vendedores**: eso lo hacen los workflows de HubSpot que 30X ya usa. Por ejemplo:

- Cuando `pulse_lista_para_ventas` pasa a sí → crear una tarea para el dueño del contacto y avisarle.
- Cuando `pulse_programa_sugerido` cambia → inscribir al contacto en la secuencia o el correo de ese programa.

Así 30X mantiene el control de qué se envía y cuándo.

## 4. Puesta en marcha

1. En HubSpot: **Configuración → Integraciones → Apps privadas → Crear app**, con los permisos `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.deals.read` y `crm.schemas.contacts.write`.
2. Copiar el token y el secreto de la app a `.env` (`HUBSPOT_TOKEN` y `HUBSPOT_CLIENT_SECRET`).
3. Crear las propiedades `pulse_*`: `docker compose exec backend python -m app.hubspot crear-propiedades`.
4. En la app, pestaña **Webhooks**: URL `https://<dominio-de-pulse>/webhooks/hubspot` y suscripciones a `contact.creation`, `contact.propertyChange` (las propiedades de la tabla de arriba), `deal.creation` y `deal.propertyChange` (`dealstage`).
5. Crear los workflows de la sección 3.
6. Las dos primeras semanas, con `HUBSPOT_SYNC=false` (modo sombra): Pulse decide y guarda en `crm_profiles`, el equipo compara en el tablero y no se escribe nada en HubSpot.

## Probar sin HubSpot

```bash
curl -X POST localhost:8000/webhooks/hubspot -H "content-type: application/json" \
  -d '[{"eventId":1,"subscriptionType":"contact.propertyChange","objectId":555,"propertyName":"rol_30x","propertyValue":"Fundador, socio o CEO"}]'
curl localhost:8000/crm/hs_555
```
