import django.forms as forms
from django.core.cache import cache
from django.forms.formsets import BaseFormSet
from django.utils.safestring import mark_safe
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.utils import timezone

import machiavelli.models as machiavelli
from condottieri_scenarios.models import Scenario, Country

CITIES_TO_WIN = (
    (15, _('Normal game (15 cities)')),
    (23, _('Long game (23 cities)')),
    (12, _('Short game (12 cities - see help)')),
)

class GameBaseForm(forms.ModelForm):
    scenario = forms.ModelChoiceField(queryset=Scenario.objects.filter(enabled=True),
                                    empty_label=None,
                                    #cache_choices=True,
                                    label=_("Scenario"))
    time_limit = forms.ChoiceField(choices=machiavelli.TIME_LIMITS, label=_("Time limit"))
    visible = forms.BooleanField(required=False, label=_("Visible players?"))
    
    def __init__(self, user, **kwargs):
        super(GameBaseForm, self).__init__(**kwargs)
        self.instance.created_by = user
        if not self.instance.pk:  # Only for new instances
            self.instance.created = timezone.now()

    def save(self, commit=True):
        instance = super(GameBaseForm, self).save(commit=False)
        instance.slots = max(0, instance.scenario.number_of_players - 1)
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super(GameBaseForm, self).clean()
        fast = private = False
        if int(cleaned_data['time_limit']) in machiavelli.FAST_LIMITS:
            fast = True
        if cleaned_data['private']:
            private = True
        user = self.instance.created_by
        msg = user.profile.check_karma_to_join(fast=fast, private=private)
        if msg != "":
            raise forms.ValidationError(msg)
        return cleaned_data

class GameForm(GameBaseForm):
    cities_to_win = forms.ChoiceField(choices=CITIES_TO_WIN, label=_("How to win"))

    class Meta:
        model = machiavelli.Game
        fields = (#'slug',
                'title',
                'scenario',
                'time_limit',
                'cities_to_win',
                'visible',
                'private',)

TEAM_SIZES=(
    (2, 2),
    (3, 3),
    (4, 4))

class TeamGameForm(GameBaseForm):
    teams = forms.ChoiceField(choices=TEAM_SIZES, label=_("Number of teams"))

    class Meta:
        model = machiavelli.Game
        fields = (#'slug',
                'title',
                'scenario',
                'teams',
                'time_limit',
                'visible',
                'private',)

    def clean(self):
        cleaned_data = super(TeamGameForm, self).clean()        
        scenario = cleaned_data['scenario']
        teams = cleaned_data['teams']
        if scenario.number_of_players / int(teams) < 2:
            msg = _("Either select fewer teams or a scenario for more players")
            raise forms.ValidationError(msg)
        return cleaned_data

class ConfigurationForm(forms.ModelForm):
    def clean(self):
        cleaned_data = self.cleaned_data
        if cleaned_data['unbalanced_loans']:
            cleaned_data['lenders'] = True
        if cleaned_data['assassinations'] or cleaned_data['lenders'] or cleaned_data['special_units']:
            cleaned_data['finances'] = True
        if 'taxation' in list(cleaned_data.keys()) and cleaned_data['taxation']:
            cleaned_data['finances'] = True
            cleaned_data['famine'] = True
        if 'variable_home' in list(cleaned_data.keys()) and cleaned_data['variable_home']:
            cleaned_data['conquering'] = False
        return cleaned_data

    class Meta:
        model = machiavelli.Configuration
        #exclude = ('strategic',)
        exclude = getattr(settings, 'DISABLED_RULES', ())

class InvitationForm(forms.Form):
    user_list = forms.CharField(required=True,
                                label=_("User list, comma separated"))
    message = forms.CharField(label=_("Optional message"),
                                required=False,
                                widget=forms.Textarea)

class WhisperForm(forms.ModelForm):
    class Meta:
        model = machiavelli.Whisper
        fields = ('text',)
        exclude = ('user', 'game',)
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'cols': 20})
        }
    
    def save(self, user, game, commit=True):
        instance = super(WhisperForm, self).save(commit=False)
        instance.user = user
        instance.game = game
        if commit:
            instance.save()
        return instance

class JournalForm(forms.ModelForm):
    class Meta:
        model = machiavelli.Journal
        fields = ('content',)

    def __init__(self, user, game, **kwargs):
        super(JournalForm, self).__init__(**kwargs)
        self.instance.user = user
        self.instance.game = game

