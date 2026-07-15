# Primera prueba con dinero real (Binance)

Guía para el primer live. Sigue los pasos en orden: cada uno valida algo que el anterior
no puede.

> **No hay testnet, y no es un olvido.** Freqtrade no soporta cuentas sandbox por diseño
> (`docs/faq.md`) y desactiva el testnet de Binance a propósito (`supports_demo_trading:
> False` — *"a separate market, not a simulated live market"*). **El dry-run ES el ensayo**:
> corre contra precios y libros de órdenes reales. Lo único que el dry-run no puede validar
> es la fontanería real (claves, permisos, órdenes, comisiones), y para eso está esta prueba.

**Qué cuesta esta prueba.** El tope duro es 25 USDT, pero ese no es el coste esperado. Con
`stake=15`, `max_open_trades=1` y stoploss `-10%`, el peor caso realista de una operación
es perder **~1,5 USDT** más unos 0,03 de comisiones. No estás arriesgando 25; estás
arriesgando el stoploss de una sola posición.

---

## 0. Comprobar que el VPS alcanza Binance (bloqueante)

Binance bloquea por **país del servidor** y por rangos de datacenter. Si el VPS está
bloqueado, nada de lo demás funciona: la API REST de Freqtrade solo arranca *después* de
cargar los mercados, así que el bot ni levantaría.

**Desde el VPS** (no desde tu portátil):

```bash
curl -o /dev/null -w '%{http_code}\n' https://api.binance.com/api/v3/ping   # espera 200
```

- `200` → adelante.
- `451` → ese host no puede operar con Binance. No hay configuración que lo arregle.

> Tu VPS (`173.249.10.101`, Contabo, Lauterbourg, Francia) no está en la lista de países
> bloqueados de Binance (Canadá, Malasia, Países Bajos, EEUU). Aun así, compruébalo: la
> lista cambia.

---

## 1. Crear la clave API en Binance

En Binance → API Management → Create API:

| Ajuste | Valor | Por qué |
| --- | --- | --- |
| Tipo de clave | **HMAC-SHA256** | Una clave RSA/Ed25519 funciona en Freqtrade pero **no se puede verificar** automáticamente; la sonda la rechazará pidiéndote una HMAC. |
| Enable Spot & Margin Trading | **ON** | Sin esto la clave se rechaza al guardarla (`canTrade: false`). |
| Enable Withdrawals | **OFF** | Un bot de trading nunca necesita retirar. Si está activo, el panel te avisa. |
| Restrict access to trusted IPs | **`173.249.10.101`** | Aunque te roben la clave, no sirve fuera del VPS. |

Guarda el **secret** al crearla: Binance no vuelve a mostrarlo.

---

## 2. Depositar

Deposita **~30 USDT** (el tope es 25; el resto es margen para comisiones y para que el
mínimo del par nunca te pille justo).

El `MIN_NOTIONAL` de Binance es **5 USDT** en los pares principales (BTC, ETH, SOL, XRP,
ADA, LINK), así que un stake de 15 es holgado.

---

## 3. Guardar la clave en el panel

Como **admin** → usuario → *Exchange credentials*:

1. Exchange: `binance` (es la única opción).
2. Pega key y secret → **Save & inject**.

La clave se verifica contra Binance **antes** de guardarse. Qué esperar:

| Respuesta | Significado |
| --- | --- |
| **200** + `Verified — X USDT available` | Todo bien. Ese saldo confirma que el depósito llegó. |
| **422** | Binance rechazó la clave. **No es saltable**: está mal, revocada, sin permiso de trading, o la IP no coincide. |
| **503** | No se pudo *alcanzar* Binance (timeout, 451, reloj desincronizado). Eso no dice nada de la clave: te ofrece guardarla sin verificar. |

> Prueba a poner un secret mal a propósito una vez: debes ver un 422 con el mensaje del
> propio Binance. Así sabes que la verificación está viva.

---

## 4. Ensayo en dry-run — **no te lo saltes**

Como **usuario** → *Settings*:

1. **Elige una estrategia que NO sea "Off".** ⚠️ La estrategia por defecto es `off`: arranca
   el bot y **no abre ninguna operación jamás** (`enter_long = 0` siempre). Es un default
   seguro, pero si vas a live con ella no pasará nada y parecerá que está roto.
2. Pares: deja `BTC/USDT`.
3. Guarda.

Como usuario → *Controls* → **Start**. ⚠️ El bot arranca con `initial_state: stopped`: el
contenedor corre pero el bucle de trading está parado hasta que le das a Start.

**Déjalo correr hasta ver abrir y cerrar operaciones.** Ese es el ensayo de la estrategia.
Si en dry-run no opera, en live tampoco.

> **Ojo, hay dos "Start" distintos.** El del panel de **admin** arranca el *contenedor*
> (docker start). El de **Controls** del usuario arranca el *bucle de trading* de Freqtrade.
> Necesitas el segundo.

---

## 5. Configurar la prueba live (todavía en dry-run)

Como usuario → *Settings*, con el bot **aún en dry-run**:

