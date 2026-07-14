#!/usr/bin/env python3
import os
import sys
import struct
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# ANSI color codes for premium CLI interface
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"{CYAN}{BOLD}==================================================")
    print("      HIKVISION SD CARD SEGMENT EXTRACTOR CLI")
    print(f"=================================================={RESET}")

def parse_datetime(dt_str):
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def find_index_file():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(current_dir, "index00.bin")
    if os.path.exists(index_path):
        return current_dir, index_path
    
    # Fallback to current working directory
    cwd = os.getcwd()
    index_path_cwd = os.path.join(cwd, "index00.bin")
    if os.path.exists(index_path_cwd):
        return cwd, index_path_cwd
        
    return None, None

def get_segments(card_path, index_file, tz_offset=3):
    header_len = 1280
    file_len = 32
    segment_len = 80
    max_segments = 256
    mask = 0x00000000ffffffff
    
    header_keys = ['modifyTimes', 'version', 'avFiles', 'nextFileRecNo', 'lastFileRecNo', 'curFileRec', 'unknown', 'checksum']
    unpack_format = "Q4I1176s76sI"
    
    with open(index_file, mode='rb') as f:
        byte = f.read(header_len)
        if len(byte) < header_len:
            raise ValueError("index00.bin dosyası bozuk veya çok kısa.")
        header = dict(zip(header_keys, struct.unpack(unpack_format, byte)))
        
    av_files = header['avFiles']
    segment_keys = [
        'type', 'status', 'resA', 'resolution',
        'startTime', 'endTime', 'firstKeyFrame_absTime',
        'firstKeyFrame_stdTime', 'lastFrame_stdTime',
        'startOffset', 'endOffset', 'resB', 'infoNum',
        'infoTypes', 'infoStartTime', 'infoEndTime',
        'infoStartOffset', 'infoEndOffset'
    ]
    segment_unpack_format = "ss2s4s3Q4I4s4s8s4s4s4s4s"
    
    segments = []
    offset = header_len + av_files * file_len
    
    with open(index_file, mode='rb') as f:
        f.seek(offset)
        for file_num in range(av_files):
            for event_num in range(max_segments):
                byte = f.read(segment_len)
                if len(byte) < segment_len:
                    break
                
                seg = dict(zip(segment_keys, struct.unpack(segment_unpack_format, byte)))
                start_ts = seg['startTime'] & mask
                end_ts = seg['endTime'] & mask
                
                if start_ts != 0 and end_ts != 0 and end_ts > start_ts:
                    start_utc = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                    end_utc = datetime.fromtimestamp(end_ts, tz=timezone.utc)
                    
                    local_tz = timezone(timedelta(hours=tz_offset))
                    start_local = start_utc.astimezone(local_tz)
                    end_local = end_utc.astimezone(local_tz)
                    
                    file_path = os.path.join(card_path, f"hiv{file_num:05d}.mp4")
                    
                    segments.append({
                        'id': len(segments),
                        'file_num': file_num,
                        'start_ts': start_ts,
                        'end_ts': end_ts,
                        'start_local': start_local.replace(tzinfo=None),
                        'end_local': end_local.replace(tzinfo=None),
                        'start_offset': seg['startOffset'],
                        'end_offset': seg['endOffset'],
                        'file_path': file_path,
                        'size_bytes': seg['endOffset'] - seg['startOffset']
                    })
                    
    segments.sort(key=lambda x: x['start_ts'])
    return segments

def copy_segment(seg, output_dir, file_prefix, has_ffmpeg):
    dt = seg['start_local']
    filename = f"{file_prefix}_{dt.strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(output_dir, filename)
    
    print(f"{YELLOW}[+] Dışarı aktarılıyor: {filename} ({seg['size_bytes'] / (1024*1024):.1f} MB)...{RESET}")
    
    if has_ffmpeg:
        # Use lossless stream copy via FFmpeg (standard mp4 container packaging)
        nice_prefix = "nice -n 15 " if os.name != 'nt' else ""
        cmd = f"{nice_prefix}ffmpeg -f mpeg -i - -threads 1 -c:v copy -an \"{output_path}\" -y -hide_banner"
        process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
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
        success = process.returncode == 0 and os.path.exists(output_path)
    else:
        # Fallback to direct raw binary chunk copy (extremely fast, no dependencies)
        video_len = 4 * 1024 * 1024
        with open(seg['file_path'], "rb") as vin:
            vin.seek(seg['start_offset'])
            bytes_to_read = seg['size_bytes']
            read_so_far = 0
            with open(output_path, "wb") as vout:
                while read_so_far < bytes_to_read:
                    chunk = vin.read(min(video_len, bytes_to_read - read_so_far))
                    if not chunk:
                        break
                    vout.write(chunk)
                    read_so_far += len(chunk)
        success = os.path.exists(output_path)
        
    if success:
        print(f"{GREEN}[✓] Tamamlandı: {filename}{RESET}")
        return filename
    else:
        print(f"{RED}[✗] Hata: {filename} kopyalanamadı.{RESET}")
        return None

