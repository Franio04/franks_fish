#!/usr/bin/env python3
"""
Minecraft Reel Listener
-----------------------
Listens for UDP messages from your Fabric mod on 127.0.0.1:8765.
When it receives {"event":"reel"}, it will right-click twice using pyautogui
to reel in and recast the fishing rod.

Usage:
    pip install pyautogui
    python mc_reel_listener.py
"""

import json
import queue
import socket
import threading
import time
from dataclasses import dataclass

import pyautogui

# ---------------- CONFIG ----------------
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765

RIGHT_CLICKS = 2          # number of right clicks
BETWEEN_CLICKS = 0.33     # delay between the two clicks (seconds)
PRE_CLICK_DELAY = 0.05    # optional wait before first click
REEL_THROTTLE = 0.40      # minimum time between reel events (seconds)

# Movement and auto-cast timers
MOVEMENT_INTERVAL = 120   # 2 minutes in seconds
AUTO_CAST_INTERVAL = 60   # 1 minute in seconds

pyautogui.PAUSE = 0.02    # pause between pyautogui actions
pyautogui.FAILSAFE = True # move mouse to top-left corner to abort
# ----------------------------------------


@dataclass
class ReelEvent:
    timestamp: float


def perform_movement():
    """Perform WASD movement and mouse up/down to prevent AFK kick."""
    try:
        print("[movement] Performing anti-AFK movement...")
        
        # WASD movement sequence
        pyautogui.keyDown('w')
        time.sleep(0.1)
        pyautogui.keyUp('w')
        time.sleep(0.1)
        
        pyautogui.keyDown('a')
        time.sleep(0.1)
        pyautogui.keyUp('a')
        time.sleep(0.1)
        
        pyautogui.keyDown('s')
        time.sleep(0.1)
        pyautogui.keyUp('s')
        time.sleep(0.1)
        
        pyautogui.keyDown('d')
        time.sleep(0.1)
        pyautogui.keyUp('d')
        time.sleep(0.1)
        
        # Mouse movement up and down
        current_x, current_y = pyautogui.position()
        pyautogui.moveTo(current_x, current_y - 50, duration=0.2)
        time.sleep(0.1)
        pyautogui.moveTo(current_x, current_y + 50, duration=0.2)
        time.sleep(0.1)
        pyautogui.moveTo(current_x, current_y, duration=0.2)
        
        print("[movement] Anti-AFK movement completed")
    except Exception as e:
        print(f"[movement] Error during movement: {e}")


def auto_cast_fishing_rod():
    """Auto-cast fishing rod if it hasn't been cast recently."""
    try:
        print("[auto-cast] Auto-casting fishing rod...")
        pyautogui.click(button="right")
        print("[auto-cast] Fishing rod cast")
    except Exception as e:
        print(f"[auto-cast] Error during auto-cast: {e}")


class ReelWorker(threading.Thread):
    """Consumes ReelEvent and performs the clicks with throttling."""
    def __init__(self, evq: queue.Queue):
        super().__init__(daemon=True)
        self.evq = evq
        self._last_reel = 0.0
        self._running = True
        self.last_reel_time = 0.0  # Track when we last reeled for auto-cast

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                ev = self.evq.get(timeout=0.25)
            except queue.Empty:
                continue

            now = time.monotonic()
            if now - self._last_reel < REEL_THROTTLE:
                # ignore duplicates arriving too quickly
                continue

            self._last_reel = now
            self.last_reel_time = now  # Update last reel time
            try:
                if PRE_CLICK_DELAY > 0:
                    time.sleep(PRE_CLICK_DELAY)
                for i in range(RIGHT_CLICKS):
                    pyautogui.click(button="right")
                    if i < RIGHT_CLICKS - 1 and BETWEEN_CLICKS > 0:
                        time.sleep(BETWEEN_CLICKS)
            except Exception as e:
                print(f"[worker] click error: {e}")


def udp_server(evq: queue.Queue):
    """Listen for UDP JSON messages and push ReelEvent when needed."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    sock.settimeout(1.0)

    print(f"[udp] listening on {LISTEN_HOST}:{LISTEN_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        msg = data.decode("utf-8", "ignore").strip()
        if msg.startswith('{"event":"reel"'):
            evq.put(ReelEvent(timestamp=time.time()))
            continue

        try:
            j = json.loads(msg)
            if isinstance(j, dict) and j.get("reel") is True:
                evq.put(ReelEvent(timestamp=time.time()))
        except json.JSONDecodeError:
            pass


def main():
    evq = queue.Queue()
    worker = ReelWorker(evq)
    worker.start()

    t = threading.Thread(target=udp_server, args=(evq,), daemon=True)
    t.start()

    print("Minecraft Reel Listener running.")
    print("Press Ctrl+C to stop. Move mouse to top-left corner for pyautogui failsafe.")
    print(f"Movement every {MOVEMENT_INTERVAL} seconds, auto-cast every {AUTO_CAST_INTERVAL} seconds")

    # Initialize timers
    last_movement_time = time.monotonic()
    last_auto_cast_time = time.monotonic()

    try:
        while True:
            current_time = time.monotonic()
            
            # Check if it's time for movement (every 2 minutes)
            if current_time - last_movement_time >= MOVEMENT_INTERVAL:
                perform_movement()
                last_movement_time = current_time
            
            # Check if it's time for auto-cast (every 1 minute)
            if current_time - last_auto_cast_time >= AUTO_CAST_INTERVAL:
                # Only auto-cast if we haven't reeled recently
                if current_time - worker.last_reel_time >= AUTO_CAST_INTERVAL:
                    auto_cast_fishing_rod()
                last_auto_cast_time = current_time
            
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
        worker.stop()
        time.sleep(0.2)


if __name__ == "__main__":
    main()