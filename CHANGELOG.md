# Changelog

Todos los cambios relevantes se documentan aquí. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]
### Agregado
- **Cuentas abiertas por mesa**: varios tickets independientes a la vez, en pestañas cuyo título es el número
  de mesa. Se pueden seguir agregando consumos mientras los comensales están en la mesa; el inventario se
  descuenta (backflush) hasta el cobro. Atajo **F4** para abrir una mesa.
- **Folio único por ticket**: el folio se asigna al abrir la cuenta con un consecutivo compartido por mesas
  y ventas directas; nunca se reutiliza, ni siquiera si la cuenta se cancela. La venta conserva ese folio.
- La mesa se muestra en el ticket impreso, en el historial de ventas (con búsqueda) y en `v_ventas_detalle`.
- **Gastos fijos mensuales** (Admin → Gastos fijos): nómina, renta, luz, agua, gas, etc. con vigencia y
  plantilla de conceptos comunes de un restaurante pequeño.
- **Dashboard**: gastos fijos prorrateados por día, utilidad operativa, punto de equilibrio, costo laboral,
  prime cost, estado de resultados y gastos por categoría. La gráfica de tendencia agrega la utilidad.
- Exportación de gastos fijos a Excel/CSV.
- **Pre-cuenta**: imprime la cuenta de una mesa abierta para que el cliente la revise antes de pagar
  (marcada «No es comprobante de pago»; queda en auditoría y no cierra la cuenta ni mueve inventario).
- **Dividir cuenta / pasar consumos**: mueve piezas de una mesa a una cuenta nueva (con su propio folio) o a otra
  mesa abierta, conservando las notas. El descuento se queda en la cuenta original.
- El tipo de usuario (Admin / User) se elige en un menú desplegable con su descripción.

- **Ayuda dentro del sistema** (menú lateral o tecla **F1**): guía de operación con búsqueda y secciones según el tipo de
  usuario, más datos de versión y ubicación de datos, respaldos y registros.
- **Kit de instalación** (`python scripts/empaquetar_kit.py`): carpeta y .zip con guía de instalación, manual del usuario y
  checklist de entrega en HTML, herramientas `.bat` (verificar equipo, respaldar datos), código fuente y, si existe, el
  instalador de Windows. Nuevo `scripts/instalar-desde-codigo.bat` como alternativa al instalador.
- El instalador agrega el acceso «Punto de Venta MASTER (modo navegador)» para equipos sin WebView2.

### Corregido
- Tras actualizar el sistema, la ventana podía mostrar «The requested module '../api.js' does not provide an export named …»
  por mezclar archivos JS viejos guardados en su caché con los nuevos. Ahora el frontend se sirve bajo `/static/<huella>/…`,
  donde la huella cambia con cada versión, y el index nunca se cachea.
- Cerrar sesión desde cualquier pantalla ya no provoca un error de JavaScript en la consola.

### Cambiado
- Cerrar el turno de caja se bloquea mientras haya cuentas abiertas.
- Esquema v2 (migración automática): `ventas.mesa`, tablas `cuentas`, `cuenta_items` y `gastos_fijos`,
  y consecutivo de folios en `config.folio_consecutivo` (arranca en el último folio existente).

## [1.0.0] - 2026-09-30
### Agregado
- Punto de venta con categorías, búsqueda, notas por platillo, descuentos y cobro en efectivo/tarjeta/transferencia.
- Backflush automático de inventario por receta al vender; reversa exacta al cancelar.
- Inventario: entradas con costo promedio ponderado, ajustes manuales, conteo físico masivo y kardex.
- Caja: apertura de turno, ingresos/retiros de efectivo y corte con conteo por denominación.
- Usuarios con niveles Admin y User; contraseñas PBKDF2; bitácora de auditoría.
- Dashboard: KPIs vs. periodo anterior, tendencias, ventas por hora/día, top productos, categorías,
  métodos de pago, ingeniería de menú, rentabilidad, alertas y cobertura de inventario, merma, usuarios.
- Exportación a Excel/CSV, respaldos automáticos y restauración.
- Ticket térmico 58/80 mm y corte de caja imprimible.
- Datos de ejemplo (food truck con 90 días de operación).
- Empaquetado Windows (PyInstaller + Inno Setup) y CI en GitHub Actions.

[Sin publicar]: https://github.com/JuanDiaz-DataAnalyst/punto-de-venta-master/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/JuanDiaz-DataAnalyst/punto-de-venta-master/releases/tag/v1.0.0
