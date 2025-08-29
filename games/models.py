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
        ("FINAL", "Final"),
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

class Football(Game):
    def __str__(self):
        return f"Football Match: {self.team1} vs {self.team2} at {self.scheduled_time}"

class Basketball(Game):
    def __str__(self):
        return f"Basketball Game: {self.team1} vs {self.team2} at {self.scheduled_time}"

class Cricket(Game):
    team1_deaths = models.PositiveIntegerField(default=0)
    team2_deaths = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Cricket Match: {self.team1} vs {self.team2} at {self.scheduled_time}"

class Team(models.Model):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey('Player', related_name='teams_led', on_delete=models.SET_NULL, null=True, blank=True)

class Player(models.Model):
    name = models.CharField(max_length=100)
    last_updated = models.DateTimeField(auto_now=True)
    team = models.ForeignKey(Team, related_name='players', on_delete=models.CASCADE)


class PlayerStat(models.Model):
    game = models.ForeignKey(Game, related_name='player_stats', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='game_stats', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='player_stats', on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
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