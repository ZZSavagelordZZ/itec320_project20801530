from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Patient, Appointment, Medicine, Examination, Prescription, Secretary, BusyHours
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['name', 'phone', 'email', 'address', 'date_of_birth']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class AppointmentForm(forms.ModelForm):
    TIME_CHOICES = [
        ('09:00', '9:00 AM'),
        ('09:30', '9:30 AM'),
        ('10:00', '10:00 AM'),
        ('10:30', '10:30 AM'),
        ('11:00', '11:00 AM'),
        ('11:30', '11:30 AM'),
        ('12:00', '12:00 PM'),
        ('12:30', '12:30 PM'),
        ('13:00', '1:00 PM'),
        ('13:30', '1:30 PM'),
        ('14:00', '2:00 PM'),
        ('14:30', '2:30 PM'),
        ('15:00', '3:00 PM'),
        ('15:30', '3:30 PM'),
        ('16:00', '4:00 PM'),
        ('16:30', '4:30 PM'),
    ]

    time = forms.ChoiceField(choices=TIME_CHOICES)

    class Meta:
        model = Appointment
        fields = ['patient', 'date', 'time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time_str = cleaned_data.get('time')

        if date and time_str:
            # Convert time string to time object without using timezone
            from datetime import datetime, time
            hour, minute = map(int, time_str.split(':'))
            time_obj = time(hour=hour, minute=minute)
            cleaned_data['time'] = time_obj

            # Check for busy hours
            busy_hours = BusyHours.objects.filter(
                date=date,
                start_time__lte=time_obj,
                end_time__gt=time_obj
            )
            if busy_hours.exists():
                raise forms.ValidationError("The doctor is not available at this time.")

            # Check for existing appointments
            existing_appointments = Appointment.objects.filter(
                date=date,
                time=time_obj,
                status='upcoming'
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
        fields = ['patient', 'date', 'time', 'symptoms', 'diagnosis']
        widgets = {
            'symptoms': forms.Textarea(attrs={'rows': 4}),
            'diagnosis': forms.Textarea(attrs={'rows': 4}),
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'})
        }

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medicine', 'dosage', 'duration', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional
        for field in self.fields.values():
            field.required = False

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

class EmailLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            UserModel = get_user_model()
            try:
                user = UserModel.objects.get(email=email)
            except UserModel.DoesNotExist:
                raise forms.ValidationError("Invalid email or password.")
        return cleaned_data

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            raise forms.ValidationError("No user found with this email address.")
        return email

class SetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        strip=False,
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        strip=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("The two password fields didn't match.")
        return cleaned_data