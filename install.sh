#!/bin/bash

echo "📦 Installing dependencies..."
sudo apt update
sudo apt install python3-venv python3-pip -y

echo "🐍 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "📁 Creating log directory..."
sudo mkdir -p /var/log/rfid
sudo chown $USER:$USER /var/log/rfid

echo "🛠️ Installing service..."
sudo cp rfid-reader.service /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable rfid-reader
sudo systemctl start rfid-reader

echo "✅ Installation completed."
