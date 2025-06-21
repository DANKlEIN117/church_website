from flask import Flask, render_template, request, redirect, url_for, flash,session
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory
from urllib.parse import quote
import json

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
    for album_name in os.listdir(app.config['UPLOAD_FOLDER']):
        album_path = os.path.join(app.config['UPLOAD_FOLDER'], album_name)
        if os.path.isdir(album_path):
            songs = [f for f in os.listdir(album_path) if f.endswith('.mp3')]
            albums[album_name.replace('_', ' ')] = songs
    return render_template('audio.html', albums=albums)


@app.route('/upload_album', methods=['GET', 'POST'])
def upload_album():
    if request.method == 'POST':
        album_name = request.form['album_name'].strip().replace(' ', '_')
        files = request.files.getlist('songs')

        if not album_name:
            flash('Album name is required!')
            return redirect(request.url)

        album_folder = os.path.join(app.config['UPLOAD_FOLDER'], album_name)
        os.makedirs(album_folder, exist_ok=True)

        uploaded = 0
        for file in files:
            if file and allowed_file(file.filename.lower()):
                filename = secure_filename(file.filename)
                file.save(os.path.join(album_folder, filename))
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
        path = os.path.join(app.config['UPLOAD_FOLDER'], album, song)
        if os.path.exists(path):
            os.remove(path)
            flash(f"Deleted: {song}")
        
        # ✅ Auto-delete empty folder
        album_folder = os.path.join(app.config['UPLOAD_FOLDER'], album)
        if os.path.isdir(album_folder) and not os.listdir(album_folder):
            os.rmdir(album_folder)
            flash(f"Album '{album}' was empty and removed.")

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
            filename = secure_filename(file.filename)
            file.save(os.path.join('static', 'videos', filename))
            flash('Video uploaded successfully!')
            return redirect(url_for('video_messages'))

    return render_template('upload_video.html')

@app.route('/delete_video/<filename>', methods=['POST'])
def delete_video(filename):
    if not session.get('admin'):
        # Store pending action
        session['next_delete_video'] = filename
        flash('Admin access required to delete video.')
        return redirect(url_for('admin_login'))

    try:
        path = os.path.join('static', 'videos', filename)
        if os.path.exists(path):
            os.remove(path)
            flash(f"{filename} deleted.")
        else:
            flash("Video file not found.")
    except Exception as e:
        flash(f"Error deleting video: {e}")

    return redirect(url_for('video_messages'))


@app.route('/video_messages')
def video_messages():
    video_folder = os.path.join('static', 'videos')
    videos = [v for v in os.listdir(video_folder) if v.endswith('.mp4')]
    return render_template('videos.html', videos=videos)

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
    app.run(debug=True)