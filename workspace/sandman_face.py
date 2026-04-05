import tkinter as tk
from tkinter import Label, Entry, Canvas
import subprocess
import requests
import json
import threading

# Globals
root = None
canvas = None
label = None
entry = None
mouth_id = None
MOUTH_Y = 420
MOUTH_H = 30

def draw_face():
    canvas.delete("all")
    # Black background
    canvas.config(bg="black")
    # Yellow circle face
    canvas.create_oval(250, 50, 550, 350, fill="yellow", outline="yellow")
    # White eyes
    canvas.create_oval(310, 130, 360, 180, fill="white", outline="white")
    canvas.create_oval(440, 130, 490, 180, fill="white", outline="white")
    # Black pupils
    canvas.create_oval(325, 145, 345, 165, fill="black")
    canvas.create_oval(455, 145, 475, 165, fill="black")
    # Red mouth (closed arc)
    global mouth_id
    mouth_id = canvas.create_arc(320, 240, 480, 310, start=200, extent=140, fill="red", outline="red")

def mouth_open():
    canvas.itemconfig(mouth_id, start=220, extent=100)

def mouth_close():
    canvas.itemconfig(mouth_id, start=200, extent=140)

def speak_and_animate(text):
    """Send to Ollama, show response, animate mouth, speak via macOS say."""
    label.config(text="Thinking...")
    root.update()
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma3:4b", "prompt": text, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        answer = resp.json().get("response", "").strip()
        if not answer:
            answer = "I have no response."
    except Exception as e:
        answer = f"Error: {e}"
    # Show response
    label.config(text=answer[:300])
    root.update()
    # Animate mouth + speak in background thread
    def _speak():
        mouth_open()
        root.update()
        subprocess.run(["say", answer[:500]])
        mouth_close()
        root.update()
    threading.Thread(target=_speak, daemon=True).start()

def submit_command(event=None):
    text = entry.get().strip()
    if not text:
        return
    entry.delete(0, tk.END)
    speak_and_animate(text)

def main():
    global root, canvas, label, entry
    root = tk.Tk()
    root.title("AMRIT Sandman Face")
    root.geometry("800x600")
    root.configure(bg="black")

    canvas = Canvas(root, width=800, height=400, bg="black", highlightthickness=0)
    canvas.pack(side=tk.TOP, fill=tk.BOTH)
    draw_face()

    label = Label(root, text="ਮੈਂ AMRIT ਹਾਂ — ਕੀ ਸੇਵਾ ਕਰਾਂ?", font=("Helvetica", 14),
                  fg="white", bg="black", wraplength=750, justify=tk.LEFT)
    label.pack(fill=tk.X, padx=10, pady=(10, 5))

    frame = tk.Frame(root, bg="black")
    frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    entry = Entry(frame, font=("Helvetica", 14), bg="#222", fg="white",
                  insertbackground="white")
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
    entry.bind("<Return>", submit_command)

    btn = tk.Button(frame, text="Send", command=submit_command,
                    bg="#333", fg="white", font=("Helvetica", 12))
    btn.pack(side=tk.RIGHT, padx=(5, 0))

    entry.focus_set()
    root.mainloop()

if __name__ == '__main__':
    main()