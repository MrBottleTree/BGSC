import time
from django.utils.deprecation import MiddlewareMixin
from .models import APIAnalytics

class APIAnalyticsMiddleware(MiddlewareMixin):
    """Middleware to track frontend API endpoint usage"""
    
    # List of frontend-facing API endpoints to track
    TRACKED_ENDPOINTS = [
        '/api/matches/',
        '/api/matches/<int>/',
        '/api/basketball/games/',
        '/api/basketball/<int>/stats/',
        '/api/basketball/<int>/events/',
        '/api/basketball/<int>/player-stats/',
        '/api/basketball/<int>/live/',
        '/api/basketball/player-stats/',
        '/api/basketball/team-standings/',
        '/local-ip/',
        '/healthz/',
    ]
    
    def process_request(self, request):
        """Store request start time"""
        request._api_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Track API endpoint usage for frontend APIs only"""
        path = request.path
        
        # Only track if it's an API endpoint (starts with /api/ or is healthz/local-ip)
        if not (path.startswith('/api/') or path in ['/healthz/', '/local-ip/']):
            return response
        
        # Calculate response time
        response_time_ms = None
        if hasattr(request, '_api_start_time'):
            response_time_ms = int((time.time() - request._api_start_time) * 1000)
        
        # Get client IP
        ip_address = self.get_client_ip(request)
        
        # Normalize path (replace numeric IDs with <int>)
        normalized_path = self.normalize_path(path)
        
        # Save to database asynchronously (in production, use Celery or similar)
        try:
            APIAnalytics.objects.create(
                endpoint=normalized_path,
                method=request.method,
                response_time_ms=response_time_ms,
                status_code=response.status_code,
                ip_address=ip_address
            )
        except Exception:
            # Don't break the request if analytics fails
            pass
        
        return response
    
    def normalize_path(self, path):
        """Replace numeric IDs with <int> for aggregation"""
        import re
        # Replace /123/ or /123 at end with /<int>/
        normalized = re.sub(r'/\d+/', '/<int>/', path)
        normalized = re.sub(r'/\d+$', '/<int>', normalized)
        return normalized
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