| Campo | Valor |
| --- | --- |
| Stake amount | `15` |
| Max open trades | `1` |
| Pares | solo `BTC/USDT` |
| Stoploss | `-0.10` |

Guarda. **Tiene que ser antes de pasar a live**: el valor por defecto es `"unlimited"`, y
el servidor se niega a ir a live con eso (en live significaría la cartera entera). Si
intentas ir a live sin fijar un número, verás un **409** explicándolo.

---

## 6. Pasar a LIVE

Como **admin** → usuario → **Go LIVE** → confirma.

Luego, como usuario → *Controls* → **Start** otra vez. ⚠️ Al pasar a live el contenedor se
**recrea**, así que vuelve a `initial_state: stopped`.

Verás el badge rojo **LIVE** en Dashboard, Settings y Controls.

---

## 7. Verificar la primera orden real

**En el historial de órdenes de Binance**, no en la UI del bot. Es la única fuente que no
depende del código que estamos probando.

Comprueba que la orden existe, que el importe es ~15 USDT, y que el par es el que elegiste.

También útil:

```bash
docker logs -f cp-bot-<usuario>     # en el VPS
```

---

## 8. Cómo abortar

| Situación | Qué hacer |
| --- | --- |
| Quiero parar de operar ya | Usuario → *Controls* → **Stop** (para el bucle; las posiciones abiertas siguen abiertas en Binance). |
| Quiero volver a simulación | Admin → **Back to dry-run**. |
| Emergencia / clave comprometida | Admin → **Delete credentials**. Fuerza dry-run y recrea el contenedor con la clave vacía. **Las posiciones abiertas se quedan en Binance** — ciérralas tú a mano. |
| Pánico total | Revoca la clave en Binance. El bot deja de poder operar en el acto. |

> Ninguna de estas opciones vende tus posiciones. Cerrar una posición abierta es siempre
> una decisión tuya, en el bot (*Trades* → forceexit) o en Binance.

---

## Las barreras que te protegen

Son **dos, independientes**. Si una fallara, la otra aguanta:

1. **El control plane rechaza** ajustes inseguros: nada de `"unlimited"`, stake por
   operación entre `CP_LIVE_MIN_STAKE` (10) y `CP_LIVE_MAX_CAPITAL` (25), y
   `stake × max_open_trades` nunca por encima de 25. Rechaza, no recorta en silencio.
2. **Freqtrade se limita a sí mismo**: el config generado lleva `available_capital = 25`,
   y Freqtrade calcula el capital desplegable como `available_capital + beneficio cerrado`,
   **ignorando tu saldo real**. Aunque tengas 500 USDT en la cuenta, el bot solo puede
   mover 25.

Cuando quieras operar más fuerte, sube `CP_LIVE_MAX_CAPITAL` en `backend/.env` y reinicia
el control plane.

---

## Errores típicos

| Síntoma | Causa |
| --- | --- |
| El bot no abre ninguna operación | La estrategia es `off` (default), o no le diste a **Start** en Controls. |
| `409` al dar a Go LIVE | El stake sigue en `"unlimited"`, o `stake × max_open_trades` pasa de 25. El mensaje lo dice. |
| `422` al guardar ajustes en live | Superas el tope de exposición. Baja stake o max open trades. |
| `422` al guardar la clave | Binance la rechaza: mal copiada, revocada, sin Spot Trading, o la IP allowlist no incluye al VPS. |
| `503` al guardar la clave | El control plane no alcanza Binance. Necesita salida a `api.binance.com`. |
| El bot no levanta / `/ping` falla | Casi siempre el exchange inalcanzable desde el VPS (paso 0). Mira `docker logs cp-bot-<usuario>`. |
| El campo *Dry-run wallet* está gris | Correcto: en live Freqtrade lo ignora y usa tu saldo real de Binance. |

---

## Lo que NO funciona (a día de hoy)

**El botón *Force entry* fallará en live.** El config generado lleva
`force_entry_enable: False`, así que Freqtrade responde `Force_entry not enabled.`
(`rpc.py:1137`). Es una incoherencia preexistente entre la UI y el config, **no** algo que
esta prueba haya roto.

No es un problema para esta prueba —de hecho el default es el seguro, porque force entry
coloca una orden real saltándose la estrategia—, pero conviene saberlo: si quieres provocar
una orden a mano para probar, no puedes por ahí. Deja que la estrategia entre sola.

---

## Resumen en una pantalla

```
0. curl api.binance.com/api/v3/ping   DESDE EL VPS      -> 200
1. Clave HMAC: Spot Trading ON, Withdrawals OFF, IP 173.249.10.101
2. Depositar ~30 USDT
3. Admin  -> Save & inject          -> "Verified — 30 USDT"
4. User   -> Settings: estrategia != Off   -> Controls: START   (ensayo dry-run)
5. User   -> Settings: stake 15, max open 1, BTC/USDT   (aún en dry-run)
6. Admin  -> Go LIVE                -> User -> Controls: START otra vez
7. Verificar la orden EN BINANCE, no en la UI del bot
```
