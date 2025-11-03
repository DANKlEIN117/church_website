from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
from werkzeug.utils import secure_filename

gallery_bp = Blueprint('gallery', __name__)
ALLOWED_IMAGE_EXTENSIONS = ('jpg', 'jpeg', 'png')
GALLERY_FOLDER = os.path.join('static', 'gallery')
CAPTIONS_FILE = 'photo_captions.txt'


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@gallery_bp.route('/gallery')
def gallery():
    if not os.path.exists(GALLERY_FOLDER):
        os.makedirs(GALLERY_FOLDER)

    images = [
        img for img in os.listdir(GALLERY_FOLDER)
        if img.lower().endswith(ALLOWED_IMAGE_EXTENSIONS)
    ]

    captions = {}
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    filename, caption = line.strip().split('|', 1)
                    captions[filename] = caption

    return render_template('gallery.html', images=images, captions=captions)


@gallery_bp.route('/upload_photo', methods=['GET', 'POST'])
def upload_photo():
    if not session.get('admin'):
        flash('⚠️ Admin access required.')
        session['next'] = 'gallery.upload_photo'
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        file = request.files.get('photo')
        caption = request.form.get('caption', '').strip()

        if not file or not allowed_image(file.filename):
            flash('❌ Invalid file type. Only JPG, JPEG, and PNG allowed.')
            return redirect(url_for('gallery.upload_photo'))

        if not os.path.exists(GALLERY_FOLDER):
            os.makedirs(GALLERY_FOLDER)

        filename = secure_filename(file.filename)
        save_path = os.path.join(GALLERY_FOLDER, filename)
        file.save(save_path)

        # Save caption
        with open(CAPTIONS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{filename}|{caption}\n")

        flash(f'✅ Photo "{filename}" uploaded successfully.')
        return redirect(url_for('gallery.gallery'))

    return render_template('upload_photo.html')

@gallery_bp.route('/delete_photo/<filename>', methods=['POST'])
def delete_photo(filename):
    if not session.get('admin'):
        flash('⚠️ Admin access required.')
        return redirect(url_for('admin.admin_login'))

    file_path = os.path.join(GALLERY_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove caption line
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(CAPTIONS_FILE, 'w', encoding='utf-8') as f:
            for line in lines:
                if not line.startswith(f"{filename}|"):
                    f.write(line)

    flash(f'🗑 Photo "{filename}" deleted successfully.')
    return redirect(url_for('gallery.gallery'))

