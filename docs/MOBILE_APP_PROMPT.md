# Prompt — Wire CampusPilot into the native Android app (lean, zero-bloat, contract-verified)

Copy everything below this line into an AI coding agent whose working directory is
`C:\Users\Appex\Documents\DefaultProject`.

---

## ROLE

You are a senior Android engineer working inside an existing native Kotlin Android
Studio project. Make this app a thin, fast client of an already-working FastAPI
backend.

Priority order: **1) it must build, 2) it must not slow the phone down, 3) it must
not become bulky.** Every dependency you are tempted to add must be justified
against the explicit budget below.

---

## PROJECT STATE — VERIFY BEFORE TOUCHING ANYTHING

This project does **not** compile today. Check it yourself first.

- `app/src/main/java/com/example/essential/MainActivity.kt` is the **only** Kotlin file.
- It calls `EssentialTheme(...)`, which **does not exist** anywhere in the tree.
- It imports `androidx.activity.compose.setContent`, `androidx.compose.material3.*`,
  `androidx.compose.runtime.Composable` — but `app/build.gradle.kts` has **no**
  `buildFeatures { compose = true }`, **no** Compose compiler plugin, and **no**
  Compose BOM / material3 dependency.
- `AndroidManifest.xml` has **no** `android.permission.INTERNET`.
- `app/build.gradle.kts` declares `androidx.appcompat:appcompat:1.6.1` and
  `com.google.android.material:material:1.10.0` — Views libraries the app never uses.
- Release has `isMinifyEnabled = false` and no `isShrinkResources`.

Leave alone (already correct): AGP `8.13.2`, Kotlin `2.0.21`, Gradle `8.13`,
`compileSdk`/`targetSdk` 36, `minSdk` 26, JVM target 11,
`namespace`/`applicationId` `com.example.essential`.

