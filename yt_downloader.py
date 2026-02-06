import yt_dlp
import os
import time

def download_video(url, output_path, format_type='mp4', quality='720p', 
                  status_dict=None, download_id=None):
    """🚀 FAST Download with REAL progress updates"""
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            # 🔥 REAL PROGRESS from yt-dlp
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if total_bytes:
                progress = int((downloaded_bytes / total_bytes) * 100)
                speed = d.get('speed', '?')
                eta = d.get('eta', '?')
                
                if status_dict and download_id:
                    status_dict[download_id].update({
                        'progress': min(progress, 95),  # Leave room for post-processing
                        'speed': f"{speed/1024:.1f} KB/s" if speed else "0 KB/s",
                        'downloaded': f"{downloaded_bytes/1024/1024:.1f} MB",
                        'total': f"{total_bytes/1024/1024:.1f} MB",
                        'eta': f"{eta//60:02d}:{eta%60:02d}" if eta else "??:??"
                    })
    
    ydl_opts = {
        'outtmpl': output_path,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
    }
    
    # 🎯 Format selection
    if format_type == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # Video formats
        format_map = {
            '360p': 'worst[height<=360]',
            '720p': 'best[height<=720]',
            '1080p': 'best[height<=1080]',
            'best': 'best'
        }
        ydl_opts['format'] = format_map.get(quality, 'best[height<=720]')
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown')
            
            # Detect platform
            platform = 'YouTube'
            if 'instagram' in url.lower():
                platform = 'Instagram'
            elif 'facebook' in url.lower():
                platform = 'Facebook'
            elif 'tiktok' in url.lower():
                platform = 'TikTok'
            elif 'twitter' in url.lower() or 'x.com' in url.lower():
                platform = 'Twitter/X'
            
            # Download
            ydl.download([url])
            
            if os.path.exists(output_path):
                return True, {
                    'title': title,
                    'duration': duration,
                    'uploader': uploader,
                    'platform': platform,
                    'quality': quality,
                }
            
        return False, "Download failed"
        
    except Exception as e:
        return False, f"Error: {str(e)}"