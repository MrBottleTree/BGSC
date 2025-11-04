from django.views.decorators.http import require_GET
from django.http import JsonResponse
import socket
# API endpoint to get all matches
@require_GET
def api_get_matches(request):
    games = Game.objects.select_related('team1', 'team2').all().order_by('-created_at')
    data = []
    for g in games:
        match_data = {
            'id': g.id,
            'sport': g.sport,
            'status': g.status,
            'scheduled_time': g.scheduled_time.isoformat() if g.scheduled_time else None,
            'team1': {
                'id': g.team1.id,
                'name': g.team1.name,
                'logo': g.team1.logo,
            } if g.team1 else None,
            'team2': {
                'id': g.team2.id,
                'name': g.team2.name,
                'logo': g.team2.logo,
            } if g.team2 else None,
            'team1_score': g.team1_score,
            'team2_score': g.team2_score,
            'winner': {
                'id': g.winner.id,
                'name': g.winner.name
            } if hasattr(g, 'winner') and g.winner else None,
            'created_at': g.created_at.isoformat() if g.created_at else None,
            'updated_at': g.updated_at.isoformat() if g.updated_at else None,
        }
        
        # Add basketball-specific data if it's a basketball game
        if g.sport == 'BASKETBALL':
            try:
                basketball_game = Basketball.objects.get(id=g.id)
                
                match_data['basketball_details'] = {
                    'current_quarter': basketball_game.current_quarter,
                    'team1_fouls': basketball_game.team1_fouls_current_quarter,
                    'team2_fouls': basketball_game.team2_fouls_current_quarter,
                    'active_players': {
                        'team1': [{'id': p.id, 'name': p.name} for p in basketball_game.get_team1_active_players()],
                        'team2': [{'id': p.id, 'name': p.name} for p in basketball_game.get_team2_active_players()],
                    }
                }
            except Basketball.DoesNotExist:
                pass
        
        data.append(match_data)
    return JsonResponse({'matches': data})
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count, Q
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import *
from django.utils import timezone
from datetime import datetime
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

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
            # Get enhanced basketball statistics - handle missing fields gracefully
            bg = None
            try:
                bg = Basketball.objects.get(pk=g.pk) if hasattr(g, 'basketball') else None
            except:
                # Database might not have new fields yet
                pass
            
            # Get top scorers for each team
            t1_players = PlayerStat.objects.filter(game=g, team=g.team1).select_related("player").order_by("-points", "player__name")
            t2_players = PlayerStat.objects.filter(game=g, team=g.team2).select_related("player").order_by("-points", "player__name")
            
            # Get recent events - handle missing tables gracefully
            recent_shots = []
            recent_fouls = []
            try:
                recent_shots = BasketballShot.objects.filter(game=g).select_related('player', 'team').order_by('-created_at')[:3]
                recent_fouls = BasketballFoul.objects.filter(game=g).select_related('player', 'team').order_by('-created_at')[:2]
            except:
                # New tables might not exist yet
                pass
            
            # Get team shooting stats - handle missing tables gracefully
            team1_fg_pct = 0
            team2_fg_pct = 0
            try:
                team1_shots = BasketballShot.objects.filter(game=g, team=g.team1)
                team2_shots = BasketballShot.objects.filter(game=g, team=g.team2)
                
                if team1_shots.exists():
                    team1_made = team1_shots.filter(result='MADE').count()
                    team1_attempted = team1_shots.count()
                    team1_fg_pct = (team1_made / team1_attempted * 100) if team1_attempted > 0 else 0
                
                if team2_shots.exists():
                    team2_made = team2_shots.filter(result='MADE').count()
                    team2_attempted = team2_shots.count()
                    team2_fg_pct = (team2_made / team2_attempted * 100) if team2_attempted > 0 else 0
            except:
                # New tables might not exist yet
                pass
            
            basketball_data = {
                "type": "basketball",
                "team1_score": g.team1_score,
                "team2_score": g.team2_score,
                "team1_players": t1_players,
                "team2_players": t2_players,
                "recent_shots": recent_shots,
                "recent_fouls": recent_fouls,
                "team1_fg_pct": round(team1_fg_pct, 1),
                "team2_fg_pct": round(team2_fg_pct, 1),
            }
            
            # Add game state if it's a Basketball instance with new fields
            if bg:
                try:
                    basketball_data.update({
                        "current_quarter": bg.current_quarter,
                        "time_remaining": bg.time_remaining_seconds,
                        "team1_fouls": bg.team1_fouls_current_quarter,
                        "team2_fouls": bg.team2_fouls_current_quarter,
                        "possession_team": bg.possession_team,
                        "overtime_periods": bg.overtime_periods,
                    })
                except AttributeError:
                    # New fields might not exist yet, provide defaults
                    basketball_data.update({
                        "current_quarter": 1,
                        "time_remaining": 720,
                        "team1_fouls": 0,
                        "team2_fouls": 0,
                        "possession_team": None,
                        "overtime_periods": 0,
                    })
            
            item.update(basketball_data)
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


def _get_basketball_game_state(game: Basketball):
    """Get current state of basketball game statistics"""
    try:
        return {
            'team1_fouls': game.team1_fouls_current_quarter,
            'team2_fouls': game.team2_fouls_current_quarter,
        }
    except AttributeError:
        # Handle case where new fields don't exist yet
        return {
            'team1_fouls': 0,
            'team2_fouls': 0,
        }


def _update_basketball_score(game: Basketball, team: Team, points: int, broadcast: bool = False):
    """Update basketball game score and optionally broadcast update"""
    if team.id == game.team1_id:
        game.team1_score += points
    else:
        game.team2_score += points
    game.save()
    if broadcast:
        _broadcast_game_update(game)


def _get_player_fouls(game: Basketball, player: Player):
    """Get current foul count for a player in the game"""
    try:
        return BasketballFoul.objects.filter(game=game, player=player).count()
    except:
        # Handle case where BasketballFoul table doesn't exist yet
        return 0


def _validate_active_player(game: Basketball, player: Player):
    """Validate that a player is currently active in the game"""
    try:
        return game.is_player_active(player)
    except:
        # If active player system isn't set up yet, allow all players
        return True


def _set_initial_active_players(game: Basketball, team1_player_ids, team2_player_ids):
    """Set the initial 5 active players for each team"""
    try:
        # Validate we have exactly 5 players per team
        if len(team1_player_ids) != 5:
            return False, f"Team {game.team1.name} must have exactly 5 active players (selected {len(team1_player_ids)})"
        if len(team2_player_ids) != 5:
            return False, f"Team {game.team2.name} must have exactly 5 active players (selected {len(team2_player_ids)})"
        
        # Get players and validate they belong to correct teams
        team1_players = Player.objects.filter(id__in=team1_player_ids, team=game.team1)
        team2_players = Player.objects.filter(id__in=team2_player_ids, team=game.team2)
        
        if team1_players.count() != 5:
            return False, f"All 5 selected players for {game.team1.name} must belong to the team"
        if team2_players.count() != 5:
            return False, f"All 5 selected players for {game.team2.name} must belong to the team"
        
        # Set active players
        game.team1_active_players.set(team1_players)
        game.team2_active_players.set(team2_players)
        
        return True, "Active players set successfully (5 per team)"
    except Exception as e:
        return False, f"Error setting active players: {str(e)}"