def main():
    print_banner()
    
    card_path, index_file = find_index_file()
    if not index_file:
        print(f"{RED}[!] Hata: Bulunduğunuz dizinde 'index00.bin' dosyası bulunamadı.{RESET}")
        print("Lütfen bu betiği SD kartın içinde veya kayıt dosyalarının olduğu dizinde çalıştırın.")
        sys.exit(1)
        
    print(f"{GREEN}[i] SD Kart dizini algılandı: {card_path}{RESET}")
    
    try:
        segments = get_segments(card_path, index_file)
        print(f"{GREEN}[i] Toplam {len(segments)} adet video segmenti başarıyla dizinlendi.{RESET}")
    except Exception as e:
        print(f"{RED}[!] Dizinleme hatası: {e}{RESET}")
        sys.exit(1)
        
    # Get datetime inputs
    print(f"\n{BOLD}Tarih/Saat Aralığı Girin (Format: YYYY-MM-DD HH:MM:SS){RESET}")
    
    while True:
        start_str = input(f"{CYAN}Başlangıç Tarih ve Saati:{RESET} ").strip()
        start_dt = parse_datetime(start_str)
        if start_dt:
            break
        print(f"{RED}[!] Geçersiz format. Lütfen '2026-06-13 10:00:00' şeklinde girin.{RESET}")
        
    while True:
        end_str = input(f"{CYAN}Bitiş Tarih ve Saati:    {RESET} ").strip()
        end_dt = parse_datetime(end_str)
        if end_dt:
            if end_dt > start_dt:
                break
            print(f"{RED}[!] Bitiş tarihi başlangıç tarihinden sonra olmalıdır.{RESET}")
        else:
            print(f"{RED}[!] Geçersiz format. Lütfen '2026-06-13 14:00:00' şeklinde girin.{RESET}")
            
    # Filter segments
    selected_segments = [
        seg for seg in segments 
        if seg['start_local'] < end_dt and seg['end_local'] > start_dt
    ]
    
    if not selected_segments:
        print(f"\n{YELLOW}[!] Seçilen tarih aralığında hiçbir video segmenti bulunamadı.{RESET}")
        sys.exit(0)
        
    print(f"\n{GREEN}[i] Bu aralıkta {len(selected_segments)} adet video segmenti bulundu.{RESET}")
    
    # Get output directory
    while True:
        output_dir = input(f"\n{CYAN}Kopyalanacak Hedef Klasör Yolu:{RESET} ").strip()
        if not output_dir:
            print(f"{RED}[!] Yol boş olamaz.{RESET}")
            continue
        output_dir = os.path.abspath(output_dir)
        try:
            os.makedirs(output_dir, exist_ok=True)
            break
        except Exception as e:
            print(f"{RED}[!] Klasör oluşturulamadı: {e}{RESET}")
            
    # Get file prefix
    file_prefix = input(f"{CYAN}Dosya Önadı (Varsayılan: 'hik_export'):{RESET} ").strip()
    if not file_prefix:
        file_prefix = "hik_export"
        
    has_ffmpeg = bool(shutil.which("ffmpeg"))
    if not has_ffmpeg:
        print(f"\n{YELLOW}[!] Uyarı: Sistemde FFmpeg bulunamadı. Ham binary kopyalama yöntemi kullanılacaktır.{RESET}")
        print(f"{YELLOW}    (Oluşturulan dosyalar VLC Player ile sorunsuz oynatılabilir).{RESET}")
    else:
        print(f"\n{GREEN}[i] FFmpeg algılandı. Dosyalar kayıpsız MP4 paketlemesi ile kopyalanacaktır.{RESET}")
        
    print(f"\n{BOLD}{CYAN}Kopyalama işlemi başlatılıyor...{RESET}\n")
    
    success_count = 0
    # Run copy operations in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(copy_segment, seg, output_dir, file_prefix, has_ffmpeg) for seg in selected_segments]
        results = [f.result() for f in futures]
        success_count = len([r for r in results if r is not None])
        
    print(f"\n{GREEN}{BOLD}==================================================")
    print(f"               İŞLEM TAMAMLANDI!")
    print(f"  Başarılı Kopya: {success_count} / {len(selected_segments)}")
    print(f"  Hedef Klasör  : {output_dir}")
    print(f"=================================================={RESET}\n")

if __name__ == "__main__":
    main()
