# Smoke Test Manual del CLI

Este documento describe cómo correr un smoke test real del CLI usando procesos de terminal, sin `pytest` y sin `tests/test_*.py`.

El runner automatizado está en `scripts/smoke_test_cli.py`.

## Qué cubre

El script cubre en dos etapas:

1. todo el surface público que existe hoy en el repo
2. suites adicionales para comandos futuros, activadas automáticamente cuando aparezcan en `--help`

Surface actual cubierto:

- `wapu --help`
- `auth --help`
- `deposit --help`
- `deposit lightning --help`
- `tx --help`
- `withdraw --help`
- `auth login` por email/password
- `auth login` por API key recuperada desde la config guardada
- `auth status`
- `auth logout`
- `balance` en `table`, `json`, `yaml` y `quiet`
- `deposit lightning address`
- `deposit lightning create`
- `tx list`
- `tx get`
- `withdraw ars --type fiat_transfer`
- `withdraw ars --type fast_fiat_transfer`
- flags globales `--output`, `--json`, `--yaml`, `--quiet`, `--api-base-url`, `--api-key`, `--access-token`

Surface futuro preparado:

- `contacts list/favourite/delete`
- `tx cancel/tentative-amount/inner-transfer`
- `api-token status`
- `user spending-limit/referral/profile/settings`
- `deposit crypto`
- `withdraw crypto`

También incluye casos negativos de validación local, conflictos de flags y errores típicos de backend.

## Requisitos

- `uv venv`
- `uv sync --dev`
- acceso al backend de stage
- credenciales de prueba por variables de entorno

## Variables de entorno

Variables requeridas:

- `WAPU_SMOKE_EMAIL`
- `WAPU_SMOKE_PASSWORD`

Variables opcionales del surface actual:

- `WAPU_SMOKE_API_BASE_URL`
- `WAPU_SMOKE_TX_ID`
- `WAPU_SMOKE_WITHDRAW_ALIAS`
- `WAPU_SMOKE_RECEIVER_NAME`
- `WAPU_SMOKE_FAST_AMOUNT`
- `WAPU_SMOKE_DEPOSIT_AMOUNT`
- `WAPU_SMOKE_RUN_SIDE_EFFECTS`
- `WAPU_SMOKE_RUN_NEGATIVE`

Variables opcionales del surface futuro, exigidas sólo si esos comandos existen en el binario:

- `WAPU_SMOKE_CONTACT_ID`
- `WAPU_SMOKE_CONTACT_FILTER_TYPE`
- `WAPU_SMOKE_CANCEL_TX_ID`
- `WAPU_SMOKE_INNER_TRANSFER_USERNAME`
- `WAPU_SMOKE_INNER_TRANSFER_AMOUNT`
- `WAPU_SMOKE_INNER_TRANSFER_CURRENCY`
- `WAPU_SMOKE_TENTATIVE_AMOUNT`
- `WAPU_SMOKE_TENTATIVE_CURRENCY_PAYMENT`
- `WAPU_SMOKE_TENTATIVE_CURRENCY_TAKEN`
- `WAPU_SMOKE_TENTATIVE_TYPE`
- `WAPU_SMOKE_REFERRAL_EMAIL`
- `WAPU_SMOKE_REFERRAL_PHONE`
- `WAPU_SMOKE_PROFILE_BETA_VERSION`
- `WAPU_SMOKE_SETTINGS_LANGUAGE`
- `WAPU_SMOKE_SETTINGS_FAVOURITE_CURRENCY`
- `WAPU_SMOKE_DEPOSIT_CRYPTO_AMOUNT`
- `WAPU_SMOKE_DEPOSIT_CRYPTO_CURRENCY`
- `WAPU_SMOKE_DEPOSIT_CRYPTO_NETWORK`
- `WAPU_SMOKE_WITHDRAW_CRYPTO_AMOUNT`
- `WAPU_SMOKE_WITHDRAW_CRYPTO_ADDRESS`
- `WAPU_SMOKE_WITHDRAW_CRYPTO_NETWORK`
- `WAPU_SMOKE_WITHDRAW_CRYPTO_CURRENCY`
- `WAPU_SMOKE_WITHDRAW_CRYPTO_RECEIVER_NAME`

Defaults relevantes:

- `WAPU_SMOKE_API_BASE_URL=https://be-stage.wapu.app`
- `WAPU_SMOKE_WITHDRAW_ALIAS=C`
- `WAPU_SMOKE_FAST_AMOUNT=10000`
- `WAPU_SMOKE_DEPOSIT_AMOUNT=10`
- `WAPU_SMOKE_RUN_SIDE_EFFECTS=true`
- `WAPU_SMOKE_RUN_NEGATIVE=true`

## Ejemplos

Con login por email/password en stage:

```bash
export WAPU_SMOKE_EMAIL='zource.code@gmail.com'
export WAPU_SMOKE_PASSWORD='test'
uv run python scripts/smoke_test_cli.py
```

Con override manual del backend:

```bash
export WAPU_SMOKE_API_BASE_URL=https://be-stage.wapu.app
export WAPU_SMOKE_EMAIL='zource.code@gmail.com'
export WAPU_SMOKE_PASSWORD='test'
uv run python scripts/smoke_test_cli.py
```

## Comportamiento esperado

- El script imprime cada comando ejecutado, exit code, stdout y stderr.
- Los secretos en línea de comando se muestran redactados.
- Hace discovery del surface leyendo `--help` y marca con `SKIP` las suites futuras que aún no existen en este build.
- Lee la API key guardada tras `auth login --email/--password` para cubrir luego `auth login --api-key` y `--api-key` inline.
- Si encuentra un `transaction_id` en `tx list`, lo reutiliza para `tx get`.
- Si crea un depósito o un retiro rápido, intenta validar luego esos ids con `tx get`.
- Termina con `auth logout` para dejar el estado local limpio.

## Fallos aceptados

Hay respuestas que el runner considera aceptables porque dependen del estado de stage:

- `withdraw-ars-fiat-transfer`: acepta `0`, `1` o `2`
  - `1` o `2` cubren el caso donde el backend deshabilita temporalmente el flujo
- `withdraw-ars-fast-fiat-transfer`: acepta `0` o `1`
  - `1` cubre mínimo de ARS, alias inválido u otras restricciones de negocio
- `tx-get-missing`: acepta `1` o `2`
  - algunos entornos devuelven error genérico y otros un not found tipado

Si necesitás una corrida más estricta, cambiá esos criterios en `scripts/smoke_test_cli.py`.

## Prerequisitos faltantes

- `WAPU_SMOKE_EMAIL` y `WAPU_SMOKE_PASSWORD` son obligatorios siempre.
- Las fixtures del surface futuro sólo se exigen si el comando correspondiente ya existe.
- Cuando falta una fixture requerida, el summary la separa bajo `Missing prerequisites` y el script termina con exit code distinto de cero.

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
4. Mirar `Skipped` para distinguir surface todavía no implementado de fallos reales.
5. Mirar `Missing prerequisites` antes de concluir que falta soporte del CLI.
6. Si falla un paso aceptado por negocio, leer `note` y el mensaje del backend antes de catalogarlo como bug del CLI.
7. Confirmar que la corrida terminó con `auth-status-final` y sin credenciales activas si ese aislamiento importa para la sesión.