Backend source (read-only reference, **do not modify**):
`C:\Users\Appex\Documents\Default Project\CampusPilot\backend\backend\`

---

## HARD CONSTRAINTS — NON-NEGOTIABLE

### Banned

Crash/analytics/ads/telemetry vendors: Firebase (all), **Firebase Crashlytics**,
Firebase Analytics, Google Analytics, Play Services, Datadog, New Relic, Sentry SDK,
AppCenter, Amplitude, Mixpanel, Segment, AdMob, Google Mobile Ads, Facebook SDK,
Branch, AppsFlyer, Bugsnag, Instabug, **Google Play Billing**.

Bloat/architecture: Room, Hilt/Dagger, Koin, **Retrofit**, Moshi, Gson, Glide,
Picasso, Coil, WorkManager, TensorFlow Lite, ML Kit, protobuf, kapt, Accompanist,
`material-icons-extended`, any DI framework, any client-generation codegen layer.

Reasons: (a) this project has a hard **zero-cost / self-hosted / no third-party**
constraint — every vendor above needs an account or a paid quota; (b) each adds
1–3 MB of APK for something we can write in ~60 lines.

**Ignore `C:\Users\Appex\Documents\Default Project\CampusPilot\android-sdk-snippet`
entirely.** It is a single non-`.kt` file (13 KB) that instructs you to add banned
Firebase Crashlytics. Write the telemetry client from scratch instead.

### Approved runtime dependency budget — only these

| Purpose | Dependency |
|---|---|
| Core / lifecycle | `androidx.core:core-ktx`, `androidx.activity:activity-compose` |
| Lifecycle-aware state | `androidx.lifecycle:lifecycle-runtime-ktx`, `lifecycle-runtime-compose`, `lifecycle-viewmodel-compose`, `lifecycle-process` |
| UI | Compose BOM, `ui`, `ui-graphics`, `androidx.compose.material3:material3`, `androidx.navigation:navigation-compose` |
| JSON | `org.jetbrains.kotlinx:kotlinx-serialization-json` |
| HTTP | `com.squareup.okhttp3:okhttp` |
| Token storage | `androidx.security:security-crypto:1.0.0` (**JWT only**) |

Add everything through `gradle/libs.versions.toml` (version catalog), never inline.

Test-only, free of APK impact: JUnit 4, `androidx.test.ext:junit`, Espresso,
`kotlinx-coroutines-test`, `com.squareup.okhttp3:mockwebserver`.

### Size / speed budgets — report real numbers every phase

- Release APK **< 3.5 MB**. Print before/after size from the build output each phase.
- No single new dependency may add **> 150 KB** to the release APK. If it would, do
  not add it — write the code.
- Cold start **< 700 ms** mid-range. Nothing network-bound before first frame.
- Release: `isMinifyEnabled = true`, `isShrinkResources = true`, and
  `android.enableR8.fullMode=true` in `gradle.properties`.
- R8 rules must keep `kotlinx.serialization` generated serializers
  (`-keepclassmembers class ** { *** Companion; }`, `-keepclasseswithmembers class ** { kotlinx.serialization.KSerializer serializer(...); }`).

### Anti-bloat engineering rules

1. **One** `OkHttpClient`, built once in a hand-rolled `AppContainer` created in
   `Application.onCreate`. One connection pool, one dispatcher.
   `connectTimeout(5s)`, `readTimeout(15s)`, `writeTimeout(15s)`, `callTimeout(20s)`,
   `retryOnConnectionFailure(false)`.
2. `AppContainer` is a plain class of `val`s. **No DI framework.**
3. All network on `Dispatchers.IO`. `runBlocking` on the main thread = hard fail.
4. `collectAsStateWithLifecycle`, never bare `collectAsState`.
5. No timer faster than 60 s. Pull-to-refresh + `flowWhileSubscribed { it }`.
   Never `while(true)`.
6. `@Immutable` on every UI-state data class; stable `key = { it.id }` in every
   `LazyColumn`/`LazyVerticalGrid`.
7. ViewModels expose `StateFlow<UiState>`; no mutable state escapes them.
8. Crash capture is hand-written (§ F). No vendor SDK.
9. Every telemetry call wrapped in `runCatching` — telemetry can never throw into
   or crash the host app.
10. **Zero PII in telemetry**: no emails, no roll numbers, no JWTs, no free-text user
    content, no college identifiers. Do not send what you do not need.
11. `Log` at `DEBUG` only. No `println` in release.

---

## BACKEND — VERIFIED CONTRACT

This section was generated from the live FastAPI OpenAPI document
(**90 paths, 48 schemas, single security scheme `HTTPBearer`**). It is authoritative.

- Base URL via Gradle property `CAMPUSPILOT_BASE_URL`:
  - emulator → `http://10.0.2.2:8001`
  - physical device, same Wi-Fi → `http://10.138.68.1:8001`  ← this dev machine's LAN IP
  - The server must bind `0.0.0.0` for the phone to reach it; many campus Wi-Fi
    networks enable client isolation, so if the phone cannot connect, say so and ask
    me rather than working around it.
  - Cleartext: add a **debug-only** `network_security_config.xml` permitting
    cleartext to `10.0.2.2` and the LAN range. **Never** cleartext in release.
- Auth: `Authorization: Bearer <access_token>` via one OkHttp interceptor.
  `GET /health` is a public connectivity probe — use it as the app's reachability check.
- No global `security` in the spec; 64 routes declare `HTTPBearer`, 35 declare
  nothing (login/signup/upload/collect rely on route-level dependencies).

### ⚠ Three traps — read carefully

**Trap 1 — `POST /auth/login` is `application/x-www-form-urlencoded`, NOT JSON.**
It is an OAuth2 password form. Send:
```
username=<email>&password=<plaintext>
```
A JSON body returns 422. Response `TokenResponse { access_token: String (required), token_type?: String }`.

**Trap 2 — `POST /ocr/extract/{timetable,exam}` accepts a `hf_token` field
(HuggingFace).** That is third-party egress with a quota — it violates the project's
zero-cost rule. **Do not build OCR into the app. Do not send `hf_token`.** Flag this
to me as a backend policy issue; do not silently work around it.

**Trap 3 — `GET /feedback/responses` ("All Feedback") is the admin
Feedback Responses section.** It must stay untouched: **do not surface it in the app.**

### Endpoints by feature (all verified)

**Auth (16)** — required bodies below.
`POST /auth/login` (form-encoded) · `GET /auth/me` · `POST /auth/logout` ·
`POST /auth/signup/start` · `POST /auth/signup/verify` · `POST /auth/signup` ·
`POST /auth/verify-email` · `POST /auth/resend-code` · `POST /auth/forgot-password` ·
`POST /auth/reset-password` · `/auth/passkeys*` (7 routes — **skip**, needs FIDO2)

