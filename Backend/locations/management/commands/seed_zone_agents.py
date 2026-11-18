"""
Seed 8-12 verified delivery agents per zone, sized by the zone's pincode span.

Why pincode span: Zone has no area/population field, and the pincode range is
the zone's real locator. Widths are interpolated GLOBALLY (smallest zone ->
min agents, widest zone -> max agents) so bigger coverage areas get more
agents. A zone that is already at (or above) its target is left untouched, so
the command is safe to re-run and only ever tops zones up.

Capacity rationale: MAX_ACTIVE_LOAD in orders/signals.py is 5 concurrent tasks
per agent, so a zone at the 8-agent floor can absorb 40 simultaneous pickups
and the 12-agent ceiling 60.

Conventions (match the existing seed):
  - username  : "First Last" (spaces allowed at the DB level, as already used)
  - password  : the agent's first name, lowercased (e.g. "aarav")
  - profile   : city + zone set, is_delivery_agent + is_verified True
  - group     : DeliveryAgent (the engine's eligibility check)

Names are drawn from the unused "First Last" pool, so repeated runs keep
producing clean names instead of "Aarav Sharma 2/3/4" fallbacks. Pass
--fix-suffixed-names to rename agents created by an earlier run that already
picked up a numeric suffix (passwords are first-name based, so a rename that
keeps the first name leaves every login working).
"""
import re

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile
from locations.models import Zone

DEFAULT_MIN_AGENTS = 8
DEFAULT_MAX_AGENTS = 12

FIRST_NAMES = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Reyansh', 'Krishna',
    'Ishaan', 'Shaurya', 'Atharv', 'Rudra', 'Kabir', 'Aryan', 'Devansh',
    'Neel', 'Om', 'Yuvraj', 'Pranav', 'Rohan', 'Siddharth', 'Tanmay',
    'Manav', 'Harsh', 'Nikhil', 'Aniket', 'Gaurav', 'Rajat', 'Varun',
    'Kunal', 'Abhishek', 'Sameer', 'Farhan', 'Imran', 'Zaid', 'Aakash',
    'Deepak', 'Suresh', 'Mahesh', 'Ganesh', 'Vinod', 'Prakash', 'Rajesh',
    'Anil', 'Sunil', 'Manoj', 'Dinesh', 'Rakesh', 'Naveen', 'Pradeep',
    'Ashok', 'Vijay', 'Ajay', 'Sanjay', 'Ravi', 'Sachin', 'Yash',
    'Rishabh', 'Anish', 'Dhruv', 'Kartik', 'Bhavesh', 'Chirag', 'Faisal',
    'Girish', 'Harish', 'Jatin', 'Kamal', 'Lalit', 'Mohit', 'Nakul',
    'Omkar', 'Pawan', 'Prashant', 'Raghav', 'Sandeep', 'Shivam', 'Tarun',
    'Uday', 'Vishal', 'Yogesh',
]

LAST_NAMES = [
    'Sharma', 'Patel', 'Nair', 'Gupta', 'Singh', 'Das', 'Chatterjee',
    'Kapoor', 'Desai', 'Mehta', 'Joshi', 'Reddy', 'Iyer', 'Menon', 'Bose',
    'Banerjee', 'Chauhan', 'Verma', 'Yadav', 'Mishra', 'Pandey', 'Rao',
    'Kulkarni', 'Deshmukh', 'Jain', 'Agarwal', 'Bhat', 'Shetty', 'Pillai',
    'Khan',
]

SUFFIXED_USERNAME = re.compile(r' \d+$')


def agents_per_zone(width, min_width, max_width,
                    min_agents=DEFAULT_MIN_AGENTS, max_agents=DEFAULT_MAX_AGENTS):
    """Interpolate the zone's pincode span into the [min_agents, max_agents] band."""
    if max_width <= min_width:
        return (min_agents + max_agents) // 2
    ratio = (width - min_width) / (max_width - min_width)
    return min_agents + round(ratio * (max_agents - min_agents))


def available_names(used):
    """Group unused "First Last" combinations by first name, in a stable order."""
    by_first = {}
    for last in LAST_NAMES:
        for first in FIRST_NAMES:
            name = f'{first} {last}'
            if name not in used:
                by_first.setdefault(first, []).append(name)
    return by_first


