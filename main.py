from flask import Flask, send_file, abort
import whisper
import moviepy.editor as mp
from moviepy.video.tools.subtitles import SubtitlesClip
import os

app = Flask(__name__)

# Load the whisper model once when the application starts
try:
    model = whisper.load_model("base")
except Exception as e:
    # If the model fails to load, you might want to log this
    # and handle it gracefully. For now, we'll print and exit
    # if it's critical, or just log if the app can run without it.
    print(f"Error loading whisper model: {e}")
    model = None


# Create a blue background image if it doesn't exist
if not os.path.exists("background.png"):
    try:
        img = mp.ColorClip(size=(640, 480), color=(0, 0, 255), duration=1)
        img.save_frame("background.png")
    except Exception as e:
        print(f"Error creating background image: {e}")

@app.route('/video')
def generate_video():
    if model is None:
        abort(500, "Whisper model is not available.")

    audio_path = "audio.mp3"
    if not os.path.exists(audio_path):
        abort(404, "Audio file 'audio.mp3' not found.")

    try:
        # 1. Transcribe audio to get segments
        result = model.transcribe(audio_path)
        segments = result["segments"]

        # 2. Prepare subtitles in the format required by MoviePy
        # The format is a list of ((start, end), text) tuples
        subtitle_data = []
        for segment in segments:
            start_time = float(segment['start'])
            end_time = float(segment['end'])
            text = segment['text'].strip()
            if text: # a segment can have empty text
                subtitle_data.append(((start_time, end_time), text))


        # 3. Create a background image clip
        audio_clip = mp.AudioFileClip(audio_path)
        img_clip = mp.ImageClip("background.png").set_duration(audio_clip.duration)

        # 4. Create subtitles clip
        generator = lambda txt: mp.TextClip(txt, font='DejaVu-Sans', fontsize=24, color='white', size=img_clip.size, method='caption')
        subtitles_clip = SubtitlesClip(subtitle_data, generator)

        # 5. Composite the video
        video = mp.CompositeVideoClip([img_clip, subtitles_clip.set_pos(('center', 'bottom'))])
        video.audio = audio_clip
        
        output_path = "output.mp4"
        # Use a codec that is widely supported
        video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')

        return send_file(output_path, as_attachment=True, mimetype='video/mp4')

    except Exception as e:
        print(f"An error occurred during video generation: {e}")
        abort(500, "Failed to generate video.")


if __name__ == "__main__":
    # Use 0.0.0.0 to make the server accessible from outside the container
    app.run(debug=True, host='0.0.0.0', port=8080)