import numpy as np
import cv2
import sys
from dash import Dash, dcc, html, Input, Output
import threading
from flask import Response, request
import time

# Initialize the Dash app
app = Dash(__name__)
app.title = "Real-Time Video with Color Masking"

# Color ranges for different colors (in HSV)
color_ranges = {
    "Red": ([0, 120, 70], [10, 255, 255], [170, 120, 70], [180, 255, 255]),
    "Green": ([35, 100, 100], [85, 255, 255]),
    "Blue": ([94, 80, 2], [126, 255, 255]),
    "Yellow": ([20, 100, 100], [30, 255, 255]),
    "Cyan": ([80, 100, 100], [90, 255, 255]),
    "Magenta": ([125, 100, 100], [150, 255, 255]),
    "Orange": ([10, 100, 100], [20, 255, 255]),
    "Purple": ([130, 50, 50], [160, 255, 255]),
    "Pink": ([160, 50, 50], [170, 255, 255]),
    "Brown": ([10, 100, 50], [20, 150, 100]),
}

# Video capture setup
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open video stream.")
    sys.exit()

background = None
running = True

# Read the background frame for invisibility effect
def capture_background():
    global background
    for _ in range(50):
        ret, frame = cap.read()
        if ret:
            background = frame

capture_background()

# Flask endpoint for video streaming
def generate_video(selected_color):
    global running
    while running:
        ret, img = cap.read()
        if not ret or background is None:
            continue

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Get the HSV range for the selected color
        ranges = color_ranges[selected_color]
        if len(ranges) == 4:
            lower1, upper1, lower2, upper2 = ranges
            mask1 = cv2.inRange(hsv, np.array(lower1), np.array(upper1))
            mask2 = cv2.inRange(hsv, np.array(lower2), np.array(upper2))
            mask = mask1 + mask2
        else:
            lower, upper = ranges
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))

        # Apply morphological operations
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((3, 3), np.uint8), iterations=1)

        # Invert the mask
        inverse_mask = cv2.bitwise_not(mask)

        # Combine background and current frame based on masks
        res1 = cv2.bitwise_and(background, background, mask=mask)
        res2 = cv2.bitwise_and(img, img, mask=inverse_mask)
        final_output = cv2.addWeighted(res1, 1, res2, 1, 0)

        # Encode the frame to JPEG format
        _, buffer = cv2.imencode('.jpg', final_output)
        frame = buffer.tobytes()

        # Serve the frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Layout for the Dash app
app.layout = html.Div([
    html.H1("Real-Time Video with Color Masking", style={"textAlign": "center"}),
    dcc.Dropdown(
        id="color-dropdown",
        options=[{"label": color, "value": color} for color in color_ranges.keys()],
        value="Red",
        clearable=False,
        style={"width": "50%", "margin": "auto"}
    ),
    html.Div([
        html.Img(id="video-feed", style={"maxWidth": "100%", "height": "auto"})
    ], style={"textAlign": "center"}),
])

# Callback to update the video feed URL
@app.callback(
    Output("video-feed", "src"),
    [Input("color-dropdown", "value")]
)
def update_video_feed(selected_color):
    return f"/video_feed?color={selected_color}"

@app.server.route("/video_feed")
def video_feed():
    color = request.args.get("color", "Red")
    return Response(generate_video(color), mimetype="multipart/x-mixed-replace; boundary=frame")

# Function to stop the app and release resources
def stop_server():
    global running
    running = False
    cap.release()
    print("Application stopped.")

# Run the Dash app in a separate thread
def run_dash_app():
    app.run_server(debug=True, use_reloader=False)

if __name__ == "__main__":
    # Start the Dash app in a separate thread
    threading.Thread(target=run_dash_app).start()

    try:
        # Keep the main program running until interrupted
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_server()
