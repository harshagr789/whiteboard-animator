# Whiteboard Video Pipeline

## Status

This document records the plan for a new repository named
`whiteboard-video-pipeline`. The reusable pipeline and proposed commands below
are **not implemented yet**.

The existing `whiteboard-animator` repository remains the rendering engine.
Its main `README.md` documents the current engine; this document describes the
automation to build around it.

## Goal

Turn interview transcripts, narration audio, and manually generated images into
whiteboard videos through a local, folder-based, resumable pipeline.

The only routine manual tasks in the first version are:

1. Provide the transcript.
2. Provide the voice-over audio.
3. Generate images in the Gemini app using the pipeline's prompts and save the
   downloaded images into the job folder.

All other processing should be automatic, including scene planning, prompt
creation, image preparation, timing, rendering, audio/video assembly, and
verification.

**Version 1 prioritizes good-looking videos and reliable automation, not
word-perfect synchronization.** Precise speech alignment must not block a render.

## What worked in the prototype

The Scene 05 test used the shareholder-approval section of an interview script:

1. Read the script and divided it into visual scenes.
2. Prepared Gemini image prompts and a copy-friendly HTML page.
3. Received a finished image generated manually in Gemini.
4. Received a Clipchamp voice-over and its SRT captions.
5. Selected the narration between 48.75 and 63.25 seconds.
6. Prepared the image and assigned five drawing groups: shareholder support,
   Tesla, the share grid and percentage statement, the voting clarification,
   and the hurdle.
7. Revealed those groups at approximately 0.25, 4, 6.5, 9, and 11.75 seconds.
8. Rendered a 14.5-second silent MP4, exported its narration separately, and used
   FFmpeg to make a preview containing both tracks.
9. Checked the duration, frame count, image completeness, and reveal order.

The user accepted the visual result and explicitly deprioritized exact matching
between spoken words and drawing actions.

The prototype was **landscape, 1280x720 at 24 fps**. It is a rendering proof of
concept, not the format to use for future production.

Its files are currently under:

```text
C:\Repos\whiteboard-animator\tmp\scene05-clipchamp\
  render_scene.py
  scene_05.png
  scene_05.mp4
  scene_05_preview.mp4
  scene_05.wav
  scene_05.srt
  scene_05.timeline.json
  scene_05_contact_sheet.png
  verification.json
```

The reusable pipeline must replace the prototype's hard-coded source paths,
audio range, image regions, reveal times, and filenames.

## Fixed decisions

| Area | Decision |
|---|---|
| New repository | `whiteboard-video-pipeline` |
| Implementation | A local Python application with separate processing stages |
| Rendering engine | Reuse `whiteboard-animator`, pinned to a known revision |
| Production format | **Portrait 9:16, 1080x1920, 30 fps** |
| Encoding | MP4 with H.264 video; narrated outputs use AAC audio |
| Manual inputs | Transcript, voice-over audio, Gemini-generated images |
| Initial timing | Approximate scene and drawing timing |
| Outputs | Individual scene videos, separate audio, and combined videos |
| Operation | A folder watcher with persisted progress and restart recovery |
| Gemini API | Optional; not required for the initial pipeline |

Do not introduce separate services or a large orchestration framework for the
first version.

## User workflow

1. Create a folder for a video and put its transcript in `input`.
2. The pipeline automatically prepares the script, divides it into scenes, and
   creates `generated\prompts.html`.
3. Copy each prompt from that page into Gemini.
4. Save the resulting portrait images into `input\images`, using the scene
   filenames shown on the page.
5. Put the final narration audio into `input`. It can arrive before or after
   the images.
6. The pipeline resumes when the required files are available and generates the
   videos automatically.

Files can arrive incrementally. There should be no need to restart the process,
enter bounding boxes, calculate timestamps, or run FFmpeg manually.

The watcher must already be running to react to new files. Persisted state lets
it continue after being stopped and restarted.

## Independent processing stages

Each stage reads defined inputs, writes reusable outputs, and can be rerun
independently when its prerequisites are available.

| Stage | Automatic processing | Saved result |
|---|---|---|
| Intake | Detect complete files, validate formats, inspect audio duration, identify missing inputs | Input inventory and status |
| Transcript normalization | Parse TXT/SRT/VTT, remove timestamp-only lines, retain wording and available timestamps | `transcript.json` and clean script |
| Scene planning | Divide narration into contiguous visual ideas; assign stable scene IDs and required objects | `scenes.json` |
| Prompt generation | Create consistent, portrait-oriented Gemini prompts | Individual prompts and `prompts.html` |
| Image preparation | Associate images with scene IDs; validate portrait format; normalize transparency, background, and dimensions | Prepared scene images |
| Timeline planning | Allocate scene durations and drawing/hold periods using available timestamps and audio duration | `timeline.json` |
| Rendering | Animate each image with the existing engine | Individual silent MP4s |
| Assembly | Create corresponding audio segments, narrated previews, and combined videos | Scene audio, previews, and final videos |
| Verification | Check dimensions, frame rate, duration, decodability, audio streams, and completed drawings | Contact sheet and validation report |

