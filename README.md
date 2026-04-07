
# Whisper Video Transcriber 🎙️📼

A simple Python GUI app for transcribing `.mp4` videos using OpenAI's Whisper.  
Supports timestamps, translation to English, multiple model choices, and video preview thumbnails.

---

## 🚀 Features

- 🧠 Supports Whisper models: `tiny`, `base`, `small`, `medium`, `large`
- 🕒 Option to include timestamps (`HH:MM:SS.SSS`)
- 🌍 Optional translation to English
- 🖼️ Shows video title and thumbnail preview
- 📄 Saves transcript to a `.txt` file with the same base name as your video
- 🔄 Thread-safe UI with loading progress bar

---

## 🧰 First-Time Setup

### 1. ✅ Prerequisites

Make sure Python 3.8+ is installed:

```bash
python --version
```

### 2. 📦 Install Required Packages

```bash
pip install git+https://github.com/openai/whisper.git
pip install ffmpeg-python Pillow opencv-python
```

Also install **FFmpeg**:

- **Windows**:  
  Download and install from https://ffmpeg.org/download.html and add it to your `PATH`.

- **macOS**:

```bash
brew install ffmpeg
```

- **Ubuntu/Debian**:

```bash
sudo apt update && sudo apt install ffmpeg
```

---

## 📂 How to Run

1. Run it:

```bash
python program.py
```

---

## 💡 How to Use

1. Click **“Select Video”** and choose an `.mp4` file.
2. Choose from the options:
   - ✅ Include timestamps
   - 🌍 Translate to English
   - 🧠 Select model size
3. Click **“Transcribe”**

---

## 📋 What to Expect

- App shows a thumbnail and filename on the left
- Transcription appears on the right
- A `.txt` file is saved in the same folder as your video
- A loading bar indicates transcription progress

---

## ⚠️ Notes

- First run may take time (models are downloaded automatically).
- Larger Whisper models give better accuracy but take more time.
- Translation works best for spoken languages.

---

## 🙌 Credits

Built with:
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Tkinter](https://docs.python.org/3/library/tkinter.html)
- [FFmpeg](https://ffmpeg.org/)
- [Pillow](https://pillow.readthedocs.io/)
- [OpenCV](https://opencv.org/)

---

Feel free to extend it with drag-and-drop, subtitle export, or multi-file support!
