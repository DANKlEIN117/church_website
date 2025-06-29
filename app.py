from flask import Flask, render_template, request, redirect, url_for, flash,session
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory
from urllib.parse import quote
import json
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="ds0zvwpph",
    api_key="253451278637439",
    api_secret="m__whU-CTItr9ZkrjQm1lFAjZPE"
)


app = Flask(__name__)
app.secret_key = '12508'

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "church123"

# Set upload folder path
UPLOAD_FOLDER = 'static/media'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Allowed file types
ALLOWED_EXTENSIONS = {'mp3'}
ALLOWED_IMAGE_EXTENSIONS = ('jpg', 'jpeg', 'png')



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/audio')
def audio():
    albums = {}

    # Search Cloudinary for all audio files inside church_albums/*
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


@app.route('/upload_album', methods=['GET', 'POST'])
def upload_album():
    if not session.get('admin'):
        flash('Admin access required to upload albums.')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        album_name = request.form['album_name'].strip().replace(' ', '_')
        files = request.files.getlist('songs')
        uploaded = 0

        for file in files:
            if file and allowed_file(file.filename.lower()):
                # Fix: Read the file's stream and upload using 'upload' not 'upload_large'
                result = cloudinary.uploader.upload(
                    file,
                    resource_type='video',
                    folder=f"church_albums/{album_name}",
                    public_id=file.filename.rsplit('.', 1)[0]
                )
                uploaded += 1

        flash(f"{uploaded} song(s) uploaded to album '{album_name.replace('_', ' ')}'!")
        return redirect(url_for('audio'))

    return render_template('upload.html')

@app.route('/delete/<album>/<song>', methods=['POST'])
def delete_song(album, song):
    if not session.get('admin'):
        session['next_delete_audio'] = {'album': album, 'song': song}
        flash('Admin access required to delete songs.')
        return redirect(url_for('admin_login'))

    try:
        # Get Cloudinary public_id
        public_id = f"church_albums/{album}/{song.rsplit('.', 1)[0]}"  # remove .mp3 extension
        result = cloudinary.uploader.destroy(public_id, resource_type="video")  # 'video' works for audio too

        if result.get("result") == "ok":
            flash(f"Deleted: {song}")
        else:
            flash(f"Failed to delete {song}: {result.get('result')}")
        
        # 🚫 Note: Cloudinary folders are virtual; we can't remove empty folders directly
        # Optionally, we can check if album still has songs via the API

    except Exception as e:
        flash(f"Error deleting file: {e}")

    return redirect(url_for('audio'))




@app.route('/gallery')
def gallery():
    image_folder = os.path.join(app.static_folder, 'gallery')
    images = [img for img in os.listdir(image_folder) if img.lower().endswith(('.jpg', '.jpeg', '.png'))]

    captions = {}
    caption_file = 'photo_captions.txt'
    if os.path.exists(caption_file):
        with open(caption_file, 'r') as f:
            for line in f:
                if '|' in line:
                    filename, caption = line.strip().split('|', 1)
                    captions[filename] = caption

    return render_template('gallery.html', images=images, captions=captions)



