from django.contrib import admin
from games.models import *

admin.site.register(Game)
admin.site.register(Football)
admin.site.register(Basketball)
admin.site.register(Cricket)
admin.site.register(Team)
admin.site.register(Player)
admin.site.register(PlayerStat)
admin.site.register(ScoreEvent)
@admin.register(APIAnalytics)
class APIAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'method', 'timestamp', 'response_time_ms', 'status_code', 'ip_address')
    list_filter = ('method', 'status_code', 'timestamp')
    search_fields = ('endpoint', 'ip_address')
    date_hierarchy = 'timestamp'
    readonly_fields = ('endpoint', 'method', 'timestamp', 'response_time_ms', 'status_code', 'ip_address')
