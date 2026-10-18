# Guion del pitch — 30X Pulse

**3 minutos, una sola persona, con la demo adentro.** Son unas 430 palabras: a ritmo ágil dan unos 2:55, contando la demo. Se cuenta como una historia y en palabras de todos los días; lo técnico queda para las preguntas.

- Deck (playbook, 7 slides): https://claude.ai/artifact/QXTucVVub9vPUwPrzzXHwE. Las notas de cada slide traen este texto.
- Tablero en vivo: https://reto-30-x-jev.vercel.app
- Código: https://github.com/SantiagoChitiva/Reto-30X-Jev

| # | Qué se ve | Tiempo | Acumulado |
|---|---|---|---|
| 1 | Slide: Portada | 0:05 | 0:05 |
| 2 | Slide: La historia y el problema | 0:35 | 0:40 |
| 3 | Slide: La solución | 0:20 | 1:00 |
| — | **Demo en vivo: el tablero** | 0:40 | 1:40 |
| 4 | Slide: Cómo decide | 0:25 | 2:05 |
| 5 | Slide: HubSpot | 0:20 | 2:25 |
| 6 | Slide: Resultados y quién lo opera | 0:15 | 2:40 |
| 7 | Slide: Por qué nosotros | 0:15 | 2:55 |

Las slides 4, 5 y 6 son el playbook que pide el reto: las decisiones de JEV, las preguntas, los umbrales, quién lo opera y cómo se mide.

## Antes de subir al escenario

1. Unos 10 minutos antes, en Railway, limpiar la base (consulta en `docs/Despliegue.md`) y pulsar **Simular 10.000** en el tablero, para que tenga datos cuando lo muestres.
2. Dejar abiertas dos pestañas: el deck en pantalla completa y el tablero. Se cambia entre ellas con **Alt + Tab**.
3. Plan B, por si falla internet: un video de 40 segundos del tablero, grabado antes.

---

## 1. Portada (0:05)

> Hola, soy [nombre], del equipo 10x, y les presento 30X Pulse.

## 2. La historia y el problema (0:35)

> Empiezo con una historia. Una fundadora se inscribe a una clase gratis de 30X; de ella solo sabemos que quiere vender más. Una semana después asiste y abre tres correos sobre ventas con IA. Y el día 15 cuenta que es dueña y que vende sin proceso: está lista para comprar.
>
> ¿Y qué pasa hoy? Nada. Sigue en el mismo grupo, recibe el mismo boletín y ventas no se entera. Ahora multipliquen eso por 32.300 personas: cada una que se enfría es una venta que 30X pierde.

## 3. La solución (0:20)

> Por eso creamos 30X Pulse. Cada vez que pasa algo, Pulse vuelve a mirar a la persona y actualiza su ficha. La pasamos por JEV real, señal por señal: los primeros días recibe contenido gratis, y el día 15, apenas cuenta su problema, ventas recibe el aviso con Sales Machine.

## Demo en vivo (0:40)

*Cambiar al tablero con Alt + Tab y pulsar **Simular 10.000**.*

> Y esto no es una maqueta: está funcionando, con JEV real. Pulso simular y empiezan a llegar señales. Cada fila es una decisión: quién es la persona, qué programa le sirve y qué camino tomó.

*Señalar el reparto por ruta.*

> Casi seis de cada diez salen solas.

*Bajar al diagrama de flujos.*

> Aquí se ve a la gente cambiar de grupo a medida que la conocemos mejor.

*Bajar a «Listas para ventas en el CRM».*

> Y esto es lo que ve ventas: las personas listas, con su programa. Los casos dudosos quedan aquí abajo, para que el equipo los resuelva.

## 4. Cómo decide (0:25)

*Volver al deck con Alt + Tab.*

> ¿Y cómo decide? JEV, el motor del reto, responde cuatro preguntas cerradas: quién es, qué tan avanzada está en IA, si está lista para ventas y qué programa le sirve. Luego nuestro código pone las reglas, como un semáforo: si está segura de quién es, actúa sola; si duda, manda contenido gratis; si no sabe, decide una persona. Y para avisar a ventas exige todavía más certeza.

## 5. HubSpot (0:20)

> Además, se conecta al HubSpot que ya usan. Cuando algo cambia en HubSpot, Pulse se entera al instante y escribe en la misma ficha del contacto. Sus automatizaciones hacen el resto, y a JEV nunca le llegan nombres ni correos. El plan son tres semanas: conectar, probar en paralelo y encender.

## 6. Resultados y quién lo opera (0:15)

> ¿Y cuánto cuesta? Con JEV real, unos siete centavos de dólar por cada mil decisiones, cuatro veces menos que una IA como ChatGPT. Ventas recibe la lista y el equipo solo revisa los casos dudosos.

