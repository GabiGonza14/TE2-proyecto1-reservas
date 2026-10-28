from django.contrib import admin
from .models import Resource, Availability, Booking, PaymentMethod

# Enlace al dashboard de demanda desde la portada del admin.
admin.site.index_template = 'admin/prevision_index.html'

# --- CONFIGURACIÓN DEL PANEL ADMIN ---

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')  # Columnas que veremos en el admin
    search_fields = ('name',)                     # Buscar recursos por nombre


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'resource', 'start_time', 'end_time')
    list_filter = ('resource',)                   # Filtro por recurso
    search_fields = ('resource__name',)
    verbose_name = 'Bloqueo'
    verbose_name_plural = 'Bloqueos'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'resource', 'start_time', 'end_time', 'created_at')
    list_filter = ('resource', 'user')
    search_fields = ('user__username', 'resource__name')


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'brand', 'last4', 'exp_month', 'exp_year', 'created_at')
    list_filter = ('brand',)
    search_fields = ('user__username', 'holder_name', 'last4')
