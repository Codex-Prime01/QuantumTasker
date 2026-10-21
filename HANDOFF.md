# Handoff: where we stopped

If a chat runs out, start a new one and say: "continue from HANDOFF.md in my QuantumTasker folder".

## Request being worked on
1. More, modern alarm sounds in a sleek dropdown
2. Custom alarm uploads bigger than 2 MB
3. "Enable alarms" failing until you tap it several times
4. Black background behind the Q logo when the PWA opens

## Done (Chunk 1) ✅
- **Uploads:** the limit is now 25 MB. Sounds go to Cloudinary as "video" files (the free plan allows 100 MB that way, but raw files only 10 MB). Files: `djangoTodo/settings.py`, `tasks/views.py` (`_save_custom_tone`), `tasks/templates/tasks/_task_form.html`, and `Procfile` (`--timeout 120`).
- **Enable alarms:** in `tasks/static/tasks/app.js`, `QM.push.enable()` now does these things:
  - waits for the service worker to be fully active
  - retries the subscription and clears old subscriptions made with different keys
  - retries the server call (Render's free plan is slow to wake up)
  - shows clearer error messages
- **Icon:** new solid blue icons are in `tasks/static/tasks/icons/`. That includes `maskable-*.png`, `apple-touch-icon.png`, and `logo-mark.png` (the notification badge). The manifest has separate `any` and `maskable` entries, and its splash colour is `#0B1E52`. The service worker cache was bumped to `qm-v5`.

## Done (Chunk 2) ✅
- **19 original alarm sounds** are in `tasks/static/tasks/tones/*.mp3`, about 90 KB each. They're made from scratch with `python manage.py make_tones`, so there's no copyright problem. They're grouped as Gentle, Modern, Classic and Loud.
- **One list for every sound:** `tasks/tones.py`. The form, Settings, the dropdown and the player all read from it. To add a sound, add a recipe in `make_tones.py`, add it to `tones.py`, then run `make_tones`.
- **Dropdown:** `QM.tonePicker` in `app.js` and the `.tp-*` styles in `qm.css`. It turns any `<select data-tone-select>` into the sleek picker with a ▶ preview on each row. "Upload your own sound" sits at the bottom.
- **Alarms now loop** and get louder over 25 seconds until you tap Snooze or Got it. They stop on their own after 3 minutes.
- **Tests:** `tasks/tests/test_alarm_sounds.py`. All 73 tests pass.

## Done (Chunk 3) ✅
- **Alarm and due date are now one thing.** The task form no longer has a separate "Ring at" date to fill in — you set the due date once, then just pick how early the alarm should ring (at the due time / 15 min / 30 min / 1 hour / 1 day before), and it's computed automatically. If you leave the alarm on with no due date, it tells you to add one above instead of silently failing.
- **A "liquid glass" look** on the alarm popup and the account dropdown menu — a frosted, softly-lit panel (pure CSS blur + light gradients, not a WebGL library), with a one-time light sheen when it opens. Chosen after checking the 4 repos Perey sent: the React/Three.js ones (`react-three-fiber`, `shadergradient`) need a whole React+bundler setup this project doesn't have, `scroll-world` is a paid AI video pipeline for marketing pages, and `liquid-glass-js` is vanilla JS but has no documented way to wrap existing cards and needs WebGL that drains battery. The CSS version gets the same look with zero new dependencies and degrades safely (`@supports`) on old phones; it also gets lighter automatically on small screens, and the sheen is skipped under reduced motion.

## Done (Chunk 4) ✅ iPhone Clock style
- **Alarms page** (`/alarms/`, view `alarms_list`, template `alarms.html`): every upcoming task with a time, big thin digits, a green iOS switch per alarm. The switch saves right away through `POST /api/toggle-alarm/<id>/` (`toggle_alarm`) and flips back with a toast if saving fails. It also has Edit mode (red minus) and swipe-left to delete. It's linked in the sidebar and the bottom nav (now 5 tabs).
- **Task sheet** (`_task_form.html`): Cancel / Save bar, a scroll-wheel time picker plus day chips, and iOS grouped rows (Repeat, Rings, Sound, Priority, Categories, Notes). Same form fields and backend as before. If the wheel fails to load, the plain date box shows instead.
- **Look:** the `.ios-*` styles at the end of `qm.css`. There's a slow drifting gradient (`body.ios-bg`, a CSS take on shadergradient) and frosted groups. Switches are green only here. It respects reduced motion.
- **Tests:** `tasks/tests/test_alarms_page.py`. All 86 pass when `CLOUDINARY_URL` is blank. With the real key from `.env`, 2 upload tests try real Cloudinary and fail.

## Done (Phase 1) ✅ iPhone look everywhere + 3D
- **Global iPhone layer:** the "iPhone feel on every page" section at the end of `qm.css`. It restyles the shared classes (`.card`, `.stat`, `.task-list`, `.switch`, `.chip`, `.btn`, the sidebar, the tab bar, the login card) as frosted glass, with green switches and Reminders-style round checkboxes. No page templates were rewritten.
- **3D:**
  - Cards tilt toward the mouse (`QM.depth` in `app.js`, mouse only). Buttons press in.
  - Lists rise in with a slight flip.
  - iOS page slides use View Transitions (only in browsers that support them).
  - A real WebGL shader background (`QM.shader`, hand-written, no library) shows on pages whose body has the class `hero-3d`: Alarms, Dashboard, Achievements and the login pages. It's skipped on data saver, shows one still frame on old phones or with reduced motion, and pauses when the tab is hidden.
- **Drum wheel:** `drum()` in `_task_form.html`, plus a vibration tick on Android.
- Service worker cache is now `qm-v8`.

## Done (Phase 2) ✅ Offline app
- **Saved pages:** `sw.js` (cache `qm-v9`) saves every page you open, and warms `/`, `/alarms/`, `/create/`, `/notes/`, `/notes/create/` and `/dashboard/` after login. Offline, you get the saved copy.
- **Outbox:** `tasks/static/tasks/outbox.js` (IndexedDB), used by both the pages and the service worker.
  - Forms sent offline are caught by the service worker: add, edit and delete a task, quick add, and new or edited notes.
  - Ticks and alarm switches are queued with `QM.queue` in `app.js`.
  - It replays on reconnect, on page load, and through Background Sync on Chrome/Android.
- **No double changes:** every replayed change sends an `X-QM-Op` header. The `@replay_safe` decorator plus the `SyncReceipt` model (migration 0018) apply each one only once. `quick_toggle` now takes `{"complete": bool}` so a replayed tick can't flip back.
- **Installed-app extras:**
  - Share target at `/share/`: Android Chrome only, not iPhone.
  - App badge: `nav_counts.due`, set with `navigator.setAppBadge`.
  - Shortcuts: New task, Alarms, New note, Templates.
- **Log out** wipes the saved pages and the outbox, and warns first if changes haven't synced.
- **Tests:** `tasks/tests/test_offline.py`. 98 tests total pass.
- **Limit:** alarms created offline only ring with the app closed after they sync.

## Done: design pass from emilkowalski/skills ✅
- Read: `apple-design`, `mobile-native`, `emil-design-eng`, `animation-performance`. Skipped: Swift, Expo and React-only skills.
- All 45 `:hover` rules in `qm.css` are now behind `@media (hover: hover) and (pointer: fine)`. The script that did it is a scratch file and isn't in the repo.
- "Feels like an installed app" section at the end of `qm.css`:
  - no tap flash, `touch-action: manipulation`, 16px inputs on touch screens (no iPhone zoom)
  - safe-area padding (`--topbar-total`), press-in `:active` states
  - menus "materialize", support for reduced transparency and increased contrast
- `QM.haptic()` fires on ticking a task done, alarm switches and swipe snaps (Android only).
- Alarms swipe-to-delete: pointer capture, rubber-band edges, decides from flick speed (Apple's projection function).
- **Performance:** the background gradient no longer drifts, and the WebGL shader stops after 8s. Glass re-blurs every frame anything moves behind it, which hit 100% CPU in testing.

## Done (Phase 3) ✅ Calendar
- `tasks/ical.py`: a hand-written .ics builder, with VALARM and RRULE support and 75-byte line folding.
- `/task/<id>/calendar.ics`: "Add to Calendar" on each task row and in the edit sheet. It keeps its alarm, so it rings offline.
- `/calendar/<token>.ics`: private subscribe feed. Settings → Calendar tab has iPhone, Google and Outlook buttons, a copy-link field and a reset button. The token is made the first time the tab opens (migration 0019).

## Done (Phase 4) ✅ Siri / Android
- `POST /api/shortcut/add/` with `Authorization: Bearer qm_...` and `{"text": ...}`. Only a sha256 of the key is stored (migration 0020). It uses `_create_from_text`, the same parser as quick add, in the user's saved timezone.
- Settings → "Siri & shortcuts" tab: create, revoke or replace the key, plus step-by-step iPhone Shortcuts setup and Android tips.

## Done (Phase 5) ✅ Extra features
- **Streak heatmap:** dashboard, last 20 weeks (`_heatmap`).
- **Subtasks:** `Subtask` model (0021). Checklist in the edit sheet, tickable on the task list (works offline), copied unticked to the next repeat.
- **Calendar view:** `/calendar/`, an iOS month grid with dots and today in red. Swipe or the arrows change month; `+` opens New task with `?due=`.
- **Prove you're awake:** `Task.wake_check` (0022). The in-app alarm needs a sum; the notification has no "Got it", and `alarm_action` refuses a dismiss.
- **Bedtime mode:** `/bedtime/`, profile fields (0023). It manages two daily `kind='bedtime'` and `kind='wake'` tasks. These are hidden from the task list, badge, calendar and stats, and stopping one rolls on to tomorrow with no points.
- **Shared lists:** `SharedList` and `ListItem` (0024), code in `tasks/list_views.py`. Invite link plus a Join button (a GET never joins). It polls every 10s, works offline, and the privacy switches are now real.
- Tests: `test_calendar.py`, `test_shortcuts.py`, `test_subtasks_heatmap.py`, `test_phase5.py`.

## Next phases (agreed order)
All agreed phases are done. Still open from the plan: the focus timer (left out for now). Google or Outlook two-way sync could come later.

## Old plan notes
3. Calendar: per-task .ics "Add to Calendar" + a private subscribe feed
4. Siri / Android shortcuts (personal API key + add-task endpoint)
5. Extra features: calendar view, "prove you're awake" alarms, subtasks, bedtime mode, shared lists, streak heatmap (NOT the focus timer)

## Things Perey still has to do
- Render → Settings → Start Command: `gunicorn djangoTodo.wsgi:application --bind 0.0.0.0:$PORT --timeout 120`
- `git rm tasks/static/tasks/style.css tasks/static/tasks/sounds/alarms.js`
- Commit, push the `redesign` branch, and merge
- Generate the VAPID keys (`python manage.py generate_vapid_keys`), then set them and `CRON_SECRET` in Render
- Set up the cron-job.org ping every minute (see the README)
