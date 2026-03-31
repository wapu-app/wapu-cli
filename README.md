# Wapu CLI
## Qué es 

`wapu-cli` es una interfaz de línea de comandos para integrar depósitos por Lightning y retiros fiat desde herramientas, scripts y flujos automatizados. Está pensada para developers, operadores y equipos que quieran conectar productos sobre Bitcoin/Lightning con una experiencia real de entrada y salida para usuarios finales.

El problema que resuelve es reducir la fricción en la adopción de Lightning, permitiendo mover valor entre el ecosistema Lightning y moneda local de manera simple, programable y utilizable desde software. En ese sentido, el proyecto funciona como un puente para builders que ya están construyendo sobre Lightning/Bitcoin y necesitan una vía práctica de off-ramp para sus usuarios.

La propuesta se apoya directamente en Lightning como parte central del flujo:

- permite crear depósitos Lightning
- expone la Lightning Address del usuario para recibir fondos
- habilita automatización y operación desde terminal, scripts y agentes

## Alcance y arquitectura

Este CLI consume el backend para resolver problemas que incluye operaciones con dinero fiat, ejecución de retiros, escrow entre el P2P y el usuario. 

La idea del proyecto es ofrecer una interfaz simple y programable sobre ese flujo, de forma que nuevos productos puedan integrar depósitos Lightning y retiros ARS sin tener que reinventar la operación completa. Aportando valor en la experiencia de integración que habilita para el ecosistema Lightning.

## Instalación

Instalación recomendada para uso normal:

```bash
uv tool install wapu
```

Luego puedes usar directamente:

```bash
wapu --help
```

También puedes correrlo de forma efímera sin instalarlo globalmente:

```bash
uvx wapu --help
```

## Desarrollo local

Si quieres clonar el repositorio y trabajar sobre el código:

```bash
uv venv
uv sync --dev
```

Luego puedes usar:

```bash
uv run wapu --help
uv run python -m wapu_cli --help
```

## Configuración

Precedencia de configuración:

1. flags del comando
2. variables de entorno
3. credenciales guardadas en `~/.config/wapu-cli/config.json`

Variables soportadas:

- `WAPU_API_BASE_URL`
- `WAPU_ACCESS_TOKEN`
- `WAPU_API_KEY`

Backend de test por default:

```text
https://be-prod.wapu.app
```

## Auth

Guardar una API key:

```bash
wapu auth login --api-key '...'
```

Guardar un JWT:

```bash
wapu auth login --email you@example.com --password '...'
```

Ver estado local:

```bash
wapu auth status
```

Borrar credenciales:

```bash
wapu auth logout
```

## Comandos

Balance:

```bash
wapu balance
```

Crear depósito Lightning:

```bash
wapu deposit lightning create --amount 10 --currency SAT
```

Crear depósito on-chain:

```bash
wapu deposit crypto --amount 100 --currency USDT --network POLYGON
```

Obtener la Lightning address:

```bash
wapu deposit lightning address
```

Listar transacciones:

```bash
wapu tx list
```

Obtener una transacción:

```bash
wapu tx get 2b753493-687b-431f-8d85-f9b4cb99199e
```

Cancelar una transacción:

```bash
wapu tx cancel 2b753493-687b-431f-8d85-f9b4cb99199e
```

Cotizar monto tentativo:

```bash
wapu tx tentative-amount --amount 10000 --currency-payment ARS --currency-taken USDT --type fiat_transfer
```

Transferencia interna:

```bash
wapu tx inner-transfer --amount 10 --currency USDT --receiver-username johndoe
```

Crear retiro ARS:

```bash
wapu withdraw ars --type fiat_transfer --alias test.alias --amount 100 --receiver-name 'Test Receiver'
wapu withdraw ars --type fast_fiat_transfer --alias test.alias --amount 100
```

Crear retiro crypto:

```bash
wapu withdraw crypto --address TCZ7Gm6gmZhAFLLZWT12XwNLRwaWaxcVqA --network TRON --currency USDT --amount 25 --receiver-name 'Jane Doe'
```

Contactos:

```bash
wapu contacts list
wapu contacts list --filter-type favourite
wapu contacts favourite 1 --value true
wapu contacts delete 1
```

API token:

```bash
wapu api-token status
```

Usuario:

```bash
wapu user spending-limit
wapu user referral
wapu user referral --email friend@example.com --phone 5491155556666
wapu user profile get
wapu user profile update --username newusername --telegram my_telegram_handle
wapu user settings get
wapu user settings update --language ES --beta-version --favourite-currency ARS
```

## Salida

Formatos:

```bash
wapu --json balance
wapu --yaml balance
wapu --output json balance
wapu --output yaml balance
wapu --output table tx list
```

Modo silencioso:

```bash
wapu --quiet balance
```

## Tests

```bash
uv run pytest
```

## Smoke Test Manual

Para correr un smoke test real del CLI contra stage usando comandos `uv run wapu ...`, usa:

```bash
uv run python scripts/smoke_test_cli.py
```

La guía completa y las variables de entorno soportadas están en [docs/smoke-test-cli.md](/Users/andychapo/Projects/wapu/wapu-cli/docs/smoke-test-cli.md).
