import os
import struct
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import shutil

class HikParser:
    def __init__(self, card_path):
        self.card_path = card_path
        self.header_len = 1280
        self.file_len = 32
        self.segment_len = 80
        self.max_segments = 256
        self.mask = 0x00000000ffffffff

        # Check for FFmpeg installation
        if not shutil.which("ffmpeg"):
            raise RuntimeError("Sisteminizde FFmpeg bulunamadı. Lütfen bilgisayarınıza FFmpeg kurup ortam değişkenlerine (PATH) ekleyin.")

        self.index_file = os.path.join(self.card_path, "index00.bin")
        if not os.path.exists(self.index_file):
            raise FileNotFoundError(f"Could not find index00.bin at {self.card_path}")

        self.header = self._read_header()

    def _read_header(self):
        header_keys = [
            'modifyTimes',
            'version',
            'avFiles',
            'nextFileRecNo',
            'lastFileRecNo',
            'curFileRec',
            'unknown',
            'checksum',
        ]
        unpack_format = "Q 4I 1176s 76s I".replace(' ', '')
        with open(self.index_file, mode='rb') as f:
            byte = f.read(self.header_len)
            if len(byte) < self.header_len:
                raise ValueError("Index file header is corrupted or too short")
            return dict(zip(header_keys, struct.unpack(unpack_format, byte)))

    def get_segments(self, tz_offset=3):
        """Parses the index file and returns all valid video segments.
        tz_offset: Timezone offset in hours (e.g. 3 for Turkey/Istanbul).
        """
        av_files = self.header['avFiles']
        segment_keys = [
            'type', 'status', 'resA', 'resolution',
            'startTime', 'endTime', 'firstKeyFrame_absTime',
            'firstKeyFrame_stdTime', 'lastFrame_stdTime',
            'startOffset', 'endOffset', 'resB', 'infoNum',
            'infoTypes', 'infoStartTime', 'infoEndTime',
            'infoStartOffset', 'infoEndOffset'
        ]
        segment_unpack_format = "s s 2s 4s 3Q 4I 4s 4s 8s 4s 4s 4s 4s".replace(' ', '')
        
        segments = []
        offset = self.header_len + av_files * self.file_len
        
        with open(self.index_file, mode='rb') as f:
            f.seek(offset)
            for file_num in range(av_files):
                for event_num in range(self.max_segments):
                    byte = f.read(self.segment_len)
                    if len(byte) < self.segment_len:
                        break
                    
                    seg = dict(zip(segment_keys, struct.unpack(segment_unpack_format, byte)))
                    start_ts = seg['startTime'] & self.mask
                    end_ts = seg['endTime'] & self.mask
                    
                    if start_ts != 0 and end_ts != 0 and end_ts > start_ts:
                        # Convert UTC timestamps to datetime
                        start_utc = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                        end_utc = datetime.fromtimestamp(end_ts, tz=timezone.utc)
                        
                        # Apply timezone offset to show local time
                        local_tz = timezone(timedelta(hours=tz_offset))
                        start_local = start_utc.astimezone(local_tz)
                        end_local = end_utc.astimezone(local_tz)
                        
                        duration = end_ts - start_ts
                        file_path = os.path.join(self.card_path, f"hiv{file_num:05d}.mp4")
                        
                        segments.append({
                            'id': len(segments),
                            'file_num': file_num,
                            'event_num': event_num,
                            'start_ts': start_ts,
                            'end_ts': end_ts,
                            'start_local': start_local.strftime('%Y-%m-%d %H:%M:%S'),
                            'end_local': end_local.strftime('%Y-%m-%d %H:%M:%S'),
                            'duration': duration,
                            'start_offset': seg['startOffset'],
                            'end_offset': seg['endOffset'],
                            'file_path': file_path,
                            'size_bytes': seg['endOffset'] - seg['startOffset']
                        })
                        
        # Sort chronologically
        segments.sort(key=lambda x: x['start_ts'])
        return segments

    def extract_thumbnail(self, segment, output_path):
        """Extracts a single frame from the start of the segment as a JPEG preview."""
        file_path = segment['file_path']
        start_offset = segment['start_offset']
        
        # Read a 5MB chunk starting at start_offset (contains initialization headers and first keyframe)
        chunk_size = 5 * 1024 * 1024
        
        cmd = f"ffmpeg -f mpeg -i - -vframes 1 -q:v 2 {output_path} -y -hide_banner"
        
        try:
            process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with open(file_path, "rb") as f:
                f.seek(start_offset)
                chunk = f.read(chunk_size)
                try:
                    process.stdin.write(chunk)
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            process.wait()
            return process.returncode == 0 and os.path.exists(output_path)
        except Exception:
            return False

    def export_range(self, start_ts, end_ts, output_dir, file_prefix="hik_export", tz_offset=3, compress=False):
        """Extracts video segments for the given time range and saves them individually in parallel."""
        segments = self.get_segments(tz_offset)
        
        # Find indices of segments that overlap
        overlapping_indices = [i for i, seg in enumerate(segments) if seg['start_ts'] < end_ts and seg['end_ts'] > start_ts]
        
        if not overlapping_indices:
            raise ValueError("No video segments found for the requested time range.")
            
        min_idx = min(overlapping_indices)
        max_idx = max(overlapping_indices)
        
        # Expand range by 1 segment on each side for lossless padding
        start_idx = max(0, min_idx - 1)
        end_idx = min(len(segments) - 1, max_idx + 1)
        
        selected_segments = segments[start_idx : end_idx + 1]
        
        def export_single_segment(seg):
            dt = datetime.fromtimestamp(seg['start_ts'])
            filename = f"{file_prefix}_{dt.strftime('%Y%m%d_%H%M%S')}.mp4"
            output_path = os.path.join(output_dir, filename)
            
            if compress:
                # Transcode to 1080p width-preserving h264 with crf 23 for compression
                cmd = f"ffmpeg -f mpeg -i - -threads auto -vf scale=-2:1080 -c:v libx264 -crf 23 -preset fast -an {output_path} -y -hide_banner"
            else:
                cmd = f"ffmpeg -f mpeg -i - -threads auto -c:v copy -an {output_path} -y -hide_banner"
                
            process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Fast 4MB buffer size
            video_len = 4 * 1024 * 1024
            with open(seg['file_path'], "rb") as vin:
                vin.seek(seg['start_offset'])
                bytes_to_read = seg['size_bytes']
                read_so_far = 0
                try:
                    while read_so_far < bytes_to_read:
                        chunk = vin.read(min(video_len, bytes_to_read - read_so_far))
                        if not chunk:
                            break
                        process.stdin.write(chunk)
                        read_so_far += len(chunk)
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            process.wait()
            
            if process.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
                raise RuntimeError(f"Failed to demux segment {seg['id']}")
                
            return filename

        # Run up to 4 exports in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(export_single_segment, seg) for seg in selected_segments]
            exported_files = [f.result() for f in futures]
            
        return exported_files
