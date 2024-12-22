from django.contrib import admin
from .models import Secretary, Patient, Appointment, Medicine, Examination, Prescription, BusyHours

@admin.register(Secretary)
class SecretaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone')
    search_fields = ('user__username', 'phone')

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'date_of_birth')
    search_fields = ('name', 'phone', 'email')
    list_filter = ('created_at',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date', 'time', 'created_by', 'status', 'created_at')
    list_filter = ('date', 'status')
    search_fields = ('patient__name', 'created_by__user__username')

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'description')

@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date', 'created_by')
    list_filter = ('date', 'created_by')
    search_fields = ('patient__name', 'symptoms', 'diagnosis')

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('examination', 'medicine', 'dosage', 'duration')
    search_fields = ('examination__patient__name', 'medicine__name')

@admin.register(BusyHours)
class BusyHoursAdmin(admin.ModelAdmin):
    list_display = ('date', 'start_time', 'end_time', 'reason')
    list_filter = ('date',)
    search_fields = ('reason',)