def _determine_basketball_winner(game: Basketball) -> None:
    """Determine and set the winner of a basketball game based on final scores"""
    if game.team1_score > game.team2_score:
        game.winner = game.team1
    elif game.team2_score > game.team1_score:
        game.winner = game.team2
    else:
        # It's a tie - winner remains null
        game.winner = None


def _broadcast_game_update(game: Game, kind: str = "score_update", extra: dict | None = None) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    
    data = {
        "kind": kind,
        "game_id": game.id,
        "sport": game.sport,
        "team1_score": game.team1_score,
        "team2_score": game.team2_score,
        "status": game.status,
    }
    
    # Add basketball-specific data if it's a basketball game
    if game.sport == "BASKETBALL":
        try:
            basketball_game = Basketball.objects.get(pk=game.id)
            data.update({
                "team1_fouls": basketball_game.team1_fouls_current_quarter,
                "team2_fouls": basketball_game.team2_fouls_current_quarter,
                "actual_start_time": basketball_game.actual_start_time.isoformat() if basketball_game.actual_start_time else None,
            })
            
        except Basketball.DoesNotExist:
            pass
    
    # Add winner information if game is finished
    if game.status == "FINISHED" and hasattr(game, 'winner') and game.winner:
        data.update({
            "winner": {
                "id": game.winner.id,
                "name": game.winner.name
            }
        })
    
    if extra:
        data.update(extra)
        
    async_to_sync(layer.group_send)(
        "live",
        {
            "type": "push_update",
            "data": data,
        },
    )

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
        _broadcast_game_update(game)
        return redirect("update_football", game_id=game.id)

    return render(request, "games/update_football.html", {"game": game, "players": players})


