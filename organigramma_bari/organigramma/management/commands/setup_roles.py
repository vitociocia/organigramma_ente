# organigramma/management/commands/setup_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from organigramma.models import Struttura

class Command(BaseCommand):
    help = "Crea gruppi Base/Avanzati/Amministratori e il permesso 'view_simulatore'"

    def handle(self, *args, **opts):
        ct = ContentType.objects.get_for_model(Struttura)
        perm, _ = Permission.objects.get_or_create(
            codename='view_simulatore',
            defaults={'name': 'Può accedere al simulatore', 'content_type': ct},
            content_type=ct,
        )

        base, _ = Group.objects.get_or_create(name='Base')
        avanzati, _ = Group.objects.get_or_create(name='Avanzati')
        admin_g, _ = Group.objects.get_or_create(name='Amministratori')

        avanzati.permissions.add(perm)
        admin_g.permissions.add(perm)  # opzionale; i superuser lo ignorano comunque

        self.stdout.write(self.style.SUCCESS("Ruoli/permessi creati."))
