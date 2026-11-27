from django.core.management.base import BaseCommand, CommandError

from apps.core import checks


class Command(BaseCommand):
    help = "Check that this CheMTlab instance is healthy and safely configured."

    def handle(self, *args, **options):
        failed = False
        for result in checks.run_all():
            if result.ok:
                mark = self.style.SUCCESS("OK  ")
            elif result.critical:
                mark = self.style.ERROR("FAIL")
                failed = True
            else:
                mark = self.style.WARNING("WARN")
            self.stdout.write(f"[{mark}] {result.name}: {result.detail}")
        if failed:
            raise CommandError("One or more critical checks failed.")
        self.stdout.write(self.style.SUCCESS("CheMTlab looks healthy."))
