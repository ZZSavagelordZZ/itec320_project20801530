# Generated by Django 5.1.4 on 2024-12-21 18:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('secretary_dash', '0005_alter_appointment_options_alter_examination_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='examination',
            name='is_completed',
            field=models.BooleanField(default=False),
        ),
    ]