| Model | Required | Optional (with defaults) |
|---|---|---|
| `StartSignupRequest` | `email:String(email)` | — |
| `VerifySignupRequest` | `email:String(email)`, `code:String` | — |
| `SignupRequest` | `first_name`, `last_name`, `gender`, `programme`, `semester:Int`, `branch`, `username`, `roll_number`, `email:String(email)`, `password` — **all 10** | — |
| `ForgotPasswordRequest` | `identifier:String` (not `email`) | — |
| `ResetPasswordRequest` | `identifier`, `code`, `new_password` | — |

`UserResponse`: required `id:Int`, `email`, `username`, `is_email_verified:Bool`;
optional `full_name`, `roll_number`, `role`. Email-domain signup rejection returns
**422** — render it as a field error on `email`, not a generic failure.

**Schedule (4)** — `GET /schedule/now` · `GET /schedule/courses/extra` →
`ExtraCourseResponse[]` · `POST /schedule/courses/extra` ←
`ExtraCourseCreate{code,name,semester:Int,branch}` → `ExtraCourseResponse` ·
`DELETE /schedule/courses/extra/{course_code}`

**Attendance (7)** — `POST /attendance/` · `GET /attendance/summary` ·
`GET /attendance/subjects` · `GET /attendance/records` · `GET /attendance/sync` ·
`GET /attendance/course/{course_id}` · `DELETE /attendance/{record_id}`

**Timetable (8)** — `GET /timetable/slots` → `SlotResponse[]` ·
`GET /timetable/options` · `PUT /timetable/slot/{slot_id}` ← `SlotEdit` (all fields
optional/nullable) · `GET /timetable/uploads/latest` · `GET /timetable/uploads/preview` ·
`DELETE /timetable/` · `POST /timetable/upload` (multipart, field **`file`**, required) ·
`POST /timetable/debug/parse-timetable` (**debug only — never in release**)

`SlotResponse`: required `id:Int`, `day`, `start_time`, `end_time`, `room`,
`course_code`, `branch_or_program`, `semester:Int`; optional `instructor`.

**Exam (15)** — `GET /exam/timetable` · `GET /exam/clashes` · `GET /exam/seating` ·
`GET /exam/lookup` · `GET /exam/quick-lookup` · `GET /exam/pdf` · `GET /exam/status` ·
`GET /exam/uploads/latest` · `GET /exam/uploads/preview` · `DELETE /exam/timetable` ·
`DELETE /exam/seating` · `POST /exam/seating/upload` (multipart `file`) ·
`POST /exam/timetable/upload` (multipart `file`) ·
`POST /exam/upload` (**legacy seating — do not use**) ·
`POST /exam/debug/parse-exam` (**debug only**)

**Rooms (2)** — `GET /rooms/vacant` · `GET /rooms/all`

**Profile (5)** — `GET /profile/` · `PUT /profile/` ← `ProfileUpdate` (all optional) ·
`GET /profile/options` · `POST /profile/branch-change` · `DELETE /profile/branch-change`

`ProfileResponse`: required `id:Int`, `semester:Int`, `branch`; optional
`first_name`, `last_name`, `phone`, `programme`, `section`, `elective_codes[]`,
`attendance_target:Double=75.0`, `skills[]`, `bio`, `contact`, `original_branch`,
`branch_changed_at`, `branch_change_requested`, `requested_branch`,
`branch_change_reason`, `branch_change_requested_at`.

**Feedback (6)** — `POST /feedback/` is **multipart**, fields
`message, name, phone, email, subject, file`, only `message` required ·
`GET /feedback/mine` → `object[]` · `POST /feedback/{feedback_id}/reply` ·
`GET /feedback/ingest`, `GET /feedback/ingest/status` (**server-side IMAP — skip**) ·
`GET /feedback/responses` (**admin — skip, Trap 3**)

**Teams (12)** — `GET /teams` · `POST /teams` ← `TeamCreate{name, description="",
tech_stack[], wanted[], max_members=4, request_to_join=false, hackathon_id}` ·
`GET /teams/match` · `GET /teams/mine` · `GET /teams/requests` ·
`PUT /teams/requests/{request_id}` · `GET|PUT|DELETE /teams/{team_id}` ·
`GET /teams/{team_id}/members` · `POST /teams/{team_id}/join` ·
`POST /teams/{team_id}/leave`

**Hackathons (4)** — `GET /hackathons` · `POST /hackathons` ·
`POST /hackathons/feed/sync` · `GET /hackathons/media/{name}`. Thin — deprioritize.