@login_required(login_url='/login/')
def update_basketball(request, game_id: int):
    game = get_object_or_404(Basketball, pk=game_id)
    teams = [game.team1, game.team2]
    players = Player.objects.filter(team__in=teams).order_by("team__name", "name")
    
    # Get game state and recent events - handle gracefully if fields don't exist
    try:
        game_state = _get_basketball_game_state(game)
        recent_shots = BasketballShot.objects.filter(game=game).order_by('-created_at')[:10]
        recent_fouls = BasketballFoul.objects.filter(game=game).select_related('player', 'team').order_by('-created_at')[:5]
        recent_subs = BasketballSubstitution.objects.filter(game=game).select_related('player_out', 'player_in', 'team').order_by('-created_at')[:5]
    except:
        # Fallback if new models don't exist yet
        game_state = {
            'current_quarter': 1,
            'time_remaining_seconds': 720,
            'overtime_periods': 0,
            'team1_fouls': 0,
            'team2_fouls': 0,
            'possession_team': None,
        }
        recent_shots = []
        recent_fouls = []
        recent_subs = []
    
    # Get player statistics
    team1_stats = PlayerStat.objects.filter(game=game, team=game.team1).select_related('player').order_by('-points')
    team2_stats = PlayerStat.objects.filter(game=game, team=game.team2).select_related('player').order_by('-points')
    
    # Get player foul counts - handle gracefully
    player_fouls = {}
    try:
        for player in players:
            player_fouls[player.id] = _get_player_fouls(game, player)
    except:
        # If BasketballFoul table doesn't exist yet
        for player in players:
            player_fouls[player.id] = 0

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "shot":
            player_id = int(request.POST.get("player_id"))
            shot_type = request.POST.get("shot_type", "2PT")  # 2PT, 3PT, FT
            result = request.POST.get("result", "MADE")  # MADE, MISSED, BLOCKED
            
            player = get_object_or_404(Player, pk=player_id)
            
            # Validate that the player is currently active
            if not _validate_active_player(game, player):
                # Redirect with error message (you might want to use Django messages framework)
                return redirect("update_basketball", game_id=game.id)
            
            # Determine points scored
            points_scored = 0
            if result == "MADE":
                if shot_type == "3PT":
                    points_scored = 3
                elif shot_type == "FT":
                    points_scored = 1
                else:  # 2PT
                    points_scored = 2
            
            # Create shot record - simplified
            shot = BasketballShot.objects.create(
                game=game,
                team=player.team,
                player=player,
                shot_type=shot_type,
                result=result,
                points_scored=points_scored,
                quarter=1,  # Default quarter since we're not tracking time
                time_remaining_seconds=0,  # Not tracking time
            )
            
            # Update player stats and game score
            if points_scored > 0:
                stat = _get_or_create_stat(game, player)
                stat.points += points_scored
                stat.save()
                _update_basketball_score(game, player.team, points_scored, broadcast=False)
                
                # Also create ScoreEvent for compatibility
                ScoreEvent.objects.create(
                    game=game, 
                    team=player.team, 
                    player=player, 
                    sport="BASKETBALL", 
                    points=points_scored
                )
            
            # Broadcast shot event
            shot_data = {
                "shot_id": shot.id,
                "player_name": player.name,
                "player_id": player.id,
                "team_name": player.team.name,
                "team_id": player.team.id,
                "shot_type": shot_type,
                "result": result,
                "points_scored": points_scored,
            }
            _broadcast_game_update(game, kind="shot", extra=shot_data)
        
        elif action == "player_foul":
            player_id = int(request.POST.get("player_id"))
            player = get_object_or_404(Player, pk=player_id)
            
            # Validate that player is active
            if not _validate_active_player(game, player):
                return redirect("update_basketball", game_id=game.id)
            
            # Create foul record for the specific player
            foul = BasketballFoul.objects.create(
                game=game,
                team=player.team,
                player=player,
                foul_type="PERSONAL",
                shots_awarded="NONE",
                quarter=game.current_quarter,
                time_remaining_seconds=game.time_remaining_seconds,
            )
            
            # Update team foul count
            if player.team.id == game.team1_id:
                game.team1_fouls_current_quarter += 1
            else:
                game.team2_fouls_current_quarter += 1
            game.save()
            
            # Broadcast foul event
            foul_data = {
                "foul_id": foul.id,
                "player_name": player.name,
                "player_id": player.id,
                "team_name": player.team.name,
                "team_id": player.team.id,
                "team1_fouls": game.team1_fouls_current_quarter,
                "team2_fouls": game.team2_fouls_current_quarter,
            }
            _broadcast_game_update(game, kind="player_foul", extra=foul_data)
        
        elif action == "foul":
            team_id = int(request.POST.get("team_id"))
            
            team = get_object_or_404(Team, pk=team_id)
            
            # Create foul record - simplified
            foul = BasketballFoul.objects.create(
                game=game,
                team=team,
                player=team.players.first(),  # Use first player as placeholder
                foul_type="PERSONAL",
                shots_awarded="NONE",
                quarter=game.current_quarter,
                time_remaining_seconds=game.time_remaining_seconds,
            )
            
            # Update team foul count
            if team.id == game.team1_id:
                game.team1_fouls_current_quarter += 1
            else:
                game.team2_fouls_current_quarter += 1
            game.save()
            
            # Broadcast foul event
            foul_data = {
                "foul_id": foul.id,
                "team_name": team.name,
                "team_id": team.id,
                "team1_fouls": game.team1_fouls_current_quarter,
                "team2_fouls": game.team2_fouls_current_quarter,
            }
            _broadcast_game_update(game, kind="foul", extra=foul_data)
        
        elif action == "substitution":
            team_id = int(request.POST.get("team_id"))
            player_out_id = int(request.POST.get("player_out_id"))
            player_in_id = int(request.POST.get("player_in_id"))
            
            team = get_object_or_404(Team, pk=team_id)
            player_out = get_object_or_404(Player, pk=player_out_id)
            player_in = get_object_or_404(Player, pk=player_in_id)
            
            # Validate that player_out is currently active
            if not _validate_active_player(game, player_out):
                return redirect("update_basketball", game_id=game.id)
            
            # Validate that player_in is not currently active
            if _validate_active_player(game, player_in):
                return redirect("update_basketball", game_id=game.id)
            
            # Update active players roster
            try:
                if team.id == game.team1_id:
                    game.team1_active_players.remove(player_out)
                    game.team1_active_players.add(player_in)
                elif team.id == game.team2_id:
                    game.team2_active_players.remove(player_out)
                    game.team2_active_players.add(player_in)
            except Exception:
                # Handle case where active player system isn't set up yet
                pass
            
            # Create substitution record - simplified
            substitution = BasketballSubstitution.objects.create(
                game=game,
                team=team,
                player_out=player_out,
                player_in=player_in,
                quarter=1,  # Default quarter
                time_remaining_seconds=0  # Not tracking time
            )
            
            # Broadcast substitution event
            sub_data = {
                "substitution_id": substitution.id,
                "team_name": team.name,
                "team_id": team.id,
                "player_out_name": player_out.name,
                "player_out_id": player_out.id,
                "player_in_name": player_in.name,
                "player_in_id": player_in.id,
            }
        
        elif action == "set_active_players":
            # Get selected players for each team
            team1_player_ids = request.POST.getlist("team1_players")
            team2_player_ids = request.POST.getlist("team2_players")
            
            # Convert to integers
            team1_player_ids = [int(pid) for pid in team1_player_ids if pid]
            team2_player_ids = [int(pid) for pid in team2_player_ids if pid]
            
            # Set the active players
            success, message = _set_initial_active_players(game, team1_player_ids, team2_player_ids)
            
            # Add message for user feedback
            from django.contrib import messages
            if success:
                messages.success(request, message)
                # Broadcast active players update
                active_data = {
                    "team1_active_players": [{"id": p.id, "name": p.name} for p in game.get_team1_active_players()],
                    "team2_active_players": [{"id": p.id, "name": p.name} for p in game.get_team2_active_players()],
                }
            else:
                messages.error(request, message)
        
        elif action == "undo_last_shot":
            # Find and delete the most recent shot
            try:
                last_shot = BasketballShot.objects.filter(game=game).order_by('-created_at').first()
                if last_shot:
                    # Reverse the points scored
                    if last_shot.result == "MADE":
                        points = 3 if last_shot.shot_type == "3PT" else (1 if last_shot.shot_type == "FT" else 2)
                        _update_basketball_score(game, last_shot.team, -points)
                        
                        # Update player stats
                        stat = _get_or_create_stat(game, last_shot.player)
                        stat.points = max(0, stat.points - points)
                        stat.save()
                    
                    # Broadcast undo shot event
                    undo_data = {
                        "shot_id": last_shot.id,
                        "player_name": last_shot.player.name,
                        "player_id": last_shot.player.id,
                        "team_name": last_shot.team.name,
                        "team_id": last_shot.team.id,
                        "shot_type": last_shot.shot_type,
                        "result": last_shot.result,
                        "points_reversed": points if last_shot.result == "MADE" else 0,
                    }
                    
                    last_shot.delete()
            except Exception:
                pass
        
        elif action == "undo_last_foul":
            # Find and delete the most recent foul
            try:
                last_foul = BasketballFoul.objects.filter(game=game).order_by('-created_at').first()
                if last_foul:
                    # Reverse team foul count
                    if last_foul.team == game.team1:
                        game.team1_fouls_current_quarter = max(0, game.team1_fouls_current_quarter - 1)
                    else:
                        game.team2_fouls_current_quarter = max(0, game.team2_fouls_current_quarter - 1)
                    game.save()
                    
                    # Broadcast undo foul event
                    undo_data = {
                        "foul_id": last_foul.id,
                        "player_name": last_foul.player.name,
                        "player_id": last_foul.player.id,
                        "team_name": last_foul.team.name,
                        "team_id": last_foul.team.id,
                        "foul_type": last_foul.foul_type,
                        "team1_fouls": game.team1_fouls_current_quarter,
                        "team2_fouls": game.team2_fouls_current_quarter,
                    }
                    
                    # Delete the foul record (this will decrease the individual player's foul count)
                    last_foul.delete()
            except Exception:
                pass
        
        elif action == "undo_last_substitution":
            # Find and reverse the most recent substitution
            try:
                last_sub = BasketballSubstitution.objects.filter(game=game).order_by('-created_at').first()
                if last_sub:
                    # Reverse the substitution by swapping the players back
                    if last_sub.team == game.team1:
                        active_players = list(game.team1_active_players.all())
                        if last_sub.player_in in active_players:
                            active_players.remove(last_sub.player_in)
                            active_players.append(last_sub.player_out)
                            game.team1_active_players.set(active_players)
                    else:
                        active_players = list(game.team2_active_players.all())
                        if last_sub.player_in in active_players:
                            active_players.remove(last_sub.player_in)
                            active_players.append(last_sub.player_out)
                            game.team2_active_players.set(active_players)
                    
                    # Broadcast undo substitution event
                    undo_data = {
                        "substitution_id": last_sub.id,
                        "team_name": last_sub.team.name,
                        "team_id": last_sub.team.id,
                        "player_out_name": last_sub.player_out.name,
                        "player_out_id": last_sub.player_out.id,
                        "player_in_name": last_sub.player_in.name,
                        "player_in_id": last_sub.player_in.id,
                        "team1_active_players": [{"id": p.id, "name": p.name} for p in game.get_team1_active_players()],
                        "team2_active_players": [{"id": p.id, "name": p.name} for p in game.get_team2_active_players()],
                    }
                    
                    last_sub.delete()
            except Exception:
                pass
        
        elif action == "next_quarter":
            # Move to next quarter and reset team fouls
            try:
                if game.current_quarter < 4:
                    game.current_quarter += 1
                    # Reset team fouls for new quarter
                    game.team1_fouls_current_quarter = 0
                    game.team2_fouls_current_quarter = 0
                    game.save()
                    
                    # Set quarter finished time for previous quarter
                    from django.utils import timezone
                    current_time = timezone.now()
                    if game.current_quarter == 2:
                        game.quarter1_finished_time = current_time
                    elif game.current_quarter == 3:
                        game.quarter2_finished_time = current_time
                    elif game.current_quarter == 4:
                        game.quarter3_finished_time = current_time
                    game.save()
                    
                    # Broadcast quarter change
                    quarter_data = {
                        "current_quarter": game.current_quarter,
                        "team1_fouls": game.team1_fouls_current_quarter,
                        "team2_fouls": game.team2_fouls_current_quarter,
                    }
                elif game.current_quarter == 4:
                    # Game finished
                    game.status = "FINISHED"
                    game.quarter4_finished_time = timezone.now()
                    
                    # Determine and set the winner
                    _determine_basketball_winner(game)
                    
                    game.save()
            except Exception:
                pass
        
        elif action == "end_game":
            # End the game immediately
            try:
                from django.utils import timezone
                game.status = "FINISHED"
                game.end_time = timezone.now()
                
                # Set quarter finished time if not already set
                current_time = timezone.now()
                if game.current_quarter == 1 and not game.quarter1_finished_time:
                    game.quarter1_finished_time = current_time
                elif game.current_quarter == 2 and not game.quarter2_finished_time:
                    game.quarter2_finished_time = current_time
                elif game.current_quarter == 3 and not game.quarter3_finished_time:
                    game.quarter3_finished_time = current_time
                elif game.current_quarter == 4 and not game.quarter4_finished_time:
                    game.quarter4_finished_time = current_time
                
                # Determine and set the winner
                _determine_basketball_winner(game)
                
                game.save()
                
                # Redirect to dashboard when game is ended
                return redirect("dashboard")
            except Exception:
                pass
        
        return redirect("update_basketball", game_id=game.id)

    context = {
        "game": game, 
        "players": players,
        "teams": teams,
        "game_state": game_state,
        "recent_shots": recent_shots,
        "recent_fouls": recent_fouls,
        "recent_subs": recent_subs,
        "team1_stats": team1_stats,
        "team2_stats": team2_stats,
        "player_fouls": player_fouls,
    }
    
    # Add active players data safely
    try:
        context.update({
            "team1_active_players": game.get_team1_active_players(),
            "team2_active_players": game.get_team2_active_players(),
        })
    except:
        # If active player system isn't set up yet
        context.update({
            "team1_active_players": [],
            "team2_active_players": [],
        })
    
    return render(request, "games/update_basketball.html", context)

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
        logo = request.POST.get("logo").strip() or None
        if name:
            Team.objects.create(name=name, logo=logo)
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
def delete_game(request, game_id: int):
    """Delete a game and all its associated data"""
    game = get_object_or_404(Game, pk=game_id)
    
    # Delete the game (cascade will handle related objects)
    game_info = f"{game.team1.name} vs {game.team2.name}"
    game.delete()
    
    return redirect("dashboard")


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
def remove_team(request, team_id: int):
    team = get_object_or_404(Team, pk=team_id)
    if request.method == "POST":
        team.delete()
        return redirect("teams")
    return render(request, "games/teams.html", {"team": team})


