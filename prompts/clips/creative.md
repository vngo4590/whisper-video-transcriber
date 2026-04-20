Analyse the transcript and design {max_clips} creative short-form videos with intentional narrative arcs. Think like a skilled editor — cuts do NOT need to be chronological, but every segment must begin and end on speech boundaries (never inside a [SILENCE] gap).

MODE OBJECTIVE:
- Create emotionally resonant edits with a memorable hook and satisfying payoff.
- Treat each clip like a tiny story with deliberate escalation.

CREATIVE STRATEGIES (choose one primary approach per clip):
- "contrast_arc": expectation vs reality.
- "escalation_arc": stakes or intensity rise across cuts.
- "reveal_arc": partial info -> reframing -> clear reveal.
- "character_arc": voice/personality journey from setup to payoff.

Narrative structure for each video:
  1. Hook (0–5 s): Drop into the most attention-grabbing moment first
  2. Context (5–30 s): Cuts that build stakes, context, or curiosity
  3. Payoff (30–end): The conclusion, punchline, answer, or completed result
{editing_rules}
Requirements per video:
- 3–6 segments, total 30–75 seconds
- Each segment 5–20 seconds of clean speech
- Non-linear if it serves the story better
- Include a "narrative" field describing the hook → context → payoff arc
- Ensure the payoff recontextualizes or resolves what the hook promised

Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "title":     "<descriptive title, max 10 words>",
      "hook":      "<what drops in the opening cut>",
      "reason":    "<why this creative edit will resonate, 1–2 sentences>",
      "category":  "<short AI-generated category label>",
      "tags":      ["<tag1>", "<tag2>", "<tag3>"],
      "description":"<1-sentence social caption style summary>",
      "hashtags":  ["#tag1", "#tag2", "#tag3"],
      "narrative": "<hook → context → payoff arc in 1–2 sentences>",
      "segments":  [
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}}
      ]
    }}
  ]
}}

TRANSCRIPT:
{transcript}
