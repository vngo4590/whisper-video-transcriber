Analyse the transcript and identify the {max_clips} most compelling CONTINUOUS moments worth extracting as standalone clips. Each clip must be one uninterrupted speech window — no silence gaps inside.

MODE OBJECTIVE:
- Produce clean standalone clips that can be posted with minimal editing.
- Favor complete, high-value ideas over flashy but context-dependent moments.

Requirements per clip:
- Duration: 30–90 seconds (ideal 45–60 s)
- Self-contained: viewer grasps the point without extra context
- Strong opening in the first 3 seconds — a claim, question, result, or surprising statement
- Ends at a natural break (punchline, conclusion, revelation, or completed step)
- Engaging: surprising, useful, funny, inspiring, instructional, or thought-provoking
- Diversity: each clip should cover a different subtopic, claim, or emotional beat when possible
{editing_rules}
Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "start_time": <float — seconds from video start, matching a speech segment start>,
      "end_time":   <float — seconds from video start, matching a speech segment end>,
      "title":      "<descriptive title, max 10 words>",
      "hook":       "<what is said or shown in the first 3 seconds>",
      "reason":     "<why this moment stands alone, 1–2 sentences>",
      "category":   "<short AI-generated category label>",
      "tags":       ["<tag1>", "<tag2>", "<tag3>"],
      "description":"<1-sentence social caption style summary>",
      "hashtags":   ["#tag1", "#tag2", "#tag3"]
    }}
  ]
}}

TRANSCRIPT:
{transcript}