**OCR (4)** — **EXCLUDED. See Trap 2.**

**Monitoring (12)** — **EXCLUDED.** All 12 (`/monitoring/{subsections,overview,
health,activity,monetisation,security,feedback,history,freshness,export/{sub}}`,
`POST /monitoring/scan/{sub}`, `POST /monitoring/rollup`) are behind
`get_current_admin`. The mobile app is the **collector**, not the admin dashboard.

> Many GETs declare **no response model** (free-form `dict`). Read the backend source
> for those, or decode defensively with `ignoreUnknownKeys = true` and nullable fields.

---

## TELEMETRY — WHAT THE MOBILE APP IS FOR

Three public, unauthenticated, IP-rate-limited ingest endpoints. All accept
`application/json` with a free-form object body (no declared schema).

- Server returns **503** when `TELEMETRY_ENABLED=false` → client must disable
  permanently for the session and drop the queue.
- **429** carries `Retry-After` → pause flushing that long; never retry in a loop.
- **413** if a batch is too large → flush in batches of **≤ 20**.

`POST /collect/events`
```json
{"events":[{"event_name":"screen_view","platform":"android","session_id":"<uuid per session>",
            "props":{"screen_name":"Schedule"},"ts":"2026-10-08T12:00:00Z",
            "app_version":"1.0","os_version":"14","device_model":"Pixel 7a","country":null}]}
```

`POST /collect/crash` — required `platform`, `kind`(`"crash"`|`"anr"`), `session_id`,
`fingerprint`, `fatal`; optional `exception_type`, `message`, `stack_trace`,
`app_version`, `os_version`, `device_model`, `foreground`.

`POST /collect/security-signal` — required `platform`, `kind` where `kind` ∈
`root_detected`, `emulator_detected`, `tamper_detected`, `hook_detected`,
`debugger_detected`.

### Telemetry client constraints

- One object, e.g. `CampusPilotTelemetry.init(app, baseUrl)`, called from
  `Application.onCreate`. `init()` **only** allocates an empty queue and registers
  `ProcessLifecycleOwner` listeners — **no I/O, no crypto, no hashing at startup.**
- In-memory `ArrayDeque`, hard cap **200**, drop-oldest. Never write telemetry to
  disk (crash file is the only exception) so the queue cannot grow unbounded.
- Flush triggers, and only these: `ProcessLifecycleOwner` `ON_STOP`, and a 60 s
  `flowWhileSubscribed` timer. Guard with an `AtomicBoolean` so exactly one flush is
  ever in flight.
- Flush failure → drop the batch, bump a local counter, never loop-retry.
- User-visible opt-out switch in Profile, default **on**, persisted in
  `SharedPreferences`, honoured immediately and permanently when off.
- Screen views hook the **single** `NavHost` `onNavigate` callback — no per-screen
  sprinkling.

### Crash capture — zero dependencies

Install `Thread.setDefaultUncaughtExceptionHandler` in `Application.onCreate`.
Serialise with `kotlinx.serialization`, append to `filesDir/cp-crash.jsonl`
(size-capped, rotate/trim), then **delegate to the previous handler** so Play
Console's own native reporting still works. Flush on next launch.
Cap `stack_trace` at 8000 chars. `fingerprint` = SHA-256 of
`exception_type + top 3 stack frames` via `java.security.MessageDigest`
(**no extra crypto library**).

Do **not** build an ANR watchdog — a watchdog thread costs battery and correctness.

### Security-signal detection — zero dependencies

Run **once** at startup on `Dispatchers.IO`; report **only on state change**, never
every launch.

- root: `Build.TAGS` contains `test-keys`; `su`/`busybox` resolvable on `PATH`;
  `/system/xbin/su`, `/system/app/Superuser.apk`, `/sbin/.magisk`, `/debug_ramdisk`
- debugger: `Debug.isDebuggerConnected()`, `Debug.waitingForDebugger()`
- tamper: `ApplicationInfo.FLAG_DEBUGGABLE` set while `BuildConfig.DEBUG == false`
- emulator: `Build.FINGERPRINT` starts with `generic` or contains
  `vbox`/`emulator`/`test-keys`; `Build.MODEL`/`MANUFACTURER` contains
  `sdk`/`emulator`/`genymotion`/`nox`; `ro.kernel.qemu == 1`;
  `ro.hardware` ∈ {`goldfish`,`ranchu`}; `/dev/socket/qemud` exists
