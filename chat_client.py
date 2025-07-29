import os
import threading
import time
import sys
import json
from pynput import keyboard
from collections import deque
from rich.console import Console

OUTPUT_FILE = "output.txt"
INPUT_FILE = "input.txt"

input_buffer = ""
conversation_history = deque(maxlen=30)
running = True
ui_lock = threading.Lock()
console = Console()

def map_color(color_name):
    color_map = {
        "soft pink": "light_pink3",
        "shimmering blue": "bright_cyan",
        "deep purple": "purple",
        "emerald green": "green",
        "fiery orange": "orange_red1"
    }
    return color_map.get(color_name.lower(), "default")

def redraw_screen():
    with ui_lock:
        console.clear()
        console.print("--- Jessica's Phone ---", style="bold magenta")
        console.print("Type '/quit' on a new line to exit.")
        console.print("-" * 30)
        
        for entry_type, content, data in conversation_history:
            if entry_type == "chat":
                hair_color = data.get("hair_color", "default")
                style = map_color(hair_color)
                console.print(f"[bold {style}]Jessica:[/] {content}")
            elif entry_type == "user":
                console.print(f"[bold cyan]You:[/] {content}")

        console.print("\n" + "-" * 30)
        console.print(f"> {input_buffer}", end="")

def output_reader():
    last_read_content = ""
    if os.path.exists(OUTPUT_FILE):
         with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
             last_read_content = f.read().strip()

    while running:
        try:
            if os.path.exists(OUTPUT_FILE):
                with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content and content != last_read_content:
                        last_read_content = content
                        try:
                            message_data = json.loads(content)
                            msg_type = message_data.get("type")
                            
                            if msg_type == "chat" or msg_type == "narration":
                                msg_content = message_data.get("content")
                                msg_metadata = message_data.get("metadata", {})
                                with ui_lock:
                                    conversation_history.append((msg_type, msg_content, msg_metadata))
                                redraw_screen()

                        except (json.JSONDecodeError, AttributeError):
                            pass
        except Exception:
            pass
        time.sleep(0.1)

def on_press(key):
    global input_buffer, running
    
    if not running:
        return False

    try:
        if key == keyboard.Key.enter:
            if input_buffer.lower().strip() == '/quit':
                running = False
                return False
            
            if input_buffer:
                with open(INPUT_FILE, 'w', encoding='utf-8') as f:
                    f.write(input_buffer)
                
                with ui_lock:
                    conversation_history.append(("user", input_buffer, {}))
                input_buffer = ""
            redraw_screen()

        elif key == keyboard.Key.backspace:
            input_buffer = input_buffer[:-1]
            redraw_screen()
        
        elif key == keyboard.Key.space:
            input_buffer += " "
            redraw_screen()

        elif hasattr(key, 'char') and key.char:
            input_buffer += key.char
            redraw_screen()
            
    except AttributeError:
        pass

    return True

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w") as f: pass
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, "w") as f: pass
    
    reader_thread = threading.Thread(target=output_reader, daemon=True)
    reader_thread.start()

    redraw_screen()
    
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    try:
        while running:
            time.sleep(0.1)
    finally:
        listener.stop()
        console.print("\n...connection terminated...")