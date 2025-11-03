from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import cloudinary
import cloudinary.uploader

video_bp = Blueprint('video', __name__)


@video_bp.route('/video_messages')
def video_messages():
    videos = []
    try:
        # Using a flexible search that works with Cloudinary video folders
        response = (
            cloudinary.Search()
            .expression("folder:church_videos AND resource_type:video")
            .sort_by("public_id", "desc")
            .max_results(100)
            .execute()
        )

        for item in response.get("resources", []):
            title = item["public_id"].split("/")[-1].replace("_", " ").title()
            videos.append({
                "title": title,
                "url": item["secure_url"]
            })

    except Exception as e:
        flash(f"⚠️ Error loading videos: {e}")

    return render_template("videos.html", videos=videos)


@video_bp.route('/upload_video', methods=['GET', 'POST'])
def upload_video():
    if not session.get('admin'):
        flash('⚠️ Admin access required.')
        session['next'] = 'video.upload_video'
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        file = request.files.get('video')

        if not file or not file.filename.lower().endswith('.mp4'):
            flash('❌ Invalid file. Only .mp4 videos are allowed.')
            return redirect(url_for('video.upload_video'))

        try:
            cloudinary.uploader.upload(
                file,
                resource_type="video",
                folder="church_videos",
                public_id=file.filename.rsplit('.', 1)[0]
            )
            flash('✅ Video uploaded successfully!')
            return redirect(url_for('video.video_messages'))
        except Exception as e:
            flash(f"⚠️ Upload error: {e}")

    return render_template('upload_video.html')


@video_bp.route('/delete_video/<filename>', methods=['POST'])
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

    return redirect(url_for('video.video_messages'))