class GameCommentForm(forms.ModelForm):
    class Meta:
        model = machiavelli.GameComment
        fields = ('comment',)
    
    def save(self, user, game, *args, **kwargs):
        self.instance.user = user
        self.instance.game = game
        comment = super(GameCommentForm, self).save(*args, **kwargs)
        comment.save()

class TeamMessageForm(forms.ModelForm):
    class Meta:
        model = machiavelli.TeamMessage
        fields = ('text',)
        exclude = ('player',)

    def save(self, player, commit=True):
        instance = super(TeamMessageForm, self).save(commit=False)
        instance.player = player
        if commit:
            instance.save()
        return instance
    
class UnitForm(forms.ModelForm):
    type = forms.ChoiceField(required=True, choices=machiavelli.UNIT_TYPES)
    
    class Meta:
        model = machiavelli.Unit
        fields = ('type', 'area')

def strategic_order_form_factory(player):
    units = player.strategic_units()
    areas = player.game.get_all_gameareas()

    class StrategicOrderForm(forms.ModelForm):
        unit = forms.ModelChoiceField(queryset=units, label=_("Unit"))
        area = forms.ModelChoiceField(queryset=areas, label=_("Destination"))

        class Meta:
            model = machiavelli.StrategicOrder
            fields = ('unit', 'area',)

        def clean(self):
            cleaned_data = super(StrategicOrderForm, self).clean()
            if 'unit' in cleaned_data and 'area' in cleaned_data:
                unit = cleaned_data['unit']
                area = cleaned_data['area']
                if not unit.check_strategic_movement(area):
                    raise forms.ValidationError(_("%(unit)s cannot move to %(area)s") % {'unit': unit,
        'area': area.board_area.name})
            return cleaned_data

    return StrategicOrderForm
        
class BaseStrategicOrderFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        units = []
        for i in range(0, self.total_form_count()):
            form = self.forms[i]
            if 'unit' in form.cleaned_data:
                unit = form.cleaned_data['unit']
                if unit in units:
                    raise forms.ValidationError(_("You cannot give two orders to the same unit."))
                units.append(unit)

def make_order_form(player):
    if player.game.configuration.finances:
        ## units bought by this player
        bought_ids = machiavelli.Expense.objects.filter(player=player, type__in=(6,9)).values_list('unit', flat=True)
        units_qs = machiavelli.Unit.objects.filter(Q(player=player) | Q(id__in=bought_ids))
    else:
        units_qs = player.unit_set.select_related().all()
    all_units = player.game.get_all_units()
    if player.game.configuration.fow:
        visible = player.visible_areas()    
        subunits_qs = all_units.filter(area__board_area__in=visible)
    else:
        subunits_qs = all_units
    all_areas = player.game.get_all_gameareas()
    
    class OrderForm(forms.ModelForm):
        unit = forms.ModelChoiceField(queryset=units_qs, label=_("Unit"))
        code = forms.ChoiceField(choices=machiavelli.ORDER_CODES, label=_("Order"))
        destination = forms.ModelChoiceField(required=False, queryset=all_areas, label=_("Destination"))
        type = forms.ChoiceField(choices=machiavelli.UNIT_TYPES, label=_("Convert into"))
        subunit = forms.ModelChoiceField(required=False, queryset=subunits_qs, label=_("Unit"))
        subcode = forms.ChoiceField(required=False, choices=machiavelli.ORDER_SUBCODES, label=_("Order"))
        subdestination = forms.ModelChoiceField(required=False, queryset=all_areas, label=_("Destination"))
        subtype = forms.ChoiceField(required=False, choices=machiavelli.UNIT_TYPES, label=_("Convert into"))
        
        def __init__(self, player, **kwargs):
            super(OrderForm, self).__init__(**kwargs)
            self.instance.player = player
        
        class Meta:
            model = machiavelli.Order
            fields = ('unit', 'code', 'destination', 'type',
                    'subunit', 'subcode', 'subdestination', 'subtype')
        
        class Media:
            js = ("%smachiavelli/js/order_form.js" % settings.STATIC_URL,
                  "%smachiavelli/js/jquery.form.js" % settings.STATIC_URL)
            
        def clean(self):
            cleaned_data = self.cleaned_data
            unit = cleaned_data.get('unit')
            code = cleaned_data.get('code')
            destination = cleaned_data.get('destination')
            type = cleaned_data.get('type')
            subunit = cleaned_data.get('subunit')
            subcode = cleaned_data.get('subcode')
            subdestination = cleaned_data.get('subdestination')
            subtype = cleaned_data.get('subtype')
            
            ## check if unit has already an order from the same player
            try:
                machiavelli.Order.objects.get(unit=unit, player=player)
            except:
                pass
            else:
                raise forms.ValidationError(_("This unit has already an order"))
            ## check for errors
            if code == '-' and not destination:
                raise forms.ValidationError(_("You must select an area to advance into"))
            if code == '=':
                if not type:
                    raise forms.ValidationError(_("You must select a unit type to convert into"))
                if unit.type == type:
                    raise forms.ValidationError(_("A unit must convert into a different type"))
            if code == 'C':
                if not subunit:
                    raise forms.ValidationError(_("You must select a unit to convoy"))
                if not subdestination:
                    raise forms.ValidationError(_("You must select a destination area to convoy the unit"))
                ## check if the unit is in a sea affected by a storm
                if unit.area.storm == True:
                    raise forms.ValidationError(_("A fleet cannot convoy while affected by a storm"))
            if code == 'S':
                if not subunit:
                    raise forms.ValidationError(_("You must select a unit to support"))
                if subcode == '-' and not subdestination:
                    raise forms.ValidationError(_("You must select a destination area for the supported unit"))
                if subcode == '=':
                    if not subtype:
                        raise forms.ValidationError(_("You must select a unit type for the supported unit"))
                    if subtype == subunit.type:
                        raise forms.ValidationError(_("A unit must convert into a different type"))

            ## set to None the fields that are not needed
            if code in ['H', '-', '=', 'B']:
                cleaned_data.update({'subunit': None,
                                    'subcode': None,
                                    'subdestination': None,
                                    'subtype': None})
                if code in ['H', '-', 'B']:
                    cleaned_data.update({'type': None})
                if code in ['H', '=', 'B']:
                    cleaned_data.update({'destination': None})
            elif code == 'C':
                cleaned_data.update({'destination': None,
                                    'type': None,
                                    'subcode': None,
                                    'subtype': None})
            else:
                cleaned_data.update({'destination': None,
                                    'type': None})
                if subcode in ['H', '-']:
                    cleaned_data.update({'subtype': None})
                if subcode in ['H', '=']:
                    cleaned_data.update({'subdestination': None})

            return cleaned_data
        
        def as_td(self):
            "Returns this form rendered as HTML <td>s -- excluding the <tr></tr>."
            tds = self._html_output('<td>%(errors)s %(field)s%(help_text)s</td>', '<td style="width:10%%">%s</td>', '</td>', ' %s', False)
            return str(tds)
        
    return OrderForm

