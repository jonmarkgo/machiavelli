# Copyright (c) 2010 by Jose Antonio Martin <jantonio.martin AT gmail DOT com>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License
# for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/agpl.txt>.
#
# This license is also included in the file COPYING
#
# AUTHOR: Jose Antonio Martin <jantonio.martin AT gmail DOT com>

""" This module defines ``Signals`` to be sent by machiavelli objects. 

These signals are closely related to ``condottieri_events``, so whenever a
new Signal is defined, a related Event should be defined, and conversely.
"""

from django.dispatch import Signal

player_joined = Signal()
# unit_placed is sent by Unit when placed
unit_placed = Signal()
# unit_disbanded is sent by Unit when deleted
unit_disbanded = Signal()

# maybe this one could be replaced by a post_save signal
order_placed = Signal()
# Args: "destination", "subtype", suborigin", "subcode", "subdestination", "subconversion"

standoff_happened = Signal()
unit_converted = Signal()
# Args: "before", "after"

area_controlled = Signal()
# Args: "new_home"

unit_moved = Signal()
# Args: "destination"

unit_retreated = Signal()
# Args: "destination"

support_broken = Signal()
forced_to_retreat = Signal()
unit_surrendered = Signal()
siege_started = Signal()
unit_changed_country = Signal()
unit_to_autonomous = Signal()
government_overthrown = Signal()
overthrow_attempted = Signal()
player_surrendered = Signal()
country_conquered = Signal()
# Args: "country"

country_eliminated = Signal()
# Args: "country"

famine_marker_placed = Signal()
storm_marker_placed = Signal()
plague_placed = Signal()
rebellion_started = Signal()
country_excommunicated = Signal()
country_forgiven = Signal()
income_raised = Signal()
# Args: "ducats"

expense_paid = Signal()
player_assassinated = Signal()
assassination_attempted = Signal()
game_finished = Signal()
diplomat_uncovered = Signal()
