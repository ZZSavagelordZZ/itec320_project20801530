from django import template
from secretary_dash.views import is_doctor, is_secretary

register = template.Library()

@register.filter(name='is_doctor')
def user_is_doctor(user):
    return is_doctor(user)

@register.filter(name='is_secretary')
def user_is_secretary(user):
    return is_secretary(user) 