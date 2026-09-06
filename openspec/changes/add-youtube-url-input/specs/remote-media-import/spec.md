## Purpose

Lets a user bring media into the app from a remote video URL instead of a local file, resolving it
to a local media file that every existing workflow can consume unchanged.

## ADDED Requirements

### Requirement: Import media from a pasted URL

The system SHALL accept a remote video URL as a media source. On a successful fetch, the downloaded
file SHALL become the app's active media selection, indistinguishable from a file chosen from disk.

#### Scenario: Successful fetch from a video URL

- **WHEN** the user pastes a valid single-video URL and confirms the fetch
- **THEN** the system downloads the media to the configured download folder
- **AND** the downloaded file becomes the active media selection
- **AND** the file name is displayed, a thumbnail is shown, and the file is added to recent files

#### Scenario: Fetched media is usable by every workflow

- **WHEN** a video has been fetched from a URL
- **THEN** the Transcribe, Video Clips, Content Plan, and Chapters workflows operate on it exactly as
  they would on a file the user selected from disk, with no additional steps

#### Scenario: Existing selection methods are unaffected

- **WHEN** the user selects a file via the file browser, drag-and-drop, or the recent-files list
- **THEN** the behavior is unchanged from before this capability existed

### Requirement: URL validation

The system SHALL validate a URL before attempting a download and SHALL reject unusable input with a
message that states why.

#### Scenario: Malformed or unsupported URL

- **WHEN** the user submits text that is not a recognisable video URL
- **THEN** the system rejects it without attempting a download
- **AND** displays a message identifying the input as an unsupported or malformed URL

#### Scenario: Empty input

- **WHEN** the user confirms the fetch with an empty URL field
- **THEN** the system takes no action and prompts the user to enter a URL

### Requirement: Playlist URLs are rejected

The system SHALL reject a URL that refers to a playlist rather than a single video, and SHALL NOT
silently download only part of the playlist.

#### Scenario: Playlist URL submitted

- **WHEN** the user submits a URL that identifies a playlist
- **THEN** the system rejects the fetch
- **AND** displays a message explaining that only single videos are supported
- **AND** no media is downloaded

### Requirement: Fetch mode selection

The system SHALL download full video by default and SHALL offer an explicit audio-only option for
faster transcript-only work. The chosen mode SHALL persist between sessions.

#### Scenario: Default fetch downloads video

- **WHEN** the user fetches a URL without changing any option
- **THEN** the system downloads video and audio together in a container format supported by the
  app's existing video features

#### Scenario: Audio-only fetch

- **WHEN** the user enables the audio-only option and fetches a URL
- **THEN** the system downloads only the audio stream
- **AND** the resulting file is accepted by the Transcribe and Content Plan workflows

#### Scenario: Audio-only file used where video is required

- **WHEN** the active selection is an audio-only file and the user starts a workflow that requires
  video, such as Video Clips, on-screen text extraction, or a visual analysis strategy
- **THEN** the system warns the user that the operation requires video before the workflow begins,
  rather than failing partway through

### Requirement: Download destination

The system SHALL let the user choose where fetched media is stored and SHALL remember that choice
across sessions. Because transcripts and generated clips are written alongside their source media,
the download destination also determines where those outputs are written.

#### Scenario: First fetch with no destination configured

- **WHEN** the user fetches a URL and no download folder has been configured
- **THEN** the system asks the user to choose a destination folder before downloading
- **AND** persists that choice

#### Scenario: Subsequent fetches reuse the destination

- **WHEN** the user fetches another URL and a download folder is already configured
- **THEN** the system downloads to the configured folder without prompting again

#### Scenario: Outputs are written alongside fetched media

- **WHEN** the user transcribes media that was fetched from a URL
- **THEN** the transcript is written into the same folder as the downloaded media

#### Scenario: Destination is unwritable

- **WHEN** the configured download folder no longer exists or cannot be written to
- **THEN** the system reports the problem and allows the user to choose a different folder
- **AND** no partially written media is left behind

### Requirement: Safe file naming

The system SHALL derive a file name from the source video that is valid on the host operating
system, and SHALL NOT overwrite unrelated existing files.

#### Scenario: Title contains characters illegal in a file name

- **WHEN** the source video's title contains characters that are not permitted in a file name
- **THEN** the system replaces or removes them and completes the download successfully

#### Scenario: A file of the same name already exists

- **WHEN** the derived file name matches a file that already exists in the destination
- **THEN** the system stores the download without destroying the existing file

### Requirement: Progress and activity reporting

The system SHALL report fetch progress and outcome through the app's existing activity log and
pipeline stage indicators, consistent with all other long-running operations.

#### Scenario: Progress during download

- **WHEN** a download is in progress
- **THEN** the activity log reports download progress as it advances
- **AND** the sidebar shows the fetch as a numbered pipeline stage

#### Scenario: Completion is logged

- **WHEN** a download completes successfully
- **THEN** the activity log records the completion and the resulting file location at success level

### Requirement: Cancellation during download

The system SHALL allow the user to cancel an in-progress download using the same Cancel control and
keyboard shortcut as every other operation, and SHALL stop the transfer without waiting for it to
finish.

#### Scenario: User cancels mid-download

- **WHEN** the user cancels while a download is in progress
- **THEN** the transfer stops promptly rather than continuing to completion
- **AND** the activity log records the cancellation
- **AND** the previous media selection is left unchanged

#### Scenario: Cancellation leaves no partial file

- **WHEN** a download is cancelled before it completes
- **THEN** no partially downloaded file remains in the destination folder

### Requirement: Actionable failure reporting

The system SHALL surface a fetch failure as a clear, human-readable message describing the cause,
and SHALL NOT expose a raw stack trace to the user. A failed fetch SHALL leave the app usable.

#### Scenario: Video cannot be retrieved

- **WHEN** a fetch fails because the video is private, removed, region-blocked, age-restricted, or
  otherwise unavailable
- **THEN** the system reports the specific reason in the activity log and to the user

#### Scenario: Network failure

- **WHEN** a fetch fails because of a network or connectivity problem
- **THEN** the system reports that the download could not be completed and the app returns to an
  idle, usable state

#### Scenario: Live stream URL

- **WHEN** the user submits a URL for an ongoing live stream
- **THEN** the system reports that live streams are not supported rather than downloading
  indefinitely

### Requirement: Graceful degradation when the downloader is unavailable

The system SHALL remain fully functional for local files when the components required for remote
downloading are not installed, following the app's existing pattern for optional features.

#### Scenario: Download support not installed

- **WHEN** the app starts and the components required for downloading are not available
- **THEN** the URL input is visibly unavailable and explains what is required to enable it
- **AND** the app starts normally and every local-file workflow continues to work
