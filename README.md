# ⚡ wapu-cli

CLI oficial (beta) para interactuar con la API de WapuPay y habilitar flujos **off-ramp de BTC y USDT a ARS** de forma programable.

> Objetivo: dar a developers, equipos backend, integradores y agentes de IA una herramienta simple para mover valor entre cripto y pesos argentinos.

---

## 🚀 ¿Qué es `wapu-cli`?

`wapu-cli` es una herramienta de línea de comandos para operar sobre WapuPay sin depender de frontend.

Permite:
- pruebas rápidas de producto
- automatización con scripts
- integración server-to-server
- ejecución por agentes de IA (ej. OpenClaw)

---

## 🧪 Funcionalidades base (Beta)

En esta versión inicial, el foco está en operaciones concretas de tesorería y pagos:

1. ⚡ **Depósitos vía Lightning**
   - Crear depósitos por Lightning Network.
   - Caso de uso: convertir cobros BTC en flujo operativo.

2. 💸 **Envío de FIAT (ARS) sin necesidad de KYC**
   - Solicitar transferencias en pesos argentinos vía alias/CBU.
   - Ideal para payout a comercios o proveedores locales.

3. 📜 **Listado de transacciones**
   - Ver historial para auditoría, conciliación y debugging.

4. 🔎 **Status de transacciones**
   - Consultar una transacción puntual por ID.

5. 🧾 **Ver balance**
   - Consultar balance actual desde API.

6. 🪙 **Solicitar retiro de USDT**
   - Iniciar retiro de saldo USDT desde el CLI.

---

## ✅ ¿Por qué esto le sirve a un developer?

### Menos fricción, más shipping
- Puede validar flujos de pagos **antes** de construir frontend.
- Puede correr pruebas desde terminal o CI sin UI.

### Automatización real
- Con scripts (`cron`, jobs, workers), puede programar tareas operativas:
  - conciliaciones
  - payouts periódicos
  - alertas por estado de transacción

### Integración para productos Bitcoin-first
- Un developer que construye un **POS Lightning para comercios** puede hacer que:
  - el comercio cobre en BTC,
  - y al final del día se retire automáticamente a ARS,
  - sin que el comerciante se preocupe por la operatoria.

### Listo para AI agents
- Un agente tipo OpenClaw puede ejecutar pagos en pesos con instrucciones de alto nivel, por ejemplo:
  - “programá pagos mensuales”
  - “enviá ARS a este alias cuando entre un cobro”

---

## 🌎 Visión

`wapu-cli` busca habilitar infraestructura financiera abierta para LATAM:
- rampa de salida a FIAT desde BTC/USDT
- onboarding más simple para comercios
- operación programable por humanos y agentes
- soporte para economías nativas de internet

En una frase: **cobrar en cripto y operar en ARS sin fricción**.

---

## 📌 Estado del proyecto

- **Estado:** Beta temprana (en definición de comandos y contrato de salida)
- **Nombre del repo:** `wapu-cli`
- **Enfoque actual:** DX, automatización y casos server-to-server

---

## 🤝 Próximos pasos sugeridos

- Definir contrato de comandos (`auth`, `balance`, `deposit`, `tx`, `withdraw`)
- Definir salida estable (`json` y formato legible)
- Agregar ejemplos copy/paste para scripts y agentes IA
- Documentar manejo seguro de credenciales

---

Hecho con foco en builders que quieren integrar pagos reales, no demos. 🔧