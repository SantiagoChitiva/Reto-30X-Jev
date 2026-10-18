# Guion del pitch — 30X Pulse

Unos 5 minutos de pitch y 1 de demo. La idea es contar una historia: una persona que llega a 30X, por qué hoy se enfría sin que nadie lo note y cómo la resolvemos con lo que 30X ya tiene. Lo técnico va solo en la slide 5, y en lenguaje simple.

Deck: el playbook en Artifacts (8 slides). Las notas de cada slide traen este mismo texto.

| # | Slide | Tiempo | Quién |
|---|---|---|---|
| 1 | Portada | 0:15 | [persona] |
| 2 | La historia | 0:50 | [persona] |
| 3 | El problema | 0:40 | [persona] |
| 4 | La solución | 0:40 | [persona] |
| 5 | Cómo decide | 0:40 | [persona] |
| 6 | Integración | 0:45 | [persona] |
| 7 | Resultados y quién lo opera | 0:40 | [persona] |
| — | Demo en vivo | 1:00 | [persona] |
| 8 | Por qué nosotros | 0:30 | [persona] |

---

## 1. Portada (0:15)

> Hola, somos 10x. Les vamos a contar la historia de una persona que llega a 30X, por qué hoy se enfría sin que nadie lo note y cómo 30X Pulse lo resuelve con lo que 30X ya tiene.

## 2. La historia (0:50)

> Les presento a una fundadora. Es un ejemplo, pero cada dato sale de las categorías del Excel que nos compartió 30X.
>
> El día 1 se inscribe a una clase gratis de ventas. De ella solo sabemos que quiere vender más. El día 8 asiste y abre tres correos sobre ventas con IA. El día 15, en un formulario, cuenta que es dueña de su empresa y que vende sin proceso. El día 20 está lista para Sales Machine.
>
> ¿Qué pasa hoy? Sigue en el segmento con el que llegó el día 1, recibe el mismo boletín que todos y nadie de ventas se entera. Cuando alguien por fin la llama, ya se enfrió.

*Pausa corta antes de la última frase.*

## 3. El problema (0:40)

> Y no es una persona. 30X tiene unas 32.300 personas en su base. En la muestra, el 73 % llega sin rol y el 85 % no ha contado su dolor: el perfil se completa señal a señal.
>
> Hoy hay tres caminos, y ninguno sirve. Las reglas fijas no se enteran de que la persona cambió. Revisar cada señal a mano no escala. Y pasar todo por un LLM es lento y caro para algo que se repite miles de veces.
>
> Lo que le cuesta a 30X: oportunidades que se enfrían y mensajes que no le hablan a nadie.

## 4. La solución (0:40)

> 30X Pulse hace una cosa: cada vez que pasa algo, vuelve a mirar a la persona y actualiza su ficha.
>
> La misma fundadora. El día 1 es exploradora y le llega contenido gratuito. El día 8 se nota el interés en IA y se le sugiere AI Sales. El día 15 sabemos que es fundadora y vende sin proceso: cambia a Sales Machine. El día 20, ventas recibe el aviso con el programa que le sirve.
>
> Nadie revisó nada a mano, y cada decisión tomó milisegundos.

## 5. Cómo decide (0:40)

> En cada señal, Pulse hace cuatro preguntas simples: quién es, qué tan avanzada está en IA, si está lista para ventas y qué programa le sirve. Solo puede responder con programas que 30X vende de verdad.
>
> Cada respuesta trae qué tan segura está. Como un semáforo: si está muy segura, actúa sola, pero antes revisa que no sea spam. Si duda, un LLM revisa y explica. Si no sabe, decide una persona.
>
> El motor es JEV. No escribe textos: responde preguntas cerradas, por eso es rápido y barato. Los LLM piensan, JEV decide.

## 6. Integración (0:45)

