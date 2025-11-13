
import modal
import subprocess
from pathlib import Path
import os

# Define the container image for the Modal function
app = modal.App("subtitle-generator-app")

video_generator_image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg", "fonts-dejavu-core", "imagemagick", "zlib1g-dev", "libjpeg-dev")
    .pip_install(
        "openai-whisper==20231117",
        "moviepy==1.0.3",
        "Pillow<10.0.0",
        "modal",
        "simpleitk",
        "numpy",  # Added for the animation
    )
    .add_local_file("policy.xml", "/etc/ImageMagick-6/policy.xml")
)

@app.function(
    image=video_generator_image,
    gpu="A100",
    timeout=1200,
)
def generate_video_modal(
    background_content: bytes, 
    audio_content: bytes, 
    background_filename: str,
    font_content: bytes = None, 
    highlight_color: str = '''#FFFF00''', 
    font_size: int = 70,
    subtitle_position: str = "bottom",
    padding: int = 20,
    font_weight: str = "normal",
    font_style: str = "normal"
):
    """
    This function runs on Modal, generating a karaoke-style video with an animated background.
    """
    import moviepy.editor as mp
    import whisper
    from moviepy.video.VideoClip import TextClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    import numpy as np

    data_dir = Path("/tmp/data")
    data_dir.mkdir(exist_ok=True)

    background_path = data_dir / background_filename 
    audio_path = data_dir / "input_audio"
    converted_audio_path = data_dir / "converted_audio.wav"
    output_path = data_dir / "output.mp4"

    background_path.write_bytes(background_content)
    audio_path.write_bytes(audio_content)

    # Font selection based on weight and style
    font_map = {
        ("normal", "normal"): "/usr/share/fonts/truetype/dejavu/DejaVu-Sans.ttf",
        ("bold", "normal"): "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        ("normal", "italic"): "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Oblique.ttf",
        ("bold", "italic"): "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold-Oblique.ttf",
    }
    font_path = font_map.get((font_weight.lower(), font_style.lower()), font_map[("normal", "normal")])


    if font_content:
        user_font_path = data_dir / "user_font.ttf"
        user_font_path.write_bytes(font_content)
        font_path = str(user_font_path)

    print("--- Karaoke Video Generation with Animation Started ---")

    try:
        print("Converting audio to WAV...")
        subprocess.run(
            ["ffmpeg", "-i", str(audio_path), "-y", str(converted_audio_path)],
            check=True, capture_output=True, text=True
        )
        print("Audio conversion successful.")

        print("Loading whisper model...")
        model = whisper.load_model("tiny")
        print("Whisper model loaded.")
        
        print("Transcribing audio...")
        result = model.transcribe(str(converted_audio_path), word_timestamps=True)
        print("Audio transcribed.")

        audio_clip = mp.AudioFileClip(str(converted_audio_path))
        
        print(f"Processing background image: {background_path}")
        background_clip_raw = mp.ImageClip(str(background_path))
        
        # Scale the image to fill the 1920x1080 frame, cropping if necessary
        bg_w, bg_h = background_clip_raw.size
        target_w, target_h = 1920, 1080
        if bg_w / bg_h > target_w / target_h:
            resized_background = background_clip_raw.resize(height=target_h)
        else:
            resized_background = background_clip_raw.resize(width=target_w)

        background_clip = CompositeVideoClip(
            [resized_background.set_position("center")],
            size=(target_w, target_h),
            bg_color=(0,0,0)
        ).set_duration(audio_clip.duration)
        print("Background image processed and fitted to 1920x1080.")

        print("Creating karaoke video clips (optimized)...")
        all_text_clips = []
        max_text_width = 1920 - (2 * padding)

        for segment in result.get("segments", []):
            words_in_segment = [w for w in segment.get("words", []) if w.get("word", "").strip()]
            if not words_in_segment:
                continue

            lines = []
            current_line = []
            current_line_text = ""
            for word_info in words_in_segment:
                word_text = word_info["word"].upper()
                test_line = f"{current_line_text} {word_text}".strip()
                sizing_clip = TextClip(test_line, fontsize=font_size, color="white", font=font_path)
                if sizing_clip.w > max_text_width:
                    lines.append(current_line)
                    current_line = [word_info]
                    current_line_text = word_text
                else:
                    current_line.append(word_info)
                    current_line_text = test_line
            lines.append(current_line)


            total_text_height = sum(TextClip("A", fontsize=font_size, font=font_path).h for _ in lines)
            if subtitle_position == "top":
                y_start = padding
            elif subtitle_position == "bottom":
                y_start = 1080 - total_text_height - padding
            else: # center
                y_start = (1080 - total_text_height) / 2

            current_y = y_start

            for line_words in lines:
                if not line_words:
                    continue
                line_text = " ".join([w["word"].upper() for w in line_words])
                line_clip_size = TextClip(line_text, fontsize=font_size, color="white", font=font_path).size
                line_start_x = (1920 - line_clip_size[0]) / 2
                
                segment_start = line_words[0]['start']
                segment_end = line_words[-1]['end']

                white_line_clip = TextClip(
                    line_text,
                    fontsize=font_size,
                    color="white",
                    font=font_path
                ).set_position((line_start_x, current_y))
                white_line_clip = white_line_clip.set_start(segment_start).set_end(segment_end)
                all_text_clips.append(white_line_clip)

                current_x = line_start_x
                for word_info in line_words:
                    word_text = word_info["word"].upper()
                    
                    highlight_clip = TextClip(
                        word_text,
                        fontsize=font_size,
                        color=highlight_color,
                        font=font_path
                    ).set_position((current_x, current_y))

                    highlight_clip = highlight_clip.set_start(word_info["start"]).set_end(word_info["end"])
                    all_text_clips.append(highlight_clip)

                    space = " "
                    sizing_word_clip = TextClip(word_text + space, fontsize=font_size, color="white", font=font_path)
                    current_x += sizing_word_clip.w

                current_y += line_clip_size[1]


        print(f"Generated {len(all_text_clips)} total text clips for compositing.")

        print("Compositing final video...")
        # Use the animated background instead of the static one
        final_clips = [background_clip] + all_text_clips
        video = CompositeVideoClip(final_clips, size=(1920, 1080))
        video.audio = audio_clip

        print(f"Writing video to: {output_path}")
        video.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast"
        )
        print("Video writing complete.")

        video_content = output_path.read_bytes()

        print("--- Video Generation Finished on Modal ---")
        return video_content

    except subprocess.CalledProcessError as e:
        print(f"An error occurred during audio conversion: {e.stderr}")
        raise
    except Exception as e:
        print(f"An error occurred during video generation: {e}")
        raise
