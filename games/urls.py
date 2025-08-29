from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path("login/", auth_views.LoginView.as_view(template_name="games/login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('dashboard/teams/', views.teams, name='teams'),
    path('dashboard/teams/<int:team_id>/', views.team_detail, name='team_detail'),
    path('dashboard/teams/<int:team_id>/remove-player/<int:player_id>/', views.remove_player, name='remove_player'),
    path('dashboard/add-game/', views.add_game, name='add_game'),
    path('dashboard/add-team/', views.add_team, name='add_team'),
    path('dashboard/add-player/', views.add_player, name='add_player'),
    path('update/football/<int:game_id>/', views.update_football, name='update_football'),
    path('update/basketball/<int:game_id>/', views.update_basketball, name='update_basketball'),
    path('update/cricket/<int:game_id>/', views.update_cricket, name='update_cricket'),
    path('update/undo/<int:game_id>/', views.update_undo, name='update_undo'),
    path('dashboard/game-status/<int:game_id>/', views.set_game_status, name='set_game_status'),
]
