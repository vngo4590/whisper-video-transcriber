You are editing highlight clips from a video that contains significant audio energy peaks. The transcript includes [PEAK: Xs–Ys, +ZdB above mean] markers identifying moments where audio energy spiked — audience reactions, applause, key moments in a demonstration, climactic points in a story, game events, presenter emphasis, or any high-energy event.

Your goal is to find {max_clips} highlight clips that capture the most exciting or significant peaks AND the context that makes them meaningful. This applies to any content type: live events, lectures, cooking demos, game streams, sports commentary, performances, interviews, or anything else.

MODE OBJECTIVE:
- Deliver peak-centered clips that still make narrative sense to a first-time viewer.
- Prioritize emotional impact and event significance over purely informational moments.

HIGHLIGHTS-SPECIFIC RULES (on top of the absolute rules):
- PEAK PRIORITY — Strongly prefer clip windows that overlap with at least one [PEAK] marker. A clip with no PEAK overlap is a last resort.
- CONTEXT — Include the 3–10 seconds of speech or audio immediately before a peak (the build-up) and the moment immediately after (the reaction or resolution). Cold-cutting into a peak with no context is jarring.
- ENERGY ARC — Each clip should have a clear energy arc: setup → rising tension or anticipation → peak → resolution. Use multiple segments if needed to build this arc.
- SILENCE — Never straddle a [SILENCE] marker. Treat [SILENCE] as a hard cut boundary.
- DEAD AIR — Never include segments where nothing meaningful is happening. If a peak is surrounded by dead silence with no speech, widen the window to capture the nearest relevant speech or action.
- NON-SPEECH PEAKS — A [PEAK] may represent music, applause, a crowd reaction, a sound effect, or any impactful audio event rather than speech. That is fine — include it. The clip does not need to be speech-only.
- MULTI-PEAK BONUS — Prefer clips that contain build-up to one major peak, or two related peaks with a clear connective arc.
{editing_rules}
Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "title":    "<punchy highlight title, max 8 words>",
      "hook":     "<what the viewer sees/hears in the first second>",
      "peak":     "<brief description of the peak moment — e.g. 'crowd applause', 'key result revealed', 'punchline lands', 'clutch moment'>",
      "reason":   "<why this moment will resonate with viewers, 1 sentence>",
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
