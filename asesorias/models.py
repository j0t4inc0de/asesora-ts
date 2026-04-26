from django.db import models
from datetime import time

# Create your models here.


class SobreMi(models.Model):
    nombre = models.CharField(max_length=100)
    quienSoy = models.TextField()
    ubicacion = models.CharField(max_length=100)
    trabajemosJuntos = models.TextField(max_length=450)
    cv = models.FileField(upload_to='cvs/', null=True, blank=True)
    gmail = models.EmailField(max_length=254, null=True, blank=True)

    def __str__(self):
        return self.nombre


class Experiencia(models.Model):
    persona = models.ForeignKey(
        SobreMi, on_delete=models.CASCADE, related_name='experiencias')
    cargo = models.CharField(max_length=200)
    institucion = models.CharField(max_length=200)
    descripcion = models.TextField()
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    actual = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha_inicio']


class Educacion(models.Model):
    persona = models.ForeignKey(
        SobreMi, on_delete=models.CASCADE, related_name='estudios')
    titulo = models.CharField(max_length=200)
    institucion = models.CharField(max_length=200)
    fecha_obtencion = models.DateField()

    class Meta:
        ordering = ['-fecha_obtencion']


class Proyecto(models.Model):
    persona = models.ForeignKey(
        'SobreMi', on_delete=models.CASCADE, related_name='proyectos')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    institucion = models.CharField(max_length=200, blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_inicio']


class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio = models.IntegerField(help_text="Monto en moneda local")

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    rut = models.CharField(max_length=12)
    email = models.EmailField()
    telefono = models.CharField(max_length=15)
    motivo_consulta = models.TextField()
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.rut})"


class Cita(models.Model):
    ESTADOS = [('P', 'Pendiente'), ('C', 'Confirmada'), ('X', 'Cancelada')]

    ESTADOS_PAGO = [('NO', 'No Pagado'), ('PE', 'Pago Pendiente'),
                    ('PA', 'Pagado'), ('RE', 'Reembolsado')]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT)
    fecha_hora = models.DateTimeField(unique=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')

    estado_pago = models.CharField(
        max_length=2, choices=ESTADOS_PAGO, default='NO')
    transaccion_id = models.CharField(
        max_length=100, blank=True, null=True, help_text="ID de Webpay/MercadoPago")

    def __str__(self):
        return f"Cita: {self.cliente.nombre} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"


class HorarioAtencion(models.Model):
    DIA_CHOICES = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo')
    ]
    dia_semana = models.IntegerField(choices=DIA_CHOICES, unique=True)
    hora_inicio = models.TimeField(default=time(8, 0))  # 08:00 AM
    hora_fin = models.TimeField(default=time(13, 0))   # 01:00 PM
    activo = models.BooleanField(default=True, help_text="¿Atiende este día?")

    class Meta:
        verbose_name = "Horario de Atención"
        verbose_name_plural = "Horarios de Atención"

    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.hora_inicio.strftime('%H:%M')} - {self.hora_fin.strftime('%H:%M')}"