@login_required(login_url='/login/')
def team_detail(request, team_id: int):
    team = get_object_or_404(Team.objects.prefetch_related("players"), pk=team_id)
    if request.method == "POST":
        action = request.POST.get("action", "add_player")
        
        if action == "add_player":
            name = (request.POST.get("name") or "").strip()
            if name:
                Player.objects.create(name=name, team=team)
                return redirect("team_detail", team_id=team.id)
        
        elif action == "set_captain":
            captain_id = request.POST.get("captain_id")
            if captain_id:
                try:
                    captain = Player.objects.get(id=captain_id, team=team)
                    team.leader = captain
                    team.save()
                except Player.DoesNotExist:
                    pass
                return redirect("team_detail", team_id=team.id)
        
        elif action == "remove_captain":
            team.leader = None
            team.save()
            return redirect("team_detail", team_id=team.id)
    
    return render(request, "games/team_detail.html", {"team": team})


@login_required(login_url='/login/')
@require_POST
def set_game_status(request, game_id: int):
    game = get_object_or_404(Game, pk=game_id)
    # If basketball and marking LIVE, set actual_start_time
    is_basketball = hasattr(game, 'basketball') or game.sport == 'BASKETBALL'
    status = request.POST.get("status")
    if status in ("SCHEDULED", "LIVE", "FINISHED"):
        game.status = status
        # If basketball and marking LIVE, set actual_start_time
        if is_basketball and status == "LIVE":
            # Get Basketball instance
            try:
                basketball_game = Basketball.objects.get(pk=game.id)
                if not basketball_game.actual_start_time:
                    from django.utils import timezone

                    basketball_game.actual_start_time = timezone.now()
                    basketball_game.save()
            except Basketball.DoesNotExist:
                pass
        game.save()
    return redirect("dashboard")


@login_required(login_url='/login/')
@require_POST
def remove_player(request, team_id: int, player_id: int):
    team = get_object_or_404(Team, pk=team_id)
    player = get_object_or_404(Player, pk=player_id, team=team)
    
    # If this player is the team captain, remove them as captain first
    if team.leader and team.leader.id == player.id:
        team.leader = None
        team.save()
    
    player.delete()
    return redirect("team_detail", team_id=team.id)


@login_required(login_url='/login/')
def swap_players(request):
    """View to handle player swapping between teams"""
    teams = Team.objects.all().prefetch_related("players").order_by("name")
    
    if request.method == "POST":
        player1_id = request.POST.get("player1_id")
        player2_id = request.POST.get("player2_id")
        
        if not player1_id or not player2_id:
            return render(request, "games/swap_players.html", {
                "teams": teams,
                "error": "Please select both players to swap."
            })
        
        if player1_id == player2_id:
            return render(request, "games/swap_players.html", {
                "teams": teams,
                "error": "Cannot swap a player with themselves."
            })
        
        try:
            player1 = get_object_or_404(Player, pk=player1_id)
            player2 = get_object_or_404(Player, pk=player2_id)
            
            # Check if players are from different teams
            if player1.team.id == player2.team.id:
                return render(request, "games/swap_players.html", {
                    "teams": teams,
                    "error": "Cannot swap players from the same team."
                })
            
            # Store original teams for captain checks
            team1 = player1.team
            team2 = player2.team
            
            # Handle captaincy - if either player is a captain, remove captaincy first
            captain_changes = []
            if team1.leader and team1.leader.id == player1.id:
                team1.leader = None
                captain_changes.append(f"{player1.name} was removed as captain of {team1.name}")
            
            if team2.leader and team2.leader.id == player2.id:
                team2.leader = None
                captain_changes.append(f"{player2.name} was removed as captain of {team2.name}")
            
            # Perform the swap
            player1.team = team2
            player2.team = team1
            
            # Save all changes
            player1.save()
            player2.save()
            team1.save()
            team2.save()
            
            success_message = f"Successfully swapped {player1.name} and {player2.name} between teams."
            if captain_changes:
                success_message += " " + " ".join(captain_changes)
            
            return render(request, "games/swap_players.html", {
                "teams": teams,
                "success": success_message
            })
            
        except Exception as e:
            return render(request, "games/swap_players.html", {
                "teams": teams,
                "error": f"Error occurred during swap: {str(e)}"
            })
    
    return render(request, "games/swap_players.html", {"teams": teams})