class Command(BaseCommand):
    help = ('Seed 8-12 verified delivery agents per zone by default (size = '
            'pincode span). Passwords are the agents\' lowercase first names.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Print the plan without creating or renaming anything.')
        parser.add_argument('--min-agents', type=int, default=DEFAULT_MIN_AGENTS,
                            help=f'Agents for the smallest zone (default {DEFAULT_MIN_AGENTS}).')
        parser.add_argument('--max-agents', type=int, default=DEFAULT_MAX_AGENTS,
                            help=f'Agents for the widest zone (default {DEFAULT_MAX_AGENTS}).')
        parser.add_argument('--fix-suffixed-names', action='store_true',
                            help='Rename zoned agents with a trailing number (e.g. '
                                 '"Aarav Sharma 3") to an unused clean name.')

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_agents = max(1, options['min_agents'])
        max_agents = max(min_agents, options['max_agents'])

        zones = list(Zone.objects.filter(is_active=True).order_by('city', 'name'))
        if not zones:
            self.stdout.write(self.style.WARNING('No active zones - run seed_zones first.'))
            return

        widths = {z.id: z.pincode_to - z.pincode_from for z in zones}
        min_width, max_width = min(widths.values()), max(widths.values())

        agent_group, _ = Group.objects.get_or_create(name='DeliveryAgent')

        used = set(User.objects.values_list('username', flat=True))
        by_first = available_names(used)

        # --- optional cleanup of names created by an earlier run -----------
        renamed = 0
        if options['fix_suffixed_names']:
            suffixed = (User.objects
                        .filter(profile__zone__isnull=False,
                                profile__is_delivery_agent=True)
                        .order_by('id'))
            for user in suffixed:
                if not SUFFIXED_USERNAME.search(user.username):
                    continue
                first = user.first_name or user.username.split()[0]
                pool = by_first.get(first) or []
                if not pool:
                    self.stdout.write(self.style.WARNING(
                        f'  no clean name left for {first!r} - kept {user.username!r}'))
                    continue
                new_username = pool.pop(0)
                used.add(new_username)
                if not dry_run:
                    user.username = new_username
                    user.save(update_fields=['username'])
                renamed += 1

        created_total = 0
        name_cursor = 0
        per_zone = []

        # flat, deterministic draw order: one first name across every surname
        flatten = [n for first in FIRST_NAMES for n in by_first.get(first, [])]
        for zone in zones:
            target = agents_per_zone(widths[zone.id], min_width, max_width,
                                     min_agents, max_agents)
            existing = Profile.objects.filter(
                zone=zone, is_delivery_agent=True).count()
            deficit = max(0, target - existing)
            if deficit == 0:
                per_zone.append((zone, target, existing, 0))
                continue

            for _ in range(deficit):
                if name_cursor >= len(flatten):
                    raise CommandError(
                        'Ran out of clean "First Last" names - widen the pools '
                        'in this command before seeding more agents.')
                username = flatten[name_cursor]
                name_cursor += 1
                first, last = username.split(' ', 1)

                if not dry_run:
                    user = User.objects.create_user(
                        username=username,
                        password=first.lower(),   # password = first name
                        email=f'{first.lower()}.{last.lower().replace(" ", "")}'
                              f'@agent.vendorpulse.test',
                        first_name=first,
                        last_name=last,
                    )
                    user.groups.add(agent_group)
                    profile = user.profile
                    profile.city = zone.city
                    profile.zone = zone
                    profile.is_delivery_agent = True
                    profile.is_verified = True
                    profile.phone = '9000000000'
                    profile.save()
                created_total += 1

            per_zone.append((zone, target, existing, deficit))

        # --- report -------------------------------------------------------
        for zone, target, existing, created in per_zone:
            marker = 'skip' if created == 0 else f'+{created} agent(s)'
            self.stdout.write(
                f"  {zone.city:12} {zone.name:8} span={widths[zone.id]:4} "
                f"target={target} existing={existing}  {marker}")

        prefix = '[DRY RUN] ' if dry_run else ''
        if renamed:
            self.stdout.write(f"{prefix}Renamed {renamed} suffixed agent username(s).")
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(style(
            f"{prefix}Zone agents seeded: {created_total} created across "
            f"{len(zones)} zones (band {min_agents}-{max_agents}). "
            f"Passwords = lowercase first name (e.g. 'aarav')."))
