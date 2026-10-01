# Guía de instalación — Punto de Venta MASTER

Esta guía es para quien instala el sistema en la computadora de un cliente. Tiempo estimado: **15 minutos**.
El sistema funciona **sin internet** y no necesita instalar Python ni ningún otro programa (solo en la alternativa
del apartado 3.D).

## 1. Qué necesitas llevar
- Esta carpeta completa (en una USB).
- El **instalador**: `Instalar_PuntoDeVentaMASTER_X.Y.Z.exe` (ver el apartado 3).
- Los datos del negocio: nombre, menú con precios, lista de insumos con costos, gastos fijos mensuales y los usuarios que habrá.
- La impresora de tickets conectada (opcional, pero recomendada).

## 2. Requisitos de la computadora
| Concepto | Mínimo |
|---|---|
| Sistema operativo | Windows 10 o Windows 11, **64 bits** |
| Memoria / disco | 4 GB de RAM · 500 MB libres (los datos crecen poco: unos MB por año) |
| Pantalla | 1366×768 o mayor (ideal 1920×1080 o táctil) |
| Impresora | Térmica de 58 u 80 mm instalada en Windows (opcional) |
| Internet | **No se necesita** para operar |
| Ventana propia | *Microsoft Edge WebView2 Runtime* (ya viene en Windows 11 y en Windows 10 actualizado). Si falta, el sistema abre en el navegador |

Antes de instalar, ejecuta `herramientas\Verificar-equipo.bat`: revisa Windows de 64 bits, WebView2, el puerto del
sistema y la impresora predeterminada, y te dice qué falta.

## 3. Conseguir el instalador
El instalador es **único**: el mismo `.exe` sirve para todas las computadoras. Se genera en una máquina Windows; elige una opción:

**A. GitHub Releases (recomendada).** Al publicar una versión con etiqueta `vX.Y.Z` (por ejemplo `v1.1.0`), el repositorio compila y publica
automáticamente el instalador y una versión portable. Descárgalos de
<https://github.com/JuanDiaz-DataAnalyst/punto-de-venta-master/releases>.

**B. Compilación manual en GitHub.** En el repositorio: pestaña **Actions → Build Windows → Run workflow**. Al terminar (unos 10 minutos),
descarga el artefacto `PuntoDeVentaMASTER-windows` (contiene el instalador `.exe` y el `.zip` portable).

**C. Compilar en tu propia PC con Windows.** Instala Python 3.12 (marcando *Add python.exe to PATH*) e Inno Setup 6 (gratis),
extrae `codigo-fuente\PuntoDeVentaMASTER-fuente-X.Y.Z.zip` y ejecuta `scripts\build.bat`. El instalador queda en la carpeta `instalador`.

