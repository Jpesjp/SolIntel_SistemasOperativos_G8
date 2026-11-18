# SolIntel — Documento técnico final

**Universidad Manuela Beltrán** · Facultad de Ingeniería · Ingeniería de Software
**Asignatura:** Sistemas Operativos · **Docente:** Ing. Jamilton Fernando Benavides · **Grupo:** G8

**Integrantes:** David Santiago Cárdenas Perilla · Juan Pablo Rojas Fernández · Sebastian Perez Triana

**Modalidad de entrega:** Opción A – Repositorio GitHub · Noviembre de 2026

---

## 1. Introducción
SolIntel es una plataforma web que ayuda a los hogares a entender y reducir su consumo de energía. Muestra el consumo por hora, día, semana, mes y año, identifica los dispositivos y horarios de mayor gasto, genera alertas preventivas y propone acciones de ahorro con un módulo de inteligencia artificial basado en reglas y en un algoritmo predictivo simple. Todo el componente de medición es **simulado** (no hay sensores ni integración con empresas de energía).

La solución se construyó sobre un entorno operativo Linux administrado: el sistema corre como **servicio** con un **usuario sin privilegios**, en dos **procesos** independientes (servidor web y simulador IoT), con **permisos** de mínimo privilegio, **firewall**, **tareas programadas**, **respaldos**, **monitoreo** y **auditoría**.

## 2. Problemática
La factura de energía informa el valor a pagar, pero no explica cuándo ni en qué dispositivos se consume más. En la encuesta aplicada a 42 usuarios residenciales de Bogotá, 26 percibieron un aumento en la factura (puntaje 4–5) y 31 quieren conocer su consumo por día, semana o mes. Sin esa información el usuario no corrige hábitos a tiempo.

## 3. Objetivos
**General:** desarrollar una plataforma web simulada que permita monitorear, analizar y reducir el consumo energético residencial mediante visualización de datos y recomendaciones de IA, desplegada sobre un sistema operativo configurado, seguro y monitoreado.

**Específicos:**
1. Implementar las 11 pantallas diseñadas en Figma como una aplicación web responsive.
2. Construir una API backend concurrente con autenticación segura.
3. Implementar un simulador IoT como proceso independiente y un módulo de IA de reglas y predicción.
4. Aplicar conceptos de SO: procesos, hilos, planificación, sistema de archivos, memoria, concurrencia, seguridad y E/S.
5. Automatizar instalación, monitoreo y respaldo con Bash y PowerShell.
6. Validar con pruebas automáticas y documentar evidencias en el repositorio.

## 4. Requisitos
| Tipo | Detalle |
|---|---|
| Funcionales | RF01–RF08 del README (registro e inicio de sesión, dashboard, consumo por periodo, dispositivos, alertas, recomendaciones IA, reportes, control simulado) — **todos implementados**. |
| No funcionales | RNF01 lenguaje simple y colores de estado · RNF02 dashboard < 3 s (medido: 0,17 s) · RNF03 navegadores modernos · RNF04 contraseñas cifradas y sesiones · RNF05 código modular y commits con formato · RNF06 aviso visible de datos simulados. |
| Hardware | 2 núcleos, 1 GB RAM y 1 GB de disco para el servicio (desarrollo: 8 GB RAM). |
| Software | Python 3.10+ (solo librería estándar), navegador moderno. Opcional: Docker. |

## 5. Arquitectura del entorno

