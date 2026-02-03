import io
import os

from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader, simpleSplit

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .models import (
    Datospersonales,
    Cursosrealizados,
    Experiencialaboral,
    Productosacademicos,
    Productoslaborales,
    Reconocimientos,
    Ventagarage,
)


# =========================
# Helpers
# =========================
def _get_perfil_activo():
    # SOLO perfil activo. Si no hay, devuelve None (y el front no debe mostrar nada).
    return Datospersonales.objects.filter(perfilactivo=True).order_by("-idperfil").first()


def _image_reader_from_field(image_field):
    image_field.open("rb")
    try:
        data = image_field.read()
    finally:
        try:
            image_field.close()
        except Exception:
            pass
    return ImageReader(io.BytesIO(data))


def _register_pretty_fonts():
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"

    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf", "SegoeUI", "SegoeUI-Bold"),
        (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf", "Calibri", "Calibri-Bold"),
    ]
    for reg_path, bold_path, reg_name, bold_name in candidates:
        try:
            if os.path.exists(reg_path) and os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                font_regular = reg_name
                font_bold = bold_name
                break
        except Exception:
            continue

    return font_regular, font_bold


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _draw_wrapped(c, text, x, y, max_width, font_name, font_size, leading):
    if not text or not str(text).strip():
        return y
    lines = simpleSplit(str(text), font_name, font_size, max_width)
    for ln in lines:
        c.drawString(x, y, ln)
        y -= leading
    return y


def _pairs_from_fields(pairs):
    out = []
    for label, val in pairs:
        val = _clean(val)
        if val:
            out.append((label, val))
    return out


def _collect_images(perfil, cursos, experiencias, prod_acad, prod_lab, reconoc):
    """
    certificados: imágenes tipo certificado (una por hoja)
    normales: imágenes tipo "foto del producto" (en grid)
    """
    certificados = []
    normales = []

    def add_cert(section, label, field):
        if field and getattr(field, "name", None):
            certificados.append({"section": section, "label": label, "field": field})

    def add_normal(section, label, field, kind="Imagen"):
        if field and getattr(field, "name", None):
            normales.append({"section": section, "label": f"{label} — {kind}", "field": field})

    for c_ in cursos:
        base = f'Curso "{c_.nombrecurso or "Sin título"}"'
        add_cert("Cursos", base, c_.certificado_imagen)

    for e in experiencias:
        cargo = e.cargodesempenado or "Sin título"
        emp = f" - {e.nombrempresa}" if e.nombrempresa else ""
        base = f'Experiencia "{cargo}{emp}"'
        add_cert("Experiencia laboral", base, e.certificado_imagen)

    for p in prod_acad:
        base = f'Producto académico "{p.nombreproducto or "Sin título"}"'
        add_normal("Productos académicos", base, p.imagenproducto, "Imagen del producto")
        add_cert("Productos académicos", base, p.certificado_imagen)

    for p in prod_lab:
        base = f'Producto laboral "{p.nombreproducto or "Sin título"}"'
        add_normal("Productos laborales", base, p.imagenproducto, "Imagen del producto")
        add_cert("Productos laborales", base, p.certificado_imagen)

    # ✅ FIX: en tu modelo el campo es entidadpatrocinadora
    for r in reconoc:
        tipo = r.tiporeconocimiento or "Reconocimiento"
        ent = f" - {r.entidadpatrocinadora}" if r.entidadpatrocinadora else ""
        base = f'Reconocimiento "{tipo}{ent}"'
        add_cert("Reconocimientos", base, r.certificado_imagen)

    return certificados, normales


