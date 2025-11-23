from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
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
from reportlab.lib.utils import ImageReader

# --- Authentication Views ---

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

# --- Helper Functions ---

def get_all_certificates():
    """Helper to fetch all certs from Firestore for the template"""
    # Order by created_at descending so newest are top
    docs = db.collection('certificates').order_by('created_at', direction=firestore.Query.DESCENDING).limit(100).stream()
    cert_list = []
    for doc in docs:
        cert_list.append(doc.to_dict())
    return cert_list

def create_pdf_with_qrcode(original_blob, qr_image_io, new_pdf_filename): 
    """Downloads original PDF, stamps QR, uploads new PDF."""
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    
    # Position: Top Right
    page_width = letter[0]
    qr_size = 65
    x_position = ((page_width - 9) - qr_size) / 2
    y_position = 50

    qr_image_io.seek(0)
    image = ImageReader(qr_image_io)
    c.drawImage(image, x_position, y_position, width=qr_size, height=qr_size)
    c.save()

    packet.seek(0)
    new_pdf_layer = PdfReader(packet)
 
    pdf_bytes = original_blob.download_as_bytes()
    existing_pdf = PdfReader(BytesIO(pdf_bytes))
    output_pdf = PdfWriter()

    # Merge first page
    if len(existing_pdf.pages) > 0:
        page = existing_pdf.pages[0]
        page.merge_page(new_pdf_layer.pages[0])
        output_pdf.add_page(page)
        
        # Add remaining pages
        for i in range(1, len(existing_pdf.pages)):
            output_pdf.add_page(existing_pdf.pages[i])
 
    final_pdf_io = BytesIO()
    output_pdf.write(final_pdf_io)
    final_pdf_io.seek(0)

    new_pdf_blob = bucket.blob(new_pdf_filename)
    new_pdf_blob.upload_from_file(final_pdf_io, content_type='application/pdf')

# --- Main Logic ---

@csrf_exempt 
@login_required
def upload_certificate(request):
    if request.method == 'POST':
        # 1. Grab list of files manually first to ensure we have data
        files = request.FILES.getlist('document')
        action_type = request.POST.get('action', 'add_qr')
        
        if files:
            uploaded_count = 0
            
            # 2. LOOP THROUGH EVERY FILE
            for uploaded_file in files:
                try:
                    # A. Generate Identifiers
                    cert_uuid = str(uuid.uuid4())
                    
                    # B. Upload Original/Raw (Safety Backup)
                    raw_filename = f"{cert_uuid}_raw_{uploaded_file.name}"
                    blob = bucket.blob(raw_filename)
                    uploaded_file.seek(0)
                    blob.upload_from_file(uploaded_file, content_type='application/pdf')
                    uploaded_file.seek(0) # Reset pointer

                    # C. Generate QR Code (DB needs this regardless of stamp option)
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

                    # D. Handle Action Type
                    final_document_url = ""
                    final_storage_name = ""

                    if action_type == 'add_qr':
                        # OPTION A: Add QR -> Rename to UUID
                        final_pdf_name = f"{cert_uuid}.pdf"
                        create_pdf_with_qrcode(blob, qr_io, final_pdf_name)
                        
                        final_pdf_blob = bucket.blob(final_pdf_name)
                        final_pdf_blob.make_public()
                        final_document_url = final_pdf_blob.public_url
                        final_storage_name = final_pdf_name
                    else:
                        # OPTION B: No QR -> Keep Original Name
                        final_pdf_name = uploaded_file.name
                        
                        new_blob = bucket.blob(final_pdf_name)
                        uploaded_file.seek(0)
                        new_blob.upload_from_file(uploaded_file, content_type='application/pdf')
                        new_blob.make_public()
                        final_document_url = new_blob.public_url
                        final_storage_name = final_pdf_name

                    # E. Save to Firestore
                    doc_ref = db.collection('certificates').document(cert_uuid)
                    doc_ref.set({
                        'id': cert_uuid,
                        'name': cert_uuid, # Kept for backward compatibility
                        'document_url': final_document_url,
                        'qr_code_url': qr_code_url,
                        'created_at': datetime.datetime.now(),
                        'original_filename': uploaded_file.name,
                        'storage_filename': final_storage_name, # CRITICAL for retrieval
                        'has_stamped_qr': (action_type == 'add_qr')
                    })
                    
                    uploaded_count += 1
                except Exception as e:
                    print(f"Error uploading {uploaded_file.name}: {e}")
                    # Continue loop even if one fails

            certificates = get_all_certificates()
            return render(request, 'upload.html', {
                'form': CertificateUploadForm(), 
                'message': f"Success! Processed {uploaded_count} files.", 
                'certificates': certificates
            })
        
    form = CertificateUploadForm()
    certificates = get_all_certificates()
    return render(request, 'upload.html', {'form': form, 'certificates': certificates})
def view_certificate(request, certificate_name):
    try:
        # 1. Do NOT strip the extension. We need 'file.pdf', not 'file'
        target_filename = certificate_name 
        
        # 2. Query Firestore for a document where 'storage_filename' matches
        # We use .limit(1) because standard queries return a list
        query = db.collection('certificates').where('storage_filename', '==', target_filename).limit(1).stream()
        
        found_doc = None
        for doc in query:
            found_doc = doc.to_dict()
            break
            
        # 3. Determine the file to fetch
        final_filename = ""
        
        if found_doc:
            # If found in DB, use the trusted name from DB
            final_filename = found_doc.get('storage_filename')
        else:
            # Fallback: If not in DB, try to look for the file directly in storage
            # This is useful if you uploaded files manually to Firebase Console
            final_filename = target_filename

        # 4. Check Storage
        blob = bucket.blob(final_filename)

        if not blob.exists():
            raise Http404(f"File '{final_filename}' not found in storage.")
            
        file_bytes = blob.download_as_bytes()
        
        response = HttpResponse(file_bytes, content_type="application/pdf")
        # content-disposition inline allows the browser to open it
        response["Content-Disposition"] = f'inline; filename="{final_filename}"'
        return response

    except Exception as e:
        print(f"Error viewing certificate: {e}")
        raise Http404(f"An error occurred: {e}")