from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import *
from django.utils import timezone
from datetime import datetime

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

def home(request):
    upcoming = Game.objects.filter(status="SCHEDULED").select_related("team1", "team2").order_by("scheduled_time")
    live_games = Game.objects.filter(status="LIVE").select_related("team1", "team2")

    live_context = []
    for g in live_games:
        item = {"game": g}
        if g.sport == "FOOTBALL":
            t1_top = (
                PlayerStat.objects.filter(game=g, team=g.team1).order_by("-points", "player__name").first()
            )
            t2_top = (
                PlayerStat.objects.filter(game=g, team=g.team2).order_by("-points", "player__name").first()
            )
            t1_last = (
                ScoreEvent.objects.filter(game=g, team=g.team1, sport="FOOTBALL", points__gt=0)
                .order_by("-created_at")
                .first()
            )
            t2_last = (
                ScoreEvent.objects.filter(game=g, team=g.team2, sport="FOOTBALL", points__gt=0)
                .order_by("-created_at")
                .first()
            )
            t1_last_pts = None
            t2_last_pts = None
            if t1_last and t1_last.player_id:
                ps = PlayerStat.objects.filter(game=g, player=t1_last.player).first()
                t1_last_pts = ps.points if ps else 0
            if t2_last and t2_last.player_id:
                ps = PlayerStat.objects.filter(game=g, player=t2_last.player).first()
                t2_last_pts = ps.points if ps else 0
            item.update(
                {
                    "type": "football",
                    "team1_score": g.team1_score,
                    "team2_score": g.team2_score,
                    "team1_top": t1_top,
                    "team2_top": t2_top,
                    "team1_last": t1_last,
                    "team2_last": t2_last,
                    "team1_last_pts": t1_last_pts,
                    "team2_last_pts": t2_last_pts,
                }
            )
        elif g.sport == "BASKETBALL":
            t1_players = PlayerStat.objects.filter(game=g, team=g.team1).select_related("player").order_by(
                "-points", "player__name"
            )
            t2_players = PlayerStat.objects.filter(game=g, team=g.team2).select_related("player").order_by(
                "-points", "player__name"
            )
            item.update(
                {
                    "type": "basketball",
                    "team1_score": g.team1_score,
                    "team2_score": g.team2_score,
                    "team1_players": t1_players,
                    "team2_players": t2_players,
                }
            )
        elif g.sport == "CRICKET":
            cg = Cricket.objects.get(pk=g.pk)
            batting_team = cg.team1 if cg.batting_side == "TEAM1" else cg.team2
            team_runs = g.team1_score if cg.batting_side == "TEAM1" else g.team2_score
            batsman_runs = None
            bowler_wkts = None
            if cg.current_batsman:
                ps = PlayerStat.objects.filter(game=g, player=cg.current_batsman).first()
                batsman_runs = ps.runs if ps else 0
            if cg.current_bowler:
                psb = PlayerStat.objects.filter(game=g, player=cg.current_bowler).first()
                bowler_wkts = psb.wickets if psb else 0
            item.update(
                {
                    "type": "cricket",
                    "batting_team": batting_team,
                    "team_runs": team_runs,
                    "batsman": cg.current_batsman,
                    "batsman_runs": batsman_runs,
                    "bowler": cg.current_bowler,
                    "bowler_wickets": bowler_wkts,
                }
            )
        live_context.append(item)

    return render(
        request,
        "games/home.html",
        {
            "upcoming": upcoming,
            "live_games": live_context,
        },
    )


@login_required(login_url='/login/')
def dashboard(request):
    live_games = Game.objects.filter(status="LIVE").select_related("team1", "team2").order_by("scheduled_time")
    scheduled = Game.objects.filter(status="SCHEDULED").select_related("team1", "team2").order_by("scheduled_time")
    finished = Game.objects.filter(status="FINISHED").select_related("team1", "team2").order_by("-scheduled_time")[:10]
    return render(request, "games/dashboard.html", {"live_games": live_games, "scheduled": scheduled, "finished": finished})


def _get_or_create_stat(game: Game, player: Player):
    return PlayerStat.objects.get_or_create(game=game, player=player, defaults={"team": player.team})[0]

@login_required(login_url='/login/')
def update_football(request, game_id: int):
    game = get_object_or_404(Football, pk=game_id)
    teams = [game.team1, game.team2]
    players = Player.objects.filter(team__in=teams).order_by("team__name", "name")

    if request.method == "POST":
        player_id = int(request.POST.get("player_id"))
        player = get_object_or_404(Player, pk=player_id)
        stat = _get_or_create_stat(game, player)
        stat.points += 1
        stat.save()
        if player.team_id == game.team1_id:
            game.team1_score += 1
        else:
            game.team2_score += 1
        game.save()
        ScoreEvent.objects.create(game=game, team=player.team, player=player, sport="FOOTBALL", points=1)
        return redirect("update_football", game_id=game.id)

    return render(request, "games/update_football.html", {"game": game, "players": players})


