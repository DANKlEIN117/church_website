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

    results = cloudinary.Search()\
        .expression("folder:church_albums/* AND resource_type:video")\
        .sort_by("public_id", "asc")\
        .max_results(100)\
        .execute()

    for item in results.get("resources", []):
        full_path = item["public_id"]  # e.g. church_albums/Yesu_Yuaja/hosanna
        url = item["secure_url"]

        # Split to get album and song name
        parts = full_path.split('/')
        if len(parts) < 3:
            continue

        album_slug = parts[1]
        album_name = album_slug.replace('_', ' ')
        song_title = parts[2].replace('_', ' ').title()

        if album_name not in albums:
            albums[album_name] = []

        albums[album_name].append({
            "title": song_title,
            "url": url
        })

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
