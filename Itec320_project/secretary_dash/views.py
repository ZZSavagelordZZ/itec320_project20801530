from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import logout, authenticate, login, get_user_model
from django.forms import inlineformset_factory
from django.utils.safestring import mark_safe
from .models import Patient, Appointment, Secretary, Medicine, Examination, Prescription, BusyHours
from .forms import (
    PatientForm, AppointmentForm, MedicineForm, 
    ExaminationForm, SecretaryCreationForm, PrescriptionForm, BusyHoursForm,
    EmailLoginForm, ForgotPasswordForm, SetPasswordForm
)
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .tokens import password_reset_token
import json
import logging

logger = logging.getLogger(__name__)

def is_secretary(user):
    return Secretary.objects.filter(user=user).exists()

def is_doctor(user):
    return user.is_superuser

def root_redirect(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.user.is_superuser:
        return redirect('secretary_dash:doctor_dashboard')
    
    if is_secretary(request.user):
        return redirect('secretary_dash:secretary_dashboard')
    
    return redirect('login')

@login_required
def logout_view(request):
    logout(request)
    return redirect('secretary_dash:login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('secretary_dash:root')
    
    if request.method == 'POST':
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('secretary_dash:root')
            else:
                messages.error(request, 'Invalid email or password')
    else:
        form = EmailLoginForm()
    
    return render(request, 'secretary_dash/login.html', {'form': form})

# Common views for both roles
def is_staff(user):
    """Check if user is either a doctor (superuser) or secretary"""
    return user.is_superuser or hasattr(user, 'secretary')

@login_required
@user_passes_test(is_staff)
def patient_list(request):
    patients = Patient.objects.all().order_by('name')
    return render(request, 'secretary_dash/common/patient_list.html', {
        'patients': patients
    })

@login_required
@user_passes_test(is_staff)
def patient_create(request):
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save()
            messages.success(request, 'Patient added successfully.')
            return redirect('secretary_dash:patient_list')
    else:
        form = PatientForm()
    
    return render(request, 'secretary_dash/common/patient_form.html', {
        'form': form,
        'title': 'Add New Patient'
    })

@login_required
@user_passes_test(is_staff)
def patient_edit(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, 'Patient updated successfully.')
            return redirect('secretary_dash:patient_list')
    else:
        form = PatientForm(instance=patient)
    
    return render(request, 'secretary_dash/common/patient_form.html', {
        'form': form,
        'title': 'Edit Patient'
    })

@login_required
@user_passes_test(is_staff)
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    
    # Get all examinations ordered by date and time
    all_examinations = Examination.objects.filter(
        patient=patient
    ).order_by('-date', '-time')
    
    # Get recent examinations (last 5)
    recent_examinations = all_examinations[:5]
    
    # Get examination history (excluding recent examinations)
    examination_history = all_examinations[5:] if len(all_examinations) > 5 else []
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.objects.filter(
        patient=patient,
        date__gte=timezone.now().date(),
        status='upcoming'
    ).order_by('date', 'time')
    
    return render(request, 'secretary_dash/common/patient_detail.html', {
        'patient': patient,
        'recent_examinations': recent_examinations,
        'examination_history': examination_history,
        'upcoming_appointments': upcoming_appointments
    })

@login_required
@user_passes_test(is_staff)
def patient_delete(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        patient.delete()
        messages.success(request, 'Patient deleted successfully.')
        return redirect('secretary_dash:patient_list')
    return render(request, 'secretary_dash/common/patient_confirm_delete.html', {
        'patient': patient
    })

# Appointment Management Views
@login_required
@user_passes_test(lambda u: u.is_superuser or is_secretary(u))
def appointment_list(request):
    appointments = Appointment.objects.all().order_by('date', 'time')
    return render(request, 'secretary_dash/common/appointment_list.html', {'appointments': appointments})

@login_required
@user_passes_test(lambda u: u.is_superuser or is_secretary(u))
def appointment_create(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            
            # Handle both doctors and secretaries
            if request.user.is_superuser:
                # For doctors, create a Secretary instance if it doesn't exist
                secretary, created = Secretary.objects.get_or_create(
                    user=request.user,
                    defaults={'phone': ''}  # Add a default empty phone number
                )
            else:
                # For secretaries, get their existing Secretary instance
                secretary = Secretary.objects.get(user=request.user)
            
            appointment.created_by = secretary
            appointment.status = 'upcoming'
            appointment.save()
            messages.success(request, mark_safe(
                '<div class="message-content">'
                '<h4>Appointment Created</h4>'
                '<p>The appointment has been scheduled successfully.</p>'
                '</div>'
            ))
            return redirect('secretary_dash:appointment_list')
        else:
            # Check specifically for busy hours error
            errors = form.errors.get('__all__', [])
            for error in errors:
                if "doctor is not available" in str(error):
                    date = form.cleaned_data.get('date')
                    time = form.cleaned_data.get('time')
                    if date and time:
                        busy_hours = BusyHours.objects.filter(
                            date=date,
                            start_time__lte=time,
                            end_time__gt=time
                        ).first()
                        if busy_hours:
                            warning_html = mark_safe(
                                '<div class="message-content">'
                                '<h4>Cannot Schedule Appointment</h4>'
                                f'<p>The doctor is busy on {busy_hours.date}</p>'
                                f'<p><strong>Time:</strong> {busy_hours.start_time.strftime("%H:%M")} to {busy_hours.end_time.strftime("%H:%M")}</p>'
                                f'<p><strong>Reason:</strong> {busy_hours.reason}</p>'
                                '</div>'
                            )
                            messages.error(request, warning_html)
                            continue
                elif "time slot is already booked" in str(error):
                    date = form.cleaned_data.get('date')
                    time = form.cleaned_data.get('time')
                    if date and time:
                        existing_appointment = Appointment.objects.filter(
                            date=date,
                            time=time,
                            status='upcoming'
                        ).first()
                        if existing_appointment:
                            warning_html = mark_safe(
                                '<div class="message-content">'
                                '<h4>Cannot Schedule Appointment</h4>'
                                f'<p>This time slot is already booked on {date}</p>'
                                f'<p><strong>Time:</strong> {time.strftime("%H:%M")}</p>'
                                f'<p><strong>Patient:</strong> {existing_appointment.patient.name}</p>'
                                '</div>'
                            )
                            messages.error(request, warning_html)
                            continue

            # Format other error messages
            error_messages = []
            for field, errors in form.errors.items():
                if field == '__all__':
                    # Skip busy hours and double booking errors as they're already handled
                    if not any("doctor is not available" in str(error) or "time slot is already booked" in str(error) for error in errors):
                        error_messages.extend(errors)
                else:
                    error_messages.append(f'<strong>{field}:</strong> {errors[0]}')
            
            if error_messages:
                error_html = '<div class="message-content"><h4>Appointment Form Errors</h4><ul>'
                for error in error_messages:
                    error_html += f'<li>{error}</li>'
                error_html += '</ul></div>'
                messages.error(request, mark_safe(error_html))
    else:
        initial = {}
        if patient_id := request.GET.get('patient'):
            initial['patient'] = patient_id
        form = AppointmentForm(initial=initial)
    
    return render(request, 'secretary_dash/common/appointment_form.html', {
        'form': form,
        'title': 'Schedule New Appointment'
    })

@login_required
@user_passes_test(lambda u: u.is_superuser or is_secretary(u))
def appointment_detail(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    return render(request, 'secretary_dash/common/appointment_detail.html', {'appointment': appointment})

@login_required
@user_passes_test(lambda u: u.is_superuser or is_secretary(u))
def appointment_edit(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Appointment updated successfully!')
            return redirect('secretary_dash:appointment_list')
    else:
        form = AppointmentForm(instance=appointment)
    return render(request, 'secretary_dash/common/appointment_form.html', {'form': form, 'title': 'Edit Appointment'})

@login_required
@user_passes_test(lambda u: u.is_superuser or is_secretary(u))
def appointment_cancel(request, pk):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, pk=pk)
        appointment.status = 'cancelled'
        appointment.save()
        messages.success(request, 'Appointment cancelled successfully!')
    return redirect('secretary_dash:appointment_list')

@login_required
@user_passes_test(lambda u: u.is_superuser or is_secretary(u))
def appointment_delete(request, pk):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, pk=pk)
        if appointment.status == 'cancelled':  # Only allow deletion of cancelled appointments
            appointment.delete()
            messages.success(request, 'Appointment deleted successfully!')
        else:
            messages.error(request, 'Only cancelled appointments can be deleted.')
    return redirect('secretary_dash:appointment_list')

# Secretary-specific views
@login_required
@user_passes_test(is_secretary)
def secretary_dashboard(request):
    """
    View for the secretary's dashboard.
    """
    # Get today's date and end of week using the correct timezone
    today = timezone.localtime().date()
    week_end = today + timedelta(days=6)
    
    # Get statistics
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.filter(status='upcoming').count()
    scheduled_appointments = Appointment.objects.filter(
        date__gte=today,
        status='upcoming'
    ).count()
    
    # Get all appointments for the current month
    current_month = today.month
    current_year = today.year
    month_appointments = Appointment.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).values('id', 'date', 'time', 'patient__name', 'status')
    
    # Format appointments for the calendar
    calendar_appointments = []
    for appointment in month_appointments:
        calendar_appointments.append({
            'id': appointment['id'],
            'date': appointment['date'].strftime('%Y-%m-%d'),
            'time': appointment['time'].strftime('%H:%M'),
            'patient': appointment['patient__name'],
            'status': appointment['status']
        })
    
    # Get busy hours for the current month
    busy_hours = BusyHours.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).values('id', 'date', 'start_time', 'end_time', 'reason')
    
    # Format busy hours for the calendar
    calendar_busy_hours = []
    for busy in busy_hours:
        calendar_busy_hours.append({
            'id': busy['id'],
            'date': busy['date'].strftime('%Y-%m-%d'),
            'start_time': busy['start_time'].strftime('%H:%M'),
            'end_time': busy['end_time'].strftime('%H:%M'),
            'reason': busy['reason']
        })
    
    context = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'scheduled_appointments': scheduled_appointments,
        'calendar_appointments': calendar_appointments,
        'calendar_busy_hours': calendar_busy_hours,
    }
    
    return render(request, 'secretary_dash/secretary/dashboard.html', context)

# Additional Secretary Views
@login_required
@user_passes_test(is_doctor)
def secretary_list(request):
    """
    View to list all secretaries.
    Only accessible by doctors.
    """
    secretaries = Secretary.objects.all().order_by('user__username')
    return render(request, 'secretary_dash/doctor/secretary_list.html', {'secretaries': secretaries})

@login_required
@user_passes_test(is_doctor)
def secretary_create(request):
    """
    View to create a new secretary.
    Only accessible by doctors.
    """
    if request.method == 'POST':
        form = SecretaryCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Secretary created successfully!')
            return redirect('secretary_dash:secretary_list')
    else:
        form = SecretaryCreationForm()
    return render(request, 'secretary_dash/doctor/secretary_form.html', {
        'form': form,
        'title': 'Add New Secretary'
    })

@login_required
@user_passes_test(is_doctor)
def secretary_edit(request, pk):
    """
    View to edit an existing secretary.
    Only accessible by doctors.
    """
    secretary = get_object_or_404(Secretary, pk=pk)
    if request.method == 'POST':
        form = SecretaryCreationForm(request.POST, instance=secretary.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Secretary updated successfully!')
            return redirect('secretary_dash:secretary_list')
    else:
        form = SecretaryCreationForm(instance=secretary.user)
    
    return render(request, 'secretary_dash/doctor/secretary_form.html', {
        'form': form,
        'title': 'Edit Secretary'
    })

@login_required
@user_passes_test(is_doctor)
def secretary_delete(request, pk):
    """
    View to delete a secretary.
    Only accessible by doctors.
    """
    secretary = get_object_or_404(Secretary, pk=pk)
    if request.method == 'POST':
        try:
            user = secretary.user
            secretary.delete()
            user.delete()
            messages.success(request, 'Secretary deleted successfully!')
        except Exception as e:
            messages.error(request, 'Unable to delete secretary. They may have associated records.')
        return redirect('secretary_dash:secretary_list')
    return render(request, 'secretary_dash/doctor/secretary_confirm_delete.html', {'secretary': secretary})

# Doctor Dashboard View
@login_required
@user_passes_test(is_doctor)
def doctor_dashboard(request):
    # Use timezone.localtime() to get the current time in Istanbul timezone
    today = timezone.localtime().date()
    
    # Get statistics
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.filter(status='upcoming').count()
    total_examinations = Examination.objects.count()
    total_medicines = Medicine.objects.count()
    
    # Get today's appointments using the correct timezone
    today_appointments = Appointment.objects.filter(
        date=today
    ).order_by('time')
    
    # Get calendar appointments
    calendar_appointments = []
    appointments = Appointment.objects.all()
    for appointment in appointments:
        calendar_appointments.append({
            'date': appointment.date.isoformat(),
            'time': appointment.time.strftime('%H:%M'),
            'patient': appointment.patient.name,
            'status': appointment.status
        })
    
    # Get busy hours
    busy_hours = []
    busy_periods = BusyHours.objects.all()
    for busy in busy_periods:
        busy_hours.append({
            'date': busy.date.isoformat(),
            'start_time': busy.start_time.strftime('%H:%M'),
            'end_time': busy.end_time.strftime('%H:%M'),
            'reason': busy.reason
        })
    
    return render(request, 'secretary_dash/doctor/dashboard.html', {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_examinations': total_examinations,
        'total_medicines': total_medicines,
        'today_appointments': today_appointments,
        'calendar_appointments': json.dumps(calendar_appointments),
        'busy_hours': json.dumps(busy_hours)
    })

@login_required
@user_passes_test(is_doctor)
def medicine_list(request):
    medicines = Medicine.objects.all().order_by('name')
    return render(request, 'secretary_dash/doctor/medicine_list.html', {'medicines': medicines})

@login_required
def medicine_create(request):
    """
    View to create a new medicine.
    """
    if request.method == 'POST':
        form = MedicineForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medicine created successfully!')
            return redirect('secretary_dash:medicine_list')
    else:
        form = MedicineForm()
    return render(request, 'secretary_dash/doctor/medicine_form.html', {'form': form, 'title': 'Create Medicine'})

@login_required
def medicine_edit(request, pk):
    """
    View to edit an existing medicine.
    """
    medicine = get_object_or_404(Medicine, pk=pk)
    if request.method == 'POST':
        form = MedicineForm(request.POST, instance=medicine)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medicine updated successfully!')
            return redirect('secretary_dash:medicine_list')
    else:
        form = MedicineForm(instance=medicine)
    return render(request, 'secretary_dash/doctor/medicine_form.html', {'form': form, 'title': 'Edit Medicine'})

@login_required
def medicine_delete(request, pk):
    """
    View to delete a medicine.
    Only accessible by doctors.
    """
    medicine = get_object_or_404(Medicine, pk=pk)
    if request.method == 'POST':
        try:
            medicine.delete()
            messages.success(request, 'Medicine deleted successfully!')
        except Exception as e:
            messages.error(request, 'Unable to delete medicine. It may be referenced by other records.')
        return redirect('secretary_dash:medicine_list')
    return render(request, 'secretary_dash/doctor/medicine_confirm_delete.html', {'medicine': medicine})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def examination_list(request):
    examinations = Examination.objects.all().order_by('-date', '-created_at')
    return render(request, 'secretary_dash/doctor/examination_list.html', {
        'examinations': examinations
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def examination_create(request):
    PrescriptionFormSet = inlineformset_factory(
        Examination, 
        Prescription, 
        form=PrescriptionForm,
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        form = ExaminationForm(request.POST)
        formset = PrescriptionFormSet(request.POST, prefix='prescriptions')
        
        if form.is_valid() and formset.is_valid():
            examination = form.save(commit=False)
            examination.created_by = request.user
            examination.save()
            
            # Save the formset
            prescriptions = formset.save(commit=False)
            for prescription in prescriptions:
                prescription.examination = examination
                prescription.save()
            
            # Handle deleted prescriptions
            for obj in formset.deleted_objects:
                obj.delete()
            
            # Update the related appointment status to completed
            appointment = Appointment.objects.filter(
                patient=examination.patient,
                date=examination.date,
                time=examination.time
            ).first()
            
            if appointment:
                appointment.status = 'completed'
                appointment.save()
            
            messages.success(request, mark_safe(
                '<div class="message-content">'
                '<h4>Examination Created</h4>'
                '<p>The examination has been created successfully.</p>'
                '</div>'
            ))
            return redirect('secretary_dash:examination_list')
        else:
            # Format error messages
            if form.errors:
                error_html = '<div class="message-content"><h4>Examination Form Errors</h4><ul>'
                for field, errors in form.errors.items():
                    if field == '__all__':
                        error_html += f'<li>{errors[0]}</li>'
                    else:
                        error_html += f'<li><strong>{field}:</strong> {errors[0]}</li>'
                error_html += '</ul></div>'
                messages.error(request, mark_safe(error_html))
            
            if formset.errors:
                error_html = '<div class="message-content"><h4>Prescription Form Errors</h4><ul>'
                for form_num, form_errors in enumerate(formset.errors):
                    if form_errors:
                        error_html += f'<li><strong>Prescription {form_num + 1}:</strong><ul>'
                        for field, errors in form_errors.items():
                            error_html += f'<li><strong>{field}:</strong> {errors[0]}</li>'
                        error_html += '</ul></li>'
                error_html += '</ul></div>'
                messages.error(request, mark_safe(error_html))
            
            if formset.non_form_errors():
                error_html = '<div class="message-content"><h4>Prescription Errors</h4><ul>'
                for error in formset.non_form_errors():
                    error_html += f'<li>{error}</li>'
                error_html += '</ul></div>'
                messages.error(request, mark_safe(error_html))
    else:
        initial = {}
        if appointment_id := request.GET.get('appointment'):
            appointment = get_object_or_404(Appointment, id=appointment_id)
            
            # Check if appointment is cancelled
            if appointment.status == 'cancelled':
                messages.error(request, mark_safe(
                    '<div class="message-content">'
                    '<h4>Cannot Create Examination</h4>'
                    '<p>Cannot create examination for a cancelled appointment.</p>'
                    '</div>'
                ))
                return redirect('secretary_dash:doctor_dashboard')
            
            initial.update({
                'patient': appointment.patient,
                'date': appointment.date,
                'time': appointment.time
            })
        
        form = ExaminationForm(initial=initial)
        formset = PrescriptionFormSet(prefix='prescriptions')
    
    return render(request, 'secretary_dash/doctor/examination_form.html', {
        'form': form,
        'prescription_formset': formset,
        'title': 'New Examination'
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def examination_edit(request, pk):
    examination = get_object_or_404(Examination, pk=pk)
    PrescriptionFormSet = inlineformset_factory(
        Examination, 
        Prescription, 
        form=PrescriptionForm,
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        form = ExaminationForm(request.POST, instance=examination)
        if form.is_valid():
            examination = form.save()
            
            formset = PrescriptionFormSet(request.POST, instance=examination, prefix='prescriptions')
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Examination updated successfully.')
                return redirect('secretary_dash:examination_list')
    else:
        form = ExaminationForm(instance=examination)
        formset = PrescriptionFormSet(instance=examination, prefix='prescriptions')
    
    return render(request, 'secretary_dash/doctor/examination_form.html', {
        'form': form,
        'prescription_formset': formset,
        'title': 'Edit Examination'
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def examination_detail(request, pk):
    examination = get_object_or_404(Examination, pk=pk)
    return render(request, 'secretary_dash/doctor/examination_detail.html', {
        'examination': examination
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def examination_delete(request, pk):
    """
    View to delete an examination.
    Only accessible by doctors.
    """
    examination = get_object_or_404(Examination, pk=pk)
    if request.method == 'POST':
        examination.delete()
        messages.success(request, 'Examination deleted successfully.')
        return redirect('secretary_dash:examination_list')
    return render(request, 'secretary_dash/doctor/examination_confirm_delete.html', {
        'examination': examination
    })

# Busy Hours Views
@login_required
@user_passes_test(is_doctor)
def busy_hours_list(request):
    """
    View to list all busy hours.
    Only accessible by doctors.
    """
    busy_hours = BusyHours.objects.all().order_by('date', 'start_time')
    return render(request, 'secretary_dash/doctor/busy_hours_list.html', {'busy_hours': busy_hours})

@login_required
@user_passes_test(is_doctor)
def busy_hours_create(request):
    """
    View to create new busy hours.
    Only accessible by doctors.
    """
    if request.method == 'POST':
        form = BusyHoursForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Busy hours added successfully!')
            return redirect('secretary_dash:busy_hours_list')
    else:
        form = BusyHoursForm()
    
    return render(request, 'secretary_dash/doctor/busy_hours_form.html', {
        'form': form,
        'title': 'Add Busy Hours'
    })

@login_required
@user_passes_test(is_doctor)
def busy_hours_edit(request, pk):
    """
    View to edit existing busy hours.
    Only accessible by doctors.
    """
    busy_hours = get_object_or_404(BusyHours, pk=pk)
    if request.method == 'POST':
        form = BusyHoursForm(request.POST, instance=busy_hours)
        if form.is_valid():
            form.save()
            messages.success(request, 'Busy hours updated successfully!')
            return redirect('secretary_dash:busy_hours_list')
    else:
        form = BusyHoursForm(instance=busy_hours)
    
    return render(request, 'secretary_dash/doctor/busy_hours_form.html', {
        'form': form,
        'title': 'Edit Busy Hours'
    })

@login_required
@user_passes_test(is_doctor)
def busy_hours_delete(request, pk):
    """
    View to delete busy hours.
    Only accessible by doctors.
    """
    busy_hours = get_object_or_404(BusyHours, pk=pk)
    if request.method == 'POST':
        busy_hours.delete()
        messages.success(request, 'Busy hours deleted successfully!')
        return redirect('secretary_dash:busy_hours_list')
    return render(request, 'secretary_dash/doctor/busy_hours_confirm_delete.html', {
        'busy_hours': busy_hours
    })

def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            logger.debug(f"Processing password reset request for email: {email}")
            
            try:
                user = get_user_model().objects.get(email=email)
                
                # Generate password reset token
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = password_reset_token.make_token(user)
                
                # Build reset URL
                reset_url = request.build_absolute_uri(f'/reset-password/{uid}/{token}/')
                
                # Create email content
                subject = 'Password Reset Request'
                message = render_to_string('registration/password_reset_email.html', {
                    'user': user,
                    'reset_url': reset_url,
                })
                from_email = settings.EMAIL_HOST_USER
                recipient_list = [email]
                
                # Log all email settings
                logger.debug("Email settings:")
                logger.debug(f"Reset URL: {reset_url}")
                logger.debug(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
                logger.debug(f"EMAIL_HOST: {settings.EMAIL_HOST}")
                logger.debug(f"EMAIL_PORT: {settings.EMAIL_PORT}")
                logger.debug(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
                logger.debug(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
                
                try:
                    # Send the email
                    email_sent = send_mail(
                        subject,
                        message,
                        from_email,
                        recipient_list,
                        fail_silently=False,
                        html_message=message,
                    )
                    
                    if email_sent:
                        logger.debug(f"Password reset email sent successfully to {email}")
                        messages.success(request, 'Password reset instructions have been sent to your email.')
                    else:
                        logger.error(f"Failed to send password reset email to {email}")
                        messages.error(request, 'Failed to send email. Please try again later.')
                    
                except Exception as smtp_error:
                    logger.exception(f"SMTP Error: {str(smtp_error)}")
                    messages.error(request, f'SMTP Error: {str(smtp_error)}')
                
            except Exception as e:
                logger.exception(f"Unexpected error: {str(e)}")
                messages.error(request, 'An unexpected error occurred. Please try again later.')
            
            return redirect('login')
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'registration/forgot_password.html', {'form': form})

def reset_password(request, uidb64, token):
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)
        
        # Verify the token
        if password_reset_token.check_token(user, token):
            if request.method == 'POST':
                form = SetPasswordForm(request.POST)
                if form.is_valid():
                    # Set the new password
                    user.set_password(form.cleaned_data['new_password1'])
                    user.save()
                    messages.success(request, 'Your password has been reset successfully. You can now login with your new password.')
                    return redirect('login')
            else:
                form = SetPasswordForm()
            
            return render(request, 'registration/password_reset.html', {
                'form': form,
                'validlink': True
            })
        else:
            return render(request, 'registration/password_reset.html', {
                'validlink': False
            })
            
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        return render(request, 'registration/password_reset.html', {
            'validlink': False
        })
