from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.conf import settings

# Import Firebase instances
from .firebase_config import db, bucket 
from .forms import CertificateUploadForm

import uuid
import qrcode
from firebase_admin import firestore
import datetime
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# --- Authentication Views ---
# Note: Django Auth still requires a small SQL DB (SQLite) by default.
# We will keep these as is to maintain functionality without complex Auth refactoring.

@csrf_exempt
def superuser_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None and user.is_superuser:
            login(request, user)
            return redirect("upload_certificate")
        return render(request, "index.html", {"error": "Invalid credentials."})
    return render(request, "index.html")

@csrf_exempt
def user_logout(request):
    logout(request)
    return redirect("login")

# --- Certificate Logic (Firebase Firestore + Storage) ---
@csrf_exempt 
@login_required
def upload_certificate(request):
    if request.method == 'POST':
        form = CertificateUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # CHANGE 1: Get list of all files
            files = request.FILES.getlist('document') 
            action_type = request.POST.get('action', 'add_qr')
            
            uploaded_count = 0
            
            # CHANGE 2: Loop through every file in the list
            for uploaded_file in files:
                
                # --- START PER-FILE LOGIC ---
                
                # 1. Generate IDs
                cert_uuid = str(uuid.uuid4())
                
                # 2. Upload Raw (Optional backup)
                # Note: If you want to save time/space for 220 files, you can skip this raw upload 
                # if you are doing Option B, but we will keep it for safety.
                raw_filename = f"{cert_uuid}_raw_{uploaded_file.name}" 
                blob = bucket.blob(raw_filename)
                blob.upload_from_file(uploaded_file, content_type='application/pdf')
                blob.make_public()
                uploaded_file.seek(0) 

                # 3. Generate QR Code
                link = request.build_absolute_uri(reverse('view_certificate', args=[cert_uuid]))
                qr = qrcode.make(link)
                qr_io = BytesIO()
                qr.save(qr_io, format="PNG")
                qr_io.seek(0)
                
                qr_filename = f"{cert_uuid}_qr.png"
                qr_blob = bucket.blob(qr_filename)
                qr_blob.upload_from_file(qr_io, content_type='image/png')
                qr_blob.make_public()
                qr_code_url = qr_blob.public_url

                # 4. Logic Split (With QR vs Original Name)
                final_document_url = ""
                final_storage_name = "" 

                if action_type == 'add_qr':
                    # --- OPTION A: STAMP QR ---
                    final_pdf_name = f"{cert_uuid}.pdf"
                    
                    create_pdf_with_qrcode(blob, qr_io, final_pdf_name)
                    
                    final_pdf_blob = bucket.blob(final_pdf_name)
                    final_pdf_blob.make_public()
                    final_document_url = final_pdf_blob.public_url
                    final_storage_name = final_pdf_name

                else:
                    # --- OPTION B: ORIGINAL NAME ---
                    # WARNING: If you upload 2 files with the exact same name in this batch, 
                    # the second one will overwrite the first one in storage!
                    final_pdf_name = uploaded_file.name 
                    
                    new_blob = bucket.blob(final_pdf_name)
                    new_blob.upload_from_file(uploaded_file, content_type='application/pdf')
                    new_blob.make_public()
                    final_document_url = new_blob.public_url
                    final_storage_name = final_pdf_name

                # 5. Save Metadata
                doc_ref = db.collection('certificates').document(cert_uuid)
                doc_ref.set({
                    'id': cert_uuid,
                    'name': cert_uuid,
                    'document_url': final_document_url,
                    'qr_code_url': qr_code_url,
                    'created_at': datetime.datetime.now(),
                    'original_filename': uploaded_file.name,
                    'storage_filename': final_storage_name,
                    'has_stamped_qr': (action_type == 'add_qr')
                })
                
                uploaded_count += 1
                # --- END PER-FILE LOGIC ---

            # Fetch list after all uploads are done
            certificates = get_all_certificates()
            
            return render(request, 'upload.html', {
                'form': form, 
                'message': f"Successfully uploaded {uploaded_count} certificates!", 
                'certificates': certificates
            })
    else:
        form = CertificateUploadForm()

    certificates = get_all_certificates()
    return render(request, 'upload.html', {'form': form, 'certificates': certificates})

def get_all_certificates():
    """Helper to fetch all certs from Firestore for the template"""
    docs = db.collection('certificates').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    cert_list = []
    for doc in docs:
        cert_list.append(doc.to_dict())
    return cert_list

def create_pdf_with_qrcode(original_blob, qr_image_io, new_pdf_filename): 
    """
    Downloads original PDF from Storage, stamps QR, uploads new PDF.
    """
    # Create the QR stamp PDF in memory
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    
    # Calculate position (Top Right)
    page_width = letter[0]
    qr_size = 65
    x_position = ((page_width - 9) - qr_size) / 2
    y_position = 50

    # Draw the QR image from the in-memory BytesIO object
    # We need to create a temporary file for ReportLab to read the image
    # or stick to drawing it if reportlab supports the stream directly (usually requires file path)
    # Simplest way: Use a temporary file for the image or ImageReader
    from reportlab.lib.utils import ImageReader
    qr_image_io.seek(0)
    image = ImageReader(qr_image_io)
    
    c.drawImage(image, x_position, y_position, width=qr_size, height=qr_size)
    c.save()

    packet.seek(0)
    new_pdf_layer = PdfReader(packet)
 
    # Download existing PDF bytes from Firebase
    pdf_bytes = original_blob.download_as_bytes()
    existing_pdf = PdfReader(BytesIO(pdf_bytes))
    output_pdf = PdfWriter()

    # Merge (assuming 1 page, or merging on the first page)
    page = existing_pdf.pages[0]
    page.merge_page(new_pdf_layer.pages[0])
    output_pdf.add_page(page)
    
    # If there are more pages, add them
    for i in range(1, len(existing_pdf.pages)):
        output_pdf.add_page(existing_pdf.pages[i])
 
    # Write final PDF to BytesIO
    final_pdf_io = BytesIO()
    output_pdf.write(final_pdf_io)
    final_pdf_io.seek(0)

    # Upload result to Firebase
    new_pdf_blob = bucket.blob(new_pdf_filename)
    new_pdf_blob.upload_from_file(final_pdf_io, content_type='application/pdf')

def view_certificate(request, certificate_name):
    try:
        # Clean the name input
        cert_id = certificate_name.replace('.pdf', '')
        
        # Fetch Metadata from Firestore
        doc_ref = db.collection('certificates').document(cert_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise Http404("Certificate metadata not found.")
        
        # We know the filename convention is {id}.pdf based on upload logic
        filename = f"{cert_id}.pdf"
        blob = bucket.blob(filename)

        if not blob.exists():
            raise Http404("Certificate PDF file not found in storage.")
            
        file_bytes = blob.download_as_bytes()
        
        response = HttpResponse(file_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    except Exception as e:
        raise Http404(f"An error occurred: {e}")