@login_required(login_url='/login/')
def basketball_game_stats(request, game_id: int):
    """Detailed basketball game statistics view"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    # Get all shots
    shots = BasketballShot.objects.filter(game=game).select_related('player', 'team', 'assist_player').order_by('-created_at')
    
    # Get shooting statistics by team
    team1_shots = shots.filter(team=game.team1)
    team2_shots = shots.filter(team=game.team2)
    
    # Calculate shooting percentages
    def get_shooting_stats(team_shots):
        total_shots = team_shots.count()
        made_shots = team_shots.filter(result='MADE').count()
        three_pointers_made = team_shots.filter(shot_type='3PT', result='MADE').count()
        three_pointers_attempted = team_shots.filter(shot_type='3PT').count()
        free_throws_made = team_shots.filter(shot_type='FT', result='MADE').count()
        free_throws_attempted = team_shots.filter(shot_type='FT').count()
        
        return {
            'total_shots': total_shots,
            'made_shots': made_shots,
            'fg_percentage': (made_shots / total_shots * 100) if total_shots > 0 else 0,
            'three_pointers_made': three_pointers_made,
            'three_pointers_attempted': three_pointers_attempted,
            'three_pt_percentage': (three_pointers_made / three_pointers_attempted * 100) if three_pointers_attempted > 0 else 0,
            'free_throws_made': free_throws_made,
            'free_throws_attempted': free_throws_attempted,
            'ft_percentage': (free_throws_made / free_throws_attempted * 100) if free_throws_attempted > 0 else 0,
        }
    
    team1_shooting = get_shooting_stats(team1_shots)
    team2_shooting = get_shooting_stats(team2_shots)
    
    # Get fouls and violations
    fouls = BasketballFoul.objects.filter(game=game).select_related('player', 'team', 'fouled_player').order_by('-created_at')
    violations = BasketballViolation.objects.filter(game=game).select_related('team', 'player').order_by('-created_at')
    substitutions = BasketballSubstitution.objects.filter(game=game).select_related('team', 'player_out', 'player_in').order_by('-created_at')
    timeouts = BasketballTimeout.objects.filter(game=game).select_related('team').order_by('-created_at')
    
    # Player statistics
    team1_player_stats = PlayerStat.objects.filter(game=game, team=game.team1).select_related('player').order_by('-points')
    team2_player_stats = PlayerStat.objects.filter(game=game, team=game.team2).select_related('player').order_by('-points')
    
    # Add additional stats for each player
    for stat in list(team1_player_stats) + list(team2_player_stats):
        player_shots = shots.filter(player=stat.player)
        player_fouls = fouls.filter(player=stat.player).count()
        assists = shots.filter(assist_player=stat.player).count()
        
        stat.shots_made = player_shots.filter(result='MADE').count()
        stat.shots_attempted = player_shots.count()
        stat.three_pointers_made = player_shots.filter(shot_type='3PT', result='MADE').count()
        stat.free_throws_made = player_shots.filter(shot_type='FT', result='MADE').count()
        stat.fouls = player_fouls
        stat.assists = assists
    
    context = {
        'game': game,
        'shots': shots,
        'team1_shooting': team1_shooting,
        'team2_shooting': team2_shooting,
        'fouls': fouls,
        'violations': violations,
        'substitutions': substitutions,
        'timeouts': timeouts,
        'team1_player_stats': team1_player_stats,
        'team2_player_stats': team2_player_stats,
    }
    
    return render(request, "games/basketball_stats.html", context)


@login_required(login_url='/login/')
@require_POST
def start_basketball_game(request, game_id: int):
    """Start a basketball game and set initial state"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    if game.status == "SCHEDULED":
        game.status = "LIVE"
        game.actual_start_time = timezone.now()
        game.current_quarter = 1
        game.time_remaining_seconds = 720  # 12 minutes
        game.team1_fouls_current_quarter = 0
        game.team2_fouls_current_quarter = 0
        game.save()
    
    return redirect("update_basketball", game_id=game.id)


@login_required(login_url='/login/')
@require_POST
def end_basketball_game(request, game_id: int):
    """End a basketball game and set winner"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    if game.status == "LIVE":
        game.status = "FINISHED"
        game.end_time = timezone.now()
        
        # Determine and set the winner
        _determine_basketball_winner(game)
        
        game.save()
    
    return redirect("dashboard")


@login_required(login_url='/login/')
def basketball_api_stats(request, game_id: int):
    """API endpoint for real-time basketball statistics"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    # Get latest statistics
    latest_shots = BasketballShot.objects.filter(game=game).order_by('-created_at')[:5]
    latest_events = []
    
    for shot in latest_shots:
        latest_events.append({
            'type': 'shot',
            'player': shot.player.name,
            'team': shot.team.name,
            'description': f"{shot.player.name} - {shot.get_shot_type_display()} {shot.get_result_display()}",
            'points': shot.points_scored,
            'time': shot.created_at.isoformat()
        })
    
    # Get latest fouls
    latest_fouls = BasketballFoul.objects.filter(game=game).order_by('-created_at')[:3]
    for foul in latest_fouls:
        latest_events.append({
            'type': 'foul',
            'player': foul.player.name,
            'team': foul.team.name,
            'description': f"{foul.player.name} - {foul.get_foul_type_display()}",
            'time': foul.created_at.isoformat()
        })
    
    # Sort events by time
    latest_events.sort(key=lambda x: x['time'], reverse=True)
    
    data = {
        'game_id': game.id,
        'quarter': game.current_quarter,
        'team1_score': game.team1_score,
        'team2_score': game.team2_score,
        'team1_fouls': game.team1_fouls_current_quarter,
        'team2_fouls': game.team2_fouls_current_quarter,
        'latest_events': latest_events[:10]
    }
    
    return JsonResponse(data)


