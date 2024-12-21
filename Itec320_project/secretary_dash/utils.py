from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
import icalendar

def send_appointment_email(appointment):
    """Send appointment confirmation email with calendar invite."""
    
    # Create calendar event
    cal = icalendar.Calendar()
    event = icalendar.Event()
    
    event.add('summary', f'Doctor Appointment - {appointment.patient}')
    event.add('dtstart', datetime.combine(appointment.date, appointment.time))
    event.add('dtend', datetime.combine(appointment.date, appointment.time) + timedelta(minutes=30))
    event.add('description', f'Appointment with Dr. {appointment.created_by.user.get_full_name()}')
    
    cal.add_component(event)
    
    # Send email
    subject = 'Your Doctor Appointment Confirmation'
    message = f'''
    Dear {appointment.patient.first_name},
    
    Your appointment has been scheduled for {appointment.date} at {appointment.time}.
    
    Please find attached calendar invite.
    
    Best regards,
    Medical Office
    '''
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[appointment.patient.email],
        attachments=[('appointment.ics', cal.to_ical(), 'text/calendar')],
    ) 