# =========================
# Views web
# =========================
def home(request):
    perfil = _get_perfil_activo()
    permitir_impresion = bool(perfil and perfil.permitir_impresion)

    counts = {
        "cursos": perfil.cursos.filter(activarparaqueseveaenfront=True).count() if perfil else 0,
        "experiencias": perfil.experiencias.filter(activarparaqueseveaenfront=True).count() if perfil else 0,
        "prod_acad": perfil.productos_academicos.filter(activarparaqueseveaenfront=True).count() if perfil else 0,
        "prod_lab": perfil.productos_laborales.filter(activarparaqueseveaenfront=True).count() if perfil else 0,
        "reconoc": perfil.reconocimientos.filter(activarparaqueseveaenfront=True).count() if perfil else 0,
        "venta": perfil.venta_garage.filter(activarparaqueseveaenfront=True).count() if perfil else 0,
    }

    return render(request, "home.html", {
        "perfil": perfil,
        "permitir_impresion": permitir_impresion,
        "counts": counts,
    })


def datos_personales(request):
    perfil = _get_perfil_activo()
    return render(request, "secciones/datos_personales.html", {"perfil": perfil})


def cursos(request):
    perfil = _get_perfil_activo()
    items = []

    if perfil:
        qs = perfil.cursos.filter(
            activarparaqueseveaenfront=True
        ).order_by("-fechafin", "-fechainicio", "-idcursorealizado")

        for c in qs:
            c.is_pdf = False
            if c.certificado_imagen and c.certificado_imagen.name:
                c.is_pdf = c.certificado_imagen.name.lower().endswith(".pdf")
            items.append(c)

    return render(request, "secciones/cursos.html", {
        "perfil": perfil,
        "items": items
    })



def experiencia(request):
    perfil = _get_perfil_activo()
    items = (
        perfil.experiencias
        .filter(activarparaqueseveaenfront=True)
        .order_by("-fechafin", "-fechainicio", "-idexperiencialaboral")
        if perfil else []
    )
    return render(request, "secciones/experiencia.html", {"perfil": perfil, "items": items})


def productos_academicos(request):
    perfil = _get_perfil_activo()
    items = []

    if perfil:
        qs = perfil.productos_academicos.filter(
            activarparaqueseveaenfront=True
        ).order_by("-idproductoacademico")

        for p in qs:
            p.is_pdf = False
            if p.certificado_imagen and p.certificado_imagen.name:
                p.is_pdf = p.certificado_imagen.name.lower().endswith(".pdf")
            items.append(p)

    return render(request, "secciones/productos_academicos.html", {
        "perfil": perfil,
        "items": items
    })


def productos_laborales(request):
    perfil = _get_perfil_activo()
    items = []

    if perfil:
        qs = perfil.productos_laborales.filter(
            activarparaqueseveaenfront=True
        ).order_by("-fechaproducto", "-idproductolaboral")

        for p in qs:
            p.is_pdf = False
            if p.certificado_imagen and p.certificado_imagen.name:
                p.is_pdf = p.certificado_imagen.name.lower().endswith(".pdf")
            items.append(p)

    return render(request, "secciones/productos_laborales.html", {
        "perfil": perfil,
        "items": items
    })

def reconocimientos(request):
    perfil = _get_perfil_activo()
    items = []

    if perfil:
        qs = perfil.reconocimientos.filter(
            activarparaqueseveaenfront=True
        ).order_by("-fechareconocimiento", "-idreconocimiento")

        for r in qs:
            r.is_pdf = False
            if r.certificado_imagen and r.certificado_imagen.name:
                r.is_pdf = r.certificado_imagen.name.lower().endswith(".pdf")
            items.append(r)

    return render(request, "secciones/reconocimientos.html", {
        "perfil": perfil,
        "items": items
    })



def venta_garage(request):
    perfil = _get_perfil_activo()
    items = (
        perfil.venta_garage
        .filter(activarparaqueseveaenfront=True)
        .order_by("-fecha", "-idventagarage")
        if perfil else []
    )

    return render(request, "secciones/venta_garage.html", {
        "perfil": perfil,
        "items": items
    })


from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from django.http import HttpResponse, HttpResponseForbidden

