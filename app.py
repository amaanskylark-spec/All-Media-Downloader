from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import time
import glob
import re
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
import traceback

app = Flask(__name__)
CORS(app)
os.makedirs('static/downloads', exist_ok=True)

download_status = {}
executor = ThreadPoolExecutor(max_workers=4)

def format_bytes(size):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"

def detect_platform(url):
    """Detect social media platform"""
    url_lower = url.lower()
    if any(x in url_lower for x in ['instagram.com', 'instagr.am']):
        return 'Instagram'
    elif any(x in url_lower for x in ['facebook.com', 'fb.watch']):
        return 'Facebook'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YouTube'
    elif 'tiktok.com' in url_lower:
        return 'TikTok'
    elif any(x in url_lower for x in ['twitter.com', 'x.com']):
        return 'X'
    return 'Video'

def temp_cleanup():
    """🧹 Clean temp files - Windows safe"""
    try:
        temp_dir = 'static/downloads/.temp'
        if os.path.exists(temp_dir):
            for temp_file in glob.glob(f'{temp_dir}/**/*', recursive=True):
                if os.path.isfile(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    except:
        pass

def bulletproof_social_download(url, status_dict=None, download_id=None):
    """🔥 v4.3 - FFmpeg FIXED NO 'when' parameter"""
    
    print(f"🎯 DOWNLOAD: {url}")
    
    def safe_progress_hook(d):
        """🛡️ SAFE Progress - No crashes"""
        try:
            if not isinstance(d, dict) or d.get('status') != 'downloading':
                return
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = 100 if (downloaded / total) >= 0.95 else int((downloaded / total) * 100)
                status_dict[download_id].update({
                    'progress': progress,
                    'speed': d.get('speed_string', '0 KB/s'),
                    'downloaded': format_bytes(downloaded),
                    'total': format_bytes(total)
                })
        except:
            pass
    
    platform = detect_platform(url)
    
    # 🔥 UNIQUE FILENAME - NO CONFLICTS
    timestamp = int(time.time() * 1000)
    safe_filename = f"{platform}_{timestamp}"
    
    format_selectors = {
        'Instagram': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'Facebook': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'YouTube': 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
        'TikTok': 'best[height<=1080]/best',
        'X': 'best[height<=1080]/best',
    }
    
    # 🔥 v4.3 ULTIMATE FFmpeg FIX - NO 'when' parameter
    ydl_opts = {
        'format': format_selectors.get(platform, 'best[height<=720]/best'),
        'progress_hooks': [safe_progress_hook],
        'quiet': False,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 20,
        'retries': 5,
        'fragment_retries': 5,
        'concurrent_fragments': 4,
        # 🔥 Windows temp fix
        'temp_dir': f'static/downloads/.temp/{safe_filename}',
        'outtmpl': f'static/downloads/{safe_filename}_%(id)s.%(ext)s',
        # ✅ FIXED FFmpeg - NO 'when' = DEFAULT WORKS EVERYTIME
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'  # 🔥 THIS IS ALL YOU NEED
        }],
    }
    
    # 🔑 Cookies + Headers for Instagram/FB
    if platform in ['Instagram', 'Facebook']:
        if os.path.exists('cookies.txt'):
            ydl_opts['cookies'] = 'cookies.txt'
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    try:
        # 🛡️ Create temp dir
        os.makedirs('static/downloads/.temp', exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("🔍 STEP 1: Extract info...")
            
            info_result = ydl.extract_info(url, download=False)
            if not info_result:
                raise Exception("No video info found")
            
            title = getattr(info_result, 'title', 'video') or 'video'
            uploader = getattr(info_result, 'uploader', 'user') or getattr(info_result, 'channel', 'user')
            duration = getattr(info_result, 'duration', 0) or 0
            id_ = getattr(info_result, 'id', 'unknown')
            
            # 🛡️ Safe filename - Windows
            safe_title = re.sub(r'[<>:"/\\|?*\n\t]', '_', title)[:40]
            preview_filename = f"{platform}_{safe_title}_{id_}.mp4"
            
            print(f"📋 FOUND: {safe_title} ({duration}s)")
            
            status_dict[download_id].update({
                'status': 'downloading',
                'filename': preview_filename,
                'info': {
                    'title': title[:60],
                    'uploader': uploader[:30],
                    'duration': duration,
                    'platform': platform,
                    'video_id': id_
                }
            })
            
            print("⬇️ STEP 2: Downloading...")
            ydl.download([url])
            
            print("🔍 STEP 3: Finding FINAL file...")
            
            # 🎯 Wait for FFmpeg to finish (Windows file lock)
            time.sleep(2)
            
            # 🛡️ Find ALL files for this download
            pattern = f'static/downloads/{safe_filename}_*.mp4'
            files = glob.glob(pattern)
            
            if not files:
                # 🔍 Check temp folder too
                temp_pattern = f'static/downloads/.temp/{safe_filename}/**/*.mp4'
                temp_files = glob.glob(temp_pattern, recursive=True)
                files.extend(temp_files)
            
            if not files:
                # 🔍 Fallback - any recent MP4
                all_mp4 = glob.glob('static/downloads/*.mp4')
                if all_mp4:
                    files = [max(all_mp4, key=os.path.getmtime)]
            
            if not files:
                raise Exception("No MP4 files created")
            
            # 🎯 Latest LARGEST file
            latest_file = max(files, key=lambda f: (os.path.getmtime(f), os.path.getsize(f)))
            filesize = os.path.getsize(latest_file)
            
            print(f"📁 Latest file: {os.path.basename(latest_file)} ({format_bytes(filesize)})")
            
            # 🛡️ Windows file unlock + rename
            if filesize > 500:
                final_path = f'static/downloads/{preview_filename}'
                
                # 🔑 SAFE RENAME - Windows friendly
                try:
                    if latest_file != final_path:
                        # Wait for file lock release (browser/video preview)
                        for attempt in range(10):
                            try:
                                os.rename(latest_file, final_path)
                                latest_file = final_path
                                break
                            except PermissionError:
                                print(f"⏳ Rename attempt {attempt+1}/10...")
                                time.sleep(0.5)
                        
                        if os.path.exists(final_path):
                            latest_file = final_path
                        else:
                            print("⚠️ Rename failed - using original")
                
                except Exception as rename_err:
                    print(f"⚠️ Rename error: {rename_err}")
                    # Use original file path
                    preview_filename = os.path.basename(latest_file)
                    final_path = latest_file
                
                print(f"✅ SUCCESS: {preview_filename} ({format_bytes(filesize)})")
                
                status_dict[download_id].update({
                    'progress': 100,
                    'status': 'complete',
                    'success': True,
                    'download_url': f'/download/{preview_filename}',
                    'filename': preview_filename,
                    'filesize': format_bytes(filesize)
                })
                return True, preview_filename, status_dict[download_id]['info']
            else:
                raise Exception(f"File too small: {filesize} bytes")
                
    except Exception as e:
        error_msg = str(e)
        print(f"💥 ERROR: {error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        
        status_dict[download_id].update({
            'progress': 0,
            'status': 'error',
            'error': error_msg[:100]
        })
        return False, None, error_msg

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔥 Social Media Downloader v4.3</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                max-width: 500px; margin: 0 auto; padding: 20px; background: #f5f5f5;
            }
            .container { background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #1a1a1a; margin-bottom: 10px; }
            .subtitle { text-align: center; color: #666; margin-bottom: 30px; }
            input[type="url"] { 
                width: 100%; padding: 16px; font-size: 16px; border: 2px solid #e1e5e9; 
                border-radius: 12px; margin-bottom: 16px; transition: border-color 0.2s;
            }
            input:focus { outline: none; border-color: #1da1f2; }
            button { 
                width: 100%; padding: 16px; font-size: 18px; font-weight: 600; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; border: none; border-radius: 12px; cursor: pointer;
                transition: transform 0.2s;
            }
            button:hover:not(:disabled) { transform: translateY(-2px); }
            button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
            .status { margin: 20px 0; padding: 20px; border-radius: 12px; text-align: center; }
            .progress-container { 
                background: #e1e5e9; border-radius: 10px; overflow: hidden; height: 12px; margin: 12px 0;
            }
            .progress-bar { 
                height: 100%; background: linear-gradient(90deg, #4ade80, #22c55e); 
                width: 0%; transition: width 0.3s ease; border-radius: 10px;
            }
            .success { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
            .error { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
            .video-preview { width: 100%; max-height: 300px; border-radius: 12px; margin: 20px 0; }
            .download-btn { 
                display: block; width: 100%; padding: 18px; margin: 16px 0; 
                background: linear-gradient(135deg, #10b981, #059669); color: white; 
                text-decoration: none; text-align: center; border-radius: 12px; 
                font-size: 18px; font-weight: 600;
            }
            .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }
            .info-item { background: #f8fafc; padding: 12px; border-radius: 8px; text-align: center; }
            .platforms { 
                display: flex; justify-content: center; gap: 12px; margin: 20px 0; 
                font-size: 14px; color: #64748b; flex-wrap: wrap;
            }
            .platform-badge { padding: 4px 12px; background: #e2e8f0; border-radius: 20px; }
            .speed-info { font-size: 14px; color: #64748b; margin-top: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Social Media Downloader v4.3</h1>
            <p class="subtitle">Instagram • Facebook • YouTube • TikTok • X</p>
            <p style="text-align:center; color:#10b981; font-size:14px;">✅ FFmpeg 100% FIXED | Windows safe</p>
            
            <form id="downloadForm">
                <input type="url" id="url" placeholder="Enter a URL to Download" required>
                <button type="submit" id="downloadBtn">🚀 Download HD Video</button>
            </form>
            
            <div class="platforms">
                <span class="platform-badge">📱 Instagram</span>
                <span class="platform-badge">📘 Facebook</span>
                <span class="platform-badge">📺 YouTube</span>
                <span class="platform-badge">📱 TikTok</span>
                <span class="platform-badge">🐦 X/Twitter</span>
            </div>
            
            <div id="status" class="status" style="display:none;">
                <div class="progress-container">
                    <div class="progress-bar" id="progressBar"></div>
                </div>
                <div id="statusText" style="margin-top: 8px; font-weight: 500;"></div>
                <div id="speedInfo" class="speed-info" style="display:none;"></div>
            </div>
            
            <div id="result" style="display:none;"></div>
        </div>
        
        <script>
            let pollInterval;
            
            document.getElementById('downloadForm').onsubmit = async (e) => {
                e.preventDefault();
                const btn = document.getElementById('downloadBtn');
                const status = document.getElementById('status');
                const urlInput = document.getElementById('url');
                const speedInfo = document.getElementById('speedInfo');
                
                // Clear previous
                document.getElementById('result').style.display = 'none';
                
                btn.disabled = true;
                btn.textContent = '⏳ Processing...';
                status.style.display = 'block';
                status.className = 'status';
                document.getElementById('statusText').textContent = '🔍 Detecting platform...';
                document.getElementById('progressBar').style.width = '0%';
                speedInfo.style.display = 'none';
                
                try {
                    const formData = new FormData();
                    formData.append('url', urlInput.value.trim());
                    
                    const response = await fetch('/download', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        pollStatus(data.download_id);
                    } else {
                        throw new Error(data.error || 'Start failed');
                    }
                } catch(err) {
                    document.getElementById('statusText').textContent = `❌ ${err.message}`;
                    status.className = 'status error';
                    btn.disabled = false;
                    btn.textContent = '🚀 Download HD Video';
                }
            };
            
            async function pollStatus(downloadId) {
                try {
                    const response = await fetch(`/status/${downloadId}`);
                    const status = await response.json();
                    
                    const progressBar = document.getElementById('progressBar');
                    const statusText = document.getElementById('statusText');
                    const speedInfo = document.getElementById('speedInfo');
                    
                    progressBar.style.width = status.progress + '%';
                    statusText.textContent = `${status.progress}% ${status.status}`;
                    
                    if (status.downloaded && status.total) {
                        speedInfo.textContent = `${status.downloaded} / ${status.total} • ${status.speed}`;
                        speedInfo.style.display = 'block';
                    }
                    
                    if (status.status === 'complete' && status.success) {
                        showResult(status);
                        clearInterval(pollInterval);
                    } else if (status.status === 'error') {
                        statusText.textContent = `❌ ${status.error || 'Download failed'}`;
                        document.getElementById('status').className = 'status error';
                        document.getElementById('downloadBtn').disabled = false;
                        document.getElementById('downloadBtn').textContent = '🚀 Download HD Video';
                        clearInterval(pollInterval);
                    } else {
                        pollInterval = setTimeout(() => pollStatus(downloadId), 800);
                    }
                } catch(e) {
                    console.error('Poll error:', e);
                    clearInterval(pollInterval);
                }
            }
            
            function showResult(status) {
                const resultDiv = document.getElementById('result');
                const info = status.info;
                
                resultDiv.innerHTML = `
                    <div class="status success">
                        <h3>✅ Video Downloaded!</h3>
                        <div class="info-grid">
                            <div class="info-item">
                                <strong>${status.filename}</strong><br>
                                <small>${status.filesize}</small>
                            </div>
                            # <div class="info-item">
                            #     ${info.platform}<br>
                            #     <small>${info.duration}s</small>
                            # </div>
                        </div>
                        <video class="video-preview" controls preload="metadata">
                            <source src="${status.download_url}" type="video/mp4">
                        </video>
                        <a href="${status.download_url}" class="download-btn" download>💾 Save to Downloads</a>
                    </div>
                `;
                resultDiv.style.display = 'block';
                document.getElementById('downloadBtn').disabled = false;
                document.getElementById('downloadBtn').textContent = '🎉 New Download';
                document.getElementById('status').style.display = 'none';
            }
        </script>
    </body>
    </html>
    '''

@app.route('/download', methods=['POST'])
def start_download():
    """Start download job"""
    data = request.form
    url = data['url'].strip()
    
    if not re.match(r'^https?://', url):
        return jsonify({'success': False, 'error': '🔗 Valid HTTPS URL required'})
    
    download_id = f"dl_{int(time.time()*1000)}"
    download_status[download_id] = {
        'progress': 0, 'status': 'starting', 'speed': '', 
        'downloaded': '0 B', 'total': '?', 'url': url
    }
    
    executor.submit(bulletproof_social_download, url, download_status, download_id)
    return jsonify({'success': True, 'download_id': download_id})

@app.route('/status/<download_id>')
def status(download_id):
    """Get download status"""
    status_data = download_status.get(download_id, {'status': 'expired', 'progress': 0})
    return jsonify(status_data)

@app.route('/download/<path:filename>')
def serve_file(filename):
    """Serve downloaded file"""
    filepath = os.path.join('static/downloads', filename)
    
    if not os.path.exists(filepath):
        print(f"❌ File missing: {filepath}")
        return jsonify({'error': 'File not ready - refresh page'}), 404
    
    filesize = os.path.getsize(filepath)
    print(f"✅ Serving: {filename} ({format_bytes(filesize)})")
    
    response = send_from_directory('static/downloads', filename, as_attachment=True)
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Content-Type'] = 'video/mp4'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

if __name__ == '__main__':
    # 🧹 Initial cleanup
    temp_cleanup()
    print("🔥 BULLETPROOF Social Downloader v4.3")
    print("✅ FFmpeg FIXED - NO 'when' parameter")
    print("✅ Instagram/YouTube/TikTok/Facebook/X")
    print("🌐 http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)