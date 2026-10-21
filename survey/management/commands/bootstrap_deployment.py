import os

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    """Create/update deployment-specific Site and Google OAuth configuration."""

    help = "Ensure the production Site and Google SocialApp are configured."

    def handle(self, *args, **options):
        domain = self._get_domain()
        site_id = int(settings.SITE_ID)

        with transaction.atomic():
            site, _ = Site.objects.update_or_create(
                pk=site_id,
                defaults={"domain": domain, "name": "Koko Survey"},
            )
            self.stdout.write(f"Configured Django Site id={site.pk} domain={site.domain}.")
            self._configure_google_app(site)
            self._configure_superuser()

    @staticmethod
    def _get_domain():
        domain = (
            os.environ.get("SITE_DOMAIN")
            or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
            or "koko-survey.onrender.com"
        ).strip().lower()
        domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")
        if not domain or "/" in domain:
            raise CommandError("SITE_DOMAIN must be a hostname without a URL path.")
        return domain

    def _configure_google_app(self, site):
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

        # Prefer the app already attached to the active site, otherwise reuse
        # an existing Google app. This repairs the unlinked-app state without
        # deleting credentials or unrelated site associations.
        apps = list(SocialApp.objects.filter(provider="google").order_by("pk"))
        app = next((item for item in apps if item.sites.filter(pk=site.pk).exists()), None)
        if app is None and apps:
            app = apps[0]

        if client_id and client_secret:
            if app is None:
                app = SocialApp(provider="google", name="Google")
            app.name = "Google"
            app.client_id = client_id
            app.secret = client_secret
            app.key = ""
            app.save()
        elif bool(client_id) != bool(client_secret):
            self.stderr.write(
                self.style.WARNING(
                    "Google OAuth was not updated: set both GOOGLE_CLIENT_ID and "
                    "GOOGLE_CLIENT_SECRET."
                )
            )

        if app is None:
            self.stderr.write(
                self.style.WARNING(
                    "No Google SocialApp or OAuth credentials found; Google sign-in "
                    "will remain hidden until configured."
                )
            )
            return

        # Ensure allauth finds exactly one Google app for this Site. Keep any
        # other app records intact for other Sites.
        for other in apps:
            if other.pk != app.pk and other.sites.filter(pk=site.pk).exists():
                other.sites.remove(site)
        app.sites.add(site)
        self.stdout.write("Configured one Google SocialApp for the active Site.")

    def _configure_superuser(self):
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_PASSWORD is not set; existing admin accounts were left unchanged."
            )
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com").strip()
        if not username:
            raise CommandError("DJANGO_SUPERUSER_USERNAME cannot be empty.")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            **{user_model.USERNAME_FIELD: username}
        )
        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        # This only runs when an operator explicitly provides a secret through
        # Render's environment settings; no password is stored in the repo.
        user.set_password(password)
        user.save()
        action = "created" if created else "updated"
        self.stdout.write(f"Superuser '{username}' {action} from environment settings.")
