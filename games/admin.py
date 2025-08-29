from django.contrib import admin
from games.models import *

admin.site.register(Game)
admin.site.register(Football)
admin.site.register(Basketball)
admin.site.register(Cricket)
admin.site.register(Team)
admin.site.register(Player)
admin.site.register(PlayerStat)
