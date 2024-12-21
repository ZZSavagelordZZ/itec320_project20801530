from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Patient, Appointment, Medicine, Examination, Prescription, Secretary

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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            Secretary.objects.create(
                user=user,
                phone=self.cleaned_data['phone']
            )
        return user