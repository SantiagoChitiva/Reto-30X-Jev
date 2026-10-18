# Guion del pitch — 30X Pulse

**3 minutos máximo.** Son unas 385 palabras: a ritmo normal dan unos 2:45, sin correr. La idea es contar una historia: una persona que llega a 30X, por qué hoy se enfría sin que nadie lo note y cómo lo resolvemos con lo que 30X ya tiene. Lo técnico va solo en la slide 5, en una frase.

Deck: el playbook en Artifacts (8 slides). Las notas de cada slide traen este mismo texto.

| # | Slide | Tiempo | Acumulado | Quién |
|---|---|---|---|---|
| 1 | Portada | 0:05 | 0:05 | [persona] |
| 2 | La historia | 0:30 | 0:35 | [persona] |
| 3 | El problema | 0:20 | 0:55 | [persona] |
| 4 | La solución | 0:25 | 1:20 | [persona] |
| 5 | Cómo decide | 0:25 | 1:45 | [persona] |
| 6 | Integración | 0:30 | 2:15 | [persona] |
| 7 | Resultados | 0:20 | 2:35 | [persona] |
| 8 | Por qué nosotros | 0:20 | 2:55 | [persona] |

La demo en vivo no cabe en 3 minutos: se muestra en las preguntas o cuando los jurados pasen por la mesa (ver abajo).

---

## 1. Portada (0:05)

> Somos 10x, y esto es 30X Pulse.

## 2. La historia (0:30)

> Una fundadora se inscribe a una clase gratis de 30X. Solo sabemos que quiere vender más. Una semana después asiste y abre tres correos sobre ventas con IA. Luego cuenta en un formulario que es dueña y que vende sin proceso. El día 20 está lista para Sales Machine.
>
> ¿Qué pasa hoy? Sigue en el segmento con el que llegó, le llega el mismo boletín que a todos y ventas no se entera. Se enfría.

## 3. El problema (0:20)

> Y no es una persona: son 32.300. El 73 % llega sin rol y el 85 % sin contar su dolor. Las reglas fijas no ven el cambio, revisar a mano no escala y un LLM para todo es lento y caro.

## 4. La solución (0:25)

> 30X Pulse mira a la persona cada vez que pasa algo y actualiza su ficha. La misma fundadora: primero recibe contenido gratis, luego se le sugiere AI Sales, después Sales Machine. El día 20, ventas recibe el aviso con el programa justo. Nadie revisó nada a mano.

## 5. Cómo decide (0:25)

> En cada señal hace cuatro preguntas: quién es, qué tan avanzada está en IA, si está lista para ventas y qué programa le sirve, solo entre los que 30X vende. Si está segura, actúa sola. Si duda, la revisa un LLM. Si no sabe, decide una persona. El motor es JEV: responde en milisegundos. Los LLM piensan, JEV decide.

## 6. Integración (0:30)

> Y no hay que cambiar nada de lo que 30X ya tiene. Cuando algo cambia en HubSpot, nos llega por webhook, y Pulse escribe en la misma ficha del contacto: segmento, programa sugerido y si está lista para ventas. Sus workflows de HubSpot deciden qué enviar y a quién avisar. JEV solo ve categorías anónimas, nunca nombres ni correos. En tres semanas: conectar, probar en modo sombra y encender.

## 7. Resultados (0:20)

> Con 10.000 señales sobre perfiles de 30X, el 68 % de las decisiones sale solo y acierta el 95 %. Es casi 7 veces más barato y 16 veces más rápido que un LLM. Una persona solo ve cerca del 5 % de los casos.

## 8. Por qué nosotros (0:20)

> Las reglas no cambian con la persona; un LLM es caro y no avisa cuando duda. Pulse cambia con ella, cuesta poco, sabe cuándo no sabe y está hecho con los datos reales de 30X. Ya funciona. Los LLM piensan, JEV decide. Gracias.

---

## Para ensayar

- Cronometrar dos veces seguidas. Si pasa de 2:55, recortar primero la slide 3: las cifras ya se ven en pantalla.
- Pasar de slide al terminar la frase, sin pausas largas.
- Las cifras son con JEV simulado. Si preguntan: «con la llave de JEV real se corre el mismo comando y se actualizan».

## Demo (en preguntas o en la mesa, 1 minuto)

1. Abrir el tablero y pulsar **Simular 10.000**.
2. **Feed en vivo:** cada fila es una señal, con su decisión y su ruta.
3. **Sankey:** así se mueven las personas entre segmentos.
4. **Listas para ventas en el CRM:** lo que ve el equipo comercial.
5. Resolver un caso de la **cola humana** y mostrar que aparece en la ficha con «Persona».

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Cómo se conecta con HubSpot? | Entrada por webhooks de HubSpot (contacto creado, propiedad cambiada, deal con etapa nueva). Salida en propiedades `pulse_*` del contacto, que disparan sus workflows. Guía en `docs/HubSpot.md`. |
| ¿Qué datos salen de 30X? | A JEV solo le llegan categorías anónimas (rol, objetivo, dolor, intereses, etapa) y conteos. Nunca nombres, correos ni el ID de HubSpot. |
| ¿Cuál es el ID de cada persona? | El ID del contacto en HubSpot. Es estable aunque cambie el correo, y se queda dentro de Pulse. |
| ¿Y si JEV se equivoca? | Si no está segura, no actúa: lo revisa un LLM o una persona. Y cada semana medimos cuánto acierta contra perfiles etiquetados. |
| ¿Puede mandar spam? | No. Hay un freno en código: la misma acción no se repite si ya salió en las últimas 3 decisiones de la persona. Además, JEV revisa que la oferta sea apropiada antes de actuar. |
| ¿Por qué no usar solo ChatGPT? | Para decisiones repetitivas es casi 7 veces más caro y 16 veces más lento, y no dice cuándo duda. El LLM lo usamos solo para los casos dudosos. |
| ¿Cómo se compara con la afinidad que ya calculan? | Mide lo mismo, si la persona encaja con el perfil de cada programa, pero se recalcula con cada señal. Comparamos contra su «Programa sugerido» para medir el acierto. |
| ¿Cuánto cuesta operarlo? | Unos 4 centavos de dólar por cada 1.000 decisiones con JEV. Corre en un contenedor, en cualquier nube. |

Antes del pitch, completar quién dice cada parte. Repositorio: https://github.com/SantiagoChitiva/Reto-30X-Jev. Cuando esté desplegado, agregar la URL del tablero a la última slide.