def imprimir_hoja_vida(request):
    # ==================================================
    # LOGICA (INTACTA)
    # ==================================================
    perfil = _get_perfil_activo()

    if not perfil:
        return HttpResponse("Perfil no encontrado", status=404)

    if not perfil.permitir_impresion:
        return HttpResponseForbidden("No autorizado", status=403)

    s = request.GET
    show_exp = s.get("experiencia") == "on"
    show_cur = s.get("cursos") == "on"
    show_rec = s.get("reconocimientos") == "on"
    show_pa  = s.get("prod_acad") == "on"
    show_pl  = s.get("prod_lab") == "on"
    show_vg  = s.get("venta") == "on"

    exp_qs = list(perfil.experiencias.filter(activarparaqueseveaenfront=True)) if show_exp else []
    cursos_qs = list(perfil.cursos.filter(activarparaqueseveaenfront=True)) if show_cur else []
    rec_qs = list(perfil.reconocimientos.filter(activarparaqueseveaenfront=True)) if show_rec else []
    pa_qs = list(perfil.productos_academicos.filter(activarparaqueseveaenfront=True)) if show_pa else []
    pl_qs = list(perfil.productos_laborales.filter(activarparaqueseveaenfront=True)) if show_pl else []
    vg_qs = list(perfil.venta_garage.filter(activarparaqueseveaenfront=True)) if show_vg else []

    cert_imgs, normal_imgs = _collect_images(
        perfil, cursos_qs, exp_qs, pa_qs, pl_qs, rec_qs,
    )
    evidencias = cert_imgs + normal_imgs

    FONT, FONT_B = _register_pretty_fonts()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="hoja_de_vida_pro.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    W, H = A4

    # ==================================================
    # NUEVO DISEÑO "CANVA STYLE"
    # ==================================================
    # Paleta de colores
    col_sidebar     = colors.HexColor("#1e293b")  # Dark Slate (Lateral)
    col_sidebar_txt = colors.HexColor("#f8fafc")  # Off-white
    col_accent      = colors.HexColor("#38bdf8")  # Light Blue/Cyan (Detalles)
    col_title       = colors.HexColor("#0f172a")  # Dark text
    col_text        = colors.HexColor("#475569")  # Gray text
    col_line        = colors.HexColor("#e2e8f0")  # Light line

    # Dimensiones
    sidebar_w = 7.0 * cm
    margin_top = 1.0 * cm
    margin_content = 1.0 * cm
    
    # Area de contenido principal
    content_x = sidebar_w + margin_content
    content_w = W - content_x - 0.8 * cm

    # ==================================================
    # HELPER: SIDEBAR (FONDO + DATOS)
    # ==================================================
    def draw_sidebar():
        # Fondo columna izquierda
        c.setFillColor(col_sidebar)
        c.rect(0, 0, sidebar_w, H, stroke=0, fill=1)
        
        # Cursor vertical
        y = H - 1.5 * cm

        # --- FOTO DE PERFIL (CIRCULAR) ---
        if perfil.foto_perfil:
            try:
                img = _image_reader_from_field(perfil.foto_perfil)
                
                # Configurar máscara circular
                c.saveState()
                path = c.beginPath()
                # Centro del circulo: (sidebar_w / 2, y - radio)
                radio = 2.2 * cm
                center_x = sidebar_w / 2
                center_y = y - radio
                
                path.circle(center_x, center_y, radio)
                c.clipPath(path, stroke=0)
                
                # Dibujar imagen
                c.drawImage(img, center_x - radio, center_y - radio, radio*2, radio*2, preserveAspectRatio=True, anchor='c')
                c.restoreState()
                
                # Borde decorativo
                c.setStrokeColor(col_accent)
                c.setLineWidth(2)
                c.circle(center_x, center_y, radio, stroke=1, fill=0)
                
                y -= (radio * 2) + 1.0 * cm
            except:
                pass
        else:
            y -= 2 * cm

        # --- NOMBRE ---
        c.setFillColor(col_sidebar_txt)
        c.setFont(FONT_B, 16)
        
        # Dividir nombre si es muy largo
        full_name = f"{perfil.nombres}\n{perfil.apellidos}"
        for line in full_name.split("\n"):
            c.drawCentredString(sidebar_w / 2, y, line.upper())
            y -= 0.7 * cm
        
        y -= 1.0 * cm

        # --- SECCION DATOS ---
        c.setFillColor(col_accent)
        c.setFont(FONT_B, 10)
        c.drawString(0.8 * cm, y, "INFORMACIÓN PERSONAL")
        c.setStrokeColor(col_accent)
        c.line(0.8 * cm, y - 0.2*cm, sidebar_w - 0.8*cm, y - 0.2*cm)
        y -= 0.8 * cm

        datos = [
            ("Cédula", perfil.numerocedula),
            ("Nacimiento", str(perfil.fechanacimiento) if perfil.fechanacimiento else ""),
            ("Teléfono", perfil.telefonofijo),
            ("Dirección", perfil.direcciondomiciliaria),
            ("Estado Civil", perfil.estadocivil),
        ]

        for label, val in datos:
            if not val: continue
            
            # Label
            c.setFillColor(colors.HexColor("#94a3b8")) # Gris azulado claro
            c.setFont(FONT_B, 8)
            c.drawString(0.8 * cm, y, label.upper())
            y -= 0.4 * cm
            
            # Valor (con wrap)
            c.setFillColor(col_sidebar_txt)
            c.setFont(FONT, 9)
            # Usamos tu funcion _draw_wrapped
            # Nota: ajustamos el width para que quepa en el sidebar
            y = _draw_wrapped(c, str(val), 0.8 * cm, y, sidebar_w - 1.6 * cm, FONT, 9, 12)
            y -= 0.4 * cm # Espacio extra entre items

    # ==================================================
    # HELPER: CONTENIDO PRINCIPAL
    # ==================================================
    y_content = H - margin_top - 0.5 * cm

    def check_space(needed_cm):
        nonlocal y_content
        # Si no hay espacio, nueva pagina
        if y_content < (margin_top + needed_cm * cm):
            c.showPage()
            draw_sidebar()
            y_content = H - margin_top - 1.5 * cm
            return True
        return False

    def draw_section_title(title):
        nonlocal y_content
        check_space(2.5)
        
        c.setFillColor(col_title)
        c.setFont(FONT_B, 14)
        c.drawString(content_x, y_content, title.upper())
        
        # Linea gruesa decorativa debajo del titulo
        c.setLineWidth(3)
        c.setStrokeColor(col_accent)
        c.line(content_x, y_content - 0.25*cm, content_x + 1.2*cm, y_content - 0.25*cm)
        
        # Linea fina extendida
        c.setLineWidth(1)
        c.setStrokeColor(col_line)
        c.line(content_x + 1.4*cm, y_content - 0.25*cm, content_x + content_w, y_content - 0.25*cm)
        
        y_content -= 1.2 * cm

    def draw_card(titulo, subtitulo):
        nonlocal y_content
        # Estimar altura para salto de pagina (calculo aproximado)
        lines = len(str(subtitulo).split('\n')) if subtitulo else 1
        height_aprox = 1.5 + (lines * 0.5)
        check_space(height_aprox)
        
        # Posiciones
        bullet_x = content_x + 0.2 * cm
        text_x = content_x + 1.0 * cm
        
        # Titulo item
        c.setFillColor(col_sidebar) # Usamos el color oscuro
        c.setFont(FONT_B, 11)
        c.drawString(text_x, y_content, titulo)
        y_content -= 0.5 * cm
        
        # Texto cuerpo
        c.setFillColor(col_text)
        c.setFont(FONT, 10)
        y_start_text = y_content
        y_content = _draw_wrapped(c, subtitulo or "", text_x, y_content, content_w - 1.0*cm, FONT, 10, 14)
        
        # Decoración lateral (Linea vertical tipo timeline)
        c.setStrokeColor(col_line)
        c.setLineWidth(1)
        # Dibujamos linea desde el titulo hasta el final del texto
        c.line(bullet_x, y_start_text + 0.5*cm, bullet_x, y_content + 0.2*cm)
        
        # Punto (Bullet)
        c.setFillColor(col_accent)
        c.circle(bullet_x, y_start_text + 0.65*cm, 0.12*cm, fill=1, stroke=0)
        
        y_content -= 0.6 * cm

    # ==================================================
    # RENDERIZADO CV
    # ==================================================
    
    # 1. Dibujar sidebar inicial
    draw_sidebar()

    # 2. Renderizar secciones activas
    if show_exp and exp_qs:
        draw_section_title("Experiencia Laboral")
        for it in exp_qs:
            draw_card(it.cargodesempenado, it.responsabilidades)

    if show_cur and cursos_qs:
        draw_section_title("Formación y Cursos")
        for it in cursos_qs:
            draw_card(it.nombrecurso, it.descripcioncurso)

    if show_pa and pa_qs:
        draw_section_title("Productos Académicos")
        for it in pa_qs:
            draw_card(it.nombreproducto, it.descripcion)

    if show_pl and pl_qs:
        draw_section_title("Productos Laborales")
        for it in pl_qs:
            draw_card(it.nombreproducto, it.descripcion)

    if show_rec and rec_qs:
        draw_section_title("Reconocimientos")
        for it in rec_qs:
            draw_card(it.tiporeconocimiento, it.descripcionreconocimiento)

    if show_vg and vg_qs:
        draw_section_title("Otros")
        for it in vg_qs:
            draw_card(it.nombreproducto, it.descripcion)

    # ==================================================
    # GALERÍA DE EVIDENCIAS (NUEVO DISEÑO GRID)
    # ==================================================
    if evidencias:
        c.showPage()
        
        # Cabecera Galeria
        c.setFillColor(col_sidebar)
        c.rect(0, H - 2.5*cm, W, 2.5*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(FONT_B, 18)
        c.drawCentredString(W/2, H - 1.5*cm, "GALERÍA DE EVIDENCIAS")
        
        # Config grid
        margin_g = 1.5 * cm
        cols = 2
        col_width = (W - (margin_g * 2) - 1.0*cm) / 2
        
        y_cursor = H - 3.5 * cm
        row_height = 7.5 * cm # Altura fija por "tarjeta"
        
        for i, ev in enumerate(evidencias):
            # Salto de pagina si no cabe la fila
            if y_cursor < margin_g + row_height:
                c.showPage()
                # Repetir cabecera pequeña
                c.setFillColor(col_sidebar)
                c.rect(0, H - 1.5*cm, W, 1.5*cm, fill=1, stroke=0)
                c.setFillColor(colors.white)
                c.setFont(FONT_B, 12)
                c.drawString(margin_g, H - 1.0*cm, "Galería (cont.)")
                y_cursor = H - 2.5 * cm

            # Calculo X (columna 0 o 1)
            col_idx = i % 2
            x_pos = margin_g + (col_idx * (col_width + 1.0*cm))
            
            # --- TARJETA IMAGEN ---
            # Fondo tarjeta
            c.setFillColor(colors.HexColor("#f1f5f9"))
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.roundRect(x_pos, y_cursor - row_height, col_width, row_height, 8, fill=1, stroke=1)
            
            # Imagen
            img_h = 4.5 * cm
            try:
                img = _image_reader_from_field(ev["field"])
                # Dibujar imagen con padding
                c.drawImage(img, x_pos + 0.2*cm, y_cursor - img_h - 0.2*cm, 
                          col_width - 0.4*cm, img_h, 
                          preserveAspectRatio=True, anchor='c', mask='auto')
            except:
                pass
            
            # Texto Caption
            text_area_y = y_cursor - img_h - 0.5*cm
            c.setFillColor(col_title)
            c.setFont(FONT_B, 9)
            c.drawString(x_pos + 0.3*cm, text_area_y, ev["section"])
            
            c.setFillColor(col_text)
            c.setFont(FONT, 8)
            _draw_wrapped(c, ev["label"], x_pos + 0.3*cm, text_area_y - 0.4*cm, col_width - 0.6*cm, FONT, 8, 10)
            
            # Bajar cursor solo si terminamos la fila (indice impar o ultimo elemento)
            if col_idx == 1 or i == len(evidencias) - 1:
                y_cursor -= (row_height + 0.5 * cm)

    c.save()
    return response