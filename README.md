# Wapu CLI

CLI en Python para interactuar con el backend de WapuPay desde terminal, scripts y agentes.

## Instalación

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

Luego puedes usar:

```bash
wapu --help
python -m wapu_cli --help
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
https://miasmal-isodose-zenobia.ngrok-free.dev
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

## Comandos MVP

Balance:

```bash
wapu balance
```

Crear depósito Lightning:

```bash
wapu deposit lightning create --amount 10 --currency SAT
```

Listar transacciones:

```bash
wapu tx list
```

Obtener una transacción:

```bash
wapu tx get 2b753493-687b-431f-8d85-f9b4cb99199e
```

Crear retiro ARS:

```bash
wapu withdraw ars --type fiat_transfer --alias test.alias --amount 100 --receiver-name 'Test Receiver'
wapu withdraw ars --type fast_fiat_transfer --alias test.alias --amount 100
```

## Salida

Formatos:

```bash
wapu --output json balance
wapu --output table tx list
```

Modo silencioso:

```bash
wapu --quiet balance
```

## Tests

```bash
pytest
```
