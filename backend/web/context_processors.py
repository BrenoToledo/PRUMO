from .forms import CapturaForm


def captura(request):
    """Formulário da captura rápida, presente em todas as telas logadas."""
    if not request.user.is_authenticated:
        return {}
    return {"form_captura": CapturaForm()}