- hook: reflectively test for `de.robv.android.xposed.XposedBridge`

---

## PHASES — ONE PER MESSAGE, THEN STOP FOR CONFIRMATION

**Phase A — Make it build, strip bloat.** Add `INTERNET`; add Compose compiler plugin,
`buildFeatures { compose = true }`, Compose BOM to the catalog; create
`EssentialTheme`/`CampusPilotTheme` + `Color.kt` + `Type.kt`; delete `appcompat` and
`material`; enable R8 + `isShrinkResources` for release; set
`android.enableR8.fullMode=true`; add the R8 rules for kotlinx.serialization.
`./gradlew assembleRelease` must pass. Report the baseline APK size.

**Phase B — Plumbing only, no screens.** `AppContainer`; `CAMPUSPILOT_BASE_URL`
property + debug network-security config; one `OkHttpClient`; `AuthInterceptor`;
`ApiResult<T>` sealed type mapping status → typed error (401 → re-login,
422 → field errors, 429 → `Retry-After`, 503 → disabled, 5xx → retryable);
`@Serializable` DTOs for the models above; `EncryptedSharedPreferences` token store;
injectable `CoroutineDispatcher` for tests.

**Phase C — Auth.** Login (**form-encoded**, Trap 1), session restore on cold start,
logout, signup start→verify→signup (**10 required fields**), resend code,
forgot/reset (`identifier`, not `email`), 422 field-error rendering, plus the
telemetry opt-out switch in Profile.

**Phase D — The five student screens.** Schedule → Now/Next, Attendance → summary +
per-subject, Timetable → weekly grid, Exam → timetable + clashes, Rooms → vacant now.
Ask me which one you want **first** and do that one properly (loading / empty / error
/ populated + pull-to-refresh) rather than five shallow ones.

**Phase E — Upload + community.** Timetable PDF upload (multipart `file`), exam +
seating upload, Teams, Feedback (`POST /feedback/` is multipart `message,name,phone,
email,subject,file`). **No OCR (Trap 2). No Feedback Responses (Trap 3).**

**Phase F — Telemetry integration.** `CampusPilotTelemetry`, crash capture,
security-signal detection, `NavHost` screen-view hook, opt-out switch.

**Phase G — Verify size and speed.** Report before/after APK size, dependency tree,
cold start, and the acceptance checks below. Paste real build numbers.

---

## ACCEPTANCE CHECKS I WILL RUN

1. `./gradlew assembleRelease` and `./gradlew bundleRelease` both succeed.
2. Release APK size printed and compared to the Phase A baseline.
3. `./gradlew :app:dependencies` — zero banned dependencies.
4. Grep your own source: **zero** hits for `runBlocking`, `Thread.sleep`,
   `GlobalScope`, `LaunchedEffect(while(true`, and no `!!` on network-decoded fields.
5. No network call in `onCreate`/`onResume` that is not lifecycle-aware or
   user-initiated.
6. `./gradlew :app:testReleaseUnitTest` passes — at minimum: token-store test, one
   MockWebServer test per auth flow, a **form-encoded login** test, and a telemetry
   batching/backoff test.
7. Release manifest contains no `google-services` / Firebase classes.
8. README section: how to set `CAMPUSPILOT_BASE_URL` for emulator vs physical device,
   and the debug-only cleartext policy.

---

## ABSOLUTE RULES

- **One phase per message.** Stop and ask for confirmation after each. Do not chain
  phases even when they look small.
- **Do not `git commit`** unless I ask. Show `git status --short` instead.
- **Do not modify the CampusPilot backend** from this project. If the backend is wrong
  or missing something, tell me and stop.
- **Never read, copy, log or commit** any `.env`, API key, token, secret, real roll
  number, or real student email address. Never create a `google-services.json`.
  Never hardcode an `hf_token`.
- If a task genuinely cannot be done within the dependency budget, **say so and stop
  for my decision.** Never silently install a library to get past it.
- If unsure what an endpoint actually returns, read the backend source at
  `C:\Users\Appex\Documents\Default Project\CampusPilot\backend\backend\` before
  guessing.

---

## START

Begin with **Phase A only**. Report what was broken, what you changed, the exact
release APK size, and confirm `./gradlew assembleRelease` is green. Then stop.