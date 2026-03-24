# Wapu CLI

CLI en Python para interactuar con el backend de WapuPay desde terminal, scripts y agentes.

## Qué es y por qué importa

`wapu-cli` es una interfaz de línea de comandos para integrar depósitos por Lightning y retiros fiat desde herramientas, scripts y flujos automatizados. Está pensada para developers, operadores y equipos que quieran conectar productos sobre Bitcoin/Lightning con una experiencia real de entrada y salida para usuarios finales.

El problema que resuelve no es solamente "usar Wapu", sino reducir una fricción concreta en la adopción de Lightning: mover valor entre el ecosistema Lightning y moneda local de manera simple, programable y utilizable desde software. En ese sentido, el proyecto funciona como un puente para builders que ya están construyendo sobre Lightning/Bitcoin y necesitan una vía práctica de off-ramp para sus usuarios.

Además, la propuesta sí se apoya directamente en Lightning como parte central del flujo:

- permite crear depósitos Lightning
- expone la Lightning Address del usuario para recibir fondos
- habilita automatización y operación desde terminal, scripts y agentes

Esto hace que el proyecto sea relevante no solo como herramienta de integración con WapuPay, sino como infraestructura de adopción para casos de uso reales sobre Lightning.

## Alcance y arquitectura

Este CLI consume un backend porque el problema que resuelve incluye operaciones con dinero fiat, cumplimiento operativo y ejecución de retiros. Un off-ramp no puede funcionar en modo offline: por definición requiere comunicación con servicios que mueven fondos y validan estado.

La apuesta del proyecto está en ofrecer una interfaz simple y programable sobre ese flujo, de forma que nuevos productos puedan integrar depósitos Lightning y retiros ARS sin tener que reinventar la operación completa. Hoy la implementación está conectada al backend de WapuPay, pero el valor del proyecto está en la experiencia de integración que habilita para el ecosistema Lightning.

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
https://be-prod.wapu.app
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

Obtener la Lightning address:

```bash
uv run wapu deposit lightning address
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
