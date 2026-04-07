import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from PIL import Image, ImageTk
import whisper
import ffmpeg
import cv2
from datetime import timedelta

# Function to convert seconds to HH:MM:SS.SSS format
def format_timestamp(seconds):
    return str(timedelta(seconds=seconds))

# Thread-safe transcription wrapper
def run_transcription():
    path = selected_video_path.get()
    if not path:
        messagebox.showwarning("No file selected", "Please select a video file first.")
        return
    use_timestamps = timestamp_var.get()
    do_translate = translate_var.get()
    selected_model = model_choice.get()

    disable_ui()
    loading_label.config(text="Loading... Please wait.")
    progress_bar.start()

    def task():
        try:
            model = whisper.load_model(selected_model)
            result = model.transcribe(path, verbose=False, task="translate" if do_translate else "transcribe")

            if use_timestamps:
                text = ""
                for segment in result["segments"]:
                    start = format_timestamp(segment["start"])
                    end = format_timestamp(segment["end"])
                    content = segment["text"]
                    text += f"[{start} - {end}] {content}\n"
            else:
                text = result["text"]

            output_path = os.path.splitext(path)[0] + "_transcription.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)

            output_textbox.config(state="normal")
            output_textbox.delete("1.0", tk.END)
            output_textbox.insert(tk.END, text)
            output_textbox.config(state="normal")

            messagebox.showinfo("Success", f"Transcription saved to:\n{output_path}")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
        finally:
            progress_bar.stop()
            loading_label.config(text="")
            enable_ui()

    threading.Thread(target=task).start()

def disable_ui():
    confirm_button.config(state="disabled")
    browse_button.config(state="disabled")
    model_menu.config(state="disabled")
    checkbox.config(state="disabled")
    translate_checkbox.config(state="disabled")

def enable_ui():
    confirm_button.config(state="normal")
    browse_button.config(state="normal")
    model_menu.config(state="readonly")
    checkbox.config(state="normal")
    translate_checkbox.config(state="normal")

def browse_file():
    file_path = filedialog.askopenfilename(
        title="Select a video or audio file",
        filetypes=[
            ("Media files", "*.mp4 *.mp3 *.wav *.m4a *.flac *.ogg"),
            ("Video files", "*.mp4"),
            ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg"),
            ("All files", "*.*")
        ]
    )
    if file_path:
        selected_video_path.set(file_path)
        video_title.config(text=os.path.basename(file_path))
        # Only update thumbnail for video files
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".mp4":
            update_thumbnail(file_path)
        else:
            video_preview_label.config(image="")

def update_thumbnail(video_path):
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img.thumbnail((180, 180))
            img_tk = ImageTk.PhotoImage(img)
            video_preview_label.img = img_tk
            video_preview_label.config(image=img_tk)
    except Exception as e:
        print(f"Thumbnail error: {e}")

root = tk.Tk()
root.title("Whisper Video Transcriber")
root.geometry("900x550")
root.resizable(False, False)

selected_video_path = tk.StringVar()
timestamp_var = tk.BooleanVar(value=False)
translate_var = tk.BooleanVar(value=False)
model_choice = tk.StringVar(value="base")

main_frame = tk.Frame(root)
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Scrollable left panel
left_panel_container = tk.Frame(main_frame)
left_panel_container.pack(side="left", fill="y")

left_canvas = tk.Canvas(left_panel_container, width=260)
scrollbar = tk.Scrollbar(left_panel_container, orient="vertical", command=left_canvas.yview)
scrollable_left_panel = tk.Frame(left_canvas)

scrollable_left_panel.bind(
    "<Configure>",
    lambda e: left_canvas.configure(
        scrollregion=left_canvas.bbox("all")
    )
)

left_canvas.create_window((0, 0), window=scrollable_left_panel, anchor="nw")
left_canvas.configure(yscrollcommand=scrollbar.set)

left_canvas.pack(side="left", fill="y")
scrollbar.pack(side="right", fill="y")


label = tk.Label(scrollable_left_panel, text="Drop or Select your video or audio file to transcribe", font=("Arial", 12), wraplength=200)
label.pack(pady=10)

browse_button = tk.Button(scrollable_left_panel, text="Select Video", command=browse_file, font=("Arial", 11))
browse_button.pack(pady=5)

video_title = tk.Label(scrollable_left_panel, text="No video selected", font=("Arial", 10), wraplength=200, fg="blue")
video_title.pack(pady=5)

video_preview_label = tk.Label(scrollable_left_panel)
video_preview_label.pack(pady=5)

checkbox = tk.Checkbutton(scrollable_left_panel, text="Include timestamps", variable=timestamp_var, font=("Arial", 10))
checkbox.pack(pady=2)

translate_checkbox = tk.Checkbutton(scrollable_left_panel, text="Translate to English", variable=translate_var, font=("Arial", 10))
translate_checkbox.pack(pady=2)

model_label = tk.Label(scrollable_left_panel, text="Select Model:", font=("Arial", 10))
model_label.pack(pady=5)

model_menu = ttk.Combobox(scrollable_left_panel, textvariable=model_choice, state="readonly", values=["tiny", "base", "small", "medium", "large"])
model_menu.pack()

confirm_button = tk.Button(scrollable_left_panel, text="Transcribe", command=run_transcription, font=("Arial", 11))
confirm_button.pack(pady=10)

progress_bar = ttk.Progressbar(scrollable_left_panel, mode='indeterminate')
progress_bar.pack(pady=5, fill="x")

loading_label = tk.Label(scrollable_left_panel, text="", font=("Arial", 9), fg="red")
loading_label.pack()

credit = tk.Label(scrollable_left_panel, text="Powered by Whisper", font=("Arial", 9), fg="gray")
credit.pack(side="bottom", pady=10)

# Right panel with output
right_panel = tk.Frame(main_frame)
right_panel.pack(side="right", fill="both", expand=True)

output_label = tk.Label(right_panel, text="Transcription Output:", font=("Arial", 12))
output_label.pack(anchor="w")

output_textbox = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, font=("Arial", 10))
output_textbox.pack(fill="both", expand=True, padx=5, pady=5)

root.mainloop()