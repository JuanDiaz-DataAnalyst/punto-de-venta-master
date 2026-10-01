# Manual de usuario

## 1. Primera vez
1. Abre **Punto de Venta MASTER**.
2. Captura el nombre del negocio y crea el usuario **administrador**.
3. *(Opcional)* Marca **Cargar datos de ejemplo** para explorar el sistema con un food truck ficticio
   y 90 días de ventas. Usuarios de ejemplo: `carla` y `luis`, contraseña `1234`.

## 2. Dar de alta el menú (Admin → Menú y recetas)
1. **Proveedores** (opcional) y **Categorías** (Tacos, Bebidas…).
2. **Insumos**: nombre, unidad (kg, l, pz…), stock mínimo, existencia inicial y costo unitario.
3. **Productos**: precio de venta y **receta** = cuánto de cada insumo consume una unidad.
   El sistema calcula costo, margen, food cost y un precio sugerido (food cost 30 %).
   - Un producto que revendes tal cual (un refresco) lleva como receta 1 pieza de ese insumo.

## 3. Operación diaria
| Momento | Dónde | Qué hacer |
|---|---|---|
| Inicio del día | Vender / Caja | **Abrir caja** con el fondo inicial |
| Llega un cliente | Vender | **+ Nueva mesa (F4)** y escribir el número de mesa (cada mesa es una pestaña con su folio) |
| Piden algo | Vender | Elegir la pestaña de la mesa y tocar productos; se puede agregar en cualquier momento |
| Piden la cuenta | Vender | Pestaña de la mesa → método de pago → **Cobrar (F12)** → imprimir ticket |
| Pago a proveedor en efectivo | Caja | **Retiro de efectivo** con concepto |
| Llega mercancía | Inventario → Entrada de material | Capturar insumos, cantidades y costo |
| Fin del día | Caja | **Cerrar turno**: contar efectivo por denominación → imprimir corte |

Atajos del punto de venta: **F2** buscar · **F4** nueva mesa · **F9** descuento · **F12** cobrar · **Esc** cerrar ventana.

### Mesas y tickets abiertos
- Cada mesa tiene su **propia pestaña** (el título es el número de mesa, con el total acumulado) y su **folio único**.
- Puedes abrir tantas mesas como necesites y cambiar entre ellas sin perder nada; las cuentas quedan guardadas aunque
  cierres el sistema.
- **Cambiar mesa** corrige el número; **Cancelar** descarta una cuenta (pide motivo si ya tiene consumos y queda en
  auditoría). Una mesa libre puede reutilizar su número, pero el folio nunca se repite.
- El inventario se descuenta al **cobrar**, no al agregar productos.
- **Pre-cuenta**: imprime la cuenta para que el cliente la revise antes de pagar; no es comprobante y no cierra la mesa.
- **Dividir / mover**: elige cuántas piezas de cada producto pasan a una **cuenta nueva** (con su propio folio, para
  cobrar por separado) o a **otra mesa abierta**. Las notas viajan con el producto y el descuento se queda en la
  cuenta original.
- No se puede cerrar el turno de caja mientras haya mesas abiertas.
- Para una venta al mostrador abre una pestaña con el nombre que quieras (por ejemplo «Llevar 1»).

## 4. Inventario
- Cada venta descuenta automáticamente los insumos de la receta (**backflush**).
- **Entradas** recalculan el costo promedio ponderado.
- **Ajuste manual** (Admin): merma, caducidad, daño o consumo interno; siempre con motivo.
- **Conteo físico** (Admin): captura lo contado y el sistema ajusta solo las diferencias.
- **Kardex**: historial de cada movimiento con existencia resultante.
- En Configuración puedes bloquear ventas cuando no hay existencia suficiente.

## 5. Cancelaciones (Admin)
Ventas → abrir el ticket → **Cancelar venta** con motivo. El inventario consumido regresa automáticamente
y la cancelación queda en auditoría.

## 6. Dashboard (Admin)
Elige el periodo (hoy, 7/30/90 días, mes, rango). Todos los indicadores se comparan con el periodo
anterior de la misma duración. Con los gastos fijos capturados verás además la utilidad operativa, el punto de
equilibrio (ventas necesarias para cubrir los gastos fijos con tu margen actual), el costo laboral (nómina ÷ ventas),
el *prime cost* (insumos + nómina ÷ ventas, conviene mantenerlo cerca o por debajo de 60-65 %) y el estado de resultados.

**Ingeniería de menú**: clasifica cada producto por popularidad y margen por unidad.
| Clase | Significado | Acción sugerida |
|---|---|---|
| Estrella | Se vende mucho y deja buen margen | Protegerla y destacarla |
| Caballo de batalla | Se vende mucho, margen bajo | Revisar porción/costo o subir precio gradualmente |
| Rompecabezas | Buen margen, poca venta | Promocionar o reubicar en el menú |
| Perro | Poca venta, poco margen | Rediseñar o retirar |

## 7. Gastos fijos (Admin → Gastos fijos)
Captura lo que cuesta mantener el negocio cada mes: sueldos, renta, luz, agua, gas, internet, contador, etc.
1. Pulsa **Agregar conceptos comunes** para cargar una lista típica de restaurante pequeño con monto $0.
2. Escribe el **monto mensual** de cada concepto directamente en la tabla (o usa **Editar** para fechas y notas).
   Puedes agregar varios renglones de nómina (uno por empleado) con **+ Nuevo gasto**.
3. El dashboard reparte cada gasto por día y lo resta al margen bruto para calcular la **utilidad operativa**, el
   **punto de equilibrio**, el **costo laboral** y el **prime cost**.

Para registrar un aumento sin alterar los meses anteriores, termina el gasto en la fecha del cambio
(**Vigente hasta**) y agrega uno nuevo con el monto actualizado.

## 8. Respaldos y exportaciones (Admin → Reportes y respaldos)
- Se crea un respaldo automático cada vez que se abre el sistema (se guardan los últimos 20).
- Copia periódicamente la carpeta `%LOCALAPPDATA%\PuntoDeVentaMASTER\respaldos` a una USB o a la nube.
- Exporta a Excel/CSV: ventas detalle, tickets, productos, inventario, kardex, recetas, cortes, gastos fijos y auditoría.

## 9. Impresora de tickets
Instala la impresora térmica en Windows y márcala como predeterminada. En el diálogo de impresión
desactiva encabezados/pies de página y márgenes. Elige 58 u 80 mm en **Configuración**.

## 10. Solución de problemas
| Síntoma | Solución |
|---|---|
| No abre la ventana | Instala *Microsoft Edge WebView2 Runtime*; mientras tanto el sistema abre en el navegador |
| "No hay un turno de caja abierto" | Abre la caja en Vender o Caja/Turno |
| "Inventario insuficiente" | Registra la entrada de material o activa *Permitir vender sin existencia* |
| Algo falla | Revisa `%LOCALAPPDATA%\PuntoDeVentaMASTER\logs\pos.log` y adjúntalo al reporte |