@login_required(login_url='/login/')
def update_basketball(request, game_id: int):
    game = get_object_or_404(Basketball, pk=game_id)
    teams = [game.team1, game.team2]
    players = Player.objects.filter(team__in=teams).order_by("team__name", "name")

    if request.method == "POST":
        player_id = int(request.POST.get("player_id"))
        points = int(request.POST.get("points", 2))
        points = points if points in (1, 2, 3) else 2
        player = get_object_or_404(Player, pk=player_id)
        stat = _get_or_create_stat(game, player)
        stat.points += points
        stat.save()
        if player.team_id == game.team1_id:
            game.team1_score += points
        else:
            game.team2_score += points
        game.save()
        ScoreEvent.objects.create(game=game, team=player.team, player=player, sport="BASKETBALL", points=points)
        return redirect("update_basketball", game_id=game.id)

    return render(request, "games/update_basketball.html", {"game": game, "players": players})

@login_required(login_url='/login/')
def update_cricket(request, game_id: int):
    game = get_object_or_404(Cricket, pk=game_id)
    teams = [game.team1, game.team2]
    players = Player.objects.filter(team__in=teams).order_by("team__name", "name")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "set_state":
            batting_side = request.POST.get("batting_side")
            batsman_id = request.POST.get("batsman_id")
            bowler_id = request.POST.get("bowler_id")
            if batting_side in ("TEAM1", "TEAM2"):
                game.batting_side = batting_side
            if "batsman_id" in request.POST:
                game.current_batsman = Player.objects.filter(pk=batsman_id).first() if batsman_id else None
            if "bowler_id" in request.POST:
                game.current_bowler = Player.objects.filter(pk=bowler_id).first() if bowler_id else None
            game.save()
        elif action == "runs":
            runs = int(request.POST.get("runs", 1))
            if game.current_batsman:
                stat = _get_or_create_stat(game, game.current_batsman)
                stat.runs += runs
                stat.balls += 1
                stat.save()
                if game.batting_side == "TEAM1":
                    game.team1_score += runs
                else:
                    game.team2_score += runs
                game.save()
                ScoreEvent.objects.create(
                    game=game,
                    team=game.current_batsman.team,
                    player=game.current_batsman,
                    sport="CRICKET",
                    runs=runs,
                    batting_side=game.batting_side,
                )
        elif action == "wicket":
            if game.current_bowler:
                st = _get_or_create_stat(game, game.current_bowler)
                st.wickets += 1
                st.save()
                if game.batting_side == "TEAM1":
                    game.team1_deaths += 1
                else:
                    game.team2_deaths += 1
                game.save()
                ScoreEvent.objects.create(
                    game=game,
                    team=game.current_bowler.team,
                    player=game.current_bowler,
                    sport="CRICKET",
                    wicket=True,
                    batting_side=game.batting_side,
                )
        return redirect("update_cricket", game_id=game.id)
    return render(
        request,
        "games/update_cricket.html",
        {"game": game, "players": players, "teams": teams, "nums": range(1, 7)},
    )


@login_required(login_url='/login/')
def add_game(request):
    teams = Team.objects.all().order_by("name")
    if request.method == "POST":
        sport = request.POST.get("sport")
        team1_id = request.POST.get("team1_id")
        team2_id = request.POST.get("team2_id")
        scheduled_str = request.POST.get("scheduled_at")
        t1 = Team.objects.filter(pk=team1_id).first()
        t2 = Team.objects.filter(pk=team2_id).first()
        # Parse scheduled datetime if provided (HTML datetime-local => YYYY-MM-DDTHH:MM)
        scheduled_dt = None
        if scheduled_str:
            try:
                # fromisoformat handles 'YYYY-MM-DDTHH:MM' and optional seconds
                scheduled_dt = datetime.fromisoformat(scheduled_str)
                if timezone.is_naive(scheduled_dt):
                    scheduled_dt = timezone.make_aware(scheduled_dt, timezone.get_current_timezone())
            except Exception:
                return render(request, "games/add_game.html", {"teams": teams, "error": "Invalid date/time format."})
        if sport in ("FOOTBALL", "BASKETBALL", "CRICKET") and t1 and t2 and t1.id != t2.id:
            if sport == "FOOTBALL":
                Football.objects.create(sport=sport, status="SCHEDULED", team1=t1, team2=t2, scheduled_time=scheduled_dt or timezone.now())
            elif sport == "BASKETBALL":
                Basketball.objects.create(sport=sport, status="SCHEDULED", team1=t1, team2=t2, scheduled_time=scheduled_dt or timezone.now())
            else:
                Cricket.objects.create(sport=sport, status="SCHEDULED", team1=t1, team2=t2, scheduled_time=scheduled_dt or timezone.now())
            return redirect("dashboard")
        # fallthrough re-render with error
        return render(request, "games/add_game.html", {"teams": teams, "error": "Please select valid inputs."})
    return render(request, "games/add_game.html", {"teams": teams})


