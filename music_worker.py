
import modal
import io

# Define the container image for the music generation function
app = modal.App("music-generator-app")

music_generator_image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install(
        "transformers",
        "torch",
        "scipy",
        "modal",
    )
)

@app.function(
    image=music_generator_image,
    gpu="T4",
    timeout=600,
)
def generate_music_modal(lyrics: str):
    """
    Generates a song from lyrics using the Suno Bark model.
    """
    import torch
    from transformers import BarkModel, BarkProcessor
    from scipy.io.wavfile import write as write_wav

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load model and processor
    print("Loading Suno Bark model...")
    model = BarkModel.from_pretrained("suno/bark").to(device)
    processor = BarkProcessor.from_pretrained("suno/bark")
    print("Model loaded.")

    # --- FIX: Wrap lyrics in musical notes to generate a song ---
    prompt = f"♪ {lyrics} ♪"
    print(f"Processing prompt: {prompt}")
    
    voice_preset = "v2/en_speaker_6" # Using a voice preset for better quality
    inputs = processor(prompt, voice_preset=voice_preset, return_tensors="pt").to(device)

    # Generate audio
    print("Generating audio...")
    speech_values = model.generate(**inputs, do_sample=True)
    print("Audio generated.")

    sampling_rate = model.generation_config.sample_rate
    audio_array = speech_values.cpu().numpy().squeeze()

    # Save to an in-memory bytes buffer
    print("Saving audio to buffer...")
    buffer = io.BytesIO()
    write_wav(buffer, sampling_rate, audio_array)
    buffer.seek(0)
    print("Audio saved.")

    return buffer.read()
