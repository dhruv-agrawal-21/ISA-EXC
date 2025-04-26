import datetime
import time
import RPi.GPIO as GPIO
import requests
import sqlite3
from threading import Thread 
import json

# Pin Configuration
PIN_CONFIG = {
    'machine': 22,
    'cycle': 7,
    'alarm': 18,
    'emergency': 14,
    'reset': 15,
    'm30': 11,
    'runoutnotok': 9,
    'spindle': 7,
    'power_failure': 31
}

# Global variables
machine_id = ""
sr_no = 0
seq_no = 0
production_pattern = ["cycleON", "m30ON", "cycleOFF", "m30OFF"]
current_pattern = []
flags = {
    'cycle': 0,
    'spindle': 0,
    'reset': 0,
    'emergency': 0,
    'alarm': 0,
    'runoutnotok': 0,
    'machine': 0,
    'm30': 0
}

# Database setup
conn = sqlite3.connect("erp.db")
cursor = conn.cursor()

# API configuration
LOCAL_SERVER = "http://127.0.0.1:3000/HoldMachine"
HEADERS = {'Content-type': 'application/json', 'Accept': 'application/json'}

def setup_pins():
    """Configure GPIO pins based on database settings"""
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    
    # Set input pins
    for pin_name, default_pin in PIN_CONFIG.items():
        pin = get_pin_from_db(pin_name, default_pin)
        GPIO.setup(pin, GPIO.IN)
    
    # Set output pin
    GPIO.setup(13, GPIO.OUT)
    GPIO.output(13, True)

def get_pin_from_db(pin_name, default_pin):
    """Get pin number from database or use default"""
    cursor.execute("SELECT pin FROM pinout WHERE signal_type=?", (pin_name,))
    result = cursor.fetchone()
    return int(result[0]) if result else default_pin

def initialize_sequence():
    """Initialize or get current sequence number"""
    global seq_no
    cursor.execute("SELECT count(*) FROM sequence_generator WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO sequence_generator(status, generateNew) VALUES(?,?)", ("null", "y"))
        conn.commit()
    
    cursor.execute("SELECT id FROM sequence_generator ORDER BY id DESC LIMIT 1")
    seq_no = cursor.fetchone()[0]

def get_next_sr_no():
    """Get and increment the serial number"""
    global sr_no
    sr_no += 1
    if sr_no > 1000:
        sr_no = 1
        update_sequence()
    return sr_no

def update_sequence():
    """Update sequence generator when SR_NO exceeds 1000"""
    global seq_no
    cursor.execute("UPDATE sequence_generator SET status='used' WHERE id=?", (seq_no,))
    cursor.execute("INSERT INTO sequence_generator(status, generateNew) VALUES(?,?)", ("null", "y"))
    conn.commit()
    cursor.execute("SELECT id FROM sequence_generator ORDER BY id DESC LIMIT 1")
    seq_no = cursor.fetchone()[0]

def log_signal(process):
    """Log signal to database"""
    sr_no = get_next_sr_no()
    timestamp = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO signals(seqNo, srNo, machineId, process, timeStamp) VALUES(?,?,?,?,?)",
        (seq_no, sr_no, machine_id, process, timestamp)
    )
    conn.commit()
    flags[process.replace('ON', '').replace('OFF', '').lower()] = 1 if 'ON' in process else 0

def handle_special_events(process):
    """Handle special events like machine hold, production count, etc."""
    if process == "machineON":
        send_machine_command("Hold")
    elif process == "cycleON":
        current_pattern.clear()
        current_pattern.append(process)
        send_live_signal("Cycle On")
    elif process == "m30ON":
        current_pattern.append(process)
    elif process == "alarmON":
        send_live_signal("Alarm ON")
    elif process == "EmergencyON":
        send_live_signal("Emergency On")
    
    # Check for production pattern match
    if process in ["cycleOFF", "m30OFF"]:
        current_pattern.append(process)
        if current_pattern == production_pattern:
            update_production_count()

def send_machine_command(command):
    """Send command to machine"""
    requests.post(LOCAL_SERVER, json.dumps({"State": command}), headers=HEADERS, timeout=2)

def send_live_signal(signal):
    """Send live signal update"""
    requests.post("127.0.0.1:3000/liveSignals", json.dumps({"liveSignal": signal}), headers=HEADERS, timeout=2)

def update_production_count():
    """Update production count in database"""
    cursor.execute("SELECT MAX(id) FROM production")
    last_id = cursor.fetchone()[0]
    cursor.execute("UPDATE production SET status='1' WHERE id=?", (last_id,))
    conn.commit()

def monitor_pin(pin, on_event, off_event):
    """Monitor a GPIO pin for state changes"""
    current_state = GPIO.input(pin)
    if flags[on_event.replace('ON', '').lower()] == 0 and current_state == 1:
        log_signal(on_event)
        handle_special_events(on_event)
    elif flags[on_event.replace('ON', '').lower()] == 1 and current_state == 0:
        log_signal(off_event)
        handle_special_events(off_event)

def main():
    print("----------------------------------------")
    print(" \t main program starting  ")
    print("----------------------------------------")
    
    setup_pins()
    initialize_sequence()
    
    try:
        while True:
            # Monitor all configured pins
            monitor_pin(PIN_CONFIG['cycle'], "cycleON", "cycleOFF")
            monitor_pin(PIN_CONFIG['machine'], "machineON", "machineOFF")
            monitor_pin(PIN_CONFIG['m30'], "m30ON", "m30OFF")
            monitor_pin(PIN_CONFIG['spindle'], "spindleON", "spindleOFF")
            monitor_pin(PIN_CONFIG['reset'], "resetON", "resetOFF")
            monitor_pin(PIN_CONFIG['emergency'], "emergencyON", "emergencyOFF")
            monitor_pin(PIN_CONFIG['alarm'], "alarmON", "alarmOFF")
            monitor_pin(PIN_CONFIG['runoutnotok'], "runoutNotOkON", "runoutNotOkOFF")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        GPIO.cleanup()
        conn.close()

if __name__ == "__main__":
    main()