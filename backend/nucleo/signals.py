from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import criar_padroes


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def novo_usuario(sender, instance, created, **kwargs):
    """Todo usuário novo ganha perfil e as áreas da vida padrão (editáveis no onboarding)."""
    if created:
        criar_padroes(instance)
