
# Whisper Video Transcriber 🎙️📼

A simple Python GUI app for transcribing `.mp4` videos using OpenAI's Whisper.  
Supports timestamps, translation to English, multiple model choices, and video preview thumbnails.

---

## 🚀 Features

- 🧠 Supports Whisper models: `tiny`, `base`, `small`, `medium`, `large`
- 🕒 Option to include timestamps (`HH:MM:SS.SSS`)
- 🌍 Optional translation to English
- 🔗 Paste a YouTube URL to download the video (or just its audio) and transcribe it
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

### 3. 🔗 Optional — YouTube URL support

To paste YouTube links into the app, install **yt-dlp**:

```bash
pip install -U yt-dlp
```

This is optional. Without it the app still runs normally — the URL box is simply
disabled and you pick files from disk as usual.

---

## 📂 How to Run

1. Run it:

```bash
python main.py
```

---

## 💡 How to Use

1. Click **“Select Video”** and choose an `.mp4` file — or paste a **YouTube URL**
   into the link box and click **Fetch**.
   - The first fetch asks where to save downloads, then remembers that folder.
   - Tick **“Audio only (faster)”** to grab just the audio when you only need a
     transcript. Note that audio-only files can't be used for video clips or
     on-screen-text extraction.
   - Playlist links aren't supported — paste a single video URL.
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
- Downloaded media and everything generated from it — transcripts, clip folders —
  share the same download folder, so pick one with room to spare.
- If a YouTube fetch fails with an extraction error, YouTube most likely changed
  something on their end. Update the downloader and try again:

```bash
pip install -U yt-dlp
```

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
