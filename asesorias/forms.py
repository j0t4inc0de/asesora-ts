from django import forms
from .models import Cliente, Cita

class FormularioDiagnostico(forms.ModelForm):
    fecha_deseada = forms.DateField(
        required=False, 
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Selecciona Fecha deseada"
    )

    class Meta:
        model = Cliente
        fields = ['nombre', 'email', 'telefono', 'rut', 'motivo_consulta', 'fecha_deseada']
        widgets = {
            'telefono': forms.TextInput(attrs={'placeholder': '+569 XXXX XXXX', 'required': 'true'}),
            'motivo_consulta': forms.Textarea(attrs={'rows': 4, 'required': 'true'}),
        }