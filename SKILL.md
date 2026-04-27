---
name: wapu-cli
description: Operar el CLI `wapu` de WapuPay desde terminal para autenticación, configuración local, balances, depósitos Lightning y crypto, inspección/cancelación/cotización de transacciones, direct payments, transferencias internas, retiros ARS y crypto, contactos, estado de API token, perfil/settings/referrals de usuario y troubleshooting. Usar cuando el usuario pida ejecutar o explicar `wapu ...`, gestionar credenciales Wapu, consultar datos de cuenta, crear instrucciones de fondeo o realizar movimientos de dinero Wapu desde la línea de comandos.
---

# Wapu CLI Skill

Operar WapuPay desde terminal. Usar esta skill para flujos de **usuario/operador**, no para desarrollar el proyecto Python.

La sintaxis autoritativa sale del CLI instalado y de `src/wapu_cli/cli.py`; ante duda, ejecutar `wapu <grupo> --help` o `uv run wapu <grupo> --help` antes de un comando con efectos.

## Reglas operativas

- No imprimir, repetir ni persistir secretos del usuario en la respuesta.
- Preferir `--json` o `--output json` para automatización; usar salida table por defecto para resúmenes humanos.
- Antes de acciones monetarias o destructivas, confirmar datos faltantes o ambiguos: monto, alias/dirección, red, receptor, transaction id, tentative id y backend.
- Tratar estos comandos como side-effectful: creación de depósitos, retiros, direct payment create/funding/create-and-fund, transferencia interna, borrar contacto, cancelar transacción, auth login/logout y updates de perfil/settings.
- No usar `--access-token` y `--api-key` juntos; el CLI rechaza auth mixta.
- Recordar que `--password`, `--api-key` y `--access-token` inline pueden quedar en historial de shell o process lists. Preferir variables de entorno o un contexto shell efímero cuando sea posible.
- Backend default: `https://be-prod.wapu.app`, salvo override explícito.

## Pre-check rápido

```bash
wapu --help
wapu auth status
```

Si `wapu` no está en PATH, usar invocación local de desarrollo:

```bash
uv run wapu --help
```

## Configuración y salida

Precedencia de configuración:

1. flags del comando
2. variables de entorno / `.env`
3. config guardada en `~/.config/wapu-cli/config.json`

Variables soportadas:

```bash
WAPU_API_BASE_URL
WAPU_ACCESS_TOKEN
WAPU_API_KEY
```

Flags globales:

```bash
wapu --output json <comando>
wapu --output yaml <comando>
wapu --output table <comando>
wapu --json <comando>
wapu --yaml <comando>
wapu --quiet <comando>
wapu --api-base-url https://be-prod.wapu.app <comando>
wapu --access-token "..." <comando>
wapu --api-key "..." <comando>
```

Usar sólo un selector de salida: `--output`, `--json` o `--yaml`.

## Autenticación

Guardar una API key:

```bash
wapu auth login --api-key "<api_key>"
```

Login con email/password. Comportamiento actual del CLI: hace login, crea un API token y guarda esa API key localmente en vez de guardar el JWT:

```bash
wapu auth login --email "<email>" --password "<password>"
```

Inspeccionar estado local sin revelar el token completo:

```bash
wapu auth status
```

Borrar credenciales locales:

```bash
wapu auth logout
```

Inspeccionar metadata del API token:

```bash
wapu api-token status
```

## Consultas read-only de cuenta

Balance:

```bash
wapu balance
wapu --json balance
```

Lightning Address para recibir fondos:

```bash
wapu deposit lightning address
```

Límite de gasto:

```bash
wapu user spending-limit
```

Referral link, opcionalmente con datos del destinatario:

```bash
wapu user referral
wapu user referral --email friend@example.com --phone 5491155556666
```

Perfil y settings:

```bash
wapu user profile get
wapu user settings get
```

## Depósitos

Crear invoice/instrucciones de depósito Lightning:

```bash
wapu deposit lightning create --amount 10 --currency SAT
```

Crear depósito crypto on-chain:

```bash
wapu deposit crypto --amount 100 --currency USDT --network POLYGON
```

Monedas crypto permitidas: `USDT`, `USDC`.
Redes crypto permitidas: `ETHEREUM`, `BSC`, `POLYGON`, `ARBITRUM`, `OPTIMISM`, `TRON`.

## Transacciones

Listar transacciones:

```bash
wapu tx list
wapu --json tx list
```

Obtener una transacción por id:

```bash
wapu tx get <transaction_id>
```

Cancelar una transacción:

```bash
wapu tx cancel <transaction_id>
```

Si el usuario quiere saber cual es el equivalente en dolares para hacer una transferecia puede usar Previsualizar/cotizar monto tentativo de una transferencia:

```bash
wapu tx tentative-amount \
  --amount 10000 \
  --currency-payment ARS \
  --currency-taken USDT \
  --type fiat_transfer
```

- `--currency-payment`: `ARS`, `BRL`, `USD`
- `--currency-taken`: `USDT`, `SAT`
- `--type`: tipo backend, por ejemplo `fiat_transfer` o `fast_fiat_transfer`

Crear transferencia interna a otro usuario Wapu:

```bash
wapu tx inner-transfer --amount 10 --currency USDT --receiver-username johndoe
```

## Direct fiat payment

