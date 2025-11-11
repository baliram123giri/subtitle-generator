
import modal
import subprocess
from pathlib import Path
import os

# Define the container image for the Modal function
app = modal.App("subtitle-generator-app")

video_generator_image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg", "fonts-dejavu-core", "imagemagick")
    .pip_install(
        "openai-whisper==20231117",
        "moviepy==1.0.3",
        "Pillow<10.0.0",
        "modal",
        "simpleitk",
    )
    .add_local_file("policy.xml", "/etc/ImageMagick-6/policy.xml")
)

@app.function(
    image=video_generator_image,
    gpu="T4",
    timeout=1200,
)
def generate_video_modal(
    background_content: bytes, 
    audio_content: bytes, 
    background_filename: str,  # Accept the filename
    font_content: bytes = None, 
    highlight_color: str = '#FFFF00', 
    font_size: int = 70
):
    """
    This function runs on Modal, generating a karaoke-style video with highlighted words.
    It uses the correct file extension for the background image.
    """
    import moviepy.editor as mp
    import whisper
    from moviepy.video.VideoClip import TextClip, ColorClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

    data_dir = Path("/tmp/data")
    data_dir.mkdir(exist_ok=True)

    # --- FIX: Use the original filename to preserve the extension ---
    background_path = data_dir / background_filename 
    audio_path = data_dir / "input_audio"
    converted_audio_path = data_dir / "converted_audio.wav"
    output_path = data_dir / "output.mp4"

    background_path.write_bytes(background_content)
    audio_path.write_bytes(audio_content)

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVu-Sans.ttf"
    if font_content:
        user_font_path = data_dir / "user_font.ttf"
        user_font_path.write_bytes(font_content)
        font_path = str(user_font_path)

    print("--- Karaoke Video Generation Started (Using Correct File Extension) ---")

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
        
        resized_background = background_clip_raw.resize(height=1080)
        if resized_background.size[0] > 1920:
             resized_background = background_clip_raw.resize(width=1920)

        background_clip = CompositeVideoClip(
            [resized_background.set_position("center")],
            size=(1920, 1080),
            bg_color=(0,0,0)
        ).set_duration(audio_clip.duration)
        print("Background image processed and fitted to 1920x1080.")

        print("Creating karaoke video clips (optimized)...")
        all_text_clips = []

        for segment in result.get("segments", []):
            words_in_segment = [w for w in segment.get("words", []) if w.get("word", "").strip()]
            if not words_in_segment:
                continue

            full_line_text = " ".join([word["word"].upper() for word in words_in_segment])
            
            try:
                sizing_clip = TextClip(full_line_text, fontsize=font_size, color="white", font=font_path)
                line_start_x = (1920 - sizing_clip.w) / 2

                white_line_clip = TextClip(
                    full_line_text,
                    fontsize=font_size,
                    color="white",
                    font=font_path
                ).set_position((line_start_x, "center"))
                
                segment_start = words_in_segment[0]['start']
                segment_end = words_in_segment[-1]['end']
                white_line_clip = white_line_clip.set_start(segment_start).set_end(segment_end)
                all_text_clips.append(white_line_clip)

                current_x = line_start_x
                for i, word_info in enumerate(words_in_segment):
                    word_text = word_info["word"].upper()
                    
                    highlight_clip = TextClip(
                        word_text,
                        fontsize=font_size,
                        color=highlight_color,
                        font=font_path
                    ).set_position((current_x, "center"))

                    highlight_clip = highlight_clip.set_start(word_info["start"]).set_end(word_info["end"])
                    all_text_clips.append(highlight_clip)
                    
                    space = " " if i < len(words_in_segment) - 1 else ""
                    sizing_word_clip = TextClip(word_text + space, fontsize=font_size, color="white", font=font_path)
                    current_x += sizing_word_clip.w

            except Exception as e:
                print(f"Skipping segment due to rendering error: {e}")
                continue

        print(f"Generated {len(all_text_clips)} total text clips for compositing.")

        print("Compositing final video...")
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
