# Wapu CLI

CLI en Python para interactuar con el backend de WapuPay desde terminal, scripts y agentes.

## Instalación

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
https://be-stage.wapu.app
```

## Auth

Guardar una API key:

```bash
uv run wapu auth login --api-key '...'
```

Guardar un JWT:

```bash
uv run wapu auth login --email you@example.com --password '...'
```

Ver estado local:

```bash
uv run wapu auth status
```

Borrar credenciales:

```bash
uv run wapu auth logout
```

## Comandos MVP

Balance:

```bash
uv run wapu balance
```

Crear depósito Lightning:

```bash
uv run wapu deposit lightning create --amount 10 --currency SAT
```

Listar transacciones:

```bash
uv run wapu tx list
```

Obtener una transacción:

```bash
uv run wapu tx get 2b753493-687b-431f-8d85-f9b4cb99199e
```

Crear retiro ARS:

```bash
uv run wapu withdraw ars --type fiat_transfer --alias test.alias --amount 100 --receiver-name 'Test Receiver'
uv run wapu withdraw ars --type fast_fiat_transfer --alias test.alias --amount 100
```

## Salida

Formatos:

```bash
uv run wapu --output json balance
uv run wapu --output table tx list
```

Modo silencioso:

```bash
uv run wapu --quiet balance
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