**D. Sin instalador (alternativa).** Extrae el `.zip` de `codigo-fuente\` en una carpeta fija (por ejemplo `C:\PuntoDeVenta`), instala
Python 3.12 en la PC del cliente y ejecuta `scripts\instalar-desde-codigo.bat`. Necesita internet **solo** durante ese paso y crea
accesos directos en el Escritorio. Usa esta opción solo si no puedes obtener el `.exe`.

Copia el `.exe` a la carpeta `instalador\` de este kit para llevarlo todo junto.

## 4. Instalación paso a paso
1. Copia el instalador a la computadora del cliente y haz doble clic.
2. Si Windows muestra **«Windows protegió su PC»** (el instalador aún no está firmado digitalmente): pulsa **Más información → Ejecutar de todas formas**.
3. Si el asistente pide el idioma, elige Español y pulsa **Siguiente**. Si Windows pide permisos de administrador, acepta (instala en *Archivos de programa*);
   si eliges instalar solo para tu usuario, no los pide.
4. Deja la carpeta de destino sugerida y marca **Crear acceso directo en el escritorio**.
5. Pulsa **Instalar** y al final **Abrir Punto de Venta MASTER**.

Se crean: acceso directo en el Escritorio, grupo en el menú Inicio y **«Punto de Venta MASTER (modo navegador)»**, que sirve si la
ventana propia no abre (equipos sin WebView2).

**Versión portable (opcional):** extrae `PuntoDeVentaMASTER-X.Y.Z-portable.zip` en una carpeta y ejecuta `PuntoDeVentaMASTER.exe`.
Funciona igual; los datos se guardan en el mismo lugar que con el instalador.

## 5. Primera configuración
1. En la primera apertura aparece **Configuración inicial**: captura el nombre del negocio y crea el usuario **administrador**
   (guarda su contraseña en un lugar seguro).
   > **No marques «Cargar datos de ejemplo»** en una instalación real: llena el sistema con ventas ficticias.
2. Entra como administrador y captura, en este orden:
   1. **Menú y recetas**: categorías, insumos (unidad, costo, mínimo, existencia inicial) y productos con su receta.
   2. **Gastos fijos**: pulsa *Agregar conceptos comunes* y escribe los montos mensuales (sueldos, renta, luz, agua, gas…).
   3. **Usuarios**: un usuario por cajero, con tipo *User — Cajero* (el *Admin* es solo para el dueño o encargado).
   4. **Configuración**: datos del ticket (dirección, teléfono, RFC, mensaje), ancho de papel 58/80 mm, IVA y si se permite vender sin existencia.
3. **Impresora**: déjala como predeterminada en Windows. En el diálogo de impresión desactiva encabezados, pies de página y márgenes.
4. Haz una **venta de prueba**: abre la caja, abre una mesa, agrega productos, imprime la pre-cuenta, cobra y reimprime el ticket.
   Después cancela esa venta de prueba (Ventas → abrir el ticket → *Cancelar venta*) para devolver el inventario.
5. Entrega al cliente la `2-Guia-del-usuario.html`. Dentro del sistema, la tecla **F1** abre la Ayuda.

## 6. Dónde quedan los datos
| Qué | Dónde |
|---|---|
| Base de datos | `%LOCALAPPDATA%\PuntoDeVentaMASTER\pos.db` |
| Respaldos automáticos (últimos 20) | `%LOCALAPPDATA%\PuntoDeVentaMASTER\respaldos` |
| Exportaciones a Excel/CSV | `%LOCALAPPDATA%\PuntoDeVentaMASTER\exportaciones` |
| Registros para soporte | `%LOCALAPPDATA%\PuntoDeVentaMASTER\logs\pos.log` |

(`%LOCALAPPDATA%` equivale a `C:\Users\<usuario>\AppData\Local`; pégalo en el Explorador de archivos para abrirlo.)

> **Importante — datos por usuario de Windows:** los datos pertenecen a la cuenta de Windows con la que se abre el sistema. Si en la misma PC se
> usan varias cuentas de Windows, cada una vería su propia base vacía. Usa **siempre la misma cuenta de Windows** para el punto de venta, o define la
> variable de entorno de sistema `POS_DATA_DIR` con una carpeta común (por ejemplo `C:\PuntoDeVentaDatos`) antes de abrir el sistema por primera vez.

## 7. Respaldos y cambio de computadora
- El sistema crea un **respaldo automático cada vez que se abre**. Aun así, copia la carpeta de respaldos a una USB o a la nube **cada semana**.
- Copia completa de los datos: cierra el sistema y ejecuta `herramientas\Respaldar-datos.bat` (deja una carpeta en el Escritorio).
- **Pasar el negocio a otra computadora:** instala el sistema en la PC nueva, ábrelo una vez y ciérralo; copia el contenido de la carpeta de
  respaldo dentro de `%LOCALAPPDATA%\PuntoDeVentaMASTER` reemplazando los archivos; abre el sistema.
  También puedes restaurar un respaldo desde **Reportes y respaldos → Restaurar** (admin).

## 8. Actualizar a una versión nueva
1. Haz un respaldo (`Respaldar-datos.bat`).
2. Cierra el sistema y ejecuta el instalador de la versión nueva **sobre la existente**: no borra los datos.
3. Abre el sistema: actualiza la base de datos automáticamente (las migraciones son idempotentes) y crea un respaldo al iniciar.
4. Revisa el `CHANGELOG.md` (en el código fuente) para ver las novedades.

## 9. Desinstalar
*Configuración de Windows → Aplicaciones → Punto de Venta MASTER → Desinstalar.* **Los datos no se borran** (para no perder información del negocio).
Si de verdad quieres eliminarlos, borra a mano la carpeta `%LOCALAPPDATA%\PuntoDeVentaMASTER` (haz antes un respaldo).

## 10. Varias computadoras en un mismo negocio
Cada instalación tiene **su propia base de datos independiente**: dos cajas no comparten ventas, inventario ni mesas.
Es válido para negocios con **una sola caja**. Para varias terminales conectadas a la misma información haría falta migrar a una base
de datos en red (PostgreSQL), que está en la hoja de ruta. No intentes compartir la carpeta de datos entre equipos: puede dañar la base.

## 11. Seguridad, firewall y antivirus
- El sistema solo escucha en `127.0.0.1` (la propia computadora): no pide permisos de firewall ni es accesible desde la red.
- Algunos antivirus marcan como sospechosos los programas empaquetados con PyInstaller que no están firmados. Si ocurre, agrega una exclusión para
  la carpeta de instalación. La solución definitiva es firmar el instalador con un certificado de firma de código.
- Las contraseñas se guardan cifradas (PBKDF2). Recomienda al cliente cambiar la contraseña inicial del administrador y no compartir usuarios.

## 12. Solución de problemas
| Síntoma | Qué hacer |
|---|---|
| «Windows protegió su PC» al abrir el instalador | Más información → Ejecutar de todas formas (ver apartado 4) |
| Error «does not provide an export named…» al abrir un módulo (solo al actualizar desde una instalación hecha antes de este arreglo) | La ventana guardó archivos viejos en su caché: pulsa **Ctrl+F5**; si persiste, cierra el sistema, borra la carpeta `%LOCALAPPDATA%\pywebview` y ábrelo de nuevo. Las versiones nuevas ya no lo presentan |
| No abre la ventana del sistema | Instala *Microsoft Edge WebView2 Runtime* o usa el acceso **modo navegador** |
| El navegador muestra «No se puede acceder» | Espera unos segundos y recarga; si persiste, cierra el sistema desde el Administrador de tareas y ábrelo de nuevo |
| «No hay un turno de caja abierto» | Abre la caja en Vender o en Caja / Turno |
| No imprime | Impresora predeterminada y encendida; prueba imprimir desde otro programa; revisa márgenes y encabezados del diálogo |
| Aparece una base de datos vacía en la misma PC | Se abrió con otra cuenta de Windows (ver apartado 6) |
| Se perdió información | Reportes y respaldos → Restaurar, o copia un respaldo de `respaldos\` (apartado 7) |
| Otro programa usa el puerto 8765 | El sistema elige otro puerto automáticamente; no requiere acción |
| Algo falla y no se sabe por qué | Envía `logs\pos.log` (y `stderr.log` si existe) a soporte |

## 13. Licencia y soporte
Punto de Venta MASTER © 2026 Juan Díaz Vega. Todos los derechos reservados: la instalación y distribución a clientes debe hacerse con autorización del titular.
Componentes de terceros: ver `THIRD_PARTY_NOTICES.md` del código fuente.
