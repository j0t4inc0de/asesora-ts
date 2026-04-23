from django.shortcuts import render
from .models import Servicio
# Create your views here.

def home(request):
    servicios = Servicio.objects.all()
    return render(request, 'index.html', {'servicios': servicios})