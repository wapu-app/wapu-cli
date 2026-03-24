---
name: wapu-cli
description: |
  Guía operativa para usar el CLI de WapuPay desde terminal (modo usuario, no desarrollo).
  Cubre login, configuración, balance, depósitos Lightning, transacciones y retiros ARS.
  Trigger sugerido: mensajes que pidan "usa wapu", "wapu ...", "/wapu".
metadata:
  {
    "openclaw": { "emoji": "💸", "requires": { "node": false } }
  }
---

# Wapu CLI Skill

Usa esta skill cuando el usuario quiera **operar Wapu desde CLI** (consultar balance, listar tx, crear depósito/retiro, gestionar credenciales), no para programar el proyecto.

## Objetivo

Ejecutar comandos `wapu ...` de forma segura y directa, con salida clara para el usuario.

---

## Pre-checks rápidos

1. Verificar binario:
```bash
wapu --help
```

2. Verificar estado local:
```bash
wapu auth status
```

3. Confirmar backend (debería ser prod por defecto):
- Esperado: `https://be-prod.wapu.app`
- Si no coincide, ajustar config en `~/.config/wapu-cli/config.json` o usar `--api-base-url`.

---

## Comandos base

### Auth

Login con email/password:
```bash
wapu auth login --email "<email>" --password "<password>"
```

Login con API key:
```bash
wapu auth login --api-key "<api_key>"
```

Estado:
```bash
wapu auth status
```

Logout:
```bash
wapu auth logout
```

---

### Balance

```bash
wapu balance
```

Con salida JSON:
```bash
wapu --output json balance
```

---

### Depósitos (Lightning)

Crear depósito Lightning:
```bash
wapu deposit lightning create --amount 10 --currency SAT
```

Notas:
- `--amount` requerido (float)
- `--currency` requerido (actualmente SAT)

---

### Transacciones

Listar:
```bash
wapu tx list
```

Obtener por ID:
```bash
wapu tx get <transaction_id>
```

Ejemplo:
```bash
wapu tx get 2b753493-687b-431f-8d85-f9b4cb99199e
```

---

### Retiros ARS

```bash
wapu withdraw ars --type fiat_transfer --alias "tu.alias" --amount 100 --receiver-name "Nombre"
```

o fast:
```bash
wapu withdraw ars --type fast_fiat_transfer --alias "tu.alias" --amount 100
```

Parámetros:
- `--type` requerido: `fiat_transfer` | `fast_fiat_transfer`
- `--alias` requerido
- `--amount` requerido
- `--receiver-name` opcional

---

## Flags globales útiles

```bash
wapu --output json <comando>
wapu --output table <comando>
wapu --quiet <comando>
wapu --api-base-url https://be-prod.wapu.app <comando>
wapu --access-token "..." <comando>
wapu --api-key "..." <comando>
```

Regla importante:
- No usar `--access-token` y `--api-key` al mismo tiempo.

---

## Troubleshooting

### `wapu: command not found` o `uv: command not found`

Verificar PATH y binarios:
```bash
which wapu
which uv
```

En esta instancia deberían resolver a `/usr/local/bin/wapu` y `/usr/local/bin/uv`.

### Autenticado = False

Ejecutar login y revalidar:
```bash
wapu auth login --email "..." --password "..."
wapu auth status
```

### Backend incorrecto

Comprobar:
```bash
wapu auth status
```

Override puntual:
```bash
wapu --api-base-url https://be-prod.wapu.app balance
```

---

## Buenas prácticas para agentes

- Si el usuario comparte credenciales, **no repetirlas en texto** al responder.
- Mostrar resultados resumidos y ofrecer detalle JSON solo si lo pide.
- Antes de operaciones sensibles (retiros), reconfirmar monto/alias si hay ambigüedad.
- Para soporte rápido, empezar por:
  1) `wapu auth status`
  2) `wapu balance`
  3) comando objetivo (`tx list`, `withdraw ars`, etc.).
