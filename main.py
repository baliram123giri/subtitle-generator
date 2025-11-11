from flask import Flask, send_file, abort, request
import modal
import io
import os

app = Flask(__name__)

# Create an output directory if it doesn't exist
os.makedirs("output", exist_ok=True)

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

    # Read file contents into memory
    background_content = background_file.read()
    audio_content = audio_file.read()
    font_content = font_file.read() if font_file else None
    
    # Get the original filename of the background image
    background_filename = background_file.filename

    # Get optional form parameters
    highlight_color = request.form.get('highlight_color', '#FFFF00') # Default to yellow
    font_size = int(request.form.get('font_size', 70))

    try:
        # Look up the deployed Modal function by its name
        f = modal.Function.from_name("subtitle-generator-app", "generate_video_modal")

        # Call the Modal function with the file contents, filename, and other parameters
        print("Calling Modal function with correct background filename...")
        video_content = f.remote(
            background_content,
            audio_content,
            background_filename=background_filename, # Pass the filename
            font_content=font_content,
            highlight_color=highlight_color,
            font_size=font_size
        )
        print("Received video content back from Modal.")

        # Save the video to a file before sending the response
        video_path = "output/output.mp4"
        with open(video_path, "wb") as video_file:
            video_file.write(video_content)
        print(f"Video successfully saved to {video_path}")

        # Send the video file back to the client
        return send_file(
            io.BytesIO(video_content),
            as_attachment=True,
            mimetype='video/mp4',
            download_name='output.mp4'
        )

    except Exception as e:
        print(f"An error occurred while calling the Modal function: {e}")
        abort(500, f"Failed to generate video via Modal: {e}")
    finally:
        print("--- Request Finished ---")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
