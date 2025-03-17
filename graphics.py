## Copyright (c) 2010 by Jose Antonio Martin <jantonio.martin AT gmail DOT com>
## This program is free software: you can redistribute it and/or modify it
## under the terms of the GNU Affero General Public License as published by the
## Free Software Foundation, either version 3 of the License, or (at your option
## any later version.
##
## This program is distributed in the hope that it will be useful, but WITHOUT
## ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
## FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License
## for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/agpl.txt>.
##
## This license is also included in the file COPYING
##
## AUTHOR: Jose Antonio Martin <jantonio.martin AT gmail DOT com>

""" This module defines functions to generate the map. """

from PIL import Image
import os
import os.path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger(__name__)

from . import models as machiavelli
from machiavelli.exceptions import GraphicsError

TOKENS_DIR=os.path.join(settings.MEDIA_ROOT, settings.SCENARIOS_ROOT, 'tokens')

def ensure_dir(f):
	d = os.path.dirname(f)
	if not os.path.exists(d):
		os.makedirs(d)

def load_token(token_path, size=(200, 200)):
	"""Load a token image, falling back to a placeholder if not found"""
	try:
		return Image.open(token_path)
	except (IOError, FileNotFoundError):
		logger.warning(f"Token not found: {token_path}, using placeholder")
		import urllib.request
		from io import BytesIO
		placeholder_url = f"https://placehold.co/{size[0]}x{size[1]}/png"
		with urllib.request.urlopen(placeholder_url) as response:
			return Image.open(BytesIO(response.read()))

# Load base tokens with placeholders
LOYAL_A = load_token(f"{TOKENS_DIR}/loyal-army.png")
LOYAL_F = load_token(f"{TOKENS_DIR}/loyal-fleet.png")
LOYAL_G = load_token(f"{TOKENS_DIR}/loyal-garrison.png")
ELITE_A = load_token(f"{TOKENS_DIR}/elite-army.png")
ELITE_F = load_token(f"{TOKENS_DIR}/elite-fleet.png")
ELITE_G = load_token(f"{TOKENS_DIR}/elite-garrison.png")
DIPLOMAT = load_token(f"{TOKENS_DIR}/diplomat-icon.png")

def load_unit_tokens(game):
	tokens = dict()
	for player in game.player_set.filter(user__isnull=False):
		t = dict()
		name = player.static_name
		t.update({'A': load_token(f"{TOKENS_DIR}/A-{name}.png")})
		t.update({'F': load_token(f"{TOKENS_DIR}/F-{name}.png")})
		t.update({'G': load_token(f"{TOKENS_DIR}/G-{name}.png")})
		tokens.update({name: t})
	tokens.update({'autonomous': {'G': load_token(f"{TOKENS_DIR}/G-autonomous.png")}})
	return tokens


def paste_units(board, game, watcher=None):
	tokens = load_unit_tokens(game)
	if isinstance(watcher, machiavelli.Player):
		visible = watcher.visible_areas()
		print("Making secret map for %s" % watcher.static_name)
	afs = machiavelli.Unit.objects.filter(type__in=('A','F'), player__game=game, placed=True)
	gars = machiavelli.Unit.objects.filter(type__exact='G', player__game=game, placed=True)
	dips = None
	if isinstance(watcher, machiavelli.Player):
		afs = afs.filter(area__board_area__in=visible)
		gars = gars.filter(area__board_area__in=visible)
		dips = watcher.diplomat_set.all()
	## paste Armies and Fleets
	for unit in afs:
			t = tokens[unit.player.static_name][unit.type]
			if unit.besieging:
				try:
					coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
				except ObjectDoesNotExist:
					logger.error("GToken object not found for area %s" % unit.area.board_area.code)
					raise GraphicsError
			else:
				try:
					coords = (unit.area.board_area.aftoken.x, unit.area.board_area.aftoken.y)
				except ObjectDoesNotExist:
					logger.error("AFToken object not found for area %s" % unit.area.board_area.code)
					raise GraphicsError
				if unit.must_retreat != '':
					coords = (coords[0] + 15, coords[1] + 15)
			if unit.type == 'A':
				board.paste(t, coords, t)
				if unit.power > 1:
					board.paste(ELITE_A, coords, ELITE_A)
				if unit.loyalty > 1:
					board.paste(LOYAL_A, coords, LOYAL_A)
			elif unit.type == 'F':
				board.paste(t, coords, t)
				if unit.power > 1:
					board.paste(ELITE_F, coords, ELITE_F)
				if unit.loyalty > 1:
					board.paste(LOYAL_F, coords, LOYAL_F)
			else:
				pass
	## paste Garrisons
	for unit in gars:
		if unit.player.user:
			t = tokens[unit.player.static_name]['G']
		else:
			t = tokens['autonomous']['G']
		try:
			coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
		except ObjectDoesNotExist:
			logger.error("GToken not found for area %s" % unit.area.board_area.code)
			raise GraphicsError
		board.paste(t, coords, t)
		if unit.power > 1:
			board.paste(ELITE_G, coords, ELITE_G)
		if unit.loyalty > 1:
			board.paste(LOYAL_G, coords, LOYAL_G)
	## paste diplomat icons
	if dips:
		for d in dips:
			try:
				coords = (d.area.board_area.controltoken.x - 24, d.area.board_area.controltoken.y - 4)
			except ObjectDoesNotExist:
				logger.error("ControlToken not found for %s" % d.area.board_area.code)
				raise GraphicsError
			board.paste(DIPLOMAT, coords, DIPLOMAT)
	
