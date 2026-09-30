# Changelog

Todos los cambios relevantes se documentan aquí. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

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
