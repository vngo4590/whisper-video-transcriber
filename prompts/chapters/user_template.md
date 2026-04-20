Analyse the following transcript and divide it into at most {max_chapters} chapters (use fewer if the video is short or has fewer distinct topics).

Return ONLY a JSON object in this exact structure — no markdown fences, no extra text:
{{
  "chapters": [
    {{
      "chapter": 1,
      "title": "Short descriptive chapter title",
      "start_time": 0.0,
      "end_time": 120.5,
      "summary": "One or two sentences describing what this chapter covers.",
      "key_points": ["Key point 1", "Key point 2", "Key point 3"]
    }}
  ]
}}

Constraints:
- start_time of chapter 1 must be 0.0
- end_time of chapter N must equal start_time of chapter N+1
- end_time of the last chapter must equal the video end time
- key_points: 2–4 bullet points per chapter

TRANSCRIPT:
{transcript}
