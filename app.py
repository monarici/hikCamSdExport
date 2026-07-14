import os
import sys
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from datetime import datetime

# Add current folder to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from hik_parser import HikParser

app = Flask(__name__, template_folder=os.path.join(current_dir, 'templates'), static_folder=os.path.join(current_dir, 'static'))

# Global cache directory for thumbnails
CACHE_DIR = os.path.join(current_dir, 'static', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Store global parser instances to avoid re-reading index00.bin excessively
_parsers = {}

def get_parser(card_path):
    if card_path not in _parsers:
        _parsers[card_path] = HikParser(card_path)
    return _parsers[card_path]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/browse', methods=['GET'])
def api_browse():
    import subprocess
    try:
        # Run folder picker in a separate python process to ensure GUI main-thread safety
        script = "import tkinter as tk; from tkinter import filedialog; r=tk.Tk(); r.withdraw(); r.attributes('-topmost', True); print(filedialog.askdirectory(title='Hikvision SD Kart Klasörünü Seçin'))"
        res = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=120)
        
        if res.returncode == 0:
            selected_path = res.stdout.strip()
            if selected_path:
                return jsonify({'path': selected_path})
            else:
                return jsonify({'path': None})
        else:
            stderr = res.stderr.strip()
            error_msg = "Klasör seçici penceresi açılamadı."
            if "No module named '_tkinter'" in stderr or "ModuleNotFoundError" in stderr:
                error_msg = "Sisteminizde Python GUI (Tkinter) modülü kurulu değil. Lütfen terminalde 'sudo apt install python3-tk' çalıştırıp sunucuyu yeniden başlatın."
            elif "couldn't connect to display" in stderr or "DISPLAY" in stderr:
                error_msg = "Grafik ekran (X11/Wayland DISPLAY) bağlantısı kurulamadı. SSH ortamında gözat çalışmaz, lütfen yolu manuel girin."
            else:
                error_msg += f" Detay: {stderr}"
            return jsonify({'error': error_msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan', methods=['GET'])
def api_scan():
    card_path = request.args.get('card_path', '/media/technopc/0000-017B')
    tz_offset = int(request.args.get('tz_offset', 0))
    
    if not os.path.exists(card_path):
        return jsonify({'error': f"Card directory '{card_path}' does not exist."}), 400
        
    try:
        parser = get_parser(card_path)
        segments = parser.get_segments(tz_offset=tz_offset)
        return jsonify({
            'card_path': card_path,
            'tz_offset': tz_offset,
            'segments_count': len(segments),
            'segments': [
                {
                    'id': s['id'],
                    'file_num': s['file_num'],
                    'start_local': s['start_local'],
                    'end_local': s['end_local'],
                    'start_ts': s['start_ts'],
                    'end_ts': s['end_ts'],
                    'duration_sec': s['duration'],
                    'size_mb': round(s['size_bytes'] / (1024 * 1024), 2)
                } for s in segments
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/thumbnail/<int:segment_id>', methods=['GET'])
def api_thumbnail(segment_id):
    card_path = request.args.get('card_path', '/media/technopc/0000-017B')
    
    try:
        parser = get_parser(card_path)
        segments = parser.get_segments()
        
        # Find the requested segment
        segment = next((s for s in segments if s['id'] == segment_id), None)
        if not segment:
            return jsonify({'error': f"Segment ID {segment_id} not found."}), 404
            
        thumb_filename = f"segment_{segment_id}.jpg"
        thumb_path = os.path.join(CACHE_DIR, thumb_filename)
        
        # Generate thumbnail if not already cached
        if not os.path.exists(thumb_path):
            success = parser.extract_thumbnail(segment, thumb_path)
            if not success:
                return jsonify({'error': "Failed to extract thumbnail"}), 500
                
        return send_from_directory(CACHE_DIR, thumb_filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['POST'])
def api_export():
    data = request.json or {}
    card_path = data.get('card_path', '/media/technopc/0000-017B')
    start_ts = data.get('start_ts')
    end_ts = data.get('end_ts')
    tz_offset = int(data.get('tz_offset', 0))
    
    if start_ts is None or end_ts is None:
        return jsonify({'error': "Missing start_ts or end_ts"}), 400
        
    try:
        parser = get_parser(card_path)
        
        # Determine output folder
        # We save directly to the Downloads directory of user for convenience,
        # or in our local scratch area as a fallback.
        downloads_dir = "/home/technopc/Downloads"
        if not os.path.exists(downloads_dir):
            downloads_dir = os.path.join(current_dir, 'static', 'exports')
            
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Create a descriptive filename based on requested start time
        dt = datetime.fromtimestamp(start_ts)
        filename = f"hik_export_{dt.strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = os.path.join(downloads_dir, filename)
        
        success = parser.export_range(start_ts, end_ts, output_path, tz_offset)
        
        if success:
            return jsonify({
                'success': True,
                'output_path': output_path,
                'filename': filename,
                'size_mb': round(os.path.getsize(output_path) / (1024 * 1024), 2)
            })
        else:
            return jsonify({'error': "Export failed"}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def api_download():
    file_path = request.args.get('path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': "File not found"}), 404
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
