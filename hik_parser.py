import os
import struct
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

class HikParser:
    def __init__(self, card_path):
        self.card_path = card_path
        self.header_len = 1280
        self.file_len = 32
        self.segment_len = 80
        self.max_segments = 256
        self.mask = 0x00000000ffffffff

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

    def export_range(self, start_ts, end_ts, output_path, tz_offset=3):
        """Extracts and merges video data for the given UTC unix timestamp range."""
        segments = self.get_segments(tz_offset)
        overlapping = []
        
        for seg in segments:
            if seg['start_ts'] < end_ts and seg['end_ts'] > start_ts:
                overlapping.append(seg)
                
        if not overlapping:
            raise ValueError("No video segments found for the requested time range.")
            
        temp_files = []
        
        try:
            for idx, seg in enumerate(overlapping):
                # Calculate portion of segment to extract
                clip_start = max(start_ts, seg['start_ts'])
                clip_end = min(end_ts, seg['end_ts'])
                clip_duration = clip_end - clip_start
                
                seg_dur = seg['duration']
                seg_size = seg['size_bytes']
                seg_start_offset = seg['start_offset']
                
                start_ratio = (clip_start - seg['start_ts']) / seg_dur
                end_ratio = (clip_end - seg['start_ts']) / seg_dur
                
                est_start = seg_start_offset + int(start_ratio * seg_size)
                est_end = seg_start_offset + int(end_ratio * seg_size)
                
                # Add safety margin of 60 seconds (clamp to segment boundaries)
                safety_time = 60
                safety_bytes = int((safety_time / seg_dur) * seg_size) if seg_dur > 0 else 0
                
                read_start = max(seg_start_offset, est_start - safety_bytes)
                read_end = min(seg['end_offset'], est_end + safety_bytes)
                
                # Estimate starting timestamp of our read block
                chunk_start_ts = seg['start_ts'] + (read_start - seg_start_offset) / seg_size * seg_dur
                ffmpeg_ss = max(0.0, clip_start - chunk_start_ts)
                
                # Temporary file for this part
                fd, temp_mp4 = tempfile.mkstemp(suffix=".mp4")
                os.close(fd)
                temp_files.append(temp_mp4)
                
                cmd = f"ffmpeg -f mpeg -i - -threads auto -ss {ffmpeg_ss:.2f} -t {clip_duration:.2f} -c:v copy -an {temp_mp4} -y -hide_banner"
                
                process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                video_len = 65536
                with open(seg['file_path'], "rb") as vin:
                    vin.seek(read_start)
                    bytes_to_read = read_end - read_start
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
                
                if process.returncode != 0 or not os.path.exists(temp_mp4) or os.path.getsize(temp_mp4) < 1000:
                    # Fallback to copy entire segment if linear interpolation clipping fails
                    # (could happen if header packet is missed)
                    print(f"Sub-segment extraction failed. Falling back to whole-segment demux for segment {seg['id']}")
                    cmd_fallback = f"ffmpeg -f mpeg -i - -threads auto -ss {clip_start - seg['start_ts']:.2f} -t {clip_duration:.2f} -c:v copy -an {temp_mp4} -y -hide_banner"
                    process_fb = subprocess.Popen(cmd_fallback, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    with open(seg['file_path'], "rb") as vin:
                        vin.seek(seg_start_offset)
                        bytes_to_read = seg_size
                        read_so_far = 0
                        try:
                            while read_so_far < bytes_to_read:
                                chunk = vin.read(min(video_len, bytes_to_read - read_so_far))
                                if not chunk:
                                    break
                                process_fb.stdin.write(chunk)
                                read_so_far += len(chunk)
                            process_fb.stdin.close()
                        except BrokenPipeError:
                            pass
                    process_fb.wait()

            # Merge files
            if len(temp_files) == 1:
                # Only 1 segment, rename directly
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_files[0], output_path)
                temp_files = []
            else:
                # Create concat list
                concat_list_path = temp_mp4 + "_concat.txt"
                with open(concat_list_path, "w") as f_concat:
                    for tf in temp_files:
                        f_concat.write(f"file '{tf}'\n")
                        
                cmd_concat = f"ffmpeg -f concat -safe 0 -i {concat_list_path} -c copy {output_path} -y -hide_banner"
                res = subprocess.run(cmd_concat, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                os.remove(concat_list_path)
                if res.returncode != 0:
                    raise RuntimeError(f"Concat failed: {res.stderr.decode()}")
                    
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            
        finally:
            # Clean up temp files
            for tf in temp_files:
                if os.path.exists(tf):
                    os.remove(tf)
