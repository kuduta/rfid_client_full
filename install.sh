#!/bin/bash

# Set working path
WORKDIR="/home/raspi/python/RFID"
SERVICE_NAME="rfid-reader.service"
VENV_DIR="$WORKDIR/venv"
PYTHON="$VENV_DIR/bin/python"

# สร้าง venv ถ้ายังไม่มี
if [ ! -d "$VENV_DIR" ]; then
    echo "[+] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# ติดตั้ง dependencies
echo "[+] Installing dependencies from requirements.txt..."
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$WORKDIR/requirements.txt"

# เขียน systemd service
echo "[+] Creating $SERVICE_NAME..."
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=RFID Reader Python Script
After=network.target

[Service]
WorkingDirectory=$WORKDIR
ExecStart=$PYTHON $WORKDIR/rfid_reader_asyncio_jwt.py
Environment="PATH=$VENV_DIR/bin"
Restart=always
RestartSec=5
User=raspi
StandardOutput=inherit
StandardError=inherit

[Install]
WantedBy=multi-user.target
EOF

# โหลดและเปิดใช้งาน service
echo "[+] Reloading systemd and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "[✓] Done. Use: sudo journalctl -u $SERVICE_NAME -f to check logs."
