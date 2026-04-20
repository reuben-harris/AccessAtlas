from django.core.management.base import BaseCommand, CommandError

from access_atlas.sites.feed import SiteFeedError, sync_configured_site_feed


class Command(BaseCommand):
    help = "Sync read-only site references from the configured site feed."

    def handle(self, *args, **options):
        try:
            result = sync_configured_site_feed()
        except SiteFeedError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "Site sync complete: "
                f"{result.created} created, "
                f"{result.updated} updated, "
                f"{result.rejected} rejected."
            )
        )
