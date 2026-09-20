import os
import random
import time
from flask import Flask, request, jsonify
import instaloader
import ffmpeg
import requests

app = Flask(__name__)

# Environment variables configured on Render
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

@app.route("/", methods=["GET"])
def home():
    return "Meme Automation Server is Live!", 200

@app.route("/process-page", methods=["POST"])
def process_page():
    data = request.get_json() or {}
    username = data.get("username")
    last_media_id = data.get("last_media_id")

    if not username:
        return jsonify({"error": "No username provided"}), 400

    print(f"Processing target account: {username}")

    try:
        # 1. Initialize Instaloader to check target page
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)

        # Get recent posts
        posts = []
        for post in profile.get_posts():
            if post.is_video:
                posts.append(post)
            if len(posts) >= 10:
                break

        if not posts:
            return jsonify({"status": "skipped", "message": "No video posts found"}), 200

        # Find post with highest engagement (viral post)
        viral_post = max(posts, key=lambda p: p.video_view_count if p.video_view_count else p.likes)

        # Skip if it's the post we already processed last time
        if str(viral_post.mediaid) == str(last_media_id):
            return jsonify({"status": "skipped", "message": "Post already processed"}), 200

        # 2. Download the post locally
        target_dir = f"downloads_{username}"
        L.download_post(viral_post, target_name=target_dir)

        # Locate downloaded .mp4 file
        input_video = None
        for file in os.listdir(target_dir):
            if file.endswith(".mp4"):
                input_video = os.path.join(target_dir, file)
                break

        if not input_video:
            return jsonify({"error": "Failed to download video file"}), 500

        # 3. Strip metadata completely using FFmpeg
        clean_video = "clean_output.mp4"
        (
            ffmpeg
            .input(input_video)
            .output(clean_video, map_metadata=-1, vcodec="copy", acodec="copy")
            .overwrite_output()
            .run(quiet=True)
        )

        # 4. Return success response to Make
        return jsonify({
            "status": "success",
            "username": username,
            "processed_media_id": str(viral_post.mediaid),
            "caption": viral_post.caption or ""
        }), 200

    except Exception as e:
        print(f"Error processing {username}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
