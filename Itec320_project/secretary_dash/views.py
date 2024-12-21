from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import logout, authenticate, login
from django.forms import inlineformset_factory
from .models import Patient, Appointment, Secretary, Medicine, Examination, Prescription
from .forms import (
    PatientForm, AppointmentForm, MedicineForm, 
    ExaminationForm, SecretaryCreationForm, PrescriptionForm
)
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count

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
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('secretary_dash:root')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'secretary_dash/login.html')

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
    return render(request, 'secretary_dash/common/patient_detail.html', {
        'patient': patient
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
            # Get the secretary instance for the current user
            if request.user.is_superuser:
                # If it's a doctor (superuser), we'll need a default secretary
                secretary = Secretary.objects.first()  # or some logic to determine default secretary
                if not secretary:
                    messages.error(request, 'No secretary available to create appointment.')
                    return redirect('secretary_dash:appointment_list')
            else:
                secretary = request.user.secretary
            
            appointment.created_by = secretary
            appointment.save()
            messages.success(request, 'Appointment scheduled successfully.')
            return redirect('secretary_dash:appointment_list')
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
        appointment.is_cancelled = True
        appointment.save()
        messages.success(request, 'Appointment cancelled successfully!')
    return redirect('secretary_dash:appointment_list')

# Secretary-specific views
@login_required
@user_passes_test(is_secretary)
def secretary_dashboard(request):
    """
    View for the secretary's dashboard.
    """
    # Get today's date and end of week
    today = timezone.localdate()
    week_end = today + timedelta(days=6)
    
    # Get statistics
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.filter(is_cancelled=False).count()
    scheduled_appointments = Appointment.objects.filter(
        date__gte=today,
        is_cancelled=False
    ).count()
    
    # Get all appointments for the current month
    current_month = today.month
    current_year = today.year
    month_appointments = Appointment.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).values('id', 'date', 'time', 'patient__name', 'is_cancelled')
    
    # Format appointments for the calendar
    calendar_appointments = []
    for appointment in month_appointments:
        calendar_appointments.append({
            'id': appointment['id'],
            'date': appointment['date'].strftime('%Y-%m-%d'),
            'time': appointment['time'].strftime('%H:%M'),
            'patient': appointment['patient__name'],
            'status': 'cancelled' if appointment['is_cancelled'] else 'active'
        })
    
    context = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'scheduled_appointments': scheduled_appointments,
        'calendar_appointments': calendar_appointments,
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
            user = form.save()
            Secretary.objects.create(user=user, phone=form.cleaned_data.get('phone'))
            messages.success(request, 'Secretary created successfully!')
            return redirect('secretary_dash:secretary_list')
    else:
        form = SecretaryCreationForm()
    return render(request, 'secretary_dash/doctor/secretary_form.html', {'form': form, 'title': 'Add New Secretary'})

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
            secretary.phone = form.cleaned_data.get('phone')
            secretary.save()
            messages.success(request, 'Secretary updated successfully!')
            return redirect('secretary_dash:secretary_list')
    else:
        form = SecretaryCreationForm(instance=secretary.user, initial={'phone': secretary.phone})
    return render(request, 'secretary_dash/doctor/secretary_form.html', {'form': form, 'title': 'Edit Secretary'})

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
    """
    View for the doctor's dashboard.
    """
    # Get today's date and end of week
    today = timezone.localdate()
    week_end = today + timedelta(days=6)
    
    # Get upcoming appointments for the week
    upcoming_appointments = Appointment.objects.filter(
        date__gte=today,
        date__lte=week_end,
        is_cancelled=False
    ).order_by('date', 'time')
    
    # Get today's appointments
    today_appointments = Appointment.objects.filter(
        date=today,
        is_cancelled=False
    ).order_by('time')
    
    # Get statistics
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.filter(is_cancelled=False).count()
    total_examinations = Examination.objects.count()
    total_medicines = Medicine.objects.count()
    
    # Get all appointments for the current month
    current_month = today.month
    current_year = today.year
    month_appointments = Appointment.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).values('id', 'date', 'time', 'patient__name', 'is_cancelled')
    
    # Format appointments for the calendar
    calendar_appointments = []
    for appointment in month_appointments:
        calendar_appointments.append({
            'id': appointment['id'],
            'date': appointment['date'].strftime('%Y-%m-%d'),
            'time': appointment['time'].strftime('%H:%M'),
            'patient': appointment['patient__name'],
            'status': 'cancelled' if appointment['is_cancelled'] else 'active'
        })
    
    context = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_examinations': total_examinations,
        'total_medicines': total_medicines,
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming_appointments,
        'calendar_appointments': calendar_appointments,
    }
    
    return render(request, 'secretary_dash/doctor/dashboard.html', context)

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
        if form.is_valid():
            examination = form.save(commit=False)
            examination.created_by = request.user
            examination.save()
            
            formset = PrescriptionFormSet(request.POST, instance=examination)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Examination created successfully.')
                return redirect('secretary_dash:examination_list')
    else:
        initial = {}
        if appointment_id := request.GET.get('appointment'):
            appointment = get_object_or_404(Appointment, id=appointment_id)
            initial['patient'] = appointment.patient
        
        form = ExaminationForm(initial=initial)
        formset = PrescriptionFormSet()
    
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
            
            formset = PrescriptionFormSet(request.POST, instance=examination)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Examination updated successfully.')
                return redirect('secretary_dash:examination_list')
    else:
        form = ExaminationForm(instance=examination)
        formset = PrescriptionFormSet(instance=examination)
    
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
