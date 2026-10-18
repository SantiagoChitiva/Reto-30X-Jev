# Guion del pitch — 30X Pulse

**3 minutos máximo.** Son unas 400 palabras: a ritmo normal dan unos 2:50, sin correr. La idea es contar una historia: una persona que llega a 30X, por qué hoy se enfría sin que nadie lo note y cómo lo resolvemos con lo que 30X ya tiene. Se cuenta en palabras de todos los días: nada de «LLM», «webhook» ni «segmento» al hablar. Lo técnico va solo en la slide 5, en una frase, y en las preguntas.

Deck: el playbook en Artifacts (8 slides), https://claude.ai/artifact/QXTucVVub9vPUwPrzzXHwE. Las notas de cada slide traen este mismo texto.

Tablero en vivo: https://reto-30-x-jev.vercel.app

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
> ¿Qué pasa hoy? Sigue en el grupo con el que llegó, le llega el mismo boletín que a todos y ventas no se entera. Se enfría.

## 3. El problema (0:20)

> Y no es una persona: son 32.300. Tres de cada cuatro llegan sin decir su cargo, y casi ninguna cuenta su problema al principio. Nadie alcanza a seguirlas una por una, y cada persona que se enfría es una venta que 30X pierde.

## 4. La solución (0:25)

> 30X Pulse mira a cada persona cada vez que pasa algo y actualiza su ficha. La misma fundadora: primero recibe contenido gratis, luego se le sugiere AI Sales, después Sales Machine. El día 20, ventas recibe el aviso con el programa justo. Nadie tuvo que revisar nada a mano.

## 5. Cómo decide (0:25)

> JEV, el motor del reto, responde cuatro preguntas: quién es, qué tan avanzada está en IA, si está lista para ventas y qué programa le sirve. Las reglas las pone nuestro código: si sabe quién es, actúa sola; si duda, manda contenido gratis; si no sabe, decide una persona. Y para avisar a ventas exige más certeza.

## 6. Integración (0:30)

> Y no hay que cambiar nada de lo que 30X ya tiene. Cuando algo cambia en HubSpot, Pulse se entera al instante y escribe en la misma ficha del contacto: quién es, qué programa le sirve y si está lista para ventas. Las automatizaciones que ya usan en HubSpot hacen el resto, y a JEV nunca le llegan nombres ni correos. En tres semanas: conectar, probar en paralelo y encender.

## 7. Resultados (0:20)

> Lo probamos con JEV real sobre perfiles de 30X. Seis de cada diez decisiones salen solas y aciertan quién es la persona el 99 % de las veces; solo 1 de cada 10 necesita a alguien del equipo. Y es 4 veces más barato y 7 veces más rápido que usar una IA como ChatGPT.

## 8. Por qué nosotros (0:20)

> Las reglas fijas no cambian con la persona, y una IA como ChatGPT es cara y no avisa cuando duda. Pulse cambia con cada persona, cuesta centavos, sabe cuándo no sabe y ya funciona con los datos reales de 30X. Los LLM piensan, JEV decide. Gracias.

---

## Para ensayar

- Cronometrar dos veces seguidas. Si pasa de 2:55, recortar primero la slide 3: las cifras ya se ven en pantalla.
- Pasar de slide al terminar la frase, sin pausas largas.
- Las cifras son con JEV real sobre 200 perfiles etiquetados del Excel. Si preguntan por las etiquetas: el programa sugerido es el de 30X; el segmento es un borrador por reglas que falta revisar a mano.

## Demo (en preguntas o en la mesa, 1 minuto)

1. Abrir el tablero y pulsar **Simular 10.000**.
2. **Feed en vivo:** cada fila es una señal, con su decisión y su ruta.
3. **Sankey:** así se mueven las personas entre segmentos.
4. **Listas para ventas en el CRM:** lo que ve el equipo comercial.
5. Resolver un caso de la **cola humana** y mostrar que aparece en la ficha con «Persona».

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿El 57 % automático del tablero es bueno? | Sí. Hoy no hay nada automático: cada cambio de una persona depende de que alguien lo vea. Con Pulse, cerca de 6 de cada 10 decisiones salen solas, otras 3 son prudentes (contenido gratis) y solo 1 de cada 10 llega a una persona. Además es a propósito: lo automático solo actúa con 85 % de certeza, y el umbral se puede bajar cuando haya más perfiles revisados. |
| ¿Qué son los «mensajes repetidos evitados»? | Cada persona manda varias señales seguidas (se inscribe, asiste, abre correos). Pulse no le repite el mismo mensaje cada vez: es el freno que evita saturar a la audiencia de 30X. |
| ¿Cómo se conecta con HubSpot? | Entrada por webhooks de HubSpot (contacto creado, propiedad cambiada, deal con etapa nueva). Salida en propiedades `pulse_*` del contacto, que disparan sus workflows. Guía en `docs/HubSpot.md`. |
| ¿Qué datos salen de 30X? | A JEV solo le llegan categorías anónimas (rol, objetivo, dolor, intereses, etapa) y conteos. Nunca nombres, correos ni el ID de HubSpot. |
| ¿Cuál es el ID de cada persona? | El ID del contacto en HubSpot. Es estable aunque cambie el correo, y se queda dentro de Pulse. |
| ¿Y si JEV se equivoca? | Si no está segura de quién es, no se arriesga: manda contenido gratuito o le pasa el caso a una persona. Avisar a ventas exige además 85 % de certeza y el visto bueno de JEV. Y cada semana medimos cuánto acierta contra perfiles etiquetados. |
| ¿Puede mandar spam? | No. Hay un freno en código: la misma acción no se repite si ya salió en las últimas 3 decisiones de la persona. Además, JEV revisa que la oferta sea apropiada antes de actuar. |
| ¿Por qué no usar ChatGPT u otro LLM? | Para decisiones repetitivas es más de 4 veces más caro y unas 7 veces más lento, y no dice cuándo duda. Además, 30X pidió evitar modelos externos. |
| ¿Cuándo entra una persona? | Solo cuando JEV no sabe quién es (cerca de 1 de cada 10) o al resolver la cola. Para enviar contenido no hace falta y se gana velocidad. Para avisar a ventas, el código exige 85 % de certeza, contexto en el perfil y el visto bueno de JEV. |
| ¿Qué hace el modelo y qué el código? | JEV solo responde preguntas cerradas con una probabilidad. El código (el harness) cuenta las señales, aplica los umbrales, frena el spam, exige contexto para avisar a ventas y decide cuándo entra una persona. |
| ¿Usan un LLM? | No. La única llamada externa es JEV, con categorías anónimas. Si 30X lo aprueba, más adelante un LLM podría revisar los casos dudosos. |
| ¿Cómo se compara con la afinidad que ya calculan? | Mide lo mismo, si la persona encaja con el perfil de cada programa, pero se recalcula con cada señal. Comparamos contra su «Programa sugerido» para medir el acierto. |
| ¿Cuánto cuesta operarlo? | Unos 6 centavos de dólar por cada 1.000 decisiones con JEV (medido con JEV real). Corre en un contenedor, en cualquier nube. |

Antes del pitch, completar quién dice cada parte. Repositorio: https://github.com/SantiagoChitiva/Reto-30X-Jev. Tablero en vivo: https://reto-30-x-jev.vercel.app.
