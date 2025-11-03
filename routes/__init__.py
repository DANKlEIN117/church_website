from .admin_routes import admin_bp
from .audio_routes import audio_bp
from .video_routes import video_bp
from .gallery_routes import gallery_bp
from .events_routes import events_bp
from .sermons_routes import sermons_bp

def register_blueprints(app):
    # Register with URL prefixes to avoid endpoint clashes
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(audio_bp, url_prefix="/audio")
    app.register_blueprint(video_bp, url_prefix="/videos")
    app.register_blueprint(gallery_bp, url_prefix="/gallery")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(sermons_bp, url_prefix="/sermons")
