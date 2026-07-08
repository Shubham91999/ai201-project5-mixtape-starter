# Mixtape Bug Hunt Submission

## AI Usage
I used AI as a code navigation and reasoning partner, not as an unverified bug guesser.

How I used AI during codebase orientation:
- Summarized file responsibilities across app.py, models.py, routes/, services/, seed_data.py, and tests/.
- Traced end-to-end call chains from routes to services (for example, playlist add and notification retrieval paths).
- Helped build the initial codebase map before bug fixes.

How I used AI during debugging:
- Structured reproduction work first, then validated behavior with concrete API and service-level checks.
- Compared working and non-working code paths (playlist-add notification vs rating path) to identify architectural mismatch.
- Helped narrow root-cause conditions in streak and playlist retrieval logic after the suspicious code was already found.

Where I verified or overrode AI output:
- All hypotheses were verified by running code and checking outputs before implementing changes.
- I validated fixes with targeted tests and direct reproduction checks after each change.
- I adjusted the initial bug-fix order after reproduction evidence showed a more deterministic path with Issues 1, 4, and 5.
- I did not accept unverified explanations as root cause; RCA entries were written only after confirmed reproduction, code trace, and fix verification.

## Codebase Map (Written Before Bug Fixing)

### Main Files and Responsibilities
- app.py: Flask app factory, SQLAlchemy initialization, blueprint registration, and database table creation.
- models.py: Core data model definitions (User, Song, Playlist, ListeningEvent, Rating, Notification, Tag) plus association tables for friendships, song tags, and ordered playlist entries.
- routes/songs.py: HTTP endpoints for song search, song detail, rating, and listening events.
- routes/playlists.py: HTTP endpoints for creating playlists, viewing playlist metadata, viewing playlist songs, and adding songs to playlists.
- routes/users.py: HTTP endpoints for user profile lookup, streak retrieval, notifications retrieval, and marking notifications as read.
- routes/feed.py: HTTP endpoints for friends listening-now feed and general activity feed.
- services/streak_service.py: Business logic for creating listening events and updating/retrieving listening streaks.
- services/feed_service.py: Business logic for friends listening-now and activity feeds.
- services/search_service.py: Business logic for searching songs and song lookup.
- services/notification_service.py: Business logic for playlist-add notifications, song rating persistence, and notification retrieval/read state updates.
- services/playlist_service.py: Business logic for playlist creation and ordered playlist song retrieval.
- seed_data.py: Deterministic seed setup for users, friendships, songs/tags, listening events, playlists, and baseline notifications.
- tests/: Unit tests targeting streak logic, search behavior, and playlist song retrieval.

### Data Flow Example: Friend Adds a Shared Song to a Playlist (Notification Path)
1. Client calls POST /playlists/<playlist_id>/songs with song_id and added_by.
2. routes/playlists.py add_song validates input and calls services/notification_service.py add_to_playlist.
3. add_to_playlist validates song, adder, and playlist existence.
4. add_to_playlist appends song to playlist if missing and commits.
5. add_to_playlist compares song.shared_by with added_by; if different, it calls create_notification.
6. create_notification inserts Notification row and commits.
7. Recipient later calls GET /users/<user_id>/notifications via routes/users.py, which calls get_notifications to return ordered notification DTOs.

### Organizational Patterns Noticed
- Thin routes, service-heavy logic: routes mostly validate request payload and delegate business rules to services.
- App factory pattern: create_app centralizes config, DB init, and blueprint registration.
- UUID-based primary keys: all entities use UUID strings, so API ids are UUIDs rather than integer ids.
- Explicit service boundaries map cleanly to issue areas listed in README.
- Seed data intentionally encodes scenarios for bug reproduction (multi-tag songs, recent/older events, existing notifications).

## All Five Issues Reviewed
- Issue 1: Streak reset on Sunday.
- Issue 2: Listening-now includes yesterday data.
- Issue 3: Search duplicates for some songs.
- Issue 4: Missing rating notification.
- Issue 5: Playlist hides newest song.

## Selected Bugs for Fixing
1. Issue 1 (My listening streak keeps resetting)
2. Issue 4 (Missing rating notification)
3. Issue 5 (Playlist hides newest song)

Reason for selection: each bug is reproducible with controlled inputs and maps cleanly to one service module, which supports targeted fixes and clean one-commit-per-fix history.

## Milestone 2 Reproduction Evidence (Before Any Fixes)

### Issue 1 Reproduction: My listening streak keeps resetting
- Setup: created a temporary user in a Python shell and invoked the streak logic directly with fixed UTC datetimes.
- Inputs:
  - Saturday timestamp: 2024-06-15T12:00:00+00:00
  - Sunday timestamp: 2024-06-16T12:00:00+00:00
- Sequence:
  1. Call update_listening_streak(user, saturday).
  2. Call update_listening_streak(user, sunday).
- Observed:
  - Saturday streak became 1.
  - Sunday streak remained 1.
- Expected:
  - Sunday should increment to 2 for a consecutive-day listen.

### Issue 4 Reproduction: Missing rating notification
- Setup: used seeded users and songs through API calls.
- Inputs:
  - Rater: nova
  - Song: Crown Heights Anthem (shared by simone)
