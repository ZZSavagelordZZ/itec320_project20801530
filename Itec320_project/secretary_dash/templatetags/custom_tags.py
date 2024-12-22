from django import template
from secretary_dash.models import Secretary

register = template.Library()

@register.filter
def is_secretary(user):
    return Secretary.objects.filter(user=user).exists() 