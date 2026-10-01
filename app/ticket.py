"""Ticket en HTML para impresora térmica de 58 mm u 80 mm (se imprime con el diálogo de Windows)."""

from html import escape


def _m(x, moneda="$"):
    return f"{moneda}{x:,.2f}"


def render_ticket(venta: dict, cfg: dict, reimpresion: bool = False, precuenta: bool = False) -> str:
    """precuenta=True imprime la cuenta de una mesa abierta (sin pago ni IVA desglosado; no es comprobante)."""
    ancho = "58mm" if str(cfg.get("ancho_ticket", "80")) == "58" else "80mm"
    fuente = "11px" if ancho == "58mm" else "12.5px"
    mon = cfg.get("moneda", "$")
    filas = "".join(
        f"""<tr><td class="q">{ln["cantidad"]:g}</td><td>{escape(ln["producto"])}
              {f'<div class="nota">{escape(ln["nota"])}</div>' if ln.get("nota") else ""}</td>
              <td class="r">{_m(ln["importe_bruto"], mon)}</td></tr>"""
        for ln in venta["lineas"]
    )
    iva = ""
    if cfg.get("mostrar_iva", "1") == "1":
        tasa = float(cfg.get("tasa_iva", "16") or 0) / 100
        if tasa > 0:
            base = venta["total"] / (1 + tasa)
            iva = f"""<tr><td>IVA incluido ({tasa * 100:g}%)</td><td class="r">{_m(venta["total"] - base, mon)}</td></tr>"""
    desc = (
        f"""<tr><td>Descuento</td><td class="r">-{_m(venta["descuento"], mon)}</td></tr>"""
        if venta["descuento"]
        else ""
    )
    pago = ""
    if venta.get("es_efectivo"):
        pago = f"""<tr><td>Recibido</td><td class="r">{_m(venta["pago_recibido"] or 0, mon)}</td></tr>
                    <tr><td>Cambio</td><td class="r">{_m(venta["cambio"] or 0, mon)}</td></tr>"""
    cabecera = "".join(f"<div>{escape(cfg[k])}</div>" for k in ("direccion", "telefono") if cfg.get(k))
    rfc = f"<div>RFC: {escape(cfg['rfc'])}</div>" if cfg.get("rfc") else ""
    cancel = '<div class="cancel">*** VENTA CANCELADA ***</div>' if venta["estado"] == "CANCELADA" else ""
    reimp = '<div class="c small">REIMPRESIÓN</div>' if reimpresion else ""
    if precuenta:
        reimp = '<div class="cancel">PRE-CUENTA<br><span class="small">No es comprobante de pago</span></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{escape(venta["folio"])}</title>
<style>
 @page {{ size: {ancho} auto; margin: 0; }}
 * {{ box-sizing: border-box; }}
 body {{ width: {ancho}; margin: 0; padding: 3mm 3mm 6mm; font-family: 'Consolas','Courier New',monospace;
        font-size: {fuente}; color: #000; background: #fff; }}
 .c {{ text-align: center; }} .r {{ text-align: right; white-space: nowrap; }}
 h1 {{ font-size: 1.35em; margin: 0 0 2px; text-align: center; }}
 .small {{ font-size: .85em; }}
 hr {{ border: 0; border-top: 1px dashed #000; margin: 5px 0; }}
 table {{ width: 100%; border-collapse: collapse; }} td {{ vertical-align: top; padding: 1px 0; }}
 td.q {{ width: 2.2em; }} .nota {{ font-size: .85em; font-style: italic; }}
 .total td {{ font-size: 1.3em; font-weight: bold; padding-top: 3px; }}
 .cancel {{ text-align:center; font-weight:bold; border:1px solid #000; margin:4px 0; padding:2px; }}
</style></head><body>
 <h1>{escape(cfg.get("nombre_negocio", ""))}</h1>
 <div class="c small">{cabecera}{rfc}</div>
 <hr>
 <div class="small">Folio: <b>{escape(venta["folio"])}</b><br>Fecha: {venta["fecha_hora"]}<br>
 {("Mesa: <b>" + escape(venta["mesa"]) + "</b><br>") if venta.get("mesa") else ""}Atendió: {escape(venta["usuario"])}{("<br>Cliente: " + escape(venta["cliente"])) if venta.get("cliente") else ""}</div>
 {reimp}{cancel}
 <hr>
 <table>{filas}</table>
 <hr>
 <table>
  <tr><td>Subtotal</td><td class="r">{_m(venta["subtotal"], mon)}</td></tr>
  {desc}
  <tr class="total"><td>TOTAL</td><td class="r">{_m(venta["total"], mon)}</td></tr>
  {iva}
  {"" if precuenta else f'<tr><td>Pago</td><td class="r">{escape(venta["metodo_pago"])}</td></tr>'}
  {pago}
 </table>
 <hr>
 <div class="c">{escape(cfg.get("mensaje_ticket", ""))}</div>
</body></html>"""