## 7. Por qué nosotros (0:15)

> En resumen: las reglas fijas no cambian con la persona, y una IA para todo es cara y no avisa cuando duda. Pulse cambia con cada persona, cuesta centavos y ya funciona con los datos de 30X. Los LLM piensan, JEV decide. Gracias.

---

## Para ensayar

- Cronometrar dos veces seguidas, con la demo incluida. Si pasa de 2:55, recortar primero la demo: basta con el feed y la lista de ventas.
- Los conectores marcan el paso de slide: «Por eso…», «Y esto no es una maqueta…», «¿Y cómo decide?», «Además…», «¿Y cuánto cuesta?», «En resumen…». Al terminar cada uno, pasar de slide.
- Las cifras salen de JEV real: el costo y el «6 de cada 10» se midieron en el tablero y en la evaluación. El «4 veces más barato» compara con una estimación de gpt-4o-mini, no con una llamada real.

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿El 57 % automático del tablero es bueno? | Sí. Hoy no hay nada automático: cada cambio de una persona depende de que alguien lo vea. Con Pulse, cerca de 6 de cada 10 decisiones salen solas, otras 3 son prudentes (contenido gratis) y solo 1 de cada 10 llega a una persona. Además es a propósito: lo automático solo actúa con 85 % de certeza, y el umbral se puede bajar cuando haya más perfiles revisados. |
| ¿Cómo saben que acierta? | Con 200 perfiles del Excel y JEV real. El programa que sugiere coincide con el que sugiere 30X en el 42 % de los casos. La etiqueta de «quién es» todavía es un borrador hecho con reglas, así que el siguiente paso es que el equipo revise esos perfiles a mano y repetir la medición. |
| ¿Qué son los «mensajes repetidos evitados»? | Cada persona manda varias señales seguidas (se inscribe, asiste, abre correos). Pulse no le repite el mismo mensaje cada vez: es el freno que evita saturar a la audiencia de 30X. |
| ¿La historia de la fundadora la hizo el sistema? | Sí. La pasamos por JEV real, señal por señal: los días 1 y 8 la ubica como exploradora con contenido gratis, y el día 15 la pasa a «fundadora que quiere vender», sugiere Sales Machine y avisa a ventas, con el visto bueno del guardrail. |
| ¿Cómo se conecta con HubSpot? | Entrada por webhooks de HubSpot (contacto creado, propiedad cambiada, deal con etapa nueva). Salida en propiedades `pulse_*` del contacto, que disparan sus workflows. Guía en `docs/HubSpot.md`. |
| ¿Qué datos salen de 30X? | A JEV solo le llegan categorías anónimas (rol, objetivo, dolor, intereses, etapa) y conteos. Nunca nombres, correos ni el ID de HubSpot. |
| ¿Cuál es el ID de cada persona? | El ID del contacto en HubSpot. Es estable aunque cambie el correo, y se queda dentro de Pulse. |
| ¿Y si JEV se equivoca? | Si no está segura de quién es, no se arriesga: manda contenido gratuito o le pasa el caso a una persona. Avisar a ventas exige además 85 % de certeza, contexto en el perfil y el visto bueno de JEV. |
| ¿Puede mandar spam? | No. Hay un freno en código: la misma acción no se repite si ya salió en las últimas 3 decisiones de la persona. |
| ¿Por qué no usar ChatGPT u otro LLM? | Para decisiones repetitivas es unas 4 veces más caro y varias veces más lento (estimado), y no dice cuándo duda. Además, 30X pidió evitar modelos externos. |
| ¿Cuándo entra una persona? | Solo cuando JEV no sabe quién es (cerca de 1 de cada 10) o al resolver la cola. Para enviar contenido no hace falta y se gana velocidad. |
| ¿Qué hace el modelo y qué el código? | JEV solo responde preguntas cerradas con una probabilidad. El código (el harness) cuenta las señales, aplica los umbrales, frena el spam, exige contexto para avisar a ventas y decide cuándo entra una persona. |
| ¿Usan un LLM? | No. La única llamada externa es JEV, con categorías anónimas. Si 30X lo aprueba, más adelante un LLM podría revisar los casos dudosos. |
| ¿De dónde sale el 32.300? | De la hoja «Notas» del Excel de 30X: unas 24.800 personas con deal y 7.500 leads. Los porcentajes (73 % sin cargo, 85 % sin dolor) son de la muestra de 697. |
| ¿Cuánto cuesta operarlo? | Unos 7 centavos de dólar por cada 1.000 decisiones, medido con JEV real. Corre en un contenedor, en cualquier nube. |
