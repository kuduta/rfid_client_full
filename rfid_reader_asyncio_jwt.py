import serial
import struct
import asyncio
import aiohttp
import socket
import uuid
import logging
import os
from datetime import datetime
from collections import defaultdict
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv

# === Load Config from .env ===
load_dotenv()

API_URL = os.getenv("API_URL")
LOGIN_URL = os.getenv("LOGIN_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DUPLICATE_TIMEOUT = int(os.getenv("DUPLICATE_TIMEOUT"))

# === Logging ===
LOG_DIR = "/var/log/rfid"
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("RFIDLogger")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler(f"{LOG_DIR}/rfid_reader.log", when="midnight", backupCount=7)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# === Get IP/MAC ===
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "0.0.0.0"
    finally:
        s.close()
    return ip

def get_mac():
    mac = uuid.getnode()
    return '-'.join(f'{(mac >> i) & 0xff:02X}' for i in reversed(range(0, 48, 8)))

DEVICE_IP = get_ip()
DEVICE_MAC = get_mac()

# === Deduplication Map ===
last_sent_time = defaultdict(float)

# === JWT Token ===
jwt_token = None

# === Login ===
async def get_jwt_token(session):
    global jwt_token
    try:
        async with session.post(LOGIN_URL, json={"username": USERNAME, "password": PASSWORD}) as resp:
            if resp.status == 200:
                data = await resp.json()
                jwt_token = data.get("access_token")
                if jwt_token:
                    logger.info("🔐 JWT token received.")
                else:
                    logger.error("⚠️ JWT token not found in response.")
            else:
                logger.warning(f"⚠️ Login failed: {resp.status}")
    except Exception as e:
        logger.error(f"Login error: {e}")

# === Send RFID Data ===
async def send_rfid(epc, rssi, session):
    global jwt_token
    now = datetime.now().timestamp()

    if now - last_sent_time[epc] < DUPLICATE_TIMEOUT:
        logger.info(f"⏳ Duplicate skipped: {epc}")
        return

    last_sent_time[epc] = now
    payload = {
        "epc": epc,
        "rssi": rssi,
        "ipaddress": DEVICE_IP,
        "macaddress": DEVICE_MAC
    }

    for attempt in range(3):
        try:
            if not jwt_token:
                logger.warning("❗ JWT token missing, trying to login...")
                await get_jwt_token(session)
                if not jwt_token:
                    logger.error("❌ Cannot send without JWT token.")
                    return

            headers = {"Authorization": f"Bearer {jwt_token}"}
            async with session.post(API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Sent: {epc} | RSSI: {rssi}")
                    return
                elif resp.status == 401:
                    logger.warning("🔁 Token expired, reauthenticating...")
                    await get_jwt_token(session)
                else:
                    logger.error(f"❌ Send failed [{resp.status}]: {await resp.text()}")
        except Exception as e:
            logger.error(f"🚨 Exception: {e}")
        await asyncio.sleep(1)

# === Extract RFID Data ===
def extract_epc_rssi_multi(hex_data):
    results = []
    pos = 0
    while True:
        idx = hex_data.find("E280", pos)
        if idx == -1 or idx + 24 > len(hex_data):
            break
        epc = hex_data[idx:idx + 24]
        rssi_pos = idx + 24
        rssi_dbm = struct.unpack('b', bytes.fromhex(hex_data[rssi_pos:rssi_pos+2]))[0] if rssi_pos + 2 <= len(hex_data) else None
        results.append((epc, rssi_dbm))
        pos = rssi_pos + 2
    return results

# === Main Async Loop ===
async def main():
    logger.info("📡 Starting RFID Reader Client")
    ser = serial.Serial(port='/dev/ttyUSB0', baudrate=115200, timeout=1)
    ser.write(b'\x04\x00\x01\xDB\x4B')

    async with aiohttp.ClientSession() as session:
        await get_jwt_token(session)

        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                hex_data = data.hex().upper()
                epc_rssi_list = extract_epc_rssi_multi(hex_data)

                for epc, rssi in epc_rssi_list:
                    await send_rfid(epc, rssi, session)

            await asyncio.sleep(0.1)

# === Entry Point ===
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("📴 Stopped by user")