Usar direct payment cuando el usuario quiera crear un payout fiat fondeado por Lightning o USDT con instrucciones de fondeo.

Crear una tentative con quote congelada:

```bash
wapu tx direct-payment create \
  --amount-ars 25000 \
  --type fiat_transfer \
  --alias juan.perez.alias \
  --receiver-name "Juan Perez" \
  --funding-method LIGHTNING \
  --network LIGHTNING
```

Emitir instrucciones de fondeo para una tentative existente:

```bash
wapu tx direct-payment funding <tentative_uuid>
```

Crear tentative y emitir fondeo inmediatamente:

```bash
wapu tx direct-payment create-and-fund \
  --amount-ars 25000 \
  --type fast_fiat_transfer \
  --alias juan.perez.alias \
  --receiver-name "Juan Perez" \
  --funding-method USDT \
  --network POLYGON
```

Restricciones direct-payment:

- `--type`: `fiat_transfer` o `fast_fiat_transfer`
- `--funding-method`: `LIGHTNING` o `USDT`
- `--network`: `LIGHTNING`, `ETHEREUM`, `POLYGON` o `ARBITRUM`
- Si `--funding-method LIGHTNING`, usar `--network LIGHTNING`.
- Si `--funding-method USDT`, usar una red EVM (`ETHEREUM`, `POLYGON` o `ARBITRUM`), no `LIGHTNING`.

Luego del fondeo, inspeccionar ids devueltos con:

```bash
wapu tx get <deposit_transaction_id>
wapu tx get <executed_transaction_id>
```

## Retiros

Crear retiro ARS usando balance USDT:

```bash
wapu withdraw ars \
  --type fiat_transfer \
  --alias "tu.alias" \
  --amount 100 \
  --receiver-name "Nombre"

wapu withdraw ars \
  --type fast_fiat_transfer \
  --alias "tu.alias" \
  --amount 100
```

- `--type`: `fiat_transfer` o `fast_fiat_transfer`
- `--alias` y `--amount` son requeridos
- `--receiver-name` es opcional para el CLI, pero puede ayudar en conciliación

Crear retiro crypto:

```bash
wapu withdraw crypto \
  --address TCZ7Gm6gmZhAFLLZWT12XwNLRwaWaxcVqA \
  --network TRON \
  --currency USDT \
  --amount 25 \
  --receiver-name "Jane Doe"
```

El retiro crypto usa las mismas monedas/redes que el depósito crypto.

## Contactos

Listar contactos:

```bash
wapu contacts list
wapu contacts list --filter-type favourite
wapu contacts list --filter-type recent
```

Marcar/desmarcar favorito:

```bash
wapu contacts favourite <contact_id> --value true
wapu contacts favourite <contact_id> --value false
```

Borrar un contacto:

```bash
wapu contacts delete <contact_id>
```

### Como diferenciar y usar contactos
- Los contactos que tienen bank_alias sirven para hacer fiat_transfer y fast_fiat_transfer en ARS (pesos Argentinos).
- Los contactos que tienen wallet_address y network son para hacer retiros via Blockchain en USDT.
- Los contactos que tienen en network Wapu Users son para hacer inner_transfer en USDT.

## Updates de usuario

Actualizar perfil; proveer al menos un campo:

```bash
wapu user profile update \
  --username newusername \
  --telegram my_telegram_handle \
  --phone 5491155556666 \
  --beta-version beta
```

Actualizar settings; proveer al menos un campo:

```bash
wapu user settings update --language ES
wapu user settings update --beta-version --favourite-currency ARS
wapu user settings update --no-beta-version
```

- `--language`: `EN`, `ES`, `PT`
- `--favourite-currency`: `USD`, `ARS`, `BRL`

## Troubleshooting

### Comando no encontrado

```bash
which wapu
uv run wapu --help
```

Instalar para uso normal:

```bash
uv tool install wapu
```

Ejecutar sin instalación global:

```bash
uvx wapu --help
```

### Sin autenticación

```bash
wapu auth status
wapu auth login --api-key "<api_key>"
wapu auth status
```

### Backend incorrecto

```bash
wapu auth status
wapu --api-base-url https://be-prod.wapu.app balance
```

Para stage/local, hacer override explícito:

```bash
wapu --api-base-url https://be-stage.wapu.app <comando>
wapu --api-base-url http://127.0.0.1:8000 <comando>
```

### Sintaxis exacta

```bash
wapu --help
wapu deposit --help
wapu deposit lightning --help
wapu tx direct-payment create --help
wapu user settings update --help
wapu withdraw crypto --help
```

### Errores backend

- Exit code `2`: validación local, bad request o not found.
- Exit code `3`: problema de auth/permisos.
- Exit code `4`: rate limit.
- Exit code `1`: red/backend/JSON inválido o error genérico.

Al reportar fallos, resumir categoría de comando, exit code y mensaje backend; no incluir secretos.

## Checklist de verificación para agentes

Antes de dar una operación por completada:

1. Ejecutar `wapu auth status` o confirmar que env/flags explícitos aportan credenciales.
2. Confirmar backend objetivo.
3. Para acciones side-effectful, verificar monto, destino, red y transaction/tentative id.
4. Preferir `--json` y parsear ids/statuses devueltos para follow-up.
5. Usar `wapu tx get <id>` luego de depósitos, retiros, direct payments o cancelaciones cuando se devuelva un id.
