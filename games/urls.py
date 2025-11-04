from django.http import JsonResponse
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/matches/', views.api_get_matches, name='api_get_matches'),
    path('api/matches/<int:match_id>/', views.api_match_detail, name='api_match_detail'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path("login/", auth_views.LoginView.as_view(template_name="games/login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('dashboard/teams/', views.teams, name='teams'),
    path('dashboard/swap-players/', views.swap_players, name='swap_players'),
    path('dashboard/teams/<int:team_id>/', views.team_detail, name='team_detail'),
    path('dashboard/teams/remove-team/<int:team_id>/', views.remove_team, name='remove_team'),
    path('dashboard/teams/<int:team_id>/remove-player/<int:player_id>/', views.remove_player, name='remove_player'),
    path('dashboard/add-game/', views.add_game, name='add_game'),
    path('dashboard/add-team/', views.add_team, name='add_team'),
    path('dashboard/add-player/', views.add_player, name='add_player'),
    path('dashboard/delete-game/<int:game_id>/', views.delete_game, name='delete_game'),
    path('update/football/<int:game_id>/', views.update_football, name='update_football'),
    path('update/basketball/<int:game_id>/', views.update_basketball, name='update_basketball'),
    path('update/cricket/<int:game_id>/', views.update_cricket, name='update_cricket'),
    path('update/undo/<int:game_id>/', views.update_undo, name='update_undo'),

    path('basketball/stats/<int:game_id>/', views.basketball_game_stats, name='basketball_game_stats'),
    path('basketball/start/<int:game_id>/', views.start_basketball_game, name='start_basketball_game'),
    path('basketball/end/<int:game_id>/', views.end_basketball_game, name='end_basketball_game'),
    path('api/basketball/<int:game_id>/stats/', views.basketball_api_stats, name='basketball_api_stats'),
    path('api/basketball/games/', views.api_basketball_games, name='api_basketball_games'),
    path('api/basketball/<int:game_id>/events/', views.api_basketball_game_events, name='api_basketball_game_events'),
    path('api/basketball/<int:game_id>/player-stats/', views.api_basketball_player_stats, name='api_basketball_player_stats'),
    path('api/basketball/<int:game_id>/live/', views.api_basketball_live_update, name='api_basketball_live_update'),
    path('api/basketball/player-stats/', views.api_basketball_overall_player_stats, name='api_basketball_overall_player_stats'),
    path('api/basketball/team-standings/', views.api_basketball_team_standings, name='api_basketball_team_standings'),

    path('dashboard/game-status/<int:game_id>/', views.set_game_status, name='set_game_status'),
    path('dashboard/analytics/', views.api_analytics, name='api_analytics'),

    path('healthz/', lambda request: JsonResponse({"message": "OK"}, status=200), name='healthz'),
        path('local-ip/', views.api_local_ip, name='api_local_ip'),

]
