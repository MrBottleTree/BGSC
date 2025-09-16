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
    # Game timing and flow
    actual_start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    winner = models.ForeignKey('Team', related_name='basketball_wins', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Current game state
    current_quarter = models.PositiveIntegerField(default=1)
    time_remaining_seconds = models.PositiveIntegerField(default=720)  # 12 minutes = 720 seconds
    possession_team = models.ForeignKey('Team', related_name='basketball_possessions', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quarter timing
    quarter1_finished_time = models.DateTimeField(null=True, blank=True)
    quarter2_finished_time = models.DateTimeField(null=True, blank=True)
    quarter3_finished_time = models.DateTimeField(null=True, blank=True)
    quarter4_finished_time = models.DateTimeField(null=True, blank=True)
    
    # Overtime tracking
    overtime_periods = models.PositiveIntegerField(default=0)
    overtime_time_added_seconds = models.PositiveIntegerField(default=0)
    
    # Team fouls (for bonus situations)
    team1_fouls_current_quarter = models.PositiveIntegerField(default=0)
    team2_fouls_current_quarter = models.PositiveIntegerField(default=0)
    
    # Active players (5 per team)
    team1_active_players = models.ManyToManyField(
        'Player', 
        related_name='team1_active_in_basketball', 
        blank=True,
        limit_choices_to={'team__team1_games__isnull': False}
    )
    team2_active_players = models.ManyToManyField(
        'Player', 
        related_name='team2_active_in_basketball', 
        blank=True,
        limit_choices_to={'team__team2_games__isnull': False}
    )
    
    def __str__(self):
        return f"Basketball Game: {self.team1} vs {self.team2} at {self.scheduled_time}"
        
    def get_team1_active_players(self):
        """Get list of currently active players for team1"""
        return list(self.team1_active_players.all())
    
    def get_team2_active_players(self):
        """Get list of currently active players for team2"""
        return list(self.team2_active_players.all())
    
    def is_player_active(self, player):
        """Check if a player is currently active in the game"""
        if player.team_id == self.team1_id:
            return self.team1_active_players.filter(id=player.id).exists()
        elif player.team_id == self.team2_id:
            return self.team2_active_players.filter(id=player.id).exists()
        return False

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
    logo = models.URLField(null=True, blank=True)
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


class BasketballShot(models.Model):
    SHOT_TYPE_CHOICES = (
        ('2PT', '2-Pointer'),
        ('3PT', '3-Pointer'),
        ('FT', 'Free Throw'),
    )
    
    SHOT_RESULT_CHOICES = (
        ('MADE', 'Made'),
        ('MISSED', 'Missed'),
        ('BLOCKED', 'Blocked'),
    )
    
    game = models.ForeignKey(Basketball, related_name='shots', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='basketball_shots', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='basketball_shots', on_delete=models.CASCADE)
    shot_type = models.CharField(max_length=3, choices=SHOT_TYPE_CHOICES)
    result = models.CharField(max_length=7, choices=SHOT_RESULT_CHOICES)
    points_scored = models.PositiveIntegerField(default=0)
    quarter = models.PositiveIntegerField()
    time_remaining_seconds = models.PositiveIntegerField()
    assist_player = models.ForeignKey(Player, related_name='basketball_assists', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['game', 'created_at']),
            models.Index(fields=['player', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.player.name} - {self.shot_type} {self.result} ({self.points_scored}pts) Q{self.quarter}"


class BasketballViolation(models.Model):
    VIOLATION_TYPE_CHOICES = (
        ('TRAVELING', 'Traveling'),
        ('DOUBLE_DRIBBLE', 'Double Dribble'),
        ('SHOT_CLOCK', 'Shot Clock Violation'),
        ('BACKCOURT', 'Backcourt Violation'),
        ('THREE_SECONDS', '3 Seconds in the Lane'),
        ('FIVE_SECONDS', '5 Second Violation'),
        ('EIGHT_SECONDS', '8 Second Violation'),
        ('GOALTENDING', 'Goaltending'),
        ('BASKET_INTERFERENCE', 'Basket Interference'),
        ('OUT_OF_BOUNDS', 'Out of Bounds'),
    )
    
    game = models.ForeignKey(Basketball, related_name='violations', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='basketball_violations', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='basketball_violations', on_delete=models.SET_NULL, null=True, blank=True)
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPE_CHOICES)
    quarter = models.PositiveIntegerField()
    time_remaining_seconds = models.PositiveIntegerField()
    points_awarded_to_opponent = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['game', 'created_at']),
            models.Index(fields=['team', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.team.name} - {self.violation_type} Q{self.quarter}"


class BasketballFoul(models.Model):
    FOUL_TYPE_CHOICES = (
        ('PERSONAL', 'Personal Foul'),
        ('TECHNICAL', 'Technical Foul'),
        ('FLAGRANT_1', 'Flagrant Foul 1'),
        ('FLAGRANT_2', 'Flagrant Foul 2'),
        ('OFFENSIVE', 'Offensive Foul'),
        ('DEFENSIVE', 'Defensive Foul'),
    )
    
    SHOT_AWARDED_CHOICES = (
        ('NONE', 'No Shots'),
        ('2_SHOTS', '2 Free Throws'),
        ('3_SHOTS', '3 Free Throws'),
        ('1_AND_1', 'One and One'),
    )
    
    game = models.ForeignKey(Basketball, related_name='fouls', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='basketball_fouls', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='basketball_fouls', on_delete=models.CASCADE)
    foul_type = models.CharField(max_length=12, choices=FOUL_TYPE_CHOICES)
    shots_awarded = models.CharField(max_length=7, choices=SHOT_AWARDED_CHOICES, default='NONE')
    points_scored_from_foul = models.PositiveIntegerField(default=0)
    quarter = models.PositiveIntegerField()
    time_remaining_seconds = models.PositiveIntegerField()
    fouled_player = models.ForeignKey(Player, related_name='basketball_fouls_received', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['game', 'created_at']),
            models.Index(fields=['player', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.player.name} - {self.foul_type} on {self.fouled_player.name if self.fouled_player else 'Unknown'} Q{self.quarter}"


class BasketballSubstitution(models.Model):
    game = models.ForeignKey(Basketball, related_name='substitutions', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='basketball_substitutions', on_delete=models.CASCADE)
    player_out = models.ForeignKey(Player, related_name='basketball_subs_out', on_delete=models.CASCADE)
    player_in = models.ForeignKey(Player, related_name='basketball_subs_in', on_delete=models.CASCADE)
    quarter = models.PositiveIntegerField()
    time_remaining_seconds = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['game', 'created_at']),
            models.Index(fields=['team', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.team.name}: {self.player_out.name} → {self.player_in.name} Q{self.quarter}"

class BasketballStop(models.Model):
    game = models.ForeignKey('Basketball', related_name='stops', on_delete=models.CASCADE)
    time_started = models.DateTimeField()
    time_ended = models.DateTimeField(null=True, blank=True)

    def duration(self):
        if self.time_ended:
            return (self.time_ended - self.time_started).total_seconds()
        return 0

    def __str__(self):
        return f"Stop: {self.time_started} - {self.time_ended}"  

class BasketballTimeout(models.Model):
    TIMEOUT_TYPE_CHOICES = (
        ('FULL', 'Full Timeout'),
        ('20_SECOND', '20 Second Timeout'),
        ('OFFICIAL', 'Official Timeout'),
    )
    
    game = models.ForeignKey(Basketball, related_name='timeouts', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, related_name='basketball_timeouts', on_delete=models.SET_NULL, null=True, blank=True)
    timeout_type = models.CharField(max_length=10, choices=TIMEOUT_TYPE_CHOICES)
    quarter = models.PositiveIntegerField()
    time_remaining_seconds = models.PositiveIntegerField()
    duration_seconds = models.PositiveIntegerField(default=60)  # Full timeout is usually 60 seconds
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['game', 'created_at']),
        ]
    
    def __str__(self):
        team_name = self.team.name if self.team else "Official"
        return f"{team_name} - {self.timeout_type} Q{self.quarter}"