@require_GET
def api_match_detail(request, match_id: int):
    """API endpoint to get comprehensive match details including all events"""
    game = get_object_or_404(Game, pk=match_id)
    
    # Basic match data
    match_data = {
        'id': game.id,
        'sport': game.sport,
        'status': game.status,
        'scheduled_time': game.scheduled_time.isoformat() if game.scheduled_time else None,
        'team1': {
            'id': game.team1.id,
            'name': game.team1.name,
            'logo': game.team1.logo,
        },
        'team2': {
            'id': game.team2.id,
            'name': game.team2.name,
            'logo': game.team2.logo,
        },
        'team1_score': game.team1_score,
        'team2_score': game.team2_score,
        'winner': {
            'id': game.winner.id,
            'name': game.winner.name
        } if hasattr(game, 'winner') and game.winner else None,
        'created_at': game.created_at.isoformat(),
        'updated_at': game.updated_at.isoformat(),
        'events': []
    }
    
    if game.sport == 'BASKETBALL':
        try:
            basketball_game = Basketball.objects.get(id=game.id)
            
            # Basketball-specific details
            match_data['basketball_details'] = {
                'current_quarter': basketball_game.current_quarter,
                'team1_fouls_current_quarter': basketball_game.team1_fouls_current_quarter,
                'team2_fouls_current_quarter': basketball_game.team2_fouls_current_quarter,
                'winner': {
                    'id': basketball_game.winner.id,
                    'name': basketball_game.winner.name,
                } if basketball_game.winner else None,
                'active_players': {
                    'team1': [{'id': p.id, 'name': p.name} for p in basketball_game.get_team1_active_players()],
                    'team2': [{'id': p.id, 'name': p.name} for p in basketball_game.get_team2_active_players()],
                },
                'quarters': [
                    {
                        'quarter': 1,
                        'team1_score': getattr(basketball_game, 'quarter1_team1_score', None),
                        'team2_score': getattr(basketball_game, 'quarter1_team2_score', None),
                        'team1_fouls': getattr(basketball_game, 'quarter1_team1_fouls', None),
                        'team2_fouls': getattr(basketball_game, 'quarter1_team2_fouls', None),
                        'finished_time': getattr(basketball_game, 'quarter1_finished_time', None).isoformat() if getattr(basketball_game, 'quarter1_finished_time', None) else None
                    },
                    {
                        'quarter': 2,
                        'team1_score': getattr(basketball_game, 'quarter2_team1_score', None),
                        'team2_score': getattr(basketball_game, 'quarter2_team2_score', None),
                        'team1_fouls': getattr(basketball_game, 'quarter2_team1_fouls', None),
                        'team2_fouls': getattr(basketball_game, 'quarter2_team2_fouls', None),
                        'finished_time': getattr(basketball_game, 'quarter2_finished_time', None).isoformat() if getattr(basketball_game, 'quarter2_finished_time', None) else None
                    },
                    {
                        'quarter': 3,
                        'team1_score': getattr(basketball_game, 'quarter3_team1_score', None),
                        'team2_score': getattr(basketball_game, 'quarter3_team2_score', None),
                        'team1_fouls': getattr(basketball_game, 'quarter3_team1_fouls', None),
                        'team2_fouls': getattr(basketball_game, 'quarter3_team2_fouls', None),
                        'finished_time': getattr(basketball_game, 'quarter3_finished_time', None).isoformat() if getattr(basketball_game, 'quarter3_finished_time', None) else None
                    },
                    {
                        'quarter': 4,
                        'team1_score': getattr(basketball_game, 'quarter4_team1_score', None),
                        'team2_score': getattr(basketball_game, 'quarter4_team2_score', None),
                        'team1_fouls': getattr(basketball_game, 'quarter4_team1_fouls', None),
                        'team2_fouls': getattr(basketball_game, 'quarter4_team2_fouls', None),
                        'finished_time': getattr(basketball_game, 'quarter4_finished_time', None).isoformat() if getattr(basketball_game, 'quarter4_finished_time', None) else None
                    }
                ]
            }
            
            # Get all basketball events
            events = []
            
            # Shots
            shots = BasketballShot.objects.filter(game=basketball_game).select_related('player', 'team', 'assist_player').order_by('-created_at')
            for shot in shots:
                events.append({
                    'type': 'shot',
                    'id': shot.id,
                    'timestamp': shot.created_at.isoformat(),
                    'quarter': shot.quarter,
                    'team': {'id': shot.team.id, 'name': shot.team.name},
                    'player': {'id': shot.player.id, 'name': shot.player.name},
                    'shot_type': shot.shot_type,
                    'shot_type_display': shot.get_shot_type_display(),
                    'points_scored': shot.points_scored,
                })
            
            # Fouls
            fouls = BasketballFoul.objects.filter(game=basketball_game).select_related('player', 'team', 'fouled_player').order_by('-created_at')
            for foul in fouls:
                events.append({
                    'type': 'foul',
                    'id': foul.id,
                    'timestamp': foul.created_at.isoformat(),
                    'quarter': foul.quarter,
                    'team': {'id': foul.team.id, 'name': foul.team.name},
                    'player': {'id': foul.player.id, 'name': foul.player.name},
                })
            
            # Substitutions
            substitutions = BasketballSubstitution.objects.filter(game=basketball_game).select_related('team', 'player_out', 'player_in').order_by('-created_at')
            for sub in substitutions:
                events.append({
                    'type': 'substitution',
                    'id': sub.id,
                    'timestamp': sub.created_at.isoformat(),
                    'quarter': sub.quarter,
                    'team': {'id': sub.team.id, 'name': sub.team.name},
                    'player_out': {'id': sub.player_out.id, 'name': sub.player_out.name},
                    'player_in': {'id': sub.player_in.id, 'name': sub.player_in.name},
                })
            
            # Sort all events by timestamp (most recent first)
            events.sort(key=lambda x: x['timestamp'], reverse=True)
            match_data['events'] = events
            
            # Player statistics
            team1_stats = []
            team2_stats = []
            
            for stat in PlayerStat.objects.filter(game=game, team=game.team1).select_related('player'):
                player_shots = shots.filter(player=stat.player)
                player_fouls = fouls.filter(player=stat.player).count()
                team1_stats.append({
                    'player': {'id': stat.player.id, 'name': stat.player.name},
                    'points': stat.points,
                    'shots_made': player_shots.filter(result='MADE').count(),
                    'three_pointers_made': player_shots.filter(shot_type='3PT', result='MADE').count(),
                    'free_throws_made': player_shots.filter(shot_type='FT', result='MADE').count(),
                    'fouls': player_fouls,
                })
            
            for stat in PlayerStat.objects.filter(game=game, team=game.team2).select_related('player'):
                player_shots = shots.filter(player=stat.player)
                player_fouls = fouls.filter(player=stat.player).count()
                team2_stats.append({
                    'player': {'id': stat.player.id, 'name': stat.player.name},
                    'points': stat.points,
                    'shots_made': player_shots.filter(result='MADE').count(),
                    'three_pointers_made': player_shots.filter(shot_type='3PT', result='MADE').count(),
                    'free_throws_made': player_shots.filter(shot_type='FT', result='MADE').count(),
                    'fouls': player_fouls,
                })
            
            match_data['player_statistics'] = {
                'team1': team1_stats,
                'team2': team2_stats,
            }
            
        except Basketball.DoesNotExist:
            pass
    
    elif game.sport == 'FOOTBALL':
        # Add football-specific events if needed
        score_events = ScoreEvent.objects.filter(game=game, sport='FOOTBALL').select_related('team', 'player').order_by('-created_at')
        events = []
        for event in score_events:
            events.append({
                'type': 'goal',
                'timestamp': event.created_at.isoformat(),
                'team': {'id': event.team.id, 'name': event.team.name},
                'player': {
                    'id': event.player.id,
                    'name': event.player.name
                } if event.player else None,
                'points': event.points,
            })
        match_data['events'] = events
    
    elif game.sport == 'CRICKET':
        # Add cricket-specific events if needed
        try:
            cricket_game = Cricket.objects.get(id=game.id)
            match_data['cricket_details'] = {
                'team1_deaths': cricket_game.team1_deaths,
                'team2_deaths': cricket_game.team2_deaths,
                'batting_side': cricket_game.batting_side,
                'current_batsman': {
                    'id': cricket_game.current_batsman.id,
                    'name': cricket_game.current_batsman.name,
                } if cricket_game.current_batsman else None,
                'current_bowler': {
                    'id': cricket_game.current_bowler.id,
                    'name': cricket_game.current_bowler.name,
                } if cricket_game.current_bowler else None,
            }
        except Cricket.DoesNotExist:
            pass
    
    return JsonResponse(match_data)

