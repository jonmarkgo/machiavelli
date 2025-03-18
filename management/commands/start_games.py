from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

from machiavelli import models

class Command(BaseCommand):
	"""
	Starts games that have all their players and have not started.
	"""

	help = 'Starts games that have all their players and have not started.'
	
	def handle(self, *args, **options):
		self.stdout.write("Starting games...\n")
		# Check for maintenance mode if it exists, otherwise assume not in maintenance
		if getattr(settings, 'MAINTENANCE_MODE', False):
			logger.warning("App is in maintenance mode. Exiting.\n")
			self.stderr.write("App is in maintenance mode. Exiting.\n")
			return
		games = models.Game.objects.filter(slots=0,
											started__isnull=True,
											finished__isnull=True,
											autostart=True)
		if games.count() > 0:
			for g in games:
				msg = "Starting game %s\n" % g.slug
				self.stdout.write(msg)
				logger.info(msg)
				g.start()
		else:
			self.stdout.write("No games ready to start.\n")