Use typed, versioned JSON contracts between stages. Keep the scene plan, image
preparation, timing decisions, and rendering configuration separate so each can
improve without rewriting the rest of the pipeline.

### Transcript normalization

- Accept plain text, SRT, and VTT.
- Preserve wording, meaning, speaker attribution where present, and source order.
- Retain supplied timestamps as data, not text to be spoken.
- Produce a clean script for copying into a voice-over platform.
- Keep original input files unchanged.

### Automated scene planning

Use a configured Copilot CLI text-agent adapter for scene planning and prompt
content. It should return structured data that the application validates, rather
than requiring the user to copy planning responses into files.

This requires an authenticated Copilot setup and uses its allowance. It does
**not** require a Gemini image API key.

Keep the text-model integration behind a provider interface so another runtime
can replace it later.

Planner requirements:

- Cover the complete transcript without omitted or duplicated passages.
- Do not invent statements or silently rewrite the interview into a summary.
- Prefer whole sentences or caption cues as boundaries.
- Group by one explainable visual idea rather than a fixed number of seconds.
- Split dense content into simpler scenes before requesting images.
- Assign stable scene IDs and image filenames.
- Freeze those IDs once prompts have been issued.

The scene plan should identify each scene's source text range, visual idea,
required objects, expected image filename, and prompt content.

### Gemini prompt generation

Create one complete prompt per scene and a self-contained HTML page with copy
buttons. Each copied scene prompt must include the shared visual style so it can
be pasted independently.

Prompts must request:

- A finished illustration, not a video, storyboard, or collage.
- A portrait 9:16 composition.
- A pure white background and clean marker-style artwork.
- Large, readable labels and a consistent palette.
- Clearly separated visual groups with no accidental connecting strokes.
- Vertically arranged content with generous margins and limited clutter.
- Only the labels and objects needed for the scene.

Save prompts as separate text files as well as in the HTML page. Show the
expected image filename beside each scene.

### Automatic drawing order

Version 1 should use the renderer's existing component detection, text
detection, and ordering heuristics. It can already render without a manually
supplied region plan.

This removes manual bounding-box creation from the workflow. The drawing order
may not follow every spoken phrase exactly, which is acceptable for the first
version.

Keep drawing-order selection separate from rendering. A later semantic-region
provider can produce explicit region plans through the same pipeline.

### Approximate timing

- For SRT/VTT, use caption boundaries to assign scene ranges.
- For plain text, estimate scene durations from text length relative to the
  measured audio duration.
- Where feasible, move estimated scene boundaries to nearby silence.
- Draw during most of a scene, then hold the completed image.
- Record whether timing is supplied or estimated.
- Keep frame-rounded scene boundaries consistent so rounding errors do not
  accumulate across a video.

Do not require speech-recognition installation or forced alignment for v1.

Keep the original full narration continuous in the combined video. Do not
reconstruct it from repeatedly encoded fragments. Separate scene audio files
are convenience outputs for editing and mixing.

## Strict Instagram portrait profile

The portrait profile must be enforced during prompting, input preparation,
rendering, and final verification.

### Prompt and layout rules

Use a vertical composition with stacked visual groups, fewer objects, large
labels, and clear margins for Instagram's interface. Do not reuse the landscape
layout from the prototype.

### Image input rules

- Accept portrait images matching 9:16, allowing a small tolerance for export
  rounding.
- Normalize accepted images to the production canvas without distorting them.
- Reject landscape or square images with a clear status message.
- Do not silently crop away meaningful content.
- Do not stretch images or disguise landscape illustrations with large bars.

### Video output rules

Every scene and combined video must be verified as:

```text
Aspect ratio: 9:16 portrait
Dimensions:  1080x1920
Frame rate:  30 fps
Container:   MP4
Video codec: H.264
Audio codec: AAC, when audio is included
```

Silent videos must remain available for independent mixing.

### Required rendering-engine adjustment

The current engine's `MAX_DIM` is 1280. Its `_downscale` method limits the
longest dimension to that value.

Without changing this, a 1080x1920 image becomes 720x1280 during rendering.

Expose the maximum dimension as a setting, preserving the existing default for
other users. The new pipeline should request a 1920-pixel maximum and render
directly at the production dimensions, rather than unnecessarily downscaling
and then enlarging the finished video.

Pass the production frame rate explicitly instead of relying on the existing
24 fps defaults and presets.

