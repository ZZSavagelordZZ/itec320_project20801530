from django.urls import path
from . import views
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

app_name = 'secretary_dash'

urlpatterns = [
    # Root and Authentication
    path('', views.root_redirect, name='root'),

    # Password Change URLs
    path('password_change/', 
        auth_views.PasswordChangeView.as_view(
            template_name='secretary_dash/common/password_change.html',
            success_url=reverse_lazy('secretary_dash:password_change_done')
        ), 
        name='password_change'
    ),
    path('password_change/done/', 
        auth_views.PasswordChangeDoneView.as_view(
            template_name='secretary_dash/common/password_change_done.html'
        ), 
        name='password_change_done'
    ),

    # Doctor URLs
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/secretaries/', views.secretary_list, name='secretary_list'),
    path('doctor/secretaries/add/', views.secretary_create, name='secretary_create'),
    path('doctor/secretaries/<int:pk>/edit/', views.secretary_edit, name='secretary_edit'),
    path('doctor/secretaries/<int:pk>/delete/', views.secretary_delete, name='secretary_delete'),

    # Common URLs (accessible by both doctor and secretary)
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/add/', views.patient_create, name='patient_create'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:pk>/edit/', views.patient_edit, name='patient_edit'),
    path('patients/<int:pk>/delete/', views.patient_delete, name='patient_delete'),

    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/add/', views.appointment_create, name='appointment_create'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:pk>/edit/', views.appointment_edit, name='appointment_edit'),
    path('appointments/<int:pk>/cancel/', views.appointment_cancel, name='appointment_cancel'),

    path('medicines/', views.medicine_list, name='medicine_list'),
    path('medicines/add/', views.medicine_create, name='medicine_create'),
    path('medicines/<int:pk>/edit/', views.medicine_edit, name='medicine_edit'),
    path('medicines/<int:pk>/delete/', views.medicine_delete, name='medicine_delete'),

    path('examinations/', views.examination_list, name='examination_list'),
    path('examinations/add/', views.examination_create, name='examination_create'),
    path('examinations/<int:pk>/', views.examination_detail, name='examination_detail'),
    path('examinations/<int:pk>/edit/', views.examination_edit, name='examination_edit'),
    path('examinations/<int:pk>/delete/', views.examination_delete, name='examination_delete'),

    # Secretary URLs
    path('secretary/', views.secretary_dashboard, name='secretary_dashboard'),
] 