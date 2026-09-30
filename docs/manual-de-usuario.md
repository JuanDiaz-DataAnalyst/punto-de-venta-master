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
| Venta | Vender | Tocar productos → método de pago → **Cobrar (F12)** → imprimir ticket |
| Pago a proveedor en efectivo | Caja | **Retiro de efectivo** con concepto |
| Llega mercancía | Inventario → Entrada de material | Capturar insumos, cantidades y costo |
| Fin del día | Caja | **Cerrar turno**: contar efectivo por denominación → imprimir corte |

Atajos del punto de venta: **F2** buscar · **F9** descuento · **F12** cobrar · **Esc** cerrar ventana.

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
anterior de la misma duración.

**Ingeniería de menú**: clasifica cada producto por popularidad y margen por unidad.
| Clase | Significado | Acción sugerida |
|---|---|---|
| Estrella | Se vende mucho y deja buen margen | Protegerla y destacarla |
| Caballo de batalla | Se vende mucho, margen bajo | Revisar porción/costo o subir precio gradualmente |
| Rompecabezas | Buen margen, poca venta | Promocionar o reubicar en el menú |
| Perro | Poca venta, poco margen | Rediseñar o retirar |

## 7. Respaldos y exportaciones (Admin → Reportes y respaldos)
- Se crea un respaldo automático cada vez que se abre el sistema (se guardan los últimos 20).
- Copia periódicamente la carpeta `%LOCALAPPDATA%\PuntoDeVentaMASTER\respaldos` a una USB o a la nube.
- Exporta a Excel/CSV: ventas detalle, tickets, productos, inventario, kardex, recetas, cortes y auditoría.

## 8. Impresora de tickets
Instala la impresora térmica en Windows y márcala como predeterminada. En el diálogo de impresión
desactiva encabezados/pies de página y márgenes. Elige 58 u 80 mm en **Configuración**.

## 9. Solución de problemas
| Síntoma | Solución |
|---|---|
| No abre la ventana | Instala *Microsoft Edge WebView2 Runtime*; mientras tanto el sistema abre en el navegador |
| "No hay un turno de caja abierto" | Abre la caja en Vender o Caja/Turno |
| "Inventario insuficiente" | Registra la entrada de material o activa *Permitir vender sin existencia* |
| Algo falla | Revisa `%LOCALAPPDATA%\PuntoDeVentaMASTER\logs\pos.log` y adjúntalo al reporte |
