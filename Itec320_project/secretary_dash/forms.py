from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Patient, Appointment, Medicine, Examination, Prescription, Secretary, BusyHours
from django.core.exceptions import ValidationError
from django.utils import timezone

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['name', 'phone', 'email', 'address', 'date_of_birth']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'date', 'time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'})
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time = cleaned_data.get('time')

        if date and time:
            # Check if appointment is during business hours (9 AM - 5 PM)
            if time.hour < 9 or time.hour >= 17:
                raise forms.ValidationError("Appointments must be between 9 AM and 5 PM")
            
            # Check if appointment is at :00 or :30
            if time.minute not in [0, 30]:
                raise forms.ValidationError("Appointments must start at :00 or :30")

            # Check for busy hours
            busy_hours = BusyHours.objects.filter(
                date=date,
                start_time__lte=time,
                end_time__gt=time
            )
            if busy_hours.exists():
                raise forms.ValidationError("The doctor is not available at this time.")

            # Check for existing appointments
            existing_appointments = Appointment.objects.filter(
                date=date,
                time=time,
                is_cancelled=False
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing_appointments.exists():
                raise forms.ValidationError("This time slot is already booked.")

        return cleaned_data

class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = ['name', 'description', 'side_effects']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'side_effects': forms.Textarea(attrs={'rows': 3}),
        }

class ExaminationForm(forms.ModelForm):
    class Meta:
        model = Examination
        fields = ['patient', 'symptoms', 'diagnosis']
        widgets = {
            'symptoms': forms.Textarea(attrs={'rows': 4}),
            'diagnosis': forms.Textarea(attrs={'rows': 4}),
        }

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medicine', 'dosage', 'duration', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

class SecretaryCreationForm(UserCreationForm):
    phone = forms.CharField(max_length=20)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # If we're editing an existing user, remove password fields
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)
            # Set initial values from the associated Secretary instance
            if hasattr(self.instance, 'secretary'):
                self.fields['phone'].initial = self.instance.secretary.phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Update or create the associated Secretary instance
            Secretary.objects.update_or_create(
                user=user,
                defaults={'phone': self.cleaned_data['phone']}
            )
        return user

class BusyHoursForm(forms.ModelForm):
    class Meta:
        model = BusyHours
        fields = ['date', 'start_time', 'end_time', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'reason': forms.TextInput(attrs={'placeholder': 'Optional: Reason for busy hours'})
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if date and start_time and end_time:
            # Check if start time is before end time
            if start_time >= end_time:
                raise ValidationError('End time must be after start time.')

            # Check if busy hours are during business hours (9 AM - 5 PM)
            if start_time.hour < 9 or end_time.hour >= 17:
                raise ValidationError('Busy hours must be between 9 AM and 5 PM')

            # Check for overlapping busy hours
            overlapping = BusyHours.objects.filter(
                date=date,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            
            if overlapping.exists():
                raise ValidationError('These busy hours overlap with existing busy hours.')