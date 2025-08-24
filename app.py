from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
import os
import random # <-- Yeh line add ki hai

app = Flask(__name__)

def load_tokens(server_name):
    base_url = "https://raw.githubusercontent.com/SaeedX302/FF-Tokens/main/"
    server_map = {
        "IND": "token_ind.json",
        "PK": "token_pk.json",
        "BR": "token_br.json",
        "US": "token_br.json",
        "SAC": "token_br.json",
        "NA": "token_br.json",
    }
    token_file = server_map.get(server_name, "token_bd.json")
    url = f"{base_url}{token_file}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        app.logger.error(f"Error fetching or decoding tokens for {server_name} from {url}: {e}")
        return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded", 'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB50"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                if response.status != 200:
                    app.logger.warning(f"Request with a token failed with status: {response.status}")
                    return None # Invalid token ya server error, isse None return karein
                return await response.text()
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None

# MODIFIED FUNCTION
async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if not protobuf_message: return None
        encrypted_uid = encrypt_message(protobuf_message)
        if not encrypted_uid: return None

        tokens = load_tokens(server_name)
        if not tokens:
            app.logger.error("Failed to load tokens or token list is empty.")
            return None

        # Tokens ko shuffle karein taake har baar random tokens use hon
        random.shuffle(tokens)
        
        # Maximum 150 requests ki limit set karein
        limit = 150
        tokens_to_use = tokens[:limit]

        tasks = [send_request(encrypted_uid, t["token"], url) for t in tokens_to_use]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return # Result return karne ki zaroorat nahi, hum likes baad mein check karte hain

    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return None


def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating uid protobuf: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    return encrypt_message(protobuf_data) if protobuf_data else None

def make_request(encrypt, server_name, token):
    try:
        server_urls = {
            "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
            "PK": "https://clientpk.freefiremobile.com/GetPlayerPersonalShow",
            "BR": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
            "US": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
            "SAC": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
            "NA": "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        }
        url = server_urls.get(server_name, "https://clientbp.ggblueshark.com/GetPlayerPersonalShow")
        
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded", 'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB50"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        response.raise_for_status()
        binary_data = response.content
        return decode_protobuf(binary_data)
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        app.logger.error(f"Error decoding Protobuf data: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error during protobuf decoding: {e}")
        return None

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "").upper()
    access_key = request.args.get("key")
    SECRET_KEY = os.environ.get('ACCESS_KEY')

    if not SECRET_KEY or access_key != SECRET_KEY:
        return jsonify({"error": "Access denied. Invalid or missing key."}), 403

    if not uid or not server_name:
        return jsonify({"error": "UID and server_name are required"}), 400

    try:
        tokens = load_tokens(server_name)
        if not tokens: return jsonify({"error": "Could not load tokens for the server."}), 500
        
        token = tokens[0]['token']
        encrypted_uid = enc(uid)
        if not encrypted_uid: return jsonify({"error": "Encryption of UID failed."}), 500

        before = make_request(encrypted_uid, server_name, token)
        if not before: return jsonify({"error": "Failed to retrieve initial player info. The UID might be invalid or the server is down."}), 404
        
        data_before = json.loads(MessageToJson(before))
        before_like = int(data_before.get('AccountInfo', {}).get('Likes', 0))

        server_like_urls = {
            "IND": "https://client.ind.freefiremobile.com/LikeProfile",
            "PK": "https://clientpk.freefiremobile.com/LikeProfile",
            "BR": "https://client.us.freefiremobile.com/LikeProfile",
            "US": "https://client.us.freefiremobile.com/LikeProfile",
            "SAC": "https://client.us.freefiremobile.com/LikeProfile",
            "NA": "https://client.us.freefiremobile.com/LikeProfile",
        }
        like_url = server_like_urls.get(server_name, "https://clientbp.ggblueshark.com/LikeProfile")

        asyncio.run(send_multiple_requests(uid, server_name, like_url))

        after = make_request(encrypted_uid, server_name, token)
        if not after: return jsonify({"error": "Failed to retrieve player info after sending likes."}), 500

        data_after = json.loads(MessageToJson(after))
        after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0))
        player_uid = int(data_after.get('AccountInfo', {}).get('UID', 0))
        player_name = str(data_after.get('AccountInfo', {}).get('PlayerNickname', ''))
        
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2
        
        return jsonify({
            "LikesGivenByAPI": like_given,
            "LikesbeforeCommand": before_like,
            "LikesafterCommand": after_like,
            "PlayerNickname": player_name,
            "UID": player_uid,
            "status": status
        })

    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