@login_required(login_url='/login/')
def add_team(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if name:
            Team.objects.create(name=name)
            return redirect("dashboard")
        return render(request, "games/add_team.html", {"error": "Team name is required."})
    return render(request, "games/add_team.html")


@login_required(login_url='/login/')
def add_player(request):
    teams = Team.objects.all().order_by("name")
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        team_id = request.POST.get("team_id")
        team = Team.objects.filter(pk=team_id).first()
        if name and team:
            Player.objects.create(name=name, team=team)
            return redirect("add_player")
        return render(request, "games/add_player.html", {"teams": teams, "error": "Name and team required."})
    return render(request, "games/add_player.html", {"teams": teams})


@login_required(login_url='/login/')
@require_POST
def update_undo(request, game_id: int):
    game = get_object_or_404(Game, pk=game_id)
    team_id = request.POST.get("team_id")
    events = ScoreEvent.objects.filter(game=game)
    if team_id:
        events = events.filter(team_id=team_id)
    last = events.order_by("-created_at").first()
    if last:
        if last.sport in ("FOOTBALL", "BASKETBALL"):
            if last.player_id:
                ps = PlayerStat.objects.filter(game=game, player_id=last.player_id).first()
                if ps:
                    ps.points = max(0, ps.points - last.points)
                    ps.save()
            if last.team_id == game.team1_id:
                game.team1_score = max(0, game.team1_score - last.points)
            else:
                game.team2_score = max(0, game.team2_score - last.points)
            game.save()
        elif last.sport == "CRICKET":
            game = get_object_or_404(Cricket, pk=game.id)
            if last.runs and last.player_id:
                ps = PlayerStat.objects.filter(game=game, player_id=last.player_id).first()
                if ps:
                    ps.runs = max(0, ps.runs - last.runs)
                    ps.balls = max(0, ps.balls - 1)
                    ps.save()
                if last.batting_side == "TEAM1":
                    game.team1_score = max(0, game.team1_score - last.runs)
                else:
                    game.team2_score = max(0, game.team2_score - last.runs)
                game.save()
            elif last.wicket and last.player_id:
                ps = PlayerStat.objects.filter(game=game, player_id=last.player_id).first()
                if ps:
                    ps.wickets = max(0, ps.wickets - 1)
                    ps.save()
                if last.batting_side == "TEAM1":
                    game.team1_deaths = max(0, game.team1_deaths - 1)
                else:
                    game.team2_deaths = max(0, game.team2_deaths - 1)
                game.save()
        last.delete()
    if game.sport == "FOOTBALL":
        return redirect("update_football", game_id=game.id)
    if game.sport == "BASKETBALL":
        return redirect("update_basketball", game_id=game.id)
    return redirect("update_cricket", game_id=game.id)


@login_required(login_url='/login/')
def teams(request):
    teams = Team.objects.all().order_by("name").prefetch_related("players")
    return render(request, "games/teams.html", {"teams": teams})


@login_required(login_url='/login/')
def team_detail(request, team_id: int):
    team = get_object_or_404(Team.objects.prefetch_related("players"), pk=team_id)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if name:
            Player.objects.create(name=name, team=team)
            return redirect("team_detail", team_id=team.id)
    return render(request, "games/team_detail.html", {"team": team})


@login_required(login_url='/login/')
@require_POST
def set_game_status(request, game_id: int):
    game = get_object_or_404(Game, pk=game_id)
    status = request.POST.get("status")
    if status in ("SCHEDULED", "LIVE", "FINISHED"):
        game.status = status
        game.save()
    # Redirect back to dashboard
    return redirect("dashboard")


@login_required(login_url='/login/')
@require_POST
def remove_player(request, team_id: int, player_id: int):
    team = get_object_or_404(Team, pk=team_id)
    player = get_object_or_404(Player, pk=player_id, team=team)
    # Deleting the player removes their per-game stats; historical score events are kept with player set to null
    player.delete()
    return redirect("team_detail", team_id=team.id)