def make_retreat_form(u):
    possible_retreats = u.get_possible_retreats()
    
    class RetreatForm(forms.Form):
        unitid = forms.IntegerField(widget=forms.HiddenInput, initial=u.id)
        area = forms.ModelChoiceField(required=False,
                            queryset=possible_retreats,
                            empty_label='Disband unit',
                            label=u)
    
    return RetreatForm

def make_reinforce_form(player, finances=False, special_units=False):
    if finances:
        unit_types = (('', '---'),) + machiavelli.UNIT_TYPES
        noarea_label = '---'
    else:
        unit_types = machiavelli.UNIT_TYPES
        noarea_label = None
    area_qs = player.get_areas_for_new_units(finances)

    class ReinforceForm(forms.Form):
        type = forms.ChoiceField(required=True, choices=unit_types)
        area = forms.ModelChoiceField(required=True,
                          queryset=area_qs,
                          empty_label=noarea_label)
        if special_units and not player.has_special_unit():
            ## special units are available for the player
            unit_class = forms.ModelChoiceField(required=False,
                                            #queryset=player.country.special_units.all(),
                                            queryset=player.contender.country.special_units.all(),
                                            empty_label=_("Regular (3d)"))

        def clean(self):
            cleaned_data = self.cleaned_data
            type = cleaned_data.get('type')
            area = cleaned_data.get('area')
            if type is None:
                raise forms.ValidationError(_('You must select a unit type'))
            if area is None:
                raise forms.ValidationError(_('You must select an area'))
            if not type in area.possible_reinforcements():
                raise forms.ValidationError(_('This unit cannot be placed in this area'))
            return cleaned_data

    return ReinforceForm

class BaseReinforceFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        areas = []
        for i in range(0, self.total_form_count()):
            form = self.forms[i]
            if 'area' in form.cleaned_data:
                area = form.cleaned_data['area']
                if area in areas:
                    raise forms.ValidationError(_('You cannot place two units in the same area in one turn'))
                areas.append(area)
        special_count = 0
        for i in range(0, self.total_form_count()):
            form = self.forms[i]
            if 'unit_class' in form.cleaned_data:
                if not form.cleaned_data['unit_class'] is None:
                    special_count += 1
                if special_count > 1:
                    raise forms.ValidationError(_("You cannot buy more than one special unit"))