- Sequence:
  1. GET /users/<simone_id>/notifications (baseline).
  2. POST /songs/<song_id>/rate with {"user_id": "<nova_id>", "score": 5}.
  3. GET /users/<simone_id>/notifications again.
- Observed:
  - Rating request returned 201 (rating saved).
  - Notification count stayed 0 before and after.
  - No song_rated notification appeared.
- Expected:
  - A rating notification should be created for the song owner.

### Issue 5 Reproduction: Playlist hides newest song
- Setup: used seeded playlist Friday Energy through API and DB count check.
- Sequence:
  1. GET /playlists/<friday_energy_id>/songs.
  2. Count songs returned by API.
  3. Compare with DB count from playlist_entries for the same playlist.
- Observed:
  - API count was 6.
  - Database count was 7.
- Expected:
  - API should return all 7 songs, including the most recently added one.

### Additional Reproduction Notes
- Issue 2 was also reproducible in current UTC timing conditions: a friend with an event from the previous calendar day still appears in listening-now.
- No source files were modified during reproduction.

## Root Cause Analysis Entries

### 1) Issue #1: My listening streak keeps resetting
1. Issue number and title
  - Issue #1: My listening streak keeps resetting.
2. How I reproduced it
  - I created a temporary user and called update_listening_streak with controlled timestamps.
  - First call used Saturday (2024-06-15 UTC), second call used Sunday (2024-06-16 UTC).
  - The streak stayed at 1 instead of incrementing to 2.
3. How I found the root cause
  - Navigation path: routes/songs.py listen -> services/streak_service.py record_listening_event -> update_listening_streak.
  - In update_listening_streak, I checked the consecutive-day branch and compared it against the expected Sunday behavior from the issue.
  - The key signal was a weekday guard that blocked increments on Sunday even when days_since_last was 1.
4. The root cause
  - The consecutive-day increment condition was coded as days_since_last == 1 and today.weekday() != 6.
  - In Python, Sunday is weekday() == 6, so a valid Saturday-to-Sunday consecutive listen was excluded from increment logic and forced into the reset branch.
5. My fix and side-effect check
  - Fix: changed the increment branch to only check days_since_last == 1.
  - Why it works: streak logic should be based on consecutive calendar days only, independent of weekday name.
  - Side-effect checks:
    - Ran pytest tests/test_streaks.py -q (5 passed).
    - Re-ran the Saturday->Sunday reproduction; streak now increments to 2.
    - Verified same-day and skipped-day behaviors still follow existing test expectations.

### 2) Issue #4: I got notified when a friend added my song to a playlist but not when they rated it
1. Issue number and title
  - Issue #4: Missing notification when a shared song is rated.
2. How I reproduced it
  - Using seeded data, I rated Crown Heights Anthem as nova via POST /songs/<song_id>/rate.
  - Before and after calls to GET /users/<song_owner_id>/notifications showed count stayed at 0 pre-fix.
  - Rating returned 201 and persisted, but no notification was created.
3. How I found the root cause
  - Navigation path: routes/songs.py rate -> services/notification_service.py rate_song.
  - I compared rate_song with the working add_to_playlist path in the same service.
  - add_to_playlist performs the business action and then calls create_notification, while rate_song only saved/upserted Rating and returned.
  - This structural mismatch showed exactly why ratings never generated notifications.
4. The root cause
  - The rating workflow persisted data but omitted notification creation entirely.
  - There was no call to create_notification in rate_song after a successful rating, so users never received song_rated notifications.
5. My fix and side-effect check
  - Fix: added a post-commit notification step in rate_song.
  - Implementation details:
    - If rater is not the song owner, call create_notification with type song_rated and a descriptive body.
    - Keep self-rating excluded to avoid self-notification noise.
  - Side-effect checks:
    - Re-seeded data, rated another user's shared song, and confirmed notification count increased and latest type was song_rated.
    - Rated own song and confirmed notification count did not increase.
    - Confirmed rating endpoint still returned 201 and saved score updates.

### 3) Issue #5: The last song in a playlist never shows up
1. Issue number and title
  - Issue #5: The newest playlist entry is consistently missing from API results.
2. How I reproduced it
  - I called GET /playlists/<friday_energy_id>/songs and captured API count.
  - I compared that count with direct playlist_entries count for the same playlist.
  - Pre-fix, API returned 6 while DB had 7.
3. How I found the root cause
  - Navigation path: routes/playlists.py get_songs -> services/playlist_service.py get_playlist_songs.
  - In get_playlist_songs, the SQL query returned ordered songs correctly.
  - The bug appeared in the final return expression, which sliced the list before serialization.
4. The root cause
  - The service returned songs[:-1] instead of songs.
  - That slice always drops exactly one element: the last song in the ordered result set.
  - Because songs are ordered by ascending playlist position, the newest entry (highest position) was always omitted.
5. My fix and side-effect check
  - Fix: changed the return expression to serialize all songs without slicing.
  - Side-effect checks:
    - Ran pytest tests/test_playlists.py -q (all passed).
    - Re-seeded and verified Friday Energy API count now matches DB count (7 vs 7).
    - Confirmed ordering behavior remained intact via playlist order test coverage.

## Milestone 4 Checklist Artifacts
- git log --oneline screenshot: to add in Milestone 4