> Lo más importante para 30X: no hay que cambiar nada de lo que ya tienen.
>
> Pulse recibe las señales que ya existen (inscripciones, asistencias, correos, formularios y etapas del CRM) por una sola entrada. Y escribe el resultado en la ficha de cada persona: segmento, programa sugerido, si está lista para ventas y quién lo decidió. Es la misma columna «Programa sugerido» que ya usan.
>
> Hoy la ficha vive en una base de datos, como nos pidió el CTO. Cuando se conecte al CRM real, solo cambia un módulo.
>
> El plan son tres semanas: conectar, correr en modo sombra para que el equipo compare y encender lo automático.

## 7. Resultados y quién lo opera (0:40)

> Lo probamos con 10.000 señales sobre los perfiles de 30X. El 68 % de las decisiones sale solo, y esas aciertan el 95 % de las veces. Las dudosas son justo las que van a un LLM o a una persona. Comparado con un LLM para todo, es más de 4 veces más barato y 16 veces más rápido.
>
> Ventas recibe la lista, contenido es dueño del tono, una persona resuelve cerca del 5 % de casos dudosos y tech revisa cada semana cuánto acierta.

*Si preguntan: las cifras son con JEV simulado. Con la llave de JEV real se corre el mismo comando (`python -m app.evaluate`) y se actualizan.*

## Demo en vivo (1:00)

1. Abrir el tablero y pulsar **Simular 10.000**.
2. Señalar el **feed en vivo**: cada fila es una señal, con su decisión y su ruta.
3. Señalar el **Sankey**: «así se mueven las personas entre segmentos mientras llegan señales».
4. Bajar a **Listas para ventas en el CRM**: «esto es lo que ve el equipo comercial, con el programa sugerido y quién lo decidió».
5. Resolver un caso en la **cola humana** y mostrar que aparece en la ficha del CRM con «Persona».

*Plan B si falla la red: un video corto de la demo grabado antes.*

## 8. Por qué nosotros (0:30)

> Hay tres caminos. Las reglas fijas son baratas, pero no cambian con la persona. Un LLM para todo entiende el cambio, pero es caro, lento y no avisa cuando duda. 30X Pulse cambia con la persona, cuesta poco, sabe cuándo no sabe y solo ofrece lo que 30X vende.
>
> Y está hecho con los datos y los programas reales de 30X, ya funciona y cada semana medimos cuánto acierta.
>
> Los LLM piensan, JEV decide. Gracias.

---

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Cómo se conecta con nuestro CRM? | Por un solo módulo de salida (`backend/app/crm.py`). Hoy escribe en una tabla con los mismos campos; para el CRM real se cambia ese módulo y nada más. |
| ¿Qué datos necesita? | Las categorías que ya tienen: rol, objetivo, dolor, intereses, etapa del CRM y las señales (inscripciones, asistencias, correos). Sin nombres ni datos personales. |
| ¿Y si JEV se equivoca? | Si no está segura, no actúa: lo revisa un LLM o una persona. Y cada semana medimos cuánto acierta contra perfiles etiquetados. |
| ¿Puede mandar spam? | No. Hay un freno en código: la misma acción no se repite si ya salió en las últimas 3 decisiones de la persona. Además, JEV revisa que la oferta sea apropiada antes de actuar. |
| ¿Por qué no usar solo Gemini o ChatGPT? | Para decisiones repetitivas es más de 4 veces más caro y 16 veces más lento, y no dice cuándo duda. El LLM lo usamos solo para los casos dudosos. |
| ¿Cómo se compara con la afinidad que ya calculan? | Mide lo mismo, si la persona encaja con el perfil de cada programa, pero se recalcula con cada señal. Comparamos contra su «Programa sugerido» para medir el acierto. |
| ¿Cuánto cuesta operarlo? | Unos 4 centavos de dólar por cada 1.000 decisiones con JEV. Corre en un contenedor, en cualquier nube. |

Antes del pitch, completar quién dice cada parte. Repositorio: https://github.com/SantiagoChitiva/Reto-30X-Jev. Cuando esté desplegado, agregar la URL del tablero a la última slide.
