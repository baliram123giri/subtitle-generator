import os
import io
import uuid
import threading
from collections import OrderedDict
from flask import Flask, request, jsonify, send_file, abort
import modal
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Create an output directory if it doesn't exist
os.makedirs("output", exist_ok=True)

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# In-memory job store, limited to the last 5 jobs
MAX_JOBS = 5
jobs = OrderedDict()
jobs_lock = threading.Lock()

def process_video_and_upload(job_id, background_content, audio_content, background_filename, font_content, highlight_color, font_size):
    try:
        print(f"Job {job_id}: Calling Modal function.")
        # Look up the deployed Modal function by its name
        f = modal.Function.from_name("subtitle-generator-app", "generate_video_modal")

        # Call the Modal function
        video_content = f.remote(
            background_content,
            audio_content,
            background_filename=background_filename,
            font_content=font_content,
            highlight_color=highlight_color,
            font_size=font_size
        )

        # Validate the content received from Modal
        if not video_content:
            raise ValueError("Modal function returned empty video content.")

        print(f"Job {job_id}: Received video content from Modal ({len(video_content)} bytes).")

        # Save the video to a temporary file before uploading
        temp_video_path = os.path.join("output", f"{job_id}.mp4")
        with open(temp_video_path, "wb") as f_out:
            f_out.write(video_content)
        
        print(f"Job {job_id}: Video saved locally to {temp_video_path}. Uploading to Cloudinary...")

        # Upload the saved file to Cloudinary
        upload_info = cloudinary.uploader.upload(
            temp_video_path,
            folder="videos",
            public_id=job_id,
            resource_type="video"
        )
        
        # Clean up the temporary file
        os.remove(temp_video_path)
        print(f"Job {job_id}: Upload complete. Temporary file {temp_video_path} removed.")

        # Safely update the job status
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id] = {"status": "completed", "url": upload_info['secure_url']}

    except Exception as e:
        print(f"Job {job_id}: An error occurred: {e}")
        # Safely update the job status
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id] = {"status": "failed", "error": str(e)}

@app.route('/video', methods=['POST'])
def generate_video():
    print("\n--- New Request: Offloading to Modal ---")
    background_file = request.files.get('background')
    audio_file = request.files.get('audio')
    font_file = request.files.get('font')

    if not background_file or not background_file.filename:
        abort(400, "Background image file part is missing or empty.")
    if not audio_file or not audio_file.filename:
        abort(400, "Audio file part is missing or empty.")

    background_content = background_file.read()
    audio_content = audio_file.read()
    font_content = font_file.read() if font_file else None
    
    background_filename = background_file.filename

    highlight_color = request.form.get('highlight_color', '#FFFF00')
    font_size = int(request.form.get('font_size', 70))

    job_id = str(uuid.uuid4())

    # Safely create the new job and manage the size of the store
    with jobs_lock:
        # If the store is full, remove the oldest job
        if len(jobs) >= MAX_JOBS:
            oldest_job_id, _ = jobs.popitem(last=False) # popitem(last=False) is FIFO
            print(f"Max jobs reached. Removed oldest job: {oldest_job_id}")
            
        jobs[job_id] = {"status": "processing"}

    thread = threading.Thread(
        target=process_video_and_upload,
        args=(job_id, background_content, audio_content, background_filename, font_content, highlight_color, font_size)
    )
    thread.start()

    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        
    if not job:
        abort(404, "Job not found. It may have been cleared from the cache.")
    return jsonify(job)


# ## temp video upload test
# @app.route("/upload", methods=["GET"])
# def upload_video_temp_file():
#     #get the video path from dir
#         temp_video_path = "video.mp4"
#      # Upload the saved file to Cloudinary
#         upload_info = cloudinary.uploader.upload(
#             temp_video_path,
#             folder="videos",
#             public_id="b6cbc981-16bb-4da0-9d3e-ce446acda2b1",
#             resource_type="video"
#         )
#         return jsonify({"url": upload_info['secure_url']})


@app.route('/music', methods=['POST'])
def generate_music():
    print("\n--- New Request: Generating Song with Suno ---")
    data = request.get_json()
    if not data or 'lyrics' not in data:
        abort(400, "Request body must be JSON with a 'lyrics' field.")

    lyrics = data['lyrics']

    try:
        # Look up the deployed Modal function by its name
        f = modal.Function.from_name("music-generator-app", "generate_music_modal")

        # Call the Modal function with the lyrics
        print(f"Calling Modal music generator with lyrics: '{lyrics}'")
        music_content = f.remote(lyrics)
        print("Received music content back from Modal.")

        # Save the music to a file
        music_path = "output/generated_song.wav"
        with open(music_path, "wb") as music_file:
            music_file.write(music_content)
        print(f"Music successfully saved to {music_path}")

        # Send the audio file back to the client
        return send_file(
            io.BytesIO(music_content),
            as_attachment=True,
            mimetype='audio/wav',
            download_name='generated_song.wav'
        )

    except Exception as e:
        print(f"An error occurred while calling the Modal function: {e}")
        abort(500, f"Failed to generate music via Modal: {e}")
    finally:
        print("--- Music Request Finished ---")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3300)