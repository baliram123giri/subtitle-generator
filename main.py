from flask import Flask, send_file, abort
import whisper
import moviepy.editor as mp
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
        # 1. Transcribe audio to get word-level timestamps
        result = model.transcribe(audio_path, word_timestamps=True)

        audio_clip = mp.AudioFileClip(audio_path)
        img_clip = mp.ImageClip("background.png").set_duration(audio_clip.duration)
        
        font_path = 'ERODED PERSONAL USE.ttf'
        if not os.path.exists(font_path):
            print(f"Font file not found at '{font_path}'. Falling back to default font.")
            font_path = 'DejaVu-Sans'

        clips = [img_clip]
        
        # Create a clip of a space to measure its width
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

                # Composite the sentence for the duration of the current word
                sentence_for_word_clip = mp.CompositeVideoClip(word_clips, size=img_clip.size)
                sentence_for_word_clip = sentence_for_word_clip.set_start(start_time).set_duration(end_time - start_time)

                clips.append(sentence_for_word_clip)

        # 5. Composite the video
        video = mp.CompositeVideoClip(clips, size=img_clip.size)
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
