# Smoke Test Manual del CLI

Este documento describe cómo correr un smoke test real del CLI usando procesos de terminal, sin `pytest` y sin `tests/test_*.py`.

El runner automatizado está en [scripts/smoke_test_cli.py](/Users/andychapo/Projects/wapu/wapu-cli/scripts/smoke_test_cli.py).

## Qué cubre

El script ejecuta los comandos públicos del CLI:

- `auth login/status/logout`
- `balance`
- `deposit lightning create`
- `tx list/get`
- `withdraw ars`
- flags globales `--output`, `--quiet`, `--api-base-url`, `--api-key`, `--access-token`

También incluye casos negativos de validación local y errores típicos de backend.

## Requisitos

- `uv venv`
- `uv sync --dev`
- acceso al backend de stage
- credenciales de prueba por variables de entorno

## Variables de entorno

Variables principales:

- `WAPU_SMOKE_API_BASE_URL`
- `WAPU_SMOKE_API_KEY`
- `WAPU_SMOKE_EMAIL`
- `WAPU_SMOKE_PASSWORD`

Variables opcionales:

- `WAPU_SMOKE_TX_ID`
- `WAPU_SMOKE_WITHDRAW_ALIAS`
- `WAPU_SMOKE_RECEIVER_NAME`
- `WAPU_SMOKE_FAST_AMOUNT`
- `WAPU_SMOKE_DEPOSIT_AMOUNT`
- `WAPU_SMOKE_RUN_SIDE_EFFECTS`
- `WAPU_SMOKE_RUN_NEGATIVE`

Defaults relevantes:

- `WAPU_SMOKE_WITHDRAW_ALIAS=C`
- `WAPU_SMOKE_FAST_AMOUNT=10000`
- `WAPU_SMOKE_DEPOSIT_AMOUNT=10`
- `WAPU_SMOKE_RUN_SIDE_EFFECTS=true`
- `WAPU_SMOKE_RUN_NEGATIVE=true`

## Ejemplos

Con API key directa:

```bash
export WAPU_SMOKE_API_BASE_URL=https://be-stage.wapu.app
export WAPU_SMOKE_API_KEY='...'
uv run python scripts/smoke_test_cli.py
```

Con login por email/password:

```bash
export WAPU_SMOKE_API_BASE_URL=https://be-stage.wapu.app
export WAPU_SMOKE_EMAIL='user@example.com'
export WAPU_SMOKE_PASSWORD='secret'
uv run python scripts/smoke_test_cli.py
```

Con ambos caminos de auth:

```bash
export WAPU_SMOKE_API_BASE_URL=https://be-stage.wapu.app
export WAPU_SMOKE_API_KEY='...'
export WAPU_SMOKE_EMAIL='user@example.com'
export WAPU_SMOKE_PASSWORD='secret'
uv run python scripts/smoke_test_cli.py
```

## Comportamiento esperado

- El script imprime cada comando ejecutado, exit code, stdout y stderr.
- Si encuentra un `transaction_id` en `tx list`, lo reutiliza para `tx get`.
- Si crea un depósito o un retiro rápido, intenta validar luego esos ids con `tx get`.
- Termina con `auth logout` para dejar el estado local limpio.

## Fallos aceptados

Hay respuestas que el runner considera aceptables porque dependen del estado de stage:

- `balance-inline-api-key`: acepta `0` o `3`
  - `3` cubre API keys revocadas o inválidas en stage
- `withdraw-ars-fiat-transfer`: acepta `0`, `1` o `2`
  - `1` o `2` cubren el caso donde el backend deshabilita temporalmente el flujo
- `withdraw-ars-fast-fiat-transfer`: acepta `0` o `1`
  - `1` cubre mínimo de ARS, alias inválido u otras restricciones de negocio
- `tx-get-missing`: acepta `1` o `2`
  - algunos entornos devuelven error genérico y otros un not found tipado

Si necesitás una corrida más estricta, cambiá esos criterios en [scripts/smoke_test_cli.py](/Users/andychapo/Projects/wapu/wapu-cli/scripts/smoke_test_cli.py).

## Side effects

Por default el script sí crea recursos remotos en stage:

- un depósito Lightning
- un retiro ARS rápido si el backend lo permite

Para desactivar eso:

```bash
export WAPU_SMOKE_RUN_SIDE_EFFECTS=false
uv run python scripts/smoke_test_cli.py
```

## Uso por otro agente

Secuencia recomendada:

1. Exportar credenciales efímeras de stage en la shell actual.
2. Ejecutar `uv run python scripts/smoke_test_cli.py`.
3. Revisar la sección final `Summary`.
4. Si falla un paso aceptado por negocio, leer `note` y el mensaje del backend antes de catalogarlo como bug del CLI.
5. Confirmar que la corrida terminó con `auth-status-final` y sin credenciales activas si ese aislamiento importa para la sesión.
