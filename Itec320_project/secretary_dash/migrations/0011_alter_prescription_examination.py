# Generated by Django 5.1.4 on 2024-12-22 00:54

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('secretary_dash', '0010_appointment_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prescription',
            name='examination',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prescriptions', to='secretary_dash.examination'),
        ),
    ]