## Local job-folder layout

Keep user media outside the source repository. Use one independent folder per
video, for example:

```text
C:\Users\harshagrawal\Videos\WhiteboardJobs\
  video-001\
    input\
      transcript.srt
      voiceover.m4a
      images\
        scene_001.png
        scene_002.png

    generated\
      script.txt
      transcript.json
      scenes.json
      prompts.html
      prompts\
      prepared-images\
      timeline.json

    output\
      scenes\
        scene_001.silent.mp4
        scene_001.preview.mp4
        scene_001.wav
        scene_001.srt
      final.silent.mp4
      final.preview.mp4
      contact-sheet.png
      verification.json

    state.json
    logs\
```

`transcript.txt` or `transcript.vtt` can replace `transcript.srt`. Narration
should support M4A, WAV, and MP3. Scene SRT files are produced when timestamped
captions are available; estimated timing must not be presented as precise
transcription.

The user manages only `input`. The pipeline owns the generated files, outputs,
state, and logs, and must not modify the original inputs.

## Watcher and recovery

Use explicit job and stage states, including:

```text
PLANNING
WAITING_FOR_IMAGES
WAITING_FOR_AUDIO
PREPARING
RENDERING
ASSEMBLING
VERIFYING
COMPLETE
```

Record validation failures and processing errors separately from waiting for
expected manual inputs.

The watcher should:

- Wait for files to finish copying before opening them.
- Record input hashes, configuration, and completed stages.
- Resume after a restart without repeating completed work.
- Prevent simultaneous processes from rendering the same job.
- Publish outputs atomically so partially written files never appear complete.
- Show exactly which image, audio file, or other input is missing or invalid.
- Keep jobs isolated so assets from different videos cannot be mixed.

### Incremental invalidation

| Changed input | Work to repeat |
|---|---|
| One scene image | Prepare and render that scene, then rebuild dependent combined outputs |
| Narration audio | Recalculate timing and rerun dependent rendering and assembly |
| Transcript | Regenerate the scene plan and prompts; identify stale images and downstream outputs |
| Render profile | Rerun dependent preparation, rendering, assembly, and verification |

Do not delete original inputs when invalidating a stage. Preserve old assets
while clearly identifying which ones no longer match the current plan.

## Proposed command interface

These are planned commands, not commands currently supplied by this repository:

```powershell
wb-video run "C:\Users\harshagrawal\Videos\WhiteboardJobs\video-001"
wb-video watch "C:\Users\harshagrawal\Videos\WhiteboardJobs"
```

The one-job command should resume from saved state. Also expose individual
stages for development and targeted reruns, validating prerequisites before
execution.

## Future providers and enhancements

| Component | Initial implementation | Later enhancement |
|---|---|---|
| Audio and captions | User supplies files | Clipchamp computer-use adapter produces the same files |
| Scene images | User supplies Gemini downloads | Optional Gemini image-generation API adapter |
| Drawing order | Local renderer heuristics | Semantic region detection and controlled reveal order |
| Timing | Approximate scene pacing | Audio alignment and phrase/word cues |
| Text planning | Configured Copilot CLI adapter | Alternative text-model runtime |

Future integrations must satisfy the same file and data contracts rather than
changing the core stages.

The existing engine's Gemini integration detects **regions**; it does not
generate scene images. Image generation needs a separate optional provider,
not merely enabling the existing API-key flag.

## Implementation order

### Phase 1: Portrait rendering foundation

- Make the rendering size limit configurable without changing existing defaults.
- Use automatic drawing order without manual boxes.
- Enforce the production export profile.
- Complete one vertical end-to-end rendering fixture.

### Phase 2: Single-job pipeline

- Implement transcript normalization, automatic scene planning, and prompts HTML.
- Validate the required files and prepare images.
- Generate approximate timelines.
- Render scene videos and produce separate audio and combined outputs.
- Check completed drawings, media properties, and duration.

### Phase 3: Folder automation

- Add waiting states and stable-file detection.
- Persist progress and input hashes.
- Support restart recovery and incremental reruns.
- Queue multiple independent video jobs.

### Phase 4: Optional automation and quality improvements

- Add Clipchamp UI automation for audio and captions.
- Add optional Gemini API image generation.
- Improve semantic drawing order.
- Add precise speech alignment only when it becomes a priority.

## First-release acceptance criteria

The first release is complete when a user can:

1. Drop a transcript and narration audio into a job folder.
2. Receive automatically generated scene prompts.
3. Add the requested portrait images.
4. Receive individual and combined videos without another manual processing
   step.

The outputs must meet the portrait profile, preserve the narration, include
complete drawings, and survive a restart or an individual image replacement
without unnecessarily redoing the entire job.

Word-perfect synchronization is not a first-release requirement.
