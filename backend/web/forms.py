from django import forms


class CapturaForm(forms.Form):
    texto = forms.CharField(
        max_length=2000,
        strip=True,
        error_messages={"required": "Escreva algo para salvar."},
    )
