# Frontend de Control Plane

Interfaz React y TypeScript con Vite. Results (`/results`) sigue siendo público;
las áreas de usuario y administración requieren su sesión habitual.

## Desarrollo y comprobaciones

Desde `frontend/`:

```bash
npm run dev
npm test
npm run build
```

Las pruebas automatizadas de `tests/results.test.mjs` ejecutan el helper real de
búsqueda y ordenación: filtros combinados, búsqueda sin distinguir mayúsculas,
valores positivos/negativos/cero, datos nulos al final y conservación del payload.
No necesitan dependencias adicionales a las del frontend.

## Interfaz

- Paleta oscura grafito y cian, controles de al menos 44 px y navegación accesible.
- Results muestra el resumen global antes de las cuentas. Los filtros afectan solo
  a las cuentas; el resumen sigue incluyendo todas las cuentas y modos.
- Por debajo de 768 px las cuentas son tarjetas; desde 768 px se usa una tabla.
  El detalle se abre junto a una sola cuenta, con métricas avanzadas plegables.
- TradingView aparece después de las cuentas, cerrado inicialmente. No hay cambios
  en endpoints, autenticación o cálculos del backend.
- Results actualiza cada 30 segundos, admite actualización manual y conserva los
  últimos datos si falla una actualización, mostrando un aviso y reintento.
- Dashboard, operaciones, historial, controles, ajustes, login y administración
  comparten estilos y etiquetas en español. Las confirmaciones operativas se mantienen.

El rediseño se verificó en Chromium con APIs interceptadas y datos simulados a
320, 390, 768 y 1440 px, incluyendo expansión, teclado, carga, listas vacías,
bots desconectados, errores de actualización, login y formularios. Las operaciones
de prueba no llegaron al backend; también se comprobó que cancelar confirmaciones
de dinero real evita el envío de la petición.

## Marca y favicon

Generado con la herramienta integrada `imagegen`; no se usó la API/CLI de fallback.
El original se conserva en `public/brand-trading.png`. Las cabeceras usan la copia
de 256 px `public/brand-trading-256.png`. Las versiones derivadas son
`public/favicon-16.png`, `public/favicon-32.png` y `public/apple-touch-icon.png` (180 px),
enlazadas desde `index.html`. ImageMagick solo se usó para reducir los tamaños.

Prompt utilizado:

> Use case: logo-brand. Create one final square favicon image for Control Plane, a
> trading bot monitoring application. A single bold geometric cyan ascending chart
> symbol, like a thick stepped rising line ending in a simple upward diagonal,
> centered on a solid graphite (#10151c) square background. Cyan #35c9db. Extremely
> simple flat graphic, thick strokes and generous negative space, recognize at
> 16x16 pixels. Fill about 70% of the square with the symbol. No text, letters,
> numbers, border, mockup, extra panels, shadows, gradients, glow or photographic
> texture. Single icon only, crisp clean edges.
