from nucleo import services

from .forms import CapturaForm


def captura(request):
    """Formulário da captura rápida e contador da caixa de entrada, presentes em todas as telas logadas."""
    if not request.user.is_authenticated:
        return {}
    return {"form_captura": CapturaForm(), "pendentes_entrada": services.caixa_de_entrada(request.user).count()}
