from django import forms
from .models import Cliente
import re

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
    
    def clean_rut(self):
        rut = self.cleaned_data.get('rut').upper().replace(".", "").replace("-", "")
        if not re.match(r"^\d{7,8}[0-9K]$Generic", rut):
            raise forms.ValidationError("El RUT no tiene un formato válido.")
        
        cuerpo = rut[:-1]
        dv = rut[-1]
        
        suma = 0
        multiplo = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo = 2 if multiplo == 7 else multiplo + 1
        
        res = 11 - (suma % 11)
        dvr = 'K' if res == 10 else '0' if res == 11 else str(res)
        
        if dv != dvr:
            raise forms.ValidationError("El RUT ingresado es incorrecto.")
        
        return rut