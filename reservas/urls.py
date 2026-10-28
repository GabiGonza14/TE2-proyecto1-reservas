from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Página principal
    path('calendario/<int:resource_id>/', views.calendario, name='calendario'),
    path('calendario_full/<int:resource_id>/', views.calendario_full, name='calendario_full'),
    path('api/reservas/<int:resource_id>/', views.api_reservas, name='api_reservas'),
    path('api/disponibilidad/<int:resource_id>/', views.api_disponibilidad, name='api_disponibilidad'),
    path('api/reservas/crear/', views.api_crear_reserva, name='api_crear_reserva'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('pagos/', views.metodos_pago, name='metodos_pago'),
    path('mis-reservas/', views.mis_reservas, name='mis_reservas'),
    path('mis-reservas/<int:booking_id>/cancelar/', views.cancelar_reserva_view, name='cancelar_reserva'),
    path('mis-reservas/<int:booking_id>/modificar/', views.modificar_reserva_view, name='modificar_reserva'),
    path('prevision-demanda/', views.prevision_demanda, name='prevision_demanda'),



]