@require_GET
def api_local_ip(request):
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = None
    return JsonResponse({'local_ip': local_ip})


@require_GET
def api_basketball_games(request):
    """API endpoint to get all basketball games with simplified data"""
    games = Basketball.objects.select_related('team1', 'team2').all().order_by('-created_at')
    data = []
    for game in games:
        data.append({
            'id': game.id,
            'status': game.status,
            'scheduled_time': game.scheduled_time.isoformat() if game.scheduled_time else None,
            'actual_start_time': game.actual_start_time.isoformat() if game.actual_start_time else None,
            'team1': {
                'id': game.team1.id,
                'name': game.team1.name,
                'logo': game.team1.logo,
            },
            'team2': {
                'id': game.team2.id,
                'name': game.team2.name,
                'logo': game.team2.logo,
            },
            'team1_score': game.team1_score,
            'team2_score': game.team2_score,
            'current_quarter': game.current_quarter,
            'team1_fouls': game.team1_fouls_current_quarter,
            'team2_fouls': game.team2_fouls_current_quarter,
            'winner': {
                'id': game.winner.id,
                'name': game.winner.name,
            } if game.winner else None,
            'active_players': {
                'team1': [{'id': p.id, 'name': p.name} for p in game.get_team1_active_players()],
                'team2': [{'id': p.id, 'name': p.name} for p in game.get_team2_active_players()],
            },
            'created_at': game.created_at.isoformat(),
            'updated_at': game.updated_at.isoformat(),
        })
    return JsonResponse({'basketball_games': data})


@require_GET
def api_basketball_game_events(request, game_id: int):
    """API endpoint to get all events for a specific basketball game"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    events = []
    
    # Shots
    shots = BasketballShot.objects.filter(game=game).select_related('player', 'team', 'assist_player').order_by('-created_at')
    for shot in shots:
        events.append({
            'type': 'shot',
            'id': shot.id,
            'timestamp': shot.created_at.isoformat(),
            'quarter': shot.quarter,
            'team': {'id': shot.team.id, 'name': shot.team.name},
            'player': {'id': shot.player.id, 'name': shot.player.name},
            'shot_type': shot.shot_type,
            'result': shot.result,
            'points_scored': shot.points_scored,
            'assist_player': {
                'id': shot.assist_player.id,
                'name': shot.assist_player.name
            } if shot.assist_player else None,
        })
    
    # Fouls
    fouls = BasketballFoul.objects.filter(game=game).select_related('player', 'team', 'fouled_player').order_by('-created_at')
    for foul in fouls:
        events.append({
            'type': 'foul',
            'id': foul.id,
            'timestamp': foul.created_at.isoformat(),
            'quarter': foul.quarter,
            'team': {'id': foul.team.id, 'name': foul.team.name},
            'player': {'id': foul.player.id, 'name': foul.player.name},
            'foul_type': foul.foul_type,
            'fouled_player': {
                'id': foul.fouled_player.id,
                'name': foul.fouled_player.name
            } if foul.fouled_player else None,
        })
    
    # Substitutions
    substitutions = BasketballSubstitution.objects.filter(game=game).select_related('team', 'player_out', 'player_in').order_by('-created_at')
    for sub in substitutions:
        events.append({
            'type': 'substitution',
            'id': sub.id,
            'timestamp': sub.created_at.isoformat(),
            'quarter': sub.quarter,
            'team': {'id': sub.team.id, 'name': sub.team.name},
            'player_out': {'id': sub.player_out.id, 'name': sub.player_out.name},
            'player_in': {'id': sub.player_in.id, 'name': sub.player_in.name},
        })
    
    # Sort events by timestamp (most recent first)
    events.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return JsonResponse({
        'game_id': game.id,
        'events': events
    })


@require_GET
def api_basketball_player_stats(request, game_id: int):
    """API endpoint to get player statistics for a basketball game"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    # Get all shots and fouls for stats calculation
    shots = BasketballShot.objects.filter(game=game).select_related('player', 'team', 'assist_player')
    fouls = BasketballFoul.objects.filter(game=game).select_related('player')
    
    team1_stats = []
    team2_stats = []
    
    # Team 1 stats
    for stat in PlayerStat.objects.filter(game=game, team=game.team1).select_related('player'):
        player_shots = shots.filter(player=stat.player)
        player_fouls_count = fouls.filter(player=stat.player).count()
        
        team1_stats.append({
            'player': {'id': stat.player.id, 'name': stat.player.name},
            'points': stat.points,
            'shots_made': player_shots.filter(result='MADE').count(),
            'shots_attempted': player_shots.count(),
            'three_pointers_made': player_shots.filter(shot_type='3PT', result='MADE').count(),
            'three_pointers_attempted': player_shots.filter(shot_type='3PT').count(),
            'free_throws_made': player_shots.filter(shot_type='FT', result='MADE').count(),
            'free_throws_attempted': player_shots.filter(shot_type='FT').count(),
            'fouls': player_fouls_count,
            'assists': shots.filter(assist_player=stat.player).count(),
        })
    
    # Team 2 stats
    for stat in PlayerStat.objects.filter(game=game, team=game.team2).select_related('player'):
        player_shots = shots.filter(player=stat.player)
        player_fouls_count = fouls.filter(player=stat.player).count()
        
        team2_stats.append({
            'player': {'id': stat.player.id, 'name': stat.player.name},
            'points': stat.points,
            'shots_made': player_shots.filter(result='MADE').count(),
            'shots_attempted': player_shots.count(),
            'three_pointers_made': player_shots.filter(shot_type='3PT', result='MADE').count(),
            'three_pointers_attempted': player_shots.filter(shot_type='3PT').count(),
            'free_throws_made': player_shots.filter(shot_type='FT', result='MADE').count(),
            'free_throws_attempted': player_shots.filter(shot_type='FT').count(),
            'fouls': player_fouls_count,
            'assists': shots.filter(assist_player=stat.player).count(),
        })
    
    return JsonResponse({
        'game_id': game.id,
        'team1_stats': team1_stats,
        'team2_stats': team2_stats,
    })


