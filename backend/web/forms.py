from django import forms


class CapturaForm(forms.Form):
    texto = forms.CharField(
        max_length=2000,
        strip=True,
        error_messages={"required": "Escreva algo para salvar."},
    )


class ListaRapidaForm(forms.Form):
    """Manda um item direto para a lista rápida: só pede a área e quanto tempo leva (até 10 min)."""

    area = forms.ModelChoiceField(queryset=None, error_messages={"invalid_choice": "Escolha uma das suas áreas."})
    minutos = forms.TypedChoiceField(choices=[(5, "5 min"), (10, "10 min")], coerce=int, initial=5)

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()
