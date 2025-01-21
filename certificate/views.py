from django.shortcuts import render, get_object_or_404,redirect
from django.http import HttpResponse
from django.urls import reverse
from .models import Certificate
from .forms import CertificateUploadForm
from django.contrib.auth.decorators import login_required 
from django.conf import settings 
import uuid
import qrcode
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter  
from django.core.files.base import ContentFile
from django.urls import reverse 
from google.cloud import storage
import uuid
from io import BytesIO
from django.views.decorators.csrf import csrf_exempt 
from django.contrib.auth import authenticate, login  

from django.contrib.auth import logout

import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def superuser_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(username=username, password=password)

        if user is not None and user.is_superuser:  
            login(request, user)  
            return redirect("upload_certificate") 
        return render(request, "index.html", {"error": "Invalid credentials or not authorized."})

    return render(request, "index.html") 

@csrf_exempt
def user_logout(request):
    logout(request)
    return redirect("login")
@csrf_exempt
@login_required
def upload_certificate(request):
    if request.method == 'POST':
        form = CertificateUploadForm(request.POST, request.FILES)
        if form.is_valid():
            certificate = form.save(commit=False)
             
            certificate.name = str(uuid.uuid4())  

            uploaded_file = request.FILES['document']
            ext = uploaded_file.name.split('.')[-1]
            new_filename = f"{uuid.uuid4()}.{ext}"

            client = storage.Client()
            bucket = client.get_bucket(settings.GS_BUCKET_NAME)

            blob = bucket.blob(new_filename)
            blob.upload_from_file(uploaded_file)

            certificate.document = blob.public_url 
            link = request.build_absolute_uri(reverse('view_certificate', args=[certificate.name]))
            qr = qrcode.make(link)
            qr_io = BytesIO()
            qr.save(qr_io, format="PNG")
            qr_content = ContentFile(qr_io.getvalue(), f"{uuid.uuid4()}.png")

            qr_code_filename = f"{uuid.uuid4()}.png"
            qr_blob = bucket.blob(qr_code_filename)
            qr_blob.upload_from_file(qr_content)

            certificate.qr_code = qr_blob.public_url

            uploaded_pdf_path = blob.public_url
            qr_code_image_path = qr_blob.public_url

            new_pdf_name = f"{uuid.uuid4()}.pdf"
            create_pdf_with_qrcode(uploaded_pdf_path, qr_code_image_path, new_pdf_name)

            certificate.document = new_pdf_name
            certificate.save()

            certificates = Certificate.objects.all()

            return render(request, 'upload.html', {'form': form, 'link': link, 'certificates': certificates})
    else:
        form = CertificateUploadForm()

    certificates = Certificate.objects.all()
    return render(request, 'upload.html', {'form': form, 'certificates': certificates})

def create_pdf_with_qrcode(pdf_path, qr_image_path, new_pdf_path): 
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)

    page_width = letter[0]
    page_height = letter[1]
    qr_size = 65
    x_position = ((page_width - 9) - qr_size) / 2
    y_position = 50

    c.drawImage(qr_image_path, x_position, y_position, width=qr_size, height=qr_size)
    c.save()

    packet.seek(0)
    new_pdf = PdfReader(packet)
 
    client = storage.Client()
    bucket = client.get_bucket(settings.GS_BUCKET_NAME)
 
    blob = bucket.blob(pdf_path.split('/')[-1])   
    pdf_bytes = blob.download_as_bytes() 

    
    existing_pdf_file = BytesIO(pdf_bytes)
    existing_pdf = PdfReader(existing_pdf_file)

    output_pdf = PdfWriter()

    page = existing_pdf.pages[0]
    page.merge_page(new_pdf.pages[0])

    output_pdf.add_page(page)
 
    new_pdf_blob = bucket.blob(new_pdf_path)
    with new_pdf_blob.open("wb") as f:
        output_pdf.write(f)
        
        
from django.http import HttpResponse, Http404
from google.cloud import storage
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Certificate

def view_certificate(request, certificate_name):
    try: 
        ceertificate_name = certificate_name.rstrip('.pdf')
        certificate = get_object_or_404(Certificate, name=certificate_name)
 
        file_url = certificate.document.url   
        file_name = file_url.split("/")[-1] 
        client = storage.Client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(file_name) 

        if not blob.exists():
            raise Http404("Certificate not found in storage.") 
        file_bytes = blob.download_as_bytes() 
        response = HttpResponse(file_bytes, content_type="application/pdf")
        
        response["Content-Disposition"] = f'inline; filename="{ceertificate_name}.pdf"'
        return response

    except Exception as e: 
        raise Http404(f"An error occurred: {e}")