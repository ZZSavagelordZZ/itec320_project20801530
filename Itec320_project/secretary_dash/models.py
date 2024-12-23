"""
Models for the medical secretary dashboard application.
This module contains all the database models for managing patients, appointments,
examinations, prescriptions, and medical staff.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

class Secretary(models.Model):
    """
    Represents a medical secretary in the system.
    
    A secretary is linked to a Django User model and has additional contact information.
    Secretaries are responsible for managing appointments and patient records.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text="The user account associated with this secretary")
    phone = models.CharField(max_length=20, help_text="Contact phone number for the secretary")

    class Meta:
        verbose_name_plural = "Secretaries"
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

class Patient(models.Model):
    """
    Represents a patient in the medical system.
    
    Stores all relevant patient information including personal details and contact information.
    Patients can have multiple appointments and examinations linked to them.
    """
    name = models.CharField(max_length=100, help_text="Full name of the patient")
    phone = models.CharField(max_length=20, help_text="Contact phone number")
    email = models.EmailField(help_text="Email address for communications")
    address = models.TextField(help_text="Physical address of the patient")
    date_of_birth = models.DateField(help_text="Patient's date of birth")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the patient record was created")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Appointment(models.Model):
    """
    Represents a medical appointment.
    
    Tracks scheduled appointments between patients and the doctor.
    Includes status tracking and appointment details.
    """
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, help_text="The patient who has the appointment")
    date = models.DateField(help_text="Date of the appointment")
    time = models.TimeField(help_text="Time of the appointment")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Staff member who created the appointment")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming', help_text="Current status of the appointment")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the appointment was created")

    def save(self, *args, **kwargs):
        """
        Custom save method to automatically update appointment status
        when an examination is completed.
        """
        # Check if there's a completed examination for this appointment
        if hasattr(self, 'pk'):  # Only check if appointment already exists
            if Examination.objects.filter(
                patient=self.patient,
                date=self.date,
                time=self.time
            ).exists():
                self.status = 'completed'
        
        super().save(*args, **kwargs)

    def get_formatted_time(self):
        """Return time in 24-hour format"""
        return self.time.strftime('%H:%M')

    def __str__(self):
        return f"{self.patient} - {self.date} {self.get_formatted_time()}"

    class Meta:
        ordering = ['date', 'time']

class Medicine(models.Model):
    """
    Represents a medicine that can be prescribed to patients.
    
    Contains information about the medicine including its description
    and potential side effects.
    """
    name = models.CharField(max_length=100, help_text="Name of the medicine")
    description = models.TextField(help_text="Description of the medicine and its uses")
    side_effects = models.TextField(help_text="Known side effects of the medicine")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this medicine was added to the system")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Examination(models.Model):
    """
    Represents a medical examination of a patient.
    
    Records the details of a patient examination including symptoms,
    diagnosis, and any prescribed medications.
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, help_text="The patient being examined")
    symptoms = models.TextField(help_text="Description of patient's symptoms")
    diagnosis = models.TextField(help_text="Doctor's diagnosis")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Doctor who performed the examination")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the examination was conducted")
    date = models.DateField(help_text="Date of examination")
    time = models.TimeField(help_text="Time of examination")

    def __str__(self):
        return f"Examination for {self.patient} on {self.date}"

    class Meta:
        ordering = ['-date']

class Prescription(models.Model):
    """
    Represents a prescription given to a patient.
    
    Links medicines prescribed during an examination with specific
    dosage and duration instructions.
    """
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='prescriptions', help_text="The examination during which this was prescribed")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, help_text="The prescribed medicine")
    dosage = models.CharField(max_length=100, help_text="Dosage instructions")
    duration = models.CharField(max_length=100, help_text="Duration for which medicine should be taken")
    notes = models.TextField(blank=True, help_text="Additional notes about the prescription")

    def __str__(self):
        return f"{self.medicine} - {self.examination.patient}"

class BusyHours(models.Model):
    """
    Represents time periods when the doctor is unavailable.
    
    Used to block out time slots where appointments cannot be scheduled.
    """
    date = models.DateField(help_text="Date when the doctor is unavailable")
    start_time = models.TimeField(help_text="Start time of unavailability")
    end_time = models.TimeField(help_text="End time of unavailability")
    reason = models.CharField(max_length=200, help_text="Reason for unavailability")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this busy period was registered")

    def clean(self):
        """
        Validates that the busy hours are properly configured:
        - End time must be after start time
        - Cannot set busy hours for past dates
        """
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError('End time must be after start time.')

        if self.date and self.date < timezone.now().date():
            raise ValidationError('Cannot set busy hours for past dates.')

    def __str__(self):
        return f"Busy on {self.date} from {self.start_time} to {self.end_time}"

    class Meta:
        verbose_name = "Busy Hours"
        verbose_name_plural = "Busy Hours"
        ordering = ['date', 'start_time']
