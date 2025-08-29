from django.db import models
from django.utils import timezone

class Game(models.Model):
    SPORT_CHOICES = (
        ("FOOTBALL", "Football"),
        ("BASKETBALL", "Basketball"),
        ("CRICKET", "Cricket"),
    )

    STATUS_CHOICES = (
        ("SCHEDULED", "Scheduled"),
        ("LIVE", "Live"),
        ("FINISHED", "Finished")
    )

    sport = models.CharField(max_length=16, choices=SPORT_CHOICES, default="FOOTBALL")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="SCHEDULED")
    scheduled_time = models.DateTimeField(default=timezone.now)
    team1 = models.ForeignKey('Team', related_name='team1_games', on_delete=models.CASCADE)
    team2 = models.ForeignKey('Team', related_name='team2_games', on_delete=models.CASCADE)
    team1_score = models.PositiveIntegerField(default=0)
    team2_score = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.team1_score = max(0, self.team1_score or 0)
        self.team2_score = max(0, self.team2_score or 0)
        is_new = self._state.adding
        retval = super().save(*args, **kwargs)

        if is_new:
            for player in self.team1.players.all().union(self.team2.players.all()):
                PlayerStat.objects.get_or_create(game=self, player=player, team=player.team)

        return retval

class Football(Game):
    def __str__(self):
        return f"Football Match: {self.team1} vs {self.team2} at {self.scheduled_time}"

class Basketball(Game):
    def __str__(self):
        return f"Basketball Game: {self.team1} vs {self.team2} at {self.scheduled_time}"

class Cricket(Game):
    team1_deaths = models.PositiveIntegerField(default=0)
    team2_deaths = models.PositiveIntegerField(default=0)
    BATTING_SIDE_CHOICES = (("TEAM1", "Team 1"), ("TEAM2", "Team 2"))
    batting_side = models.CharField(max_length=6, choices=BATTING_SIDE_CHOICES, default="TEAM1")
    current_batsman = models.ForeignKey(
        'Player', related_name='current_batsman_in', null=True, blank=True, on_delete=models.SET_NULL
    )
    current_bowler = models.ForeignKey(
        'Player', related_name='current_bowler_in', null=True, blank=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return f"Cricket Match: {self.team1} vs {self.team2} at {self.scheduled_time}"

class Team(models.Model):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey('Player', related_name='teams_led', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

class Player(models.Model):
    name = models.CharField(max_length=100)
    last_updated = models.DateTimeField(auto_now=True)
    team = models.ForeignKey(Team, related_name='players', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class PlayerStat(models.Model):
    game = models.ForeignKey(Game, related_name='player_stats', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='game_stats', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='player_stats', on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
    runs = models.PositiveIntegerField(default=0)
    balls = models.PositiveIntegerField(default=0)
    wickets = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("game", "player")
        indexes = [
            models.Index(fields=["game"]),
            models.Index(fields=["player"]),
        ]

    def __str__(self):
        return f"{self.player.name} @ {self.game_id}: pts={self.points}, balls={self.balls}, wkts={self.wickets}"


class ScoreEvent(models.Model):
    SPORT_CHOICES = Game.SPORT_CHOICES
    game = models.ForeignKey(Game, related_name='score_events', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='score_events', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='score_events', on_delete=models.SET_NULL, null=True, blank=True)
    sport = models.CharField(max_length=16, choices=SPORT_CHOICES)
    points = models.PositiveIntegerField(default=0)
    runs = models.PositiveIntegerField(default=0)
    wicket = models.BooleanField(default=False)
    batting_side = models.CharField(max_length=6, choices=(("TEAM1", "Team 1"), ("TEAM2", "Team 2")), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["game", "created_at"]),
            models.Index(fields=["team", "created_at"]),
        ]

    def __str__(self):
        label = f"+{self.points}pt" if self.points else (f"+{self.runs} run" if self.runs else ("WICKET" if self.wicket else ""))
        return f"{self.sport} event: {self.team.name} {label} @ {self.created_at:%H:%M:%S}"
