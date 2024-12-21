from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

class Secretary(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)

    class Meta:
        verbose_name_plural = "Secretaries"
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

class Patient(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    date_of_birth = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    created_by = models.ForeignKey(Secretary, on_delete=models.CASCADE)
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.is_cancelled:
            existing_appointments = Appointment.objects.filter(
                date=self.date,
                time=self.time,
                is_cancelled=False
            ).exclude(pk=self.pk)
            
            if existing_appointments.exists():
                raise ValidationError('This time slot is already booked.')

    def __str__(self):
        return f"{self.patient} - {self.date} {self.time}"

    class Meta:
        ordering = ['date', 'time']

class Medicine(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    side_effects = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Examination(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    symptoms = models.TextField()
    diagnosis = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.patient} - {self.date}"

    class Meta:
        ordering = ['-date']

class Prescription(models.Model):
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    dosage = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.medicine} - {self.examination.patient}"

class BusyHours(models.Model):
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
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
