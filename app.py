import cv2
import numpy as np
import time
import threading
from flask import Flask, Response, render_template, send_file
import json
import csv
from io import BytesIO
from datetime import datetime
import pytz

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

def rgb_to_hsl(rgb):
    r, g, b = [x/255.0 for x in rgb]
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    diff = cmax - cmin
    
    if cmax == cmin:
        h = 0
    elif cmax == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif cmax == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360
    
    l = (cmax + cmin) / 2
    
    if cmax == cmin:
        s = 0
    elif l <= 0.5:
        s = diff / (cmax + cmin)
    else:
        s = diff / (2 - cmax - cmin)
    
    return (int(h), int(s*100), int(l*100))

class ColorAnalyzer:
    def __init__(self, url):
        self.url = url
        self.cap = cv2.VideoCapture(0)
        self.current_colors = [None] * 7
        self.current_frame = None
        self.running = True
        self.color_history = []
        self.max_history_size = 1000
        self.bangkok_tz = pytz.timezone('Asia/Bangkok')

    def analyze_colors(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture frame")
                    time.sleep(1)
                    continue
                
                frame = cv2.flip(frame, 1)
                self.current_frame = frame
                height, width = frame.shape[:2]
                
                zone_width = width // 5
                zone_height = (height // 5) // 7
                start_x = (width - zone_width) // 2
                start_y = (height - (zone_height * 7)) // 2
                
                color_data = []
                timestamp = datetime.now(self.bangkok_tz).strftime('%Y-%m-%d %H:%M:%S')
                for i in range(7):
                    y1 = start_y + i * zone_height
                    y2 = y1 + zone_height
                    section = frame[y1:y2, start_x:start_x+zone_width]
                    avg_color = np.mean(section, axis=(0, 1)).astype(int)
                    self.current_colors[i] = tuple(avg_color)
                    
                    bgr = tuple(avg_color)
                    rgb = tuple(int(x) for x in bgr[::-1])
                    hex_color = rgb_to_hex(rgb)
                    hsl = rgb_to_hsl(rgb)
                    color_data.append({
                        'timestamp': timestamp,
                        'zone': i + 1,
                        'rgb': rgb,
                        'hsl': hsl,
                        'hex': hex_color
                    })
                
                self.color_history.append(color_data)
                if len(self.color_history) > self.max_history_size:
                    self.color_history.pop(0)
                
                time.sleep(0.03)  # ~30 fps
            except Exception as e:
                print(f"Error in color analysis: {e}")
                time.sleep(1)

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

    def get_frame(self):
        if self.current_frame is not None:
            frame = self.current_frame.copy()
            height, width = frame.shape[:2]
            
            zone_width = width // 5
            zone_height = (height // 5) // 7
            start_x = (width - zone_width) // 2
            start_y = (height - (zone_height * 7)) // 2
            
            for i in range(7):
                y1 = start_y + i * zone_height
                y2 = y1 + zone_height
                cv2.rectangle(frame, (start_x, y1), (start_x + zone_width, y2), (255, 0, 0), 2)

            ret, jpeg = cv2.imencode('.jpg', frame)
            return jpeg.tobytes()
        return None

    def get_color_history(self):
        return self.color_history

app = Flask(__name__)
color_analyzer = ColorAnalyzer("rtsp://admin:123456@169.254.74.126:554")

@app.route('/')
def index():
    return render_template('index.html')

def gen_frame():
    while True:
        frame = color_analyzer.get_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frame(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/color_data')
def color_data():
    data = []
    for i, color in enumerate(color_analyzer.current_colors):
        if color is not None:
            bgr = color
            rgb = tuple(int(x) for x in bgr[::-1])
            hex_color = rgb_to_hex(rgb)
            hsl = rgb_to_hsl(rgb)
            data.append({
                'zone': i + 1,
                'rgb': rgb,
                'hsl': hsl,
                'hex': hex_color
            })
    return json.dumps(data)

@app.route('/export_csv')
def export_csv():
    color_history = color_analyzer.get_color_history()
    
    output = BytesIO()
    output.write(b'Timestamp,Zone,RGB,HSL,HEX\n')
    
    for color_data in color_history:
        for zone_data in color_data:
            row = f"{zone_data['timestamp']},{zone_data['zone']},{zone_data['rgb']},{zone_data['hsl']},{zone_data['hex']}\n"
            output.write(row.encode('utf-8'))
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name='color_data.csv'
    )

if __name__ == '__main__':
    analysis_thread = threading.Thread(target=color_analyzer.analyze_colors)
    analysis_thread.start()
    app.run(host='0.0.0.0', port=3000, debug=True)
    color_analyzer.stop()
    analysis_thread.join()