def make_disband_form(player):
    class DisbandForm(forms.Form):
        units = forms.ModelMultipleChoiceField(required=True,
                          queryset=player.unit_set.all(),
                          label="Units to disband")
    return DisbandForm

class UnitPaymentMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.describe_with_cost()

def make_unit_payment_form(player):
    class UnitPaymentForm(forms.Form):
        units = UnitPaymentMultipleChoiceField(required=False,
                          queryset=player.unit_set.filter(placed=True),
                          widget=forms.CheckboxSelectMultiple,
                          label="")
    return UnitPaymentForm

def make_ducats_list(ducats, f=3):
    assert isinstance(f, int)
    if ducats > 0:
        ducats_list = ((1, 1),)
    else:
        ducats_list = ((0, 0),)
    if ducats >= f:
        items = ducats / f + 1
        for i in range(1, items):
            j = i * f
            ducats_list += ((j,j),)
    return ducats_list

def make_expense_form(player):
    ducats_list = make_ducats_list(player.ducats)
    unit_qs = machiavelli.Unit.objects.filter(player__game=player.game).order_by('area__board_area__code')
    if player.game.configuration.fow:
        visible = player.visible_areas()
        unit_qs = unit_qs.filter(area__board_area__in=visible)
    area_qs = machiavelli.GameArea.objects.filter(game=player.game).order_by('board_area__code')

    class ExpenseForm(forms.ModelForm):
        ducats = forms.ChoiceField(required=True, choices=ducats_list)
        area = forms.ModelChoiceField(required=False, queryset=area_qs)
        unit = forms.ModelChoiceField(required=False, queryset=unit_qs)
    
        def __init__(self, player, **kwargs):
            super(ExpenseForm, self).__init__(**kwargs)
            self.instance.player = player
    
        class Meta:
            model = machiavelli.Expense
            fields = ('type', 'ducats', 'area', 'unit')
    
        def clean(self):
            cleaned_data = self.cleaned_data
            type = cleaned_data.get('type')
            ducats = cleaned_data.get('ducats')
            area = cleaned_data.get('area')
            unit = cleaned_data.get('unit')

            try:
                ducats = int(ducats)
            except:
                raise forms.ValidationError(_("Ducats paid are not valid"))
    
            if type in (0,1,2,3, 10, 11):
                if not isinstance(area, machiavelli.GameArea):
                    raise forms.ValidationError(_("You must choose an area"))
                unit = None
                del cleaned_data['unit']
            elif type in (4,5,6,7,8,9):
                if not isinstance(unit, machiavelli.Unit):
                    raise forms.ValidationError(_("You must choose a unit"))
                area = None
                del cleaned_data['area']
            else:
                raise forms.ValidationError(_("Unknown expense"))
            ## check that the minimum cost is paid
            cost = machiavelli.get_expense_cost(type, unit, area)
            if int(ducats) < cost:
                raise forms.ValidationError(_("You must pay at least %s ducats") % cost)
            ## check for redundant expenses
            try:
                machiavelli.Expense.objects.get(player=player, type=type, area=area, unit=unit)
            except ObjectDoesNotExist:
                pass
            else:
                raise forms.ValidationError(_("This expense already exists"))
            ## a diplomat cannot be bribed in the sea
            if type in (10, 11):
                if not area.game.configuration.fow:
                    raise forms.ValidationError(_("This expense is not allowed in this game"))
                if area.board_area.is_sea:
                    raise forms.ValidationError(_("You must choose a land area"))
            ## if famine relief, check if there is a famine marker
            if type == 0:
                if not area.famine:
                    raise forms.ValidationError(_("There is no famine in this area"))
            ## if pacify rebellion, check if there is a rebellion
            elif type == 1:
                try:
                    machiavelli.Rebellion.objects.get(area=area)
                except ObjectDoesNotExist:
                    raise forms.ValidationError(_("There is no rebellion in this area"))
            ## if province to rebel
            elif type == 2 or type == 3:
                if area.player:
                    if area.player == player:
                        raise forms.ValidationError(_("You cannot promote a rebellion in one of your own areas"))
                    if type == 2 and area in area.player.controlled_home_country():
                        raise forms.ValidationError(_("This area is part of the player's home country"))
                    elif type == 3 and not area in area.player.controlled_home_country():
                        raise forms.ValidationError(_("This area is not in the home country of the player who controls it"))
                else:
                    raise forms.ValidationError(_("This area is not controlled by anyone"))
                    
            ## if disband or buy autonomous garrison, check if the unit is an autonomous garrison
            elif type in (5, 6):
                #if unit.type != 'G' or unit.player.country != None:
                if unit.type != 'G' or unit.player.contender.country != None:
                    raise forms.ValidationError(_("You must choose an autonomous garrison"))
            ## checks for convert, disband or buy enemy units
            elif type in (7, 8, 9):
                if unit.player == player:
                    raise forms.ValidationError(_("You cannot choose one of your own units"))
                #if unit.player.country == None:
                if unit.player.contender.country == None:
                    raise forms.ValidationError(_("You must choose an enemy unit"))
                if type == 7 and unit.type != 'G':
                    raise forms.ValidationError(_("You must choose a non-autonomous garrison"))
            ## if hiring a diplomat, check the control of area
            elif type == 10:
                if not area.player or area.player != player:
                    raise forms.ValidationError(_("You must choose a province that you control"))
            elif type == 11:
                if area.player and area.player == player:
                    raise forms.ValidationError(_("You must choose a province that you don't control"))
            ## check if bribing the unit is possible
            if type in (5,6,7,8,9):
                check_areas = unit.area.get_adjacent_areas(include_self=True)
                ok = False
                for a in check_areas:
                    if a.player == player:
                        ok = True
                        break
                if not ok:
                    check_ids = check_areas.values_list('id', flat=True)
                    try:
                        machiavelli.Unit.objects.get(player=player, area__id__in=check_ids)
                    except MultipleObjectsReturned:
                        ## there is more than one unit
                        ok = True
                    except:
                        ## no units or any other exception
                        ok = False
                    else:
                        ## there is just one unit
                        ok = True
                if not ok:
                    raise forms.ValidationError(_("You cannot bribe this unit because it's too far from your units or areas"))
            return cleaned_data
    
    return ExpenseForm

