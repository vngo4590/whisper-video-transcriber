Analyse the transcript and design {max_clips} highlight-reel videos. Each video is assembled from 2–5 short speech windows that share a theme or build toward a single point. No window may contain or straddle a [SILENCE] marker.

MODE OBJECTIVE:
- Build cohesive mini-stories by sequencing high-value moments.
- Prioritize narrative momentum over strict chronology.

ASSEMBLY STRATEGIES (pick the best fit per clip):
- "problem_to_solution": pain point -> method -> result.
- "thesis_then_proof": bold claim -> supporting evidence/examples -> conclusion.
- "question_to_answer": intriguing question -> exploration -> direct answer.
- "mistake_to_fix": common mistake -> correction -> practical takeaway.

Requirements per video:
- Total assembled duration: 45–90 seconds
- Each individual segment: 5–20 seconds of speech (trim at speech boundaries)
- Segments flow naturally when concatenated
- Together they tell a coherent mini-story, complete a step-by-step process, or build to a satisfying conclusion
- Use one dominant assembly strategy per video and reflect it in title/hook/reason wording
{editing_rules}
Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "title":    "<descriptive title, max 10 words>",
      "hook":     "<what happens in the very first cut>",
      "reason":   "<why this assembled reel works as a standalone piece, 1–2 sentences>",
      "category": "<short AI-generated category label>",
      "tags":     ["<tag1>", "<tag2>", "<tag3>"],
      "description":"<1-sentence social caption style summary>",
      "hashtags": ["#tag1", "#tag2", "#tag3"],
      "segments": [
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}}
      ]
    }}
  ]
}}

TRANSCRIPT:
{transcript}