@require_GET  
def api_basketball_live_update(request, game_id: int):
    """API endpoint for real-time basketball game updates - simplified"""
    game = get_object_or_404(Basketball, pk=game_id)
    
    # Get latest events (last 5)
    latest_shots = BasketballShot.objects.filter(game=game).order_by('-created_at')[:3]
    latest_fouls = BasketballFoul.objects.filter(game=game).order_by('-created_at')[:2]
    
    recent_events = []
    
    for shot in latest_shots:
        recent_events.append({
            'type': 'shot',
            'timestamp': shot.created_at.isoformat(),
            'player': shot.player.name,
            'team': shot.team.name,
            'description': f"{shot.player.name} - {shot.get_shot_type_display()} {shot.get_result_display()}",
            'points': shot.points_scored,
        })
    
    for foul in latest_fouls:
        recent_events.append({
            'type': 'foul',
            'timestamp': foul.created_at.isoformat(),
            'player': foul.player.name,
            'team': foul.team.name,
            'description': f"{foul.player.name} - {foul.get_foul_type_display()}",
        })
    
    # Sort by timestamp
    recent_events.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return JsonResponse({
        'game_id': game.id,
        'status': game.status,
        'quarter': game.current_quarter,
        'team1_score': game.team1_score,
        'team2_score': game.team2_score,
        'team1_fouls': game.team1_fouls_current_quarter,
        'team2_fouls': game.team2_fouls_current_quarter,
        'recent_events': recent_events[:5]
    })


@require_GET
def api_basketball_overall_player_stats(request):
    """API endpoint to get simplified player statistics across all basketball games, sorted by total points"""
    
    # Get all player stats from basketball games
    all_stats = PlayerStat.objects.filter(game__sport='BASKETBALL').select_related('player', 'team')
    
    # Dictionary to accumulate stats by player
    player_stats_dict = {}
    
    for stat in all_stats:
        player_id = stat.player.id
        
        if player_id not in player_stats_dict:
            player_stats_dict[player_id] = {
                'name': stat.player.name,
                'team': stat.team.name,
                'total_matches': 0,
                'total_3pt': 0,
                'total_2pt': 0,
                'total_1pt': 0,
            }
        
        player_stats_dict[player_id]['total_matches'] += 1
    
    # Get shot statistics to calculate points by type
    all_shots = BasketballShot.objects.filter(game__sport='BASKETBALL', result='MADE').select_related('player')
    
    for shot in all_shots:
        player_id = shot.player.id
        if player_id in player_stats_dict:
            if shot.shot_type == '3PT':
                player_stats_dict[player_id]['total_3pt'] += 3
            elif shot.shot_type == '2PT':
                player_stats_dict[player_id]['total_2pt'] += 2
            elif shot.shot_type == 'FT':
                player_stats_dict[player_id]['total_1pt'] += 1
    
    # Convert to list
    player_stats_list = []
    for stats in player_stats_dict.values():
        total_points = stats['total_3pt'] + stats['total_2pt'] + stats['total_1pt']
        player_stats_list.append({
            'name': stats['name'],
            'team': stats['team'],
            'total_matches': stats['total_matches'],
            'total_3pt': stats['total_3pt'],
            'total_2pt': stats['total_2pt'],
            'total_1pt': stats['total_1pt'],
            'total_points': total_points
        })
    
    # Sort by total points in descending order
    player_stats_list.sort(key=lambda x: x['total_points'], reverse=True)
    
    return JsonResponse({
        'player_stats': player_stats_list,
        'total_players': len(player_stats_list)
    })


@require_GET
def api_basketball_team_standings(request):
    """API endpoint to get team standings with wins, losses, and NRR for points table"""
    
    # Get all basketball games that are finished
    finished_games = Basketball.objects.filter(status='FINISHED').select_related('team1', 'team2', 'winner')
    
    # Get ALL teams, not just ones that have played
    from .models import Team
    all_teams = Team.objects.all()
    
    # Dictionary to store team statistics
    team_stats = {}
    
    # Initialize stats for ALL teams
    for team in all_teams:
        team_stats[team.id] = {
            'name': team.name,
            'matches_played': 0,
            'wins': 0,
            'losses': 0,
            'points_scored': 0,
            'points_conceded': 0,
            'nrr': 0.0,
            'points': 0  # Points for standings (1 for win, 0 for loss)
        }
    
    # Calculate stats from finished games
    for game in finished_games:
        team1_id = game.team1.id
        team2_id = game.team2.id
        
        # Update matches played
        team_stats[team1_id]['matches_played'] += 1
        team_stats[team2_id]['matches_played'] += 1
        
        # Update points scored and conceded
        team_stats[team1_id]['points_scored'] += game.team1_score
        team_stats[team1_id]['points_conceded'] += game.team2_score
        team_stats[team2_id]['points_scored'] += game.team2_score
        team_stats[team2_id]['points_conceded'] += game.team1_score
        
        # Determine winner and update wins/losses
        if game.winner:
            winner_id = game.winner.id
            loser_id = team2_id if winner_id == team1_id else team1_id
            
            team_stats[winner_id]['wins'] += 1
            team_stats[winner_id]['points'] += 1  # 1 point for win
            team_stats[loser_id]['losses'] += 1
            # Loser gets 0 points (no change needed)
        else:
            # It's a tie - both teams get 0 points (no winner/loser)
            # No points awarded for ties
            pass
    
    # Calculate NRR for each team
    for team_id in team_stats:
        stats = team_stats[team_id]
        if stats['matches_played'] > 0:
            # NRR = (Points Scored - Points Conceded)
            stats['nrr'] = stats['points_scored'] - stats['points_conceded']
    
    # Convert to list and sort by points, then by NRR
    standings_list = []
    for stats in team_stats.values():
        standings_list.append({
            'team': stats['name'],
            'matches_played': stats['matches_played'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'points_scored': stats['points_scored'],
            'points_conceded': stats['points_conceded'],
            'nrr': stats['nrr'],
            'points': stats['points']
        })
    
    # Sort by points (descending), then by NRR (descending)
    standings_list.sort(key=lambda x: (x['points'], x['nrr']), reverse=True)
    
    return JsonResponse({
        'team_standings': standings_list,
        'total_teams': len(standings_list)
    })