```
 Navegador (PC / celular)
        │  HTTP :8080 (firewall: solo 22 y 8080 abiertos)
        ▼
┌──────────────────────── Ubuntu Server 22.04 / 24.04 ───────────────────────┐
│  systemd                                                                    │
│   ├─ solintel-web.service  (usuario solintel, sin privilegios)              │
│   │    Proceso servidor.py ── ThreadingHTTPServer: 1 hilo por solicitud      │
│   │      ├─ frontend estático (src/frontend)                                │
│   │      ├─ API REST (/api/*) ── seguridad.py (PBKDF2, sesiones, bloqueo)   │
│   │      └─ motor_ia.py (reglas + regresión) ── caché en RAM por mtime       │
│   └─ solintel-simulador.service                                             │
│        Proceso simulador_iot.py ── cada 30 s completa horas y lectura en vivo│
│                     │  bloqueo de archivo (flock) + escritura atómica        │
│                     ▼                                                       │
│   /opt/solintel/data (700)  usuarios.json (600) · hogares/<uid>/*.csv|json  │
│   cron: respaldo diario 2:15 a.m. · monitoreo cada 30 min                   │
│   logrotate: logs semanales comprimidos · logs/solintel.log (auditoría)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

Capas: **presentación** (SPA HTML/CSS/JS sin dependencias), **lógica de negocio** (API + IA en Python), **datos** (JSON/CSV por hogar) y **simulador** (proceso aparte).

## 6. Sistema operativo seleccionado
| Entorno | Uso | Justificación |
|---|---|---|
| **Ubuntu Server 22.04/24.04 LTS** | Despliegue (servidor) | Gratuito, soporte LTS de 5 años, systemd, UFW, cron y logrotate nativos; es el SO de la mayoría de servicios en la nube (Render, Railway, VPS). |
| **Windows 10/11** | Desarrollo del equipo | Es el SO de los integrantes; los scripts PowerShell permiten ejecutar, monitorear y respaldar igual que en Linux. |
| Docker (opcional) | Portabilidad | Imagen `python:3.12-slim` con usuario no root y healthcheck. |

La aplicación es **multiplataforma**: el módulo de bloqueo usa `fcntl` en Linux y `msvcrt` en Windows.

## 7. Instalación
**Linux (servicio):**
```bash
git clone https://github.com/Jpesjp/SolIntel_SistemasOperativos_G8.git
cd SolIntel_SistemasOperativos_G8
sudo bash scripts/linux/instalar.sh
```
El script: instala paquetes (python3, ufw, cron, logrotate), crea usuario/grupos, copia a `/opt/solintel`, aplica permisos, instala y habilita los servicios systemd, registra cron y logrotate y configura el firewall. Evidencia: `evidencias/instalacion/instalacion_linux.txt`.

**Windows (desarrollo):** `powershell -ExecutionPolicy Bypass -File scripts\windows\iniciar.ps1`

**Docker:** `docker compose up -d`

## 8. Configuración
`config/solintel.json` centraliza puerto, tarifa de referencia (900 COP/kWh), días de historial simulado (365), duración de sesión (8 h), intervalo del simulador (30 s) y tamaño máximo de solicitud. Las variables de entorno `SOLINTEL_PUERTO`, `SOLINTEL_TARIFA`, `SOLINTEL_DATOS` y `SOLINTEL_INTERVALO` lo sobrescriben (útil en systemd y Docker).

## 9. Usuarios y permisos
| Elemento | Configuración |
|---|---|
| `solintel` | Usuario de sistema sin shell (`/usr/sbin/nologin`); ejecuta los dos servicios. |
| `solintel-admin` | Grupo del equipo: puede leer logs y respaldos, no los datos. |
| `/opt/solintel` | `root:solintel 750` — el código no lo puede modificar el servicio. |
| `data/` | `solintel 700`; `usuarios.json` `600`. |
| `logs/` | `solintel:solintel-admin 2750` (setgid para heredar grupo). |
| `respaldos/` | `solintel:solintel-admin 770`. |
| umask | `027` en los procesos y en systemd (`UMask=0027`). |
| Aplicación | Rol `residente`; cada hogar solo accede a su directorio `hogares/<uid>/` mediante su token de sesión. |

Prueba: un usuario ajeno (`tester`) recibe *Permission denied* al leer `usuarios.json` o listar `/opt/solintel` (`evidencias/seguridad/seguridad_linux.txt`).

## 10. Procesos y servicios
| Concepto de SO | Implementación |
|---|---|
| Procesos | `servidor.py` y `simulador_iot.py` son procesos distintos; con `--con-simulador` el servidor crea al simulador como **proceso hijo** (`subprocess.Popen`). El PID del simulador se publica en `data/simulador.pid`. |
| Hilos | `ThreadingHTTPServer` atiende cada solicitud en un hilo (`process_request_thread`, visible en el log). |
| Señales | Ambos procesos atienden `SIGTERM`/`SIGINT` y terminan de forma ordenada (`detener.sh`, `systemctl stop`). |
| Planificación | El simulador se ejecuta cada 30 s; cron ejecuta respaldo diario y monitoreo cada 30 min; en Windows se usan Tareas Programadas. |
| Servicios | `solintel-web.service` y `solintel-simulador.service` con `Restart=on-failure`, `MemoryMax`, `CPUQuota`. |

## 11. Red
- El servidor escucha en `0.0.0.0:8080` (configurable). Rutas: `/` (aplicación) y `/api/*` (JSON).
- `/api/salud` permite verificar disponibilidad sin sesión (usado por monitoreo y el healthcheck de Docker).
- Pruebas de conectividad: `curl http://<IP>:8080/api/salud`, `ss -ltnp | grep 8080`, `Get-NetTCPConnection -LocalPort 8080` (Windows).

## 12. Almacenamiento
- Sin motor de base de datos: archivos JSON/CSV por hogar en `data/hogares/<uid>/` (`consumo.csv` ≈ 2,5 MB por año simulado, `dispositivos.json`, `hogar.json`, `plan.json`, `lectura.json`).
- **Escritura atómica** (archivo temporal + `fsync` + `os.replace`) y **exclusión mutua** entre hilos y procesos (`flock`/`msvcrt`).
- **Respaldos**: `respaldo.sh` crea `tar.gz` + `SHA-256`, conserva 7 y permite restaurar verificando integridad (`evidencias/respaldos/respaldo_linux.txt`).
- **Gestión de memoria**: el análisis de cada CSV se guarda en caché RAM y solo se recalcula si cambia `st_mtime` (aciertos/fallos visibles en *Perfil → Estado del sistema*).

## 13. Seguridad
| Medida | Detalle |
|---|---|
| Contraseñas | PBKDF2-HMAC-SHA256, 200.000 iteraciones, sal aleatoria; política mínima de 8 caracteres con letras y números. |
| Sesiones | Token aleatorio de 32 bytes en RAM, expira en 8 h; cierre de sesión invalida el token. |
| Fuerza bruta | 5 intentos fallidos → bloqueo de 5 min (HTTP 429). |
| Cabeceras HTTP | `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`. |
| Entradas | Validación de tipos y rangos, límite de 64 KB por solicitud, escape HTML en el cliente, protección contra *path traversal*. |
| Firewall | UFW: entrada denegada por defecto; solo 22/tcp (con `limit`) y 8080/tcp. Windows: `config/firewall/windows_firewall.ps1`. |
| Servicio | `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths` solo a `data` y `logs`. |
| Auditoría | `logs/solintel.log` (rotativo) registra registro, login correcto/fallido/bloqueado, cambios de clave y de dispositivos. |
| Actualizaciones | `apt-get update && apt-get upgrade` en la instalación; se recomienda `unattended-upgrades` en el servidor. |

## 14. Automatización
| Script | Función |
|---|---|
| `scripts/linux/instalar.sh` | Instalación completa como servicio. |
| `scripts/linux/iniciar.sh` / `detener.sh` | Ejecución en segundo plano con archivos PID (modo desarrollo). |
| `scripts/linux/monitorear.sh` | Reporte de SO, CPU, memoria, disco, procesos, puertos, salud y auditoría. |
| `scripts/linux/respaldo.sh` | Respaldo y restauración con verificación SHA-256. |
| `scripts/linux/probar.sh` | Pruebas unitarias + pruebas de humo de la API. |
| `scripts/windows/*.ps1` | Equivalentes en PowerShell: iniciar, detener, monitorear, respaldo y tareas programadas. |

## 15. Monitoreo
- `monitorear.sh` / `monitorear.ps1` generan reportes en `evidencias/monitoreo/`.
- La pantalla **Perfil y ajustes → Estado del sistema** muestra en vivo: SO, PID y PPID del servidor, hilos activos, tiempo activo, memoria máxima, carga promedio, uso de disco, tamaño de los datos, PID del simulador, usuarios, sesiones y caché.
- Medido en la VM de pruebas (Ubuntu 24.04, 2 núcleos, 8 GB): servidor ≈ 35 MB de RAM, simulador < 0,3 % CPU, respuesta de la API entre 1 y 170 ms.

## 16. Pruebas
21 pruebas automáticas (`tests/test_solintel.py`), todas aprobadas:

| Grupo | Pruebas |
|---|---|
| Seguridad (7) | Hash con sal, política de clave, rutas protegidas sin token (401), bloqueo por fuerza bruta (429), cabeceras HTTP, *path traversal*, permisos 600. |
| Funcionales (6) | Registro, duplicado (409), login/logout; 15 endpoints; rendimiento del dashboard < 3 s; control de dispositivos y validación; configuración del hogar; plan de ahorro. |
| Sistemas operativos (6) | Simulador respeta estado apagado/standby; relleno de horas faltantes; **exclusión mutua con 4 procesos concurrentes** (200 incrementos sin pérdidas); 20 hilos concurrentes sobre la API; caché en RAM; endpoint de monitoreo. |
| IA (2) | Regresión lineal y cálculo de meta. |

Además se ejecutaron pruebas manuales en la interfaz (escritorio 1366 px y móvil 390 px) sin errores de consola.

## 17. Evidencias
| Evidencia obligatoria (guía) | Archivo |
|---|---|
| SO instalado y configurado | `evidencias/instalacion/instalacion_linux.txt`, `evidencias/monitoreo/*.txt` |
| Usuarios, grupos y permisos | `evidencias/seguridad/seguridad_linux.txt` |
| Servicios operativos | `evidencias/monitoreo/*.txt` (procesos y salud), `config/systemd/` |
| Red y conectividad | `evidencias/pruebas/pruebas_api.txt` |
| Procesos y recursos | `evidencias/monitoreo/*.txt`, captura `escritorio_09_perfil.jpg` |
| Seguridad y firewall | `evidencias/seguridad/seguridad_linux.txt`, `config/firewall/` |
| Scripts y automatización | `scripts/`, `evidencias/respaldos/respaldo_linux.txt` |
| Pruebas y resultados | `evidencias/pruebas/pruebas_unitarias.txt`, `pruebas_api.txt` |
| Monitoreo y rendimiento | `evidencias/monitoreo/` |
| Interfaz funcionando | `evidencias/capturas/` (22 capturas: escritorio y móvil) |

## 18. Resultados
- Plataforma web con las **11 pantallas** del prototipo en Figma, responsive (menú lateral en escritorio y barra inferior en móvil).
- Historial simulado de 365 días por hogar (8 dispositivos, lectura por hora) y lectura en vivo cada 30 s.
- Consumo simulado del hogar demo ≈ 86 kWh/mes (≈ COP 77.000 con la tarifa de referencia); el motor de IA genera hasta 6 alertas y 8 recomendaciones con ahorro estimado ≈ COP 12.000/mes.
- Servicio ejecutándose con usuario sin privilegios, permisos verificados, firewall definido, respaldos verificados por SHA-256 y 21/21 pruebas aprobadas.

## 19. Problemas encontrados y soluciones
| Problema | Solución |
|---|---|
| El servidor y el simulador escribían el mismo CSV al tiempo. | Bloqueo de archivo entre procesos (`flock`) y escritura atómica. |
| En la madrugada el "consumo de hoy" casi siempre era 0. | Se cambió a una ventana móvil de las **últimas 24 horas**. |
| Archivos nuevos quedaban legibles por otros usuarios (644). | `umask 027` en los procesos y `UMask=0027` en systemd. |
| El historial quedaba desactualizado si el simulador estaba detenido. | El servidor completa las horas faltantes al consultar (*catch-up*). |
| Los equipos de desarrollo usan Windows y el servidor Linux. | Código solo con librería estándar y bloqueo multiplataforma; scripts en Bash y PowerShell. |

## 20. Conclusiones
1. Los conceptos de Sistemas Operativos no son solo teoría: la concurrencia entre el servidor y el simulador obligó a usar exclusión mutua real entre procesos, y la prueba con 4 procesos lo demostró sin pérdidas de datos.
2. Ejecutar el servicio con un usuario sin privilegios, permisos 700/600, umask y endurecimiento de systemd reduce el impacto de una falla de seguridad.
3. La automatización (instalación, respaldo y monitoreo) hace que el despliegue sea repetible y verificable.
4. Con datos simulados fue posible validar la idea completa —visualización, alertas, predicción y recomendaciones— sin infraestructura física.
5. Trabajo futuro: base de datos (SQLite/PostgreSQL), HTTPS con proxy inverso (Nginx + Let's Encrypt), integración con medidores inteligentes reales y modelos de predicción más robustos.

## 21. Referencias
- Silberschatz, A., Galvin, P. B., & Gagne, G. (2018). *Operating System Concepts* (10.ª ed.). Wiley.
- Tanenbaum, A. S., & Bos, H. (2015). *Modern Operating Systems* (4.ª ed.). Pearson.
- ISO/IEC. (2011). *ISO/IEC 25010:2011 — Systems and software quality models.*
- Python Software Foundation. (s. f.). *http.server, threading, hashlib, fcntl — documentación de Python 3*. https://docs.python.org/3/
- freedesktop.org. (s. f.). *systemd.exec — Sandboxing*. https://www.freedesktop.org/software/systemd/man/systemd.exec.html
- Canonical. (s. f.). *Ubuntu Server documentation — Firewall (UFW)*. https://ubuntu.com/server/docs
- OWASP. (s. f.). *Password Storage Cheat Sheet*. https://cheatsheetseries.owasp.org/
