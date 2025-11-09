
from flask import Flask, send_file, abort, request
import whisper
import moviepy.editor as mp
import os
import subprocess

app = Flask(__name__)

# Load the whisper model once when the application starts
try:
    model = whisper.load_model("base")
except Exception as e:
    print(f"Error loading whisper model: {e}")
    model = None

@app.route('/video', methods=['GET'])
def test():
    return {"message":"text"}

@app.route('/video', methods=['POST'])
def generate_video():
    if model is None:
        abort(500, "Whisper model is not available.")

    background_file = request.files.get('background')
    audio_file = request.files.get('audio')
    print(background_file.filename, audio_file, "Baliram")
    # --- Robust File Validation ---
    if not background_file or not background_file.filename:
        abort(400, "Background image file part is missing or empty.")
    if not audio_file or not audio_file.filename:
        abort(400, "Audio file part is missing or empty.")

    background_data = background_file.read()
    audio_data = audio_file.read()

    if not background_data:
        abort(400, "Background image file is empty.")
    if not audio_data:
        abort(400, "Audio file is empty.")

    # Use fixed, temporary filenames. ffmpeg is smart enough to probe the format.
    safe_background_path = "temp_background"
    safe_audio_path = "temp_audio"
    
    with open(safe_background_path, "wb") as f:
        f.write(background_data)
    with open(safe_audio_path, "wb") as f:
        f.write(audio_data)
    # --- End of Validation ---

    converted_audio_path = "converted_audio.wav"

    try:
        # Convert audio to WAV to ensure compatibility and handle potential format issues.
        command = [
            "ffmpeg",
            "-i", safe_audio_path,
            "-y",  # Overwrite output file if it exists
            converted_audio_path
        ]
        process = subprocess.run(command, check=True, capture_output=True, text=True)

        # 1. Transcribe audio to get word-level timestamps
        result = model.transcribe(converted_audio_path, word_timestamps=True)

        audio_clip = mp.AudioFileClip(converted_audio_path)
        img_clip = mp.ImageClip(safe_background_path).set_duration(audio_clip.duration)
        
        # Resize image to 1920x1080
        img_clip = img_clip.resize(width=1920, height=1080)

        font_path = 'ERODED PERSONAL USE.ttf'
        if not os.path.exists(font_path):
            print(f"Font file not found at '{font_path}'. Falling back to default font.")
            font_path = 'DejaVu-Sans'

        clips = [img_clip]
        
        space_clip = mp.TextClip(" ", fontsize=50, font=font_path)
        space_width = space_clip.size[0]

        for segment in result["segments"]:
            words = segment['words']
            for i, word_info in enumerate(words):
                start_time = word_info['start']
                end_time = word_info['end']
                word_text = word_info['word'].upper()

                pre_text = " ".join([w['word'].upper() for w in words[:i]])
                post_text = " ".join([w['word'].upper() for w in words[i+1:]])

                pre_clip = mp.TextClip(pre_text, fontsize=50, color='white', font=font_path) if pre_text else None
                current_word_clip = mp.TextClip(word_text, fontsize=50, color='yellow', font=font_path)
                post_clip = mp.TextClip(post_text, fontsize=50, color='white', font=font_path) if post_text else None

                pre_width = pre_clip.size[0] if pre_clip else 0
                current_width = current_word_clip.size[0]
                post_width = post_clip.size[0] if post_clip else 0

                total_width = pre_width + current_width + post_width
                if pre_clip: total_width += space_width
                if post_clip: total_width += space_width

                start_x = (img_clip.size[0] - total_width) / 2

                word_clips = []
                current_x = start_x

                if pre_clip:
                    word_clips.append(pre_clip.set_position((current_x, 'center')))
                    current_x += pre_width + space_width
                
                word_clips.append(current_word_clip.set_position((current_x, 'center')))
                current_x += current_width + space_width
                
                if post_clip:
                    word_clips.append(post_clip.set_position((current_x, 'center')))

                sentence_for_word_clip = mp.CompositeVideoClip(word_clips, size=img_clip.size)
                sentence_for_word_clip = sentence_for_word_clip.set_start(start_time).set_duration(end_time - start_time)

                clips.append(sentence_for_word_clip)

        video = mp.CompositeVideoClip(clips, size=(1920, 1080))
        video.audio = audio_clip
        
        output_path = "output.mp4"
        video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')

        return send_file(output_path, as_attachment=True, mimetype='video/mp4')

    except subprocess.CalledProcessError as e:
        print(f"An error occurred during audio conversion: {e}")
        print(f"ffmpeg stderr: {e.stderr}")
        abort(500, "Failed to process audio file.")
    except Exception as e:
        print(f"An error occurred during video generation: {e}")
        abort(500, "Failed to generate video.")
    finally:
        # Clean up uploaded and temporary files
        if os.path.exists(safe_background_path):
            os.remove(safe_background_path)
        if os.path.exists(safe_audio_path):
            os.remove(safe_audio_path)
        if os.path.exists(converted_audio_path):
            os.remove(converted_audio_path)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)
