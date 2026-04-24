from django import forms
from .models import Cliente
import re

class FormularioDiagnostico(forms.ModelForm):
    fecha_hora_reserva = forms.DateTimeField(
        widget=forms.HiddenInput(), # Se ocultará porque usaremos botones/calendario visual en HTML
        required=True
    )

    class Meta:
        model = Cliente
        fields = ['nombre', 'email', 'telefono', 'rut', 'motivo_consulta', 'fecha_deseada']
        widgets = {
            'telefono': forms.TextInput(attrs={'placeholder': '+569 XXXX XXXX', 'required': 'true'}),
            'motivo_consulta': forms.Textarea(attrs={'rows': 4, 'required': 'true'}),
        }
    
    def clean_rut(self):
        rut_raw = self.cleaned_data.get('rut', '').upper().strip()
        rut_clean = "".join(filter(lambda char: char.isdigit() or char == 'K', rut_raw))

        if not (8 <= len(rut_clean) <= 9):
            raise forms.ValidationError("El RUT no es válido (debe tener entre 8 y 9 caracteres).")

        cuerpo = rut_clean[:-1]
        dv = rut_clean[-1]

        suma = 0
        multiplo = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo = 2 if multiplo == 7 else multiplo + 1
        
        res = 11 - (suma % 11)
        dvr = 'K' if res == 10 else '0' if res == 11 else str(res)
        
        if dv != dvr:
            raise forms.ValidationError("El RUT es incorrecto (dígito verificador no coincide).")
        
        return f"{cuerpo}-{dv}"