@app.route('/upload_photo', methods=['GET', 'POST'])
def upload_photo():
    if not session.get('admin'):
        flash('Access denied. Admins only.')
        session['next_upload_photo'] = True
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        file = request.files['photo']
        caption = request.form.get('caption')

        if file and allowed_image(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.static_folder, 'gallery', filename))

            with open('photo_captions.txt', 'a') as f:
                f.write(f"{filename}|{caption}\n")

            flash('Photo uploaded successfully!')
            return redirect(url_for('gallery'))

        flash("Invalid image type.")
    return render_template('upload_photo.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('Logged in as admin')

            if session.pop('next_upload_photo', None):
                return redirect(url_for('upload_photo'))

            if 'next_delete_audio' in session:
                target = session.pop('next_delete_audio')
                return redirect(url_for('delete_song', album=target['album'], song=target['song']))

            if 'next_delete_video' in session:
                filename = session.pop('next_delete_video')
                return redirect(url_for('delete_video', filename=filename))

            next_page = session.pop('next', None)
            if next_page:
                return redirect(url_for(next_page))

            return redirect(url_for('home'))

        flash('Invalid credentials')
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Logged out')
    return redirect(url_for('home'))

@app.route('/delete_photo/<filename>', methods=['POST'])
def delete_photo(filename):
    if not session.get('admin'):
        flash('Access denied.')
        return redirect(url_for('gallery'))

    try:
        path = os.path.join(app.static_folder, 'gallery', filename)
        if os.path.exists(path):
            os.remove(path)

            # Optional: remove caption
            if os.path.exists('photo_captions.txt'):
                with open('photo_captions.txt', 'r') as f:
                    lines = f.readlines()
                with open('photo_captions.txt', 'w') as f:
                    for line in lines:
                        if not line.startswith(filename + '|'):
                            f.write(line)

            flash(f"{filename} deleted.")
        else:
            flash("File not found.")
    except Exception as e:
        flash(f"Error deleting file: {e}")

    return redirect(url_for('gallery'))


@app.route('/calendar')
def view_calendar():
    return render_template('calendar.html')

@app.route('/upload_video', methods=['GET', 'POST'])
def upload_video():
    if not session.get('admin'):
        flash('Admin access required to upload videos.')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        file = request.files['video']
        if file and file.filename.endswith('.mp4'):
            try:
                result = cloudinary.uploader.upload(
                    file,
                    resource_type="video",
                    folder="church_videos"
                )
                flash('Video uploaded successfully!')
                return redirect(url_for('video_messages'))
            except Exception as e:
                flash(f'Upload error: {e}')
                return redirect(request.url)

    return render_template('upload_video.html')



@app.route('/delete_video/<filename>', methods=['POST'])
def delete_video(filename):
    if not session.get('admin'):
        session['next_delete_video'] = filename
        flash('Admin access required to delete video.')
        return redirect(url_for('admin_login'))

    try:
        # Reconstruct the Cloudinary public_id
        public_id = f"church_videos/{filename.rsplit('.', 1)[0]}"  # remove .mp4
        cloudinary.uploader.destroy(public_id, resource_type="video")
        flash(f"Deleted: {filename}")
    except Exception as e:
        flash(f"Error deleting video: {e}")

    return redirect(url_for('video_messages'))



@app.route('/video_messages')
def video_messages():
    videos = []

    try:
        response = cloudinary.Search()\
            .expression("folder:church_videos AND resource_type:video")\
            .sort_by("public_id", "desc")\
            .max_results(100)\
            .execute()

        for item in response.get("resources", []):
            title = item["public_id"].split("/")[-1].replace('_', ' ').title()
            url = item["secure_url"]
            videos.append({"title": title, "url": url})
    except Exception as e:
        flash(f"Error loading videos: {e}")

    return render_template("videos.html", videos=videos)

@app.route('/events')
def events():
    with open('events.json', 'r') as f:
        events = json.load(f)
    return render_template('events.html', events=events)

@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if not session.get('admin'):
        flash('Admin access required.')
        session['next'] = 'add_event'
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        description = request.form['description']

        with open('events.json', 'r') as f:
            events = json.load(f)

        event_id = (events[-1]['id'] + 1) if events else 1
        events.append({"id": event_id, "title": title, "date": date, "description": description})

        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)

        flash("Event added.")
        return redirect(url_for('events'))

    return render_template('add_event.html')

@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if not session.get('admin'):
        flash('Admin access required.')
        return redirect(url_for('admin_login'))

    with open('events.json', 'r') as f:
        events = json.load(f)

    events = [e for e in events if e['id'] != event_id]

    with open('events.json', 'w') as f:
        json.dump(events, f, indent=4)

    flash("Event deleted.")
    return redirect(url_for('events'))

@app.route('/sermons')
def sermons():
    try:
        with open('sermons.json', 'r') as f:
            sermons = json.load(f)
    except:
        sermons = []
    return render_template('sermons.html', sermons=sermons)

@app.route('/add_sermon', methods=['GET', 'POST'])
def add_sermon():
    if not session.get('admin'):
        flash('Admin access required.')
        session['next'] = 'add_sermon'
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        preacher = request.form['preacher']
        date = request.form['date']
        summary = request.form['summary']

        with open('sermons.json', 'r') as f:
            sermons = json.load(f)

        sermon_id = sermons[-1]['id'] + 1 if sermons else 1
        sermons.append({
            "id": sermon_id,
            "title": title,
            "preacher": preacher,
            "date": date,
            "summary": summary
        })

        with open('sermons.json', 'w') as f:
            json.dump(sermons, f, indent=4)

        flash('Sermon added.')
        return redirect(url_for('sermons'))

    return render_template('add_sermon.html')


@app.route('/delete_sermon/<int:sermon_id>', methods=['POST'])
def delete_sermon(sermon_id):
    if not session.get('admin'):
        flash('Admin access required.')
        return redirect(url_for('admin_login'))

    with open('sermons.json', 'r') as f:
        sermons = json.load(f)

    sermons = [s for s in sermons if s['id'] != sermon_id]

    with open('sermons.json', 'w') as f:
        json.dump(sermons, f, indent=4)

    flash('Sermon deleted.')
    return redirect(url_for('sermons'))

@app.route('/delete_album/<album>', methods=['POST'])
def delete_album(album):
    if not session.get('admin'):
        flash('Admin access required to delete albums.')
        return redirect(url_for('admin_login'))

    album_path = os.path.join(app.config['UPLOAD_FOLDER'], album)

    try:
        if os.path.exists(album_path) and os.path.isdir(album_path):
            # Remove all files inside the folder
            for filename in os.listdir(album_path):
                file_path = os.path.join(album_path, filename)
                os.remove(file_path)
            os.rmdir(album_path)  # Remove the folder itself
            flash(f"Album '{album.replace('_', ' ')}' has been deleted.")
        else:
            flash("Album does not exist.")
    except Exception as e:
        flash(f"Error deleting album: {e}")

    return redirect(url_for('audio'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
