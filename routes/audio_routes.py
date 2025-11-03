from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import cloudinary
import cloudinary.uploader

audio_bp = Blueprint('audio', __name__)
ALLOWED_EXTENSIONS = {'mp3'}


def allowed_file(filename):
    """Check if the uploaded file is an allowed type."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@audio_bp.route('/audio')
def audio():
    """Display all uploaded albums with their songs."""
    albums = {}

    try:
        results = (
            cloudinary.Search()
            .expression("folder:church_albums/** AND resource_type:auto")
            .sort_by("created_at", "desc")  # show newest first
            .max_results(100)
            .execute()
        )

        for item in results.get("resources", []):
            parts = item["public_id"].split('/')
            if len(parts) < 2:
                continue

            album_name = parts[1].replace('_', ' ')
            song_title = parts[-1].split('/')[-1].replace('_', ' ').title()

            albums.setdefault(album_name, []).append({
                "title": song_title,
                "url": item["secure_url"]
            })

        # Sort songs alphabetically within each album (optional)
        for songs in albums.values():
            songs.sort(key=lambda s: s["title"])

    except Exception as e:
        flash(f"⚠️ Error fetching songs: {e}")

    return render_template("audio.html", albums=albums)


@audio_bp.route('/upload_album', methods=['GET', 'POST'])
def upload_album():
    """Admin-only route to upload multiple MP3s into an album."""
    if not session.get('admin'):
        flash('⚠️ Admin access required.')
        session['next'] = 'audio.upload_album'
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        album_name = request.form.get('album_name', '').strip().replace(' ', '_')
        files = request.files.getlist('songs')

        if not album_name:
            flash('❗ Please provide an album name.')
            return redirect(url_for('audio.upload_album'))

        if not files or not any(file.filename for file in files):
            flash('❗ No songs selected.')
            return redirect(url_for('audio.upload_album'))

        uploaded = 0

        for file in files:
            if file and allowed_file(file.filename):
                try:
                    cloudinary.uploader.upload(
                        file,
                        resource_type='auto',
                        folder=f"church_albums/{album_name}",
                        public_id=file.filename.rsplit('.', 1)[0],
                    )
                    uploaded += 1
                except Exception as e:
                    flash(f"⚠️ Error uploading {file.filename}: {str(e)}")

        flash(f"✅ {uploaded} song(s) uploaded to '{album_name.replace('_', ' ')}'.")
        return redirect(url_for('audio.audio'))

    return render_template('upload.html')
