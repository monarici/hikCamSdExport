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

# Global exports directory for exported videos
EXPORTS_DIR = os.path.join(current_dir, 'static', 'exports')
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Store global parser instances to avoid re-reading index00.bin excessively
_parsers = {}

def get_parser(card_path):
    if card_path not in _parsers:
        _parsers[card_path] = HikParser(card_path)
    return _parsers[card_path]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/list_dir', methods=['GET'])
def api_list_dir():
    path = request.args.get('path', '')
    
    if not path:
        # Default starting directory on Linux
        for p in ['/media/technopc', '/media', os.path.expanduser('~'), '/']:
            if os.path.exists(p) and os.path.isdir(p):
                path = p
                break
                
    try:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return jsonify({'error': 'Dizin bulunamadı.'}), 400
        if not os.path.isdir(path):
            return jsonify({'error': 'Belirtilen yol klasör değil.'}), 400
            
        directories = []
        try:
            for item in os.listdir(path):
                # Filter hidden files and system trash
                if item.startswith('.') or item == 'System Volume Information':
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    directories.append(item)
        except PermissionError:
            return jsonify({'error': 'Erişim engellendi.'}), 403
            
        directories.sort(key=str.lower)
        
        parent = os.path.dirname(path)
        if parent == path:
            parent = None
            
        return jsonify({
            'current_path': path,
            'parent_path': parent,
            'directories': directories
        })
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
        compress = data.get('compress', False)
        parser = get_parser(card_path)
        
        # Create a descriptive filename based on requested start time
        dt = datetime.fromtimestamp(start_ts)
        filename = f"hik_export_{dt.strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = os.path.join(EXPORTS_DIR, filename)
        
        success = parser.export_range(start_ts, end_ts, output_path, tz_offset, compress=compress)
        
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
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': "Missing filename"}), 400
    file_path = os.path.join(EXPORTS_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': "File not found"}), 404
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