def make_taxation_form(player):
    rebellion_ids = machiavelli.Rebellion.objects.filter(player=player).values_list('area', flat=True)
    qs = player.gamearea_set.filter(taxed=False, board_area__has_city=True).exclude(id__in=rebellion_ids)
    class TaxationForm(forms.Form):
        areas = forms.ModelMultipleChoiceField(required=False,
                          queryset=qs,
                          widget=forms.CheckboxSelectMultiple,
                          label=_("Areas to tax"))
    return TaxationForm

class LendForm(forms.Form):
    ducats = forms.IntegerField(required=True, min_value=0)

TERMS = (
    (1, _("1 year, 20%")),
    (2, _("2 years, 50%")),
)

class BorrowForm(forms.Form):
    ducats = forms.IntegerField(required=True, min_value=0, label=_("Ducats to borrow"))
    term = forms.ChoiceField(required=True, choices=TERMS, label=_("Term and interest"))

class RepayForm(forms.Form):
    pass

ASSASSINATION_COSTS = (
    (10, _("10d, 1 die")),
    (18, _("18d, 2 dice")),
    (25, _("25d, 3 dice")),
    (31, _("31d, 4 dice")),
    (36, _("36d, 5 dice")),
    (40, _("40d, 6 dice")),
    (43, _("43d, 7 dice")),
    (46, _("46d, 8 dice")),
    (48, _("48d, 9 dice")),
    (50, _("50d, 10 dice")),
)

def make_assassination_form(player):
    if player.game.version < 2:
        ducats_list = make_ducats_list(player.ducats, 12)
    else:
        ducats_list = ASSASSINATION_COSTS
    assassin_ids = player.assassin_set.values_list('target', flat=True)
    #targets_qs = Country.objects.filter(contender__player__game=player.game, id__in=assassin_ids).exclude(contender__player__eliminated=True, contender__player__user__isnull=True)
    targets_qs = Country.objects.filter(contender__player__game=player.game,
        contender__player__eliminated=False, id__in=assassin_ids)

    class AssassinationForm(forms.Form):
        ducats = forms.ChoiceField(required=True, choices=ducats_list, label=_("Ducats to pay"))
        target = forms.ModelChoiceField(required=True, queryset=targets_qs, label=_("Target country"))

    return AssassinationForm

class ErrorReportForm(forms.ModelForm):
    class Meta:
        model = machiavelli.ErrorReport
        fields = ('description',)
        exclude = ('user', 'game',)

    def save(self, user, game, commit=True):
        instance = super(ErrorReportForm, self).save(commit=False)
        instance.user = user
        instance.game = game
        if commit:
            instance.save()
        return instance