def make_map(game, fow=False):
	""" Opens the base map and add flags, control markers, unit tokens and other tokens. Then saves
	the map with an appropriate name in the maps directory.
	If fow == True, makes one map for every player and doesn't make a thumbnail
	"""
	if game.finished:
		fow = False
	try:
		base_map = Image.open(game.scenario.setting.board)
	except IOError:
		logger.error("Base map not found for scenario %s" % game.scenario.slug)
		raise GraphicsError
	## if there are disabled areas, mark them
	marker = load_token(f"{TOKENS_DIR}/disabled.png")
	for a in game.get_disabled_areas():
		try:
			base_map.paste(marker, (a.aftoken.x, a.aftoken.y), marker)
		except ObjectDoesNotExist:
			logger.error("AFToken not found for area %s" % a.code)
			raise GraphicsError
	## mark special city incomes
	marker = load_token(f"{TOKENS_DIR}/chest.png")
	for i in game.scenario.cityincome_set.all():
		try:
			base_map.paste(marker, (i.city.gtoken.x + 32, i.city.gtoken.y), marker)
		except ObjectDoesNotExist:
			logger.error("GToken not found for area %s" % i.city.code)
			raise GraphicsError
	##
	for player in game.player_set.filter(user__isnull=False):
		## paste control markers
		controls = player.gamearea_set.all()
		marker = load_token(f"{TOKENS_DIR}/control-{player.static_name}.png")
		for area in controls:
			try:
				base_map.paste(marker, (area.board_area.controltoken.x, area.board_area.controltoken.y), marker)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % area.board_area.code)
				raise GraphicsError
		## paste flags
		home = player.home_country()
		flag = load_token(f"{TOKENS_DIR}/flag-{player.static_name}.png")
		for game_area in home:
			area = game_area.board_area
			try:
				base_map.paste(flag, (area.controltoken.x, area.controltoken.y - 10), flag)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % area.board_area.code)
				raise GraphicsError
	## paste famine markers
	if game.configuration.famine:
		famine = load_token(f"{TOKENS_DIR}/famine-marker.png")
		for a in game.gamearea_set.filter(famine=True):
			try:
				coords = (a.board_area.controltoken.x + 12, a.board_area.controltoken.y + 12)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % a.board_area.code)
				raise GraphicsError
			base_map.paste(famine, coords, famine)
	## paste storm markers
	if game.configuration.storms:
		storm = load_token(f"{TOKENS_DIR}/storm-marker.png")
		for a in game.gamearea_set.filter(storm=True):
			try:
				coords = (a.board_area.aftoken.x - 20, a.board_area.aftoken.y + 30)
			except ObjectDoesNotExist:
				logger.error("AFToken object not found for area %s" % a.board_area.code)
				raise GraphicsError
			base_map.paste(storm, coords, storm)
	## paste rebellion markers
	if game.configuration.finances:
		rebellion_marker = load_token(f"{TOKENS_DIR}/rebellion-marker.png")
		for r in game.get_rebellions():
			try:
				if r.garrisoned:
					coords = (r.area.board_area.gtoken.x, r.area.board_area.gtoken.y)
				else:
					coords = (r.area.board_area.controltoken.x - 12, r.area.board_area.controltoken.y - 12)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % r.area.board_area.code)
				raise GraphicsError
			base_map.paste(rebellion_marker, coords, rebellion_marker)
	if fow:
		for player in game.player_set.filter(user__isnull=False):
			player_map = base_map.copy()
			paste_units(player_map, game, watcher=player)
			result = player_map.convert("RBG")
			filename = game.get_map_path(player)
			ensure_dir(filename)
			result.save(filename)
	else:
		paste_units(base_map, game)
		result = base_map.convert("RGB")
		filename = game.get_map_path()
		ensure_dir(filename)
		result.save(filename)
		make_game_thumb(game, 187, 267)

	return True

def make_game_thumb(game, w, h):
	""" Make a thumbnail of the game map image """
	size = w, h
	fd = game.get_map_path()
	outfile = game.thumbnail_path
	im = Image.open(fd)
	im.thumbnail(size, Image.ANTIALIAS)
	ensure_dir(outfile)
	im.save(outfile, "JPEG")

