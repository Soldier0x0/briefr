# Gemini Review Reconciliation — PRs #306–#385

Generated: 2026-07-09T14:46:43Z

## Scope

- Repository: Soldier0x0/briefr
- PR range: #306–#385 (inclusive)
- Source of truth for fix status: current `main` at reconciliation time

## Extraction Method

- `gh api --paginate repos/Soldier0x0/briefr/pulls/<N>/comments` for N=306..385
- Filtered inline review comments where `user.login` matched `gemini-code-assist[bot]`
- Raw extraction preserved in `docs/reviews/gemini_inline_comments_306_385.json`

## Reviewer Identities Found

- `gemini-code-assist[bot]`

## Totals

- PRs audited: 80
- PRs with Gemini inline findings: [306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 328, 329, 330, 331, 332, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 346, 348, 350, 351, 352, 353, 354, 355, 356, 357, 358, 360, 362, 364, 365, 366, 368, 371, 372, 373, 374, 375, 376, 378, 379, 380, 381, 382, 383, 384, 385]
- Substantive Gemini inline comments: 174
- VALID_UNFIXED (pre-correction): 0
- ALREADY_FIXED: 172
- SUPERSEDED: 0
- OBSOLETE: 1
- FALSE_POSITIVE: 1
- DUPLICATE: 0

## Finding Inventory

### F-306-3539062383

- **PR:** #306
- **Comment ID:** 3539062383
- **Gemini severity:** medium
- **Original file:** `backend/.env.example`
- **Original line:** 15
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/306#discussion_r3539062383
- **Gemini finding summary:** In the **Database** section, the keys are not sorted alphabetically. Reordering them alphabetically aligns with the PR's goal of sorting keys within each section.
- **Gemini suggested fix:** BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS=10
DATABASE_POOL_COMMAND_TIMEOUT_SECONDS=60
DATABASE_POOL_SIZE=20
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
- **Current main file/path:** `backend/.env.example`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Env example key ordering applied in prior PR

### F-306-3539062387

- **PR:** #306
- **Comment ID:** 3539062387
- **Gemini severity:** medium
- **Original file:** `backend/.env.example`
- **Original line:** 41
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/306#discussion_r3539062387
- **Gemini finding summary:** In the **External API keys** section, `GREYNOISE_API_KEY` should be sorted before `GROQ_API_KEY` to maintain strict alphabetical order as stated in the section header and PR description.
- **Gemini suggested fix:** GREYNOISE_API_KEY=your_greynoise_api_key_here
GROQ_API_KEY=your_key_here
- **Current main file/path:** `backend/.env.example`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Env example key ordering applied in prior PR

### F-306-3539062394

- **PR:** #306
- **Comment ID:** 3539062394
- **Gemini severity:** medium
- **Original file:** `backend/.env.example`
- **Original line:** 125
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/306#discussion_r3539062394
- **Gemini finding summary:** In the **ML** section, `# OPENROUTER_MODEL_DETECTION` is placed before `EMBEDDINGS_CACHE_DIR`, which violates alphabetical sorting. Since the rest of the section cannot be fully reordered here without touching unmodified lines, we should remove it from this block and place it at the end of the ML section.
- **Gemini suggested fix:** DETECTION_CONTEXT_LLM_ENABLED=0
DETECTION_CONTEXT_LLM_INTERVAL_HOURS=12
DETECTION_CONTEXT_LLM_MAX_PER_RUN=10
# DETECTION_CONTEXT_SYNC_ENABLED=0
# DETECTION_CONTEXT_SYNC_INTERVAL_HOURS=6
# DETECTION_CONTEXT_SYNC_MAX_PER_RUN=500
EMBEDDINGS_CACHE_DIR=
- **Current main file/path:** `backend/.env.example`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Env example key ordering applied in prior PR

### F-307-3539113977

- **PR:** #307
- **Comment ID:** 3539113977
- **Gemini severity:** medium
- **Original file:** `docs/PROGRAM_PRODUCT_OPEN_CORE.md`
- **Original line:** 111
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/307#discussion_r3539113977
- **Gemini finding summary:** The table `correlation_infrastructure` is listed here to be included in the public intel snapshot. However, according to `docs/SPRINT_2026-07.md` (line 263), `correlation_infrastructure` is a dead schema with no writers or readers, slated to be dropped in a future migration. Including it in the public snapshot is unnecessary and could cause export/import issues once the schema is officially dropped. Consider removing it from this list.
- **Gemini suggested fix:** `correlation_actor`, `correlation_temporal`,
- **Current main file/path:** `docs/PROGRAM_PRODUCT_OPEN_CORE.md`
- **Classification:** OBSOLETE
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Referenced schema removed or documented as dead

### F-308-3539146527

- **PR:** #308
- **Comment ID:** 3539146527
- **Gemini severity:** high
- **Original file:** `frontend/src/pages/admin/ApiKeysPage.jsx`
- **Original line:** 92
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/308#discussion_r3539146527
- **Gemini finding summary:** Using `adminApi.post` directly and manually parsing/formatting the errors can lead to unhandled exceptions (e.g., if the response is not valid JSON) and poor error reporting (e.g., displaying `[object Object]` for FastAPI validation errors). Instead, leverage the existing `adminApi.postJson` helper, which automatically utilizes `adminJson` to safely parse JSON, handle network/HTTP errors, and beautifully format validation error arrays.
- **Gemini suggested fix:** let result
      if (restartRequired) {
        result = await adminApi.postJson('/config/apply-all', [{ key, value }])
      } else {
        result = await adminApi.postJson('/config', { key, value })
      }
      const { data } = result

      setEditing(({ [key]: _, ...rest }) => rest)
      await reloadConfig()
      const restarting = restartRequired && (data?.restart_required ?? data?.warning_restart_required)
      toast(saveOutcomeMessage(key, data, restarting), true)
      return true
    } catch (e) {
      toast('Failed: ' + (e.message || String(e)), false)
      return false
    }
- **Current main file/path:** `frontend/src/pages/admin/ApiKeysPage.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** ApiKeysPage uses adminApi.postJson

### F-309-3539249276

- **PR:** #309
- **Comment ID:** 3539249276
- **Gemini severity:** high
- **Original file:** `frontend/src/components/Toast.jsx`
- **Original line:** 115
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/309#discussion_r3539249276
- **Gemini finding summary:** There are two critical issues in the toast timer and pause/resume logic: 1. **Consecutive `pause` calls corrupt remaining time**: If `pause` is triggered multiple times consecutively (e.g., due to multiple `onMouseEnter` or `onFocus` events) while already paused, `remainingRef.current` is recalculated using a later `Date.now()`. This causes the remaining time to incorrectly shrink even though the toast is paused. Adding a guard for `pausedRef.current` prevents this. 2. **Timer reset on re-render**: If `scheduleDismiss` changes (for example, if `onDismiss` is not memoized in a parent component)
- **Gemini suggested fix:** useEffect(() => {
    if (toast.duration == null) return undefined
    scheduleDismiss()
    return clearTimer
  }, [toast.duration, toast.id, scheduleDismiss])

  const pause = () => {
    if (toast.duration == null || pausedRef.current) return
    pausedRef.current = true
    remainingRef.current = Math.max(0, deadlineRef.current - Date.now())
    clearTimer()
  }

  const resume = () => {
    if (toast.duration == null || !pausedRef.current) return
    pausedRef.current = false
    scheduleDismiss()
  }
- **Current main file/path:** `frontend/src/components/Toast.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Toast pause handler guards consecutive pause

### F-309-3539249412

- **PR:** #309
- **Comment ID:** 3539249412
- **Gemini severity:** high
- **Original file:** `frontend/src/pages/admin/shared/RestartBanner.jsx`
- **Original line:** 42
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/309#discussion_r3539249412
- **Gemini finding summary:** There are two issues in the restart banner polling and transition logic: 1. **Banner stuck in "online" phase**: When the fetch succeeds and `setPhase('online')` is called, the component re-renders with the new phase. Because `phase` is a dependency of the polling `useEffect`, the previous effect's cleanup function runs immediately. This cleanup function clears `pollRef.current`, which was just set to the `setPhase('hidden')` timeout, meaning the banner will never transition to `'hidden'` and remains stuck on screen. Moving the `'online'` to `'hidden'` transition to a separate, dedicated effect
- **Gemini suggested fix:** useEffect(() => {
    if (phase !== 'restarting') return undefined

    let cancelled = false

    async function pollHealth() {
      if (cancelled) return
      try {
        const res = await fetch('/api/health', { cache: 'no-store' })
        if (cancelled) return
        if (res.ok) {
          setPhase('online')
          return
        }
      } catch { /* backend still down */ }
      if (cancelled) return
      pollRef.current = setTimeout(pollHealth, POLL_MS)
    }

    pollRef.current = setTimeout(pollHealth, POLL_MS)
    return () => {
      cancelled = true
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [phase])

  useEffect(() => {
    if (phase !== 'online') return undefined
    const timer = setTimeout(() => setPhase('hidden'), BACK_MS)
    return () =>
- **Current main file/path:** `frontend/src/pages/admin/shared/RestartBanner.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-310-3539322943

- **PR:** #310
- **Comment ID:** 3539322943
- **Gemini severity:** high
- **Original file:** `backend/routers/me.py`
- **Original line:** 48
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/310#discussion_r3539322943
- **Gemini finding summary:** The `upsert_user_stack` function is called outside of the `try...except ValueError` block. Since `upsert_user_stack` calls `encode_profile`, which can raise a `ValueError` if the serialized profile JSON exceeds `MAX_PROFILE_JSON_LEN` (65536 characters), any oversized payload will result in an unhandled 500 Internal Server Error instead of a 422 Unprocessable Entity. Wrapping the entire validation and database execution block in a single `try...except ValueError` block ensures that all validation errors are cleanly returned as 422 HTTP exceptions.
- **Gemini suggested fix:** async def write_stack(body: StackBody, payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        stack_terms = validate_stack_terms(body.stack_terms)
        profile = sanitize_profile(body.profile)
        result = await upsert_user_stack(db, int(payload["sub"]), stack_terms, profile)
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await db.close()
- **Current main file/path:** `backend/routers/me.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-310-3539322951

- **PR:** #310
- **Comment ID:** 3539322951
- **Gemini severity:** medium
- **Original file:** `backend/preferences/validate.py`
- **Original line:** 42
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/310#discussion_r3539322951
- **Gemini finding summary:** The `sanitize_profile` function currently only checks if `operatingSystems`, `applications`, and `aiSystems` are lists, but does not sanitize or validate the individual items within those lists. This allows clients to persist arbitrary keys and nested structures in the database, which deviates from the documented behavior ('unknown keys are dropped and lists are sanitized to the asset-wizard shape') and poses a data integrity risk. We should recursively sanitize these lists to ensure they only contain the expected fields and types.
- **Gemini suggested fix:** def sanitize_profile(data: dict | None) -> dict | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("profile must be a JSON object")
    
    env = data.get("environment") if isinstance(data.get("environment"), dict) else {}
    
    raw_os = data.get("operatingSystems")
    os_list = []
    if isinstance(raw_os, list):
        for item in raw_os:
            if isinstance(item, dict):
                os_list.append({
                    "product": str(item.get("product") or ""),
                    "version": str(item.get("version") or ""),
                    "vendor": str(item.get("vendor") or ""),
                })
                
    raw_apps = data.get("applications")
    apps_list = []
    if isinstance(raw_apps, list):
    
- **Current main file/path:** `backend/preferences/validate.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-311-3541139984

- **PR:** #311
- **Comment ID:** 3541139984
- **Gemini severity:** high
- **Original file:** `frontend/src/utils/userStack.js`
- **Original line:** 63
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/311#discussion_r3541139984
- **Gemini finding summary:** There are three issues with the current implementation of `saveUserStack`:\n\n1. **Race Condition**: If multiple save requests are initiated concurrently (e.g., due to rapid typing/debouncing), out-of-order API responses can overwrite `cachedTerms` with an older value, causing the client-side cache to become out of sync with the latest user input.\n2. **Premature Local Storage Deletion**: `clearLegacyLocalStack()` is called before the API request succeeds. If the server save fails, the user's legacy local stack is permanently lost without being successfully migrated.\n3. **State Inconsistency 
- **Gemini suggested fix:** let saveCounter = 0;

export async function saveUserStack(stackTerms) {
  const trimmed = (stackTerms || '').trim();
  const previousTerms = cachedTerms;
  cachedTerms = trimmed;
  
  saveCounter++;
  const currentCounter = saveCounter;
  
  try {
    const data = await apiSaveUserStack({ stack_terms: trimmed });
    if (currentCounter === saveCounter) {
      cachedTerms = (data?.stack_terms || trimmed).trim();
      clearLegacyLocalStack();
    }
    window.dispatchEvent(new CustomEvent('briefr-stack-change'));
    return cachedTerms;
  } catch (err) {
    if (currentCounter === saveCounter) {
      cachedTerms = previousTerms;
    }
    throw err;
  }
}
- **Current main file/path:** `frontend/src/utils/userStack.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-311-3541139989

- **PR:** #311
- **Comment ID:** 3541139989
- **Gemini severity:** medium
- **Original file:** `frontend/src/App.jsx`
- **Original line:** 392
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/311#discussion_r3541139989
- **Gemini finding summary:** There is a potential race condition where `loadUserStack()` (triggered during the initial authentication flow in `AuthContext`) might complete and dispatch the `briefr-stack-loaded` event before the `App` component has finished mounting and registered its event listener. If this happens, the saved stack terms will not be loaded into the filters on startup.\n\nTo prevent this, we should check if `getSavedStack()` already has a non-empty value on mount and initialize the filters with it immediately, in addition to listening for the event.
- **Gemini suggested fix:** (none)
- **Current main file/path:** `frontend/src/App.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-312-3541205002

- **PR:** #312
- **Comment ID:** 3541205002
- **Gemini severity:** high
- **Original file:** `backend/detection/nuclei_parser.py`
- **Original line:** 125
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/312#discussion_r3541205002
- **Gemini finding summary:** In Nuclei templates, the `path` field can be either a single string or a list of strings. If it is a single string, iterating over it directly using `for raw_path in entry.get("path")` will iterate over each individual character of the string, leading to garbage path extraction and failure to parse the actual path. We should check if the path is a string and wrap it in a list first.
- **Gemini suggested fix:** raw_paths = entry.get("path") or []
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    for raw_path in raw_paths:
        token = str(raw_path or "")
        normalized = _normalize_path(token)
        if normalized:
            paths.append(normalized)
        params.extend(_query_params_from_path(token))
- **Current main file/path:** `backend/detection/nuclei_parser.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-312-3541205005

- **PR:** #312
- **Comment ID:** 3541205005
- **Gemini severity:** medium
- **Original file:** `backend/detection/nuclei_parser.py`
- **Original line:** 65
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/312#discussion_r3541205005
- **Gemini finding summary:** Regular expression matchers (`type: regex`) contain pattern strings (e.g., `(?i)root:.*:0:0:`) rather than literal keywords. Extracting these and appending them to the Sigma rule's `keywords` list will result in broken or unmatchable literal keyword signatures in the generated Sigma rules. We should restrict keyword extraction to `"word"` matchers only.
- **Gemini suggested fix:** if matcher.get("type") != "word":
            continue
        raw_words = matcher.get("words") or []
- **Current main file/path:** `backend/detection/nuclei_parser.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-312-3541205013

- **PR:** #312
- **Comment ID:** 3541205013
- **Gemini severity:** medium
- **Original file:** `backend/detection/nuclei_parser.py`
- **Original line:** 52
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/312#discussion_r3541205013
- **Gemini finding summary:** In `_query_params_from_path`, `parse_qs` is called with `keep_blank_values=False`. Since `_strip_template_vars` strips template variables (e.g., turning `?user={{username}}` into `?user=`), the parameter value becomes empty. With `keep_blank_values=False`, these parameters are completely ignored and not extracted. Setting `keep_blank_values=True` ensures we successfully extract the parameter names even when their values are template variables.
- **Gemini suggested fix:** parsed = parse_qs(query, keep_blank_values=True)
- **Current main file/path:** `backend/detection/nuclei_parser.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-313-3541251364

- **PR:** #313
- **Comment ID:** 3541251364
- **Gemini severity:** medium
- **Original file:** `backend/preferences/display_validate.py`
- **Original line:** 32
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/313#discussion_r3541251364
- **Gemini finding summary:** The `ZoneInfo` constructor can raise other exceptions such as `ValueError` or `OSError` on certain platforms or if the timezone name contains invalid characters (e.g., null bytes). Catching only `ZoneInfoNotFoundError` can lead to unhandled 500 Internal Server Errors. Catching `Exception` ensures all validation failures are gracefully handled as a 422 validation error.
- **Gemini suggested fix:** try:
        ZoneInfo(token)
    except Exception as exc:
        raise ValueError("timezone is not a valid IANA zone") from exc
- **Current main file/path:** `backend/preferences/display_validate.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-313-3541251380

- **PR:** #313
- **Comment ID:** 3541251380
- **Gemini severity:** medium
- **Original file:** `backend/preferences/repo.py`
- **Original line:** 131
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/313#discussion_r3541251380
- **Gemini finding summary:** If the database contains an invalid or corrupted timezone string, calling `validate_timezone` directly on read will raise a `ValueError` and crash the GET request with a 500 or 422 error. It is safer to catch `ValueError` and fall back to `"UTC"` to ensure the read path is robust.
- **Gemini suggested fix:** try:
        tz = validate_timezone(row["timezone"])
    except ValueError:
        tz = "UTC"
- **Current main file/path:** `backend/preferences/repo.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-313-3541251386

- **PR:** #313
- **Comment ID:** 3541251386
- **Gemini severity:** medium
- **Original file:** `frontend/src/pages/admin/DisplayPage.jsx`
- **Original line:** 15
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/313#discussion_r3541251386
- **Gemini finding summary:** If `setDisplayPrefs` fails (e.g., due to a network error or expired session), the optimistic update in `saveUserPreferences` will revert the global `cached` preferences and DOM styles back to their previous values. However, the local component state `prefs` is never reverted, causing the UI controls to become out of sync with the actual applied styles. Chaining `.catch()` to revert the local state on failure fixes this.
- **Gemini suggested fix:** void setDisplayPrefs(next).catch(() => setPrefs(getDisplayPrefs()))
- **Current main file/path:** `frontend/src/pages/admin/DisplayPage.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-313-3541251391

- **PR:** #313
- **Comment ID:** 3541251391
- **Gemini severity:** medium
- **Original file:** `frontend/src/pages/admin/DisplayPage.jsx`
- **Original line:** 19
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/313#discussion_r3541251391
- **Gemini finding summary:** If `resetDisplayPrefs` fails, the promise rejects and the `.then()` callback is skipped, leaving the local component state `prefs` out of sync with the reverted global preferences. Using `.finally()` ensures the local state is updated to match the actual applied preferences regardless of whether the API call succeeds or fails.
- **Gemini suggested fix:** void resetDisplayPrefs().finally(() => setPrefs(getDisplayPrefs()))
- **Current main file/path:** `frontend/src/pages/admin/DisplayPage.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-314-3541338572

- **PR:** #314
- **Comment ID:** 3541338572
- **Gemini severity:** high
- **Original file:** `frontend/src/utils/userPreferences.js`
- **Original line:** 196
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/314#discussion_r3541338572
- **Gemini finding summary:** There is a potential state-synchronization issue if `saveUserStackProfile` fails. Currently, `patchUserPreferences` is called first to update `remember_profile_on_server` on the server and in the local `cached` object. If the subsequent `saveUserStackProfile` call fails (e.g., due to a network error or validation failure), the error propagates to `handleRememberChange` in `AssetProfileContext.jsx`, which reverts the UI toggle state to `previous`. However, the server and the local `cached` preferences object will remain set to the new (failed) state, causing a mismatch. **Solution:** Perform th
- **Gemini suggested fix:** export async function setRememberProfileOnServer(enabled, sessionProfile = null) {
  if (!isUserPreferencesLoaded()) {
    return enabled
  }
  if (enabled && sessionProfile) {
    await saveUserStackProfile(sessionProfile)
  } else if (!enabled) {
    await saveUserStackProfile(null)
  }
  const data = await patchUserPreferences({ remember_profile_on_server: !!enabled })
  cached = fromApi(data)
  try {
    window.dispatchEvent(new CustomEvent('briefr-preferences-loaded', { detail: cached }))
  } catch { /* unavailable */ }
  return cached.remember_profile_on_server
}
- **Current main file/path:** `frontend/src/utils/userPreferences.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-315-3541375455

- **PR:** #315
- **Comment ID:** 3541375455
- **Gemini severity:** high
- **Original file:** `docs/DATA_SNAPSHOT.md`
- **Original line:** 46
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/315#discussion_r3541375455
- **Gemini finding summary:** Including the entire `feed_cache` table in the public bundle poses a significant security and privacy risk. While `feed_cache` stores public intelligence (like `ssvc:` and `detection_ctx:`), it also caches on-demand lookup results such as `greynoise:` and `otx:ioc:` (as detailed in `docs/SPRINT_2026-07.md` line 254). These keys contain specific indicators (IPs, domains, hashes) queried by the operator's analysts, which could leak sensitive internal investigation targets.\n\nTo prevent information disclosure, the export script must explicitly filter `feed_cache` rows to only include safe public
- **Gemini suggested fix:** (none)
- **Current main file/path:** `docs/DATA_SNAPSHOT.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-315-3541375460

- **PR:** #315
- **Comment ID:** 3541375460
- **Gemini severity:** high
- **Original file:** `docs/DATA_SNAPSHOT.md`
- **Original line:** 97
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/315#discussion_r3541375460
- **Gemini finding summary:** Excluding the `alembic_version` table from the dump will cause subsequent database migrations to fail on the restored database. When an operator runs `alembic upgrade head` on the restored database, Alembic will find no migration history (since the table is missing) and will attempt to run all migrations from the beginning, resulting in \"table already exists\" errors and crashing the application.\n\nSince `alembic_version` contains only the current schema version hash and no sensitive operator data, it is safe and necessary to include it in the public bundle.
- **Gemini suggested fix:** (none)
- **Current main file/path:** `docs/DATA_SNAPSHOT.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-315-3541375464

- **PR:** #315
- **Comment ID:** 3541375464
- **Gemini severity:** medium
- **Original file:** `docs/DATA_SNAPSHOT.md`
- **Original line:** 18
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/315#discussion_r3541375464
- **Gemini finding summary:** The custom-format `pg_dump` (`-Fc`) is already compressed using `zlib` by default. Compressing it again with `gzip` (creating a `.pgdump.gz` file) is redundant, provides negligible extra compression, and complicates the restore process because `pg_restore` cannot directly read a `.gz` file.\n\nAdditionally, the restore runbook command on line 137 uses `briefr-intel-YYYY-MM.pgdump` directly without the `.gz` extension. Removing the redundant gzip step aligns the container format with the restore command.
- **Gemini suggested fix:** | Container | `briefr-intel-YYYY-MM.pgdump` (custom-format `pg_dump`, compressed by default) |
- **Current main file/path:** `docs/DATA_SNAPSHOT.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-316-3541398169

- **PR:** #316
- **Comment ID:** 3541398169
- **Gemini severity:** high
- **Original file:** `scripts/export_intel_snapshot.py`
- **Original line:** 174
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/316#discussion_r3541398169
- **Gemini finding summary:** The current substring check (`f"TABLE public {forbidden}" in line`) can lead to false positives if any valid table name contains a forbidden table name as a prefix (for example, a table named `users_archive` or `watchlist_items` would trigger a false positive match for `users` or `watchlist`). Using a regular expression to parse the exact table name from the `pg_restore --list` output avoids these false positives.
- **Gemini suggested fix:** import re
    pattern = re.compile(r"^\\s*\\d+;\\s+\\d+\\s+(?:\\d+\\s+)?TABLE(?: DATA)?\\s+(\\S+)\\s+(\\S+)")
    for line in proc.stdout.splitlines():
        match = pattern.match(line)
        if match:
            table_name = match.group(2).strip('"')
            if table_name in FORBIDDEN_TABLES:
                raise RuntimeError(f"forbidden table {table_name} found in dump catalog")
- **Current main file/path:** `scripts/export_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-316-3541398172

- **PR:** #316
- **Comment ID:** 3541398172
- **Gemini severity:** medium
- **Original file:** `scripts/export_intel_snapshot.py`
- **Original line:** 194
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/316#discussion_r3541398172
- **Gemini finding summary:** Using `dst.writelines(src)` on a binary file is inefficient because it forces Python to scan the entire binary stream for newline characters (`\\n`) to split it into lines before writing. Using `shutil.copyfileobj` is the standard, chunk-based, and highly efficient way to copy binary streams.
- **Gemini suggested fix:** import shutil
        with staging.open("rb") as src, gzip.open(output_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
- **Current main file/path:** `scripts/export_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-316-3541398177

- **PR:** #316
- **Comment ID:** 3541398177
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_intel_snapshot_export.py`
- **Original line:** 57
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/316#discussion_r3541398177
- **Gemini finding summary:** Using `rsplit("/", 1)[0]` to manipulate the database URL strips any query parameters (such as `sslmode=disable` or other connection options). This can cause connection failures in environments where specific query parameters are required. Using `urllib.parse.urlparse` and `urlunparse` allows safely replacing the database name while preserving all query parameters.
- **Gemini suggested fix:** from urllib.parse import urlparse, urlunparse
    parsed = urlparse(database_url)
    admin_url = urlunparse(parsed._replace(path="/postgres"))
    admin_params = parse_postgres_url(admin_url)
- **Current main file/path:** `backend/tests/test_intel_snapshot_export.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-316-3541398180

- **PR:** #316
- **Comment ID:** 3541398180
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_intel_snapshot_export.py`
- **Original line:** 81
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/316#discussion_r3541398180
- **Gemini finding summary:** Using `rsplit("/", 1)[0]` to construct the restore URL strips any query parameters. Use `urlunparse` with the parsed URL to safely replace the database name while preserving query parameters.
- **Gemini suggested fix:** restore_url = urlunparse(parsed._replace(path=f"/{restore_db}"))
- **Current main file/path:** `backend/tests/test_intel_snapshot_export.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-317-3541433593

- **PR:** #317
- **Comment ID:** 3541433593
- **Gemini severity:** high
- **Original file:** `scripts/export_intel_snapshot.py`
- **Original line:** 167
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/317#discussion_r3541433593
- **Gemini finding summary:** The regular expression `_RESTORE_LIST_TABLE_RE` assumes the schema name is always `public`. If a custom schema is used, `(?:public\s+)?` will match nothing, and `(\S+)` will capture the schema name (e.g., `my_schema`) instead of the table name. This would bypass the forbidden table check, potentially allowing sensitive tables to be exported or restored without detection.\n\nTo fix this, update the regex to correctly capture the table name (the second-to-last field) regardless of the schema name or PostgreSQL version.
- **Gemini suggested fix:** _RESTORE_LIST_TABLE_RE = re.compile(r"^\d+;\s+(?:\d+\s+){1,2}TABLE(?: DATA)?\s+(?:\S+\s+)?(\S+)\s+\S+\s*$")
- **Current main file/path:** `scripts/export_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-318-3541543439

- **PR:** #318
- **Comment ID:** 3541543439
- **Gemini severity:** medium
- **Original file:** `docs/POSTGRES_NATIVE_PLAN.md`
- **Original line:** 9
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/318#discussion_r3541543439
- **Gemini finding summary:** The documentation updates state that the `test-postgres` CI job now runs the full test suite (`pytest tests/ -q`). However, the actual GitHub Actions workflow file (`.github/workflows/backend-tests.yml`) is not modified in this pull request. To fully enable the gate, the workflow file needs to be updated to replace the pool-only/smoke tests with the full suite run.
- **Gemini suggested fix:** (none)
- **Current main file/path:** `docs/POSTGRES_NATIVE_PLAN.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-319-3541685507

- **PR:** #319
- **Comment ID:** 3541685507
- **Gemini severity:** high
- **Original file:** `.gitleaks.toml`
- **Original line:** 12
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/319#discussion_r3541685507
- **Gemini finding summary:** Allowlisting the entire `scripts/` directory is a significant security risk. Scripts (especially deployment, migration, or utility scripts) are common places where real production credentials, API keys, or tokens might accidentally be hardcoded.\n\nSince your local scan of the entire history was clean, you likely do not need to allowlist this directory at all. It is highly recommended to remove this path from the global allowlist to ensure any future scripts are properly scanned for secrets.
- **Gemini suggested fix:** ]
- **Current main file/path:** `.gitleaks.toml`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-320-3541883878

- **PR:** #320
- **Comment ID:** 3541883878
- **Gemini severity:** high
- **Original file:** `backend/db/sync_state.py`
- **Original line:** 97
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/320#discussion_r3541883878
- **Gemini finding summary:** We can optimize these database functions by checking `type(db).__name__` directly. This avoids the overhead of environment lookups and URL parsing inside `is_postgres()` on every query execution, and uses the unified `_SELECT_MAX_MODIFIED_SQL` constant.
- **Gemini suggested fix:** async def get_sync_state_value(db: DbConnection, key: str) -> str | None:
    """Read any sync_state key; returns None when absent."""
    sql = _SELECT_VALUE_PG if type(db).__name__ == "PostgresConnection" else _SELECT_VALUE_SQLITE
    rows = await db.execute_fetchall(sql, (key,))
    return rows[0]["value"] if rows else None


async def set_sync_state_value(db: DbConnection, key: str, value: str) -> None:
    """Upsert any sync_state key (caller commits)."""
    sql = _UPSERT_PG if type(db).__name__ == "PostgresConnection" else _UPSERT_SQLITE
    await db.execute(sql, (key, value, utcnow_str()))


async def get_nvd_sync_watermark(db: DbConnection) -> str | None:
    sql = _SELECT_VALUE_PG if type(db).__name__ == "PostgresConnection" else _SELECT_VALUE_SQLITE
    rows = await db.execute_f
- **Current main file/path:** `backend/db/sync_state.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-320-3541883885

- **PR:** #320
- **Comment ID:** 3541883885
- **Gemini severity:** medium
- **Original file:** `backend/db/sync_state.py`
- **Original line:** 14
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/320#discussion_r3541883885
- **Gemini finding summary:** Since we can optimize the dialect check by inspecting the connection class name directly (e.g., `type(db).__name__ == "PostgresConnection"`), we can avoid importing `is_postgres` and eliminate the overhead of parsing the database URL on every query execution.
- **Gemini suggested fix:** from db.dialect import utcnow_str
from db.metadata import get_cve_count
from db.types import DbConnection
- **Current main file/path:** `backend/db/sync_state.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-320-3541883896

- **PR:** #320
- **Comment ID:** 3541883896
- **Gemini severity:** medium
- **Original file:** `backend/db/sync_state.py`
- **Original line:** 51
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/320#discussion_r3541883896
- **Gemini finding summary:** The SQLite and PostgreSQL queries for selecting the maximum modified date are identical. We can unify them into a single `_SELECT_MAX_MODIFIED_SQL` constant to reduce duplication.
- **Gemini suggested fix:** _SELECT_MAX_MODIFIED_SQL = """
SELECT MAX(modified) AS latest
FROM cves
WHERE modified IS NOT NULL AND modified != ''
"""
- **Current main file/path:** `backend/db/sync_state.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-320-3541883904

- **PR:** #320
- **Comment ID:** 3541883904
- **Gemini severity:** medium
- **Original file:** `backend/db/sync_state.py`
- **Original line:** 63
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/320#discussion_r3541883904
- **Gemini finding summary:** These helper functions can be removed entirely by performing a fast inline class name check on the connection object, which avoids the overhead of calling `is_postgres()` on every query execution.
- **Gemini suggested fix:** (none)
- **Current main file/path:** `backend/db/sync_state.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-321-3542035901

- **PR:** #321
- **Comment ID:** 3542035901
- **Gemini severity:** medium
- **Original file:** `docs/POSTGRES_NATIVE_PLAN.md`
- **Original line:** 104
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/321#discussion_r3542035901
- **Gemini finding summary:** Using string-based type name checking (`type(db).__name__ == "PostgresConnection"`) is fragile and prone to breaking if classes are renamed, subclassed, or mocked during testing.\n\nA more robust and idiomatic approach is to define a property or method (e.g., `is_postgres: bool` or `dialect: str`) on the `DbConnection` protocol in `db/types.py` and implement it on both `SqliteConnection` and `PostgresConnection`. This avoids string-matching and concrete class imports while maintaining clean decoupling.
- **Gemini suggested fix:** 2. Pick SQL via connection property — **not** `is_postgres()` env lookup:\n   `db.is_postgres` (defined on the `DbConnection` protocol).
- **Current main file/path:** `docs/POSTGRES_NATIVE_PLAN.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-321-3542035906

- **PR:** #321
- **Comment ID:** 3542035906
- **Gemini severity:** medium
- **Original file:** `docs/POSTGRES_NATIVE_PLAN.md`
- **Original line:** 124
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/321#discussion_r3542035906
- **Gemini finding summary:** Based on the batching plan, there are exactly 7 PRs remaining in Phase 1 (1 batched PR for watchlist/webhooks, 3 individual PRs, 1 batched PR for metadata/correlation, and 2 solo PRs). Updating '~6' to '7' provides an exact count for tracking progress.
- **Gemini suggested fix:** **7 PRs remaining** in Phase 1 (down from 9 with batching).
- **Current main file/path:** `docs/POSTGRES_NATIVE_PLAN.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-321-3542035913

- **PR:** #321
- **Comment ID:** 3542035913
- **Gemini severity:** medium
- **Original file:** `docs/SPRINT_2026-07.md`
- **Original line:** 337
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/321#discussion_r3542035913
- **Gemini finding summary:** There is a slight inconsistency in the remaining PR count. After the next batched PR (`watchlist` + `webhooks`), there are exactly 6 PRs remaining in total (4 batched/individual modules + 2 solo PRs for `cve.py` and `init.py`). Saying '~5 PRs after that; solo PRs...' could be read as 5 + 2 = 7 PRs after that. Clarifying this to '4 PRs after that, plus solo PRs...' or '6 PRs remaining in total' would keep the sprint checklist perfectly aligned with the 7 total remaining PRs outlined in `POSTGRES_NATIVE_PLAN.md`.
- **Gemini suggested fix:** `sync_state` done (#320); **next:** `watchlist` + `webhooks` (batched);\n      4 PRs after that, plus solo PRs for `cve.py`, `init.py`.
- **Current main file/path:** `docs/SPRINT_2026-07.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-322-3542172254

- **PR:** #322
- **Comment ID:** 3542172254
- **Gemini severity:** high
- **Original file:** `backend/db/webhooks.py`
- **Original line:** 136
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/322#discussion_r3542172254
- **Gemini finding summary:** In PostgreSQL, passing an integer (`1` or `0`) to a `BOOLEAN` column will raise a type mismatch error (`column "enabled" is of type boolean but expression is of type integer`). Since both `sqlite3` and `asyncpg` natively support Python `bool` values (with `sqlite3` automatically converting them to `1`/`0`), we should pass the boolean value directly on Postgres, or conditionally convert it.
- **Gemini suggested fix:** params.append(enabled if pg else int(enabled))
- **Current main file/path:** `backend/db/webhooks.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-322-3542172272

- **PR:** #322
- **Comment ID:** 3542172272
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_db_webhooks.py`
- **Original line:** 94
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/322#discussion_r3542172272
- **Gemini finding summary:** To prevent test flakiness when running against a shared or persistent PostgreSQL database, it is highly recommended to use a unique `destination_id` for this test and filter by it in `list_webhook_delivery_log`. Otherwise, pre-existing delivery logs from other tests or previous runs could cause the assertions on `total` and `len(rows)` to fail.
- **Gemini suggested fix:** destination_id="env:discord_test_unique",
                event_type="kev_alert",
                dedupe_key="CVE-2024-1",
                status="ok",
                error=None,
            )
            await record_webhook_delivery(
                db,
                destination_id="env:discord_test_unique",
                event_type="backup_failure",
                dedupe_key=None,
                status="error",
                error="timeout",
            )
            await db.commit()

            rows, total = await list_webhook_delivery_log(db, destination_id="env:discord_test_unique")
            assert total == 2
            assert len(rows) == 2

            filtered, filtered_total = await list_webhook_delivery_log(
                db, destination_id="env:discord_test_uni
- **Current main file/path:** `backend/tests/test_db_webhooks.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-322-3542172277

- **PR:** #322
- **Comment ID:** 3542172277
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_db_watchlist.py`
- **Original line:** 100
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/322#discussion_r3542172277
- **Gemini finding summary:** The test inserts `CVE_SNOOZE` into the watchlist but does not clean it up. When running against a shared PostgreSQL database, this leaves leftover rows that can pollute the database and potentially affect other tests. Adding a cleanup step in the `finally` block ensures proper test isolation.
- **Gemini suggested fix:** finally:
            await delete_watchlist_entry(db, CVE_SNOOZE)
            await db.commit()
            await db.close()
- **Current main file/path:** `backend/tests/test_db_watchlist.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-323-3542291283

- **PR:** #323
- **Comment ID:** 3542291283
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_db_cache_retention.py`
- **Original line:** 33
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/323#discussion_r3542291283
- **Gemini finding summary:** Since the SQL constants for both SQLite and Postgres are always defined in the module regardless of the active database connection, we can assert both sets of placeholders unconditionally. This simplifies the test and ensures both sets of queries are always verified.
- **Gemini suggested fix:** def test_cache_retention_sql_uses_native_placeholders():\n    assert "$1" in cache_retention_mod._PURGE_IOC_CACHE_PG\n    assert "$2" in cache_retention_mod._PURGE_FEED_CACHE_PREFIX_PG\n    assert "$1" in cache_retention_mod._PURGE_EPSS_HISTORY_PG\n    assert "?" in cache_retention_mod._PURGE_IOC_CACHE_SQLITE\n    assert "?" in cache_retention_mod._PURGE_FEED_CACHE_PREFIX_SQLITE
- **Current main file/path:** `backend/tests/test_db_cache_retention.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-323-3542291288

- **PR:** #323
- **Comment ID:** 3542291288
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_db_cache_retention.py`
- **Original line:** 50
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/323#discussion_r3542291288
- **Gemini finding summary:** To ensure these tests remain compatible when the legacy `db/dialect.py` translation layer is removed in Phase 3, we should avoid using SQLite-style `?` placeholders on Postgres. We can dynamically select the correct placeholders based on the active database backend.
- **Gemini suggested fix:** placeholders = "$1, $2, $3, $4), ($5, $6, $7, $8" if is_postgres() else "?, ?, ?, ?), (?, ?, ?, ?"\n            await db.execute(\n                f"""\n                INSERT INTO ioc_cache (value, ioc_type, result, cached_at)\n                VALUES ({placeholders})\n                """,
- **Current main file/path:** `backend/tests/test_db_cache_retention.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-323-3542291292

- **PR:** #323
- **Comment ID:** 3542291292
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_db_cache_retention.py`
- **Original line:** 118
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/323#discussion_r3542291292
- **Gemini finding summary:** To ensure these tests remain compatible when the legacy `db/dialect.py` translation layer is removed in Phase 3, we should avoid using SQLite-style `?` placeholders on Postgres. We can dynamically select the correct placeholders based on the active database backend.
- **Gemini suggested fix:** placeholders = "$1, $2, $3, $4, $5), ($6, $7, $8, $9, $10" if is_postgres() else "?, ?, ?, ?, ?), (?, ?, ?, ?, ?"\n            await db.execute(\n                f"""\n                INSERT INTO cve_change_history (\n                    cve_id, field_name, old_value, new_value, detected_at\n                ) VALUES ({placeholders})\n                """,
- **Current main file/path:** `backend/tests/test_db_cache_retention.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-324-3542424012

- **PR:** #324
- **Comment ID:** 3542424012
- **Gemini severity:** high
- **Original file:** `backend/db/cache.py`
- **Original line:** 212
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/324#discussion_r3542424012
- **Gemini finding summary:** In SQLite, there is a default limit of 999 variables (parameters) in a single SQL statement. If `get_ioc_cache_batch` is called with a large list of IOCs (e.g., more than 998 distinct values), constructing a single query with that many placeholders will trigger a `sqlite3.OperationalError: too many SQL variables` crash. Since `_SQLITE_IN_CHUNK` (500) is already imported and used elsewhere in this module, we should chunk the batch lookup to ensure safety and consistency across both SQLite and Postgres backends.
- **Gemini suggested fix:** async def get_ioc_cache_batch(db: DbConnection, values: list[str]) -> dict[str, dict]:
    """Batch lookup of cached IOC enrichment results, keyed by value."""
    if not values:
        return {}
    distinct = sorted(set(values))
    pg = _is_postgres_connection(db)
    cutoff = _cutoff_datetime_hours_ago(_IOC_TTL_HOURS)
    results = {}
    for i in range(0, len(distinct), _SQLITE_IN_CHUNK):
        chunk = distinct[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        cutoff_ph = _placeholder(pg, len(chunk) + 1)
        rows = await db.execute_fetchall(
            f"""
            SELECT value, result FROM ioc_cache
            WHERE value IN ({placeholders}) AND cached_at > {cutoff_ph}
            """,
            tuple(chunk) + (cutoff
- **Current main file/path:** `backend/db/cache.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-324-3542424018

- **PR:** #324
- **Comment ID:** 3542424018
- **Gemini severity:** medium
- **Original file:** `backend/db/cache.py`
- **Original line:** 14
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/324#discussion_r3542424018
- **Gemini finding summary:** The function `_insert_cve_changes_batch` is defined in `db/cve.py` and imported into `db/enrichment.py`. Since `db/cache.py` already imports `_SQLITE_IN_CHUNK` directly from `db/cve.py` on line 12, it is cleaner and more direct to import `_insert_cve_changes_batch` from `db/cve.py` as well, rather than through `db/enrichment.py`.
- **Gemini suggested fix:** from db.cve import _SQLITE_IN_CHUNK, _insert_cve_changes_batch
from db.dialect import utcnow_str
- **Current main file/path:** `backend/db/cache.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-325-3542574069

- **PR:** #325
- **Comment ID:** 3542574069
- **Gemini severity:** medium
- **Original file:** `backend/db/enrichment.py`
- **Original line:** 185
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/325#discussion_r3542574069
- **Gemini finding summary:** Using `date.today()` relies on the server's local timezone, which can lead to off-by-one-day errors when compared against UTC timestamps stored in the database (e.g., via `utcnow_str()`). To ensure timezone consistency, use `datetime.now(timezone.utc).date()` instead.
- **Gemini suggested fix:** def _cutoff_date_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
- **Current main file/path:** `backend/db/enrichment.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-325-3542574083

- **PR:** #325
- **Comment ID:** 3542574083
- **Gemini severity:** medium
- **Original file:** `backend/db/enrichment.py`
- **Original line:** 207
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/325#discussion_r3542574083
- **Gemini finding summary:** `_renumber_qmark_placeholders` blindly replaces all `?` characters with `$n`. If the SQL query contains a literal `?` inside a string literal or a comment, it will be incorrectly replaced and corrupt the query. Update the function to skip over string literals (enclosed in single or double quotes) when renumbering placeholders, similar to `_qmark_to_dollar` in `db/dialect.py`.
- **Gemini suggested fix:** def _renumber_qmark_placeholders(sql: str, start: int) -> str:
    """Rewrite ``?`` placeholders to ``$n`` starting at *start*."""
    out: list[str] = []
    n = start
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "?":
            out.append(f"${n}")
            n += 1
            i += 1
        elif ch in ("'", '"'):
            out.append(ch)
            i += 1
            while i < len(sql):
                out.append(sql[i])
                if sql[i] == ch and sql[i - 1] != "\\":
                    i += 1
                    break
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)
- **Current main file/path:** `backend/db/enrichment.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-325-3542574086

- **PR:** #325
- **Comment ID:** 3542574086
- **Gemini severity:** medium
- **Original file:** `backend/db/enrichment.py`
- **Original line:** 286
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/325#discussion_r3542574086
- **Gemini finding summary:** Using `date.today()` relies on the server's local timezone, which can lead to off-by-one-day errors when compared against UTC timestamps stored in the database. To ensure timezone consistency, use `datetime.now(timezone.utc).date()` instead.
- **Gemini suggested fix:** async def snapshot_epss_scores(db: DbConnection, recorded_date: str | None = None) -> int:
    """Persist current EPSS scores before a bulk update (one row per CVE per day)."""
    day = recorded_date or datetime.now(timezone.utc).date().isoformat()
- **Current main file/path:** `backend/db/enrichment.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-328-3543214762

- **PR:** #328
- **Comment ID:** 3543214762
- **Gemini severity:** high
- **Original file:** `backend/tests/test_db_init.py`
- **Original line:** 107
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/328#discussion_r3543214762
- **Gemini finding summary:** In Postgres test environments, the database is typically shared across tests. Since `test_normalize_epss_scores_zeros_to_null` inserts and commits a dummy CVE (`CVE-2024-INIT`) without cleaning it up, subsequent tests like `test_init_db_is_idempotent` (which asserts that the `cves` table is empty) will fail if they run after this test.\n\nTo ensure proper test isolation and prevent flaky test failures, we should delete the inserted test record in the `finally` block.
- **Gemini suggested fix:** finally:\n            try:\n                delete_sql = (\n                    "DELETE FROM cves WHERE cve_id = $1"\n                    if is_postgres()\n                    else "DELETE FROM cves WHERE cve_id = ?"\n                )\n                await db.execute(delete_sql, ("CVE-2024-INIT",))\n                await db.commit()\n            except Exception:\n                pass\n            await db.close()
- **Current main file/path:** `backend/tests/test_db_init.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-329-3544074290

- **PR:** #329
- **Comment ID:** 3544074290
- **Gemini severity:** medium
- **Original file:** `docs/SPRINT_2026-07.md`
- **Original line:** 304
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/329#discussion_r3544074290
- **Gemini finding summary:** There is an identifier collision with **E7**. `E7` is already defined and completed in **Track L** (line 63) as `E7. Admin config Save UX.`. To avoid confusion and maintain unique identifiers across the sprint document, please rename this new Track E item to **E9** (with **E9a** and **E9b**). Additionally, the endpoint path in the E-PR4 row is listed as `GET /api/cves/{id}`, but the actual router path is `GET /api/cves/{cve_id}`. It is corrected here for consistency.
- **Gemini suggested fix:** | E-PR2 | **E9a** Intel tab | Missing CSS (corr-*, drawer-investigate-btn in DetailDrawer.css); correlation compact list; dismiss UX |
| E-PR3 | **E9b** Drawer readability | Contrast/typography floor; public exploits table; EPSS hide flat sparklines |
| E-PR4 | **E8** GreyNoise | **Off** auto GET /api/cves/{cve_id} path; on-demand Intel + weekly quota UI (50/wk); amend I6 |
- **Current main file/path:** `docs/SPRINT_2026-07.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-329-3544074308

- **PR:** #329
- **Comment ID:** 3544074308
- **Gemini severity:** medium
- **Original file:** `docs/SPRINT_2026-07.md`
- **Original line:** 319
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/329#discussion_r3544074308
- **Gemini finding summary:** Rename the checklist item from **E7** to **E9** to resolve the identifier collision with `E7. Admin config Save UX.` in Track L.
- **Gemini suggested fix:** - [ ] **E9. Drawer / Intel readability** (audit 2026-07-08). — E-PR2 + E-PR3
- [ ] **E8. GreyNoise quota-safe detail intel.** — E-PR4
- **Current main file/path:** `docs/SPRINT_2026-07.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-330-3544110612

- **PR:** #330
- **Comment ID:** 3544110612
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 215
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/330#discussion_r3544110612
- **Gemini finding summary:** When `onDismiss` is falsy, `CorrelationDismiss` returns `null`. However, the wrapping `<div className="corr-finding-foot">` is still rendered. Since this div has a top border and padding/margin defined in CSS, it will render an empty line and extra spacing at the bottom of each campaign finding card. Wrapping the entire footer container in a conditional check for `onDismiss` avoids this visual bug.
- **Gemini suggested fix:** {onDismiss && (
                <div className="corr-finding-foot">
                  <CorrelationDismiss
                    onDismiss={onDismiss}
                    body={{ scope: 'campaign_id', key: { campaign_id: item.campaign_id } }}
                  />
                </div>
              )}
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-330-3544110622

- **PR:** #330
- **Comment ID:** 3544110622
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/InvestigationPanel.css`
- **Original line:** 333
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/330#discussion_r3544110622
- **Gemini finding summary:** The styles for `.drawer-investigate-btn` have been moved to `DetailDrawer.css` (lines 1519-1535) so they are available before the lazy-loaded `InvestigationPanel` loads. Keeping them here in `InvestigationPanel.css` introduces redundant code duplication and a confusing comment. Removing this block prevents style drift and improves maintainability.
- **Gemini suggested fix:** (none)
- **Current main file/path:** `frontend/src/components/InvestigationPanel.css`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-331-3544151360

- **PR:** #331
- **Comment ID:** 3544151360
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/OverviewTab.jsx`
- **Original line:** 104
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/331#discussion_r3544151360
- **Gemini finding summary:** The boolean expression `(!showSparkline || !meaningfulTrend)` can be simplified to just `!showSparkline`. Since `meaningfulTrend` is already a required condition for `showSparkline` to be true, if `showSparkline` is false, the expression is always true. If `showSparkline` is true, the expression is always false. Simplifying this makes the logic cleaner and easier to maintain.
- **Gemini suggested fix:** const showStaticBar = !loading && score != null && !showSparkline
- **Current main file/path:** `frontend/src/components/DetailDrawer/OverviewTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-331-3544151377

- **PR:** #331
- **Comment ID:** 3544151377
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 23
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/331#discussion_r3544151377
- **Gemini finding summary:** If `new URL(exp.url).hostname` returns an empty string (e.g., for non-standard or malformed URLs), `exploitDisplayTitle` will return `""` instead of falling back to `title || 'Reference'`. Adding a check to ensure `hostname` is truthy before returning it makes the function more robust and prevents empty cells in the exploits table.
- **Gemini suggested fix:** function exploitDisplayTitle(exp) {
  const title = displayText(exp.title) || ''
  if (title && !GENERIC_EXPLOIT_TITLES.has(title)) return title
  if (exp.url) {
    try {
      const hostname = new URL(exp.url).hostname.replace(/^www\./, '')
      if (hostname) return hostname
    } catch {
      /* ignore */
    }
  }
  return title || 'Reference'
}
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-331-3544151387

- **PR:** #331
- **Comment ID:** 3544151387
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer.css`
- **Original line:** 802
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/331#discussion_r3544151387
- **Gemini finding summary:** Setting a hardcoded `max-width: 220px` on the title cell can cause aggressive text wrapping on larger screens (where the drawer is `65vw` or `75vw` wide), leaving a lot of empty space on the right while cramping the title. Since `word-break: break-word` is already present to prevent overflow, we can safely remove `max-width: 220px` to let the title column naturally expand and utilize the available drawer width.
- **Gemini suggested fix:** .drawer-exploit-title-cell {
  color: var(--text);
  word-break: break-word;
}
- **Current main file/path:** `frontend/src/components/DetailDrawer.css`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203459

- **PR:** #332
- **Comment ID:** 3544203459
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/index.jsx`
- **Original line:** 81
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203459
- **Gemini finding summary:** Introduce a `greynoiseError` state to track failures when fetching GreyNoise scans. This aligns with the Track A error-handling goals (no silent or misleading failures) by ensuring that API failures are captured and can be presented to the analyst rather than showing a misleading 'No exploitation-related IPs found' message.
- **Gemini suggested fix:** const [greynoiseScans, setGreynoiseScans] = useState([])
  const [greynoiseLoading, setGreynoiseLoading] = useState(false)
  const [greynoiseLoaded, setGreynoiseLoaded] = useState(false)
  const [greynoiseQuota, setGreynoiseQuota] = useState(null)
  const [greynoiseError, setGreynoiseError] = useState(null)
- **Current main file/path:** `frontend/src/components/DetailDrawer/index.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203479

- **PR:** #332
- **Comment ID:** 3544203479
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/index.jsx`
- **Original line:** 320
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203479
- **Gemini finding summary:** Reset the `greynoiseError` state when the active CVE changes to prevent stale error messages from persisting across different CVE records.
- **Gemini suggested fix:** useEffect(() => {
    if (!cve?.cve_id) {
      setGreynoiseScans([])
      setGreynoiseLoading(false)
      setGreynoiseLoaded(false)
      setGreynoiseQuota(null)
      setGreynoiseError(null)
      return
    }
    setGreynoiseScans([])
    setGreynoiseLoading(false)
    setGreynoiseLoaded(false)
    setGreynoiseError(null)
  }, [cve?.cve_id])
- **Current main file/path:** `frontend/src/components/DetailDrawer/index.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203484

- **PR:** #332
- **Comment ID:** 3544203484
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/index.jsx`
- **Original line:** 356
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203484
- **Gemini finding summary:** Update `loadGreynoiseScans` to catch and store the error message in `greynoiseError` when the GreyNoise scan request fails.
- **Gemini suggested fix:** const loadGreynoiseScans = useCallback(async () => {
    if (!cve?.cve_id) return
    setGreynoiseLoading(true)
    setGreynoiseError(null)
    try {
      const [data, usage] = await Promise.all([
        fetchCVEGreynoiseScans(cve.cve_id),
        fetchIOCUsage().catch(() => null),
      ])
      setGreynoiseScans(Array.isArray(data?.scans) ? data.scans : [])
      if (usage?.services) {
        const gn = usage.services.find(s => s.service === 'greynoise')
        setGreynoiseQuota(gn || null)
      }
    } catch (err) {
      setGreynoiseScans([])
      setGreynoiseError(err?.message || 'Failed to load GreyNoise scans')
    } finally {
      setGreynoiseLoading(false)
      setGreynoiseLoaded(true)
    }
  }, [cve?.cve_id])
- **Current main file/path:** `frontend/src/components/DetailDrawer/index.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203489

- **PR:** #332
- **Comment ID:** 3544203489
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/index.jsx`
- **Original line:** 721
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203489
- **Gemini finding summary:** Pass the `greynoiseError` state to the `TabIntel` component so it can render the error state.
- **Gemini suggested fix:** <TabIntel
              techniques={techniques}
              publicExploits={cve.public_exploits}
              greynoiseConfigured={cve.greynoise_configured}
              greynoiseScans={greynoiseScans}
              greynoiseLoading={greynoiseLoading}
              greynoiseLoaded={greynoiseLoaded}
              greynoiseQuota={greynoiseQuota}
              greynoiseError={greynoiseError}
              onLoadGreynoise={loadGreynoiseScans}
              otxPulses={cve.otx_pulses}
              otxConfigured={cve.otx_configured}
              cve={cve}
- **Current main file/path:** `frontend/src/components/DetailDrawer/index.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203494

- **PR:** #332
- **Comment ID:** 3544203494
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 454
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203494
- **Gemini finding summary:** Accept the `greynoiseError` prop in `TabIntel` to allow rendering of GreyNoise scan fetch errors.
- **Gemini suggested fix:** export default function TabIntel({
  techniques,
  publicExploits,
  greynoiseConfigured,
  greynoiseScans,
  greynoiseLoading,
  greynoiseLoaded,
  greynoiseQuota,
  greynoiseError,
  onLoadGreynoise,
  otxPulses,
  otxConfigured,
  cve,
  loading,
  onInvestigateIp,
  onInvestigatePulse,
  pivotNotice,
  correlation,
  correlationLoading,
  onSelectCorrelatedCve,
  onDismissCorrelation,
}) {
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203501

- **PR:** #332
- **Comment ID:** 3544203501
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 561
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203501
- **Gemini finding summary:** Render a clear error message if `greynoiseError` is present, rather than silently failing or showing a misleading 'No exploitation-related IPs found' message when the API call fails.
- **Gemini suggested fix:** {greynoiseConfigured === false ? (
          <p className="drawer-intel-empty mono">
            // GreyNoise not configured — set GREYNOISE_API_KEY to enable on-demand IP scanning context
          </p>
        ) : greynoiseLoading ? (
          <p className="drawer-intel-empty mono">// Loading GreyNoise scanning context…</p>
        ) : greynoiseError ? (
          <>
            <GreynoiseQuotaLine quota={greynoiseQuota} />
            <p className="drawer-intel-empty mono" style={{ color: 'var(--red)' }}>
              // Error: {greynoiseError}
            </p>
            {onLoadGreynoise && (
              <button type="button" className="drawer-gn-load-btn mono" onClick={onLoadGreynoise}>
                Retry GreyNoise
              </button>
            )}
          </>
        )
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203506

- **PR:** #332
- **Comment ID:** 3544203506
- **Gemini severity:** medium
- **Original file:** `backend/routers/cves.py`
- **Original line:** 1290
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203506
- **Gemini finding summary:** Add error handling and logging around the `greynoise_scans_for_cve` call. If the external GreyNoise API call fails (e.g., due to network issues or rate limits), logging the exception is crucial for diagnostics, and returning a `502 Bad Gateway` is more semantically correct than letting a generic `500 Internal Server Error` propagate.
- **Gemini suggested fix:** try:
            scans = await greynoise_scans_for_cve(
                db,
                row["description"],
                source_urls if isinstance(source_urls, list) else [],
                greynoise_key,
            )
            await db.commit()
        except Exception as exc:
            logger.error("GreyNoise scan failed for %s: %s", cve_id, exc)
            raise HTTPException(status_code=502, detail="GreyNoise API lookup failed")
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-332-3544203516

- **PR:** #332
- **Comment ID:** 3544203516
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 432
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/332#discussion_r3544203516
- **Gemini finding summary:** Apply defensive programming by using the nullish coalescing operator (`??`) to default `week.used` to `0` if it is null or undefined, preventing potential rendering of `undefined` in the UI.
- **Gemini suggested fix:** function GreynoiseQuotaLine({ quota }) {
  const week = quota?.this_week
  if (!week || week.limit == null) return null
  return (
    <p
      className="drawer-gn-quota mono"
      title="GreyNoise Community API — 50 lookups per week (shared with Visualizer)"
    >
      GreyNoise quota: {week.used ?? 0}/{week.limit} this week
      {week.remaining != null ? ` · ${week.remaining} left` : ''}
    </p>
  )
}
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-334-3544284295

- **PR:** #334
- **Comment ID:** 3544284295
- **Gemini severity:** high
- **Original file:** `frontend/src/utils/timezone.js`
- **Original line:** 78
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/334#discussion_r3544284295
- **Gemini finding summary:** In `tzOffsetMinutes`, using `hour12: false` can format midnight as `24` instead of `00` in some environments (such as certain Node.js versions or specific browsers). When parsed as a number and passed to `Date.UTC`, this shifts the constructed time by 24 hours, leading to an incorrect timezone offset. Additionally, if any date/time parts are missing or fail to parse, `Date.UTC` will return `NaN`, which propagates through `Math.round` and results in `NaN` being returned instead of falling back to `0`. To resolve these issues, we should use `hourCycle: 'h23'` (which is standard and avoids the 24
- **Gemini suggested fix:** function tzOffsetMinutes(tz, date = new Date()) {
  try {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en', {
        timeZone: tz,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
      })
        .formatToParts(date)
        .filter(p => p.type !== 'literal')
        .map(p => [p.type, Number(p.value)])
    )
    const asUtc = Date.UTC(
      parts.year,
      parts.month - 1,
      parts.day,
      parts.hour,
      parts.minute,
      parts.second
    )
    if (isNaN(asUtc)) return 0
    return Math.round((asUtc - date.getTime()) / 60000)
  } catch {
    return 0
  }
}
- **Current main file/path:** `frontend/src/utils/timezone.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-334-3544284306

- **PR:** #334
- **Comment ID:** 3544284306
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Header.jsx`
- **Original line:** 196
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/334#discussion_r3544284306
- **Gemini finding summary:** When `shortcutsOpen` is true, the `header-overflow-dropdown` container still has `role="menu"`, but its content is replaced by the `ShortcutsPanel` which has `role="dialog"` and is not a menu item. This is a semantic HTML and accessibility violation because a `menu` should only contain elements with menu-related roles (like `menuitem`). We can dynamically adjust the container's `role` and `aria-label` based on whether the shortcuts panel is currently displayed.
- **Gemini suggested fix:** {overflowOpen && (
              <div
                className="header-overflow-dropdown"
                role={shortcutsOpen ? "dialog" : "menu"}
                aria-label={shortcutsOpen ? "Keyboard shortcuts reference" : "More options"}
              >
- **Current main file/path:** `frontend/src/components/Header.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-334-3544284330

- **PR:** #334
- **Comment ID:** 3544284330
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/ShortcutsPanel.jsx`
- **Original line:** 24
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/334#discussion_r3544284330
- **Gemini finding summary:** When `listOnly` is true, the `ShortcutsPanel` is rendered inline inside the overflow dropdown (which we've updated to act as the dialog container). Having a nested `role="dialog"` here is redundant and can confuse screen readers. We should only apply `role="dialog"` and its associated `aria-label` when the panel is rendered as a standalone modal/popover (i.e., when `listOnly` is false).
- **Gemini suggested fix:** const panel = (
    <div
      className={`shortcuts-panel${listOnly ? ' shortcuts-panel--inline' : ''}`}
      role={listOnly ? undefined : "dialog"}
      aria-label={listOnly ? undefined : "Keyboard shortcuts reference"}
    >
- **Current main file/path:** `frontend/src/components/ShortcutsPanel.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-334-3544284340

- **PR:** #334
- **Comment ID:** 3544284340
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/TimelineHeatmap.jsx`
- **Original line:** 250
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/334#discussion_r3544284340
- **Gemini finding summary:** The heatmap legend has been updated to be discoverable by removing `aria-hidden="true"` and adding a `title` and `aria-label`. However, a `div` is not focusable by default. This means keyboard-only users cannot focus the element to trigger the `title` tooltip or have screen readers announce the `aria-label` in the standard tab flow. Adding `tabIndex="0"` makes the legend keyboard-focusable and fully discoverable for all users.
- **Gemini suggested fix:** <div
                className="timeline-heatmap-legend"
                tabIndex="0"
                title="Cell colour intensity maps to CVE count published that day (0 = none, darker = more)."
                aria-label="Heatmap legend: lighter cells mean fewer CVEs published that day"
              >
- **Current main file/path:** `frontend/src/components/TimelineHeatmap.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-335-3544327471

- **PR:** #335
- **Comment ID:** 3544327471
- **Gemini severity:** high
- **Original file:** `frontend/src/components/StatsRow.jsx`
- **Original line:** 21
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/335#discussion_r3544327471
- **Gemini finding summary:** Nesting an interactive `<button>` (inside `ExplainTip`) within another `<button>` (when `StatCell` is rendered as a button via `onClick`) is invalid HTML and a major accessibility violation. Browsers may parse this incorrectly, and screen readers/keyboard users will not be able to interact with the nested tooltip button properly. Since E-PR8 plans to make all hero tiles clickable (adding `onClick` to all of them), this will become an active bug for the "EXPLOITED IN WILD" tile. To resolve this, consider changing the outer `Tag` to a `div` with `role="button"` and keyboard event handlers when `
- **Gemini suggested fix:** (none)
- **Current main file/path:** `frontend/src/components/StatsRow.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-335-3544327479

- **PR:** #335
- **Comment ID:** 3544327479
- **Gemini severity:** high
- **Original file:** `frontend/src/components/FilterBar.css`
- **Original line:** 210
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/335#discussion_r3544327479
- **Gemini finding summary:** Wrapping the quick filter buttons in `.filter-btn-cell` breaks the mobile layout grid. On mobile (screens ≤ 640px), `.filter-btn` has `flex: 1 1 calc(33.333% - 2px)` to form a 3-column grid. However, because `.filter-btn-cell` is now the direct child of the `.filter-buttons` flex container, the flex properties must be applied to `.filter-btn-cell` instead of `.filter-btn` on mobile. Otherwise, the cells will shrink to their content size and align to the right, completely breaking the responsive grid. To fix this, update the mobile media query (`@media (max-width: 640px)`) to apply the flex bas
- **Gemini suggested fix:** .filter-btn-cell {
  flex: 1 1 calc(33.333% - 2px);
  min-width: 0;
}
.filter-btn {
  width: 100%;
}
- **Current main file/path:** `frontend/src/components/FilterBar.css`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-335-3544327488

- **PR:** #335
- **Comment ID:** 3544327488
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/ExplainTip.css`
- **Original line:** 38
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/335#discussion_r3544327488
- **Gemini finding summary:** Centering the tooltip bubble with `left: 50%` and `transform: translateX(-50%)` on a narrow `14px` button can easily cause horizontal overflow or clipping on mobile devices or when the button is positioned near the screen edges (e.g., in the leftmost or rightmost columns of the `StatsRow` or `FilterBar`). Consider adding optional alignment modifier classes (like `.align-left` or `.align-right`) to `ExplainTip` so that the bubble can be aligned to the left or right edge of the button when rendered near viewport boundaries. For example:
- **Gemini suggested fix:** .explain-tip-wrap.align-left .explain-tip-bubble {
  left: 0;
  transform: none;
}
.explain-tip-wrap.align-right .explain-tip-bubble {
  left: auto;
  right: 0;
  transform: none;
}
- **Current main file/path:** `frontend/src/components/ExplainTip.css`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-336-3544975072

- **PR:** #336
- **Comment ID:** 3544975072
- **Gemini severity:** high
- **Original file:** `backend/routers/cves.py`
- **Original line:** 213
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/336#discussion_r3544975072
- **Gemini finding summary:** There is a subtle but severe correctness bug in SQLite string datetime comparisons when comparing `published` (which uses the ISO8601 `'T'` separator, e.g., `'2024-01-01T00:00:00'`) with `datetime('now', ...)` (which returns a space separator, e.g., `'2024-01-01 00:00:00'`). Because `'T'` (ASCII 84) is lexicographically greater than `' '` (ASCII 32), any time on the same day with a `'T'` separator is incorrectly evaluated as greater than any time on that day with a space separator. This causes incorrect delta calculations. To fix this while preserving index-friendliness on the `published` colu
- **Gemini suggested fix:** SUM(CASE WHEN published >= replace(datetime('now', '-1 day'), ' ', 'T') THEN 1 ELSE 0 END) AS last_24h,\n                SUM(CASE WHEN severity = 'CRITICAL' AND published >= replace(datetime('now', '-1 day'), ' ', 'T') THEN 1 ELSE 0 END)\n                  - SUM(CASE WHEN severity = 'CRITICAL' AND published >= replace(datetime('now', '-2 days'), ' ', 'T')\n                    AND published < replace(datetime('now', '-1 day'), ' ', 'T') THEN 1 ELSE 0 END) AS critical_delta,\n                SUM(CASE WHEN severity = 'HIGH' AND published >= replace(datetime('now', '-1 day'), ' ', 'T') THEN 1 ELSE 0 END)\n                  - SUM(CASE WHEN severity = 'HIGH' AND published >= replace(datetime('now', '-2 days'), ' ', 'T')\n                    AND published < replace(datetime('now', '-1 day'), ' ',
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** FALSE_POSITIVE
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** SQLite datetime T-vs-space comparison is SQLite-test concern; production Postgres uses pg_adapt translation for stats queries

### F-336-3544975093

- **PR:** #336
- **Comment ID:** 3544975093
- **Gemini severity:** medium
- **Original file:** `frontend/src/App.jsx`
- **Original line:** 466
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/336#discussion_r3544975093
- **Gemini finding summary:** The `cleared` filters object in `handleStatTileClick` is missing `my_stack_only` and `summary_only` filters. If either of these filters is active when a user clicks a stat tile, the feed will remain filtered by them, which can lead to confusing or empty results that do not match the global count displayed on the clicked tile. Adding them to `cleared` ensures a consistent and expected user experience.
- **Gemini suggested fix:** const cleared = {\n      severity: null,\n      kev_only: false,\n      kev_overdue_only: false,\n      poc_only: false,\n      patch_only: false,\n      epss_min: null,\n      search: '',\n      stack: '',\n      vendors: '',\n      technique: '',\n      published_on: '',\n      watchlist_only: false,\n      ai_context_only: false,\n      ai_profile_match: false,\n      ai_profile: '',\n      my_stack_only: false,\n      summary_only: false,\n    }
- **Current main file/path:** `frontend/src/App.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-336-3544975105

- **PR:** #336
- **Comment ID:** 3544975105
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/StatsRow.jsx`
- **Original line:** 127
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/336#discussion_r3544975105
- **Gemini finding summary:** When `onStatTileClick` is not provided (e.g., if the component is used in a context where clicking is disabled), the `StatCell` components will still receive a function for `onClick` (since `() => onStatTileClick?.(...)` is always a function) and `interactive` will be `true`. This causes the cells to render as buttons with hover effects and pointer cursors, but clicking them does nothing. To fix this UX issue, conditionally pass `onClick` and `interactive` based on whether `onStatTileClick` is defined.
- **Gemini suggested fix:** interactive={!!onStatTileClick}\n        onClick={onStatTileClick ? () => onStatTileClick('critical') : undefined}\n      />\n      <StatCell\n        value={stats?.high?.toLocaleString()}\n        label="HIGH"\n        variant="amber"\n        loading={loading}\n        delta={stats?.high_delta}\n        interactive={!!onStatTileClick}\n        onClick={onStatTileClick ? () => onStatTileClick('high') : undefined}\n      />\n      <StatCell\n        value={stats?.kev_count?.toLocaleString()}\n        label="EXPLOITED IN WILD"\n        variant="red"\n        loading={loading}\n        delta={stats?.kev_delta}\n        interactive={!!onStatTileClick}\n        onClick={onStatTileClick ? () => onStatTileClick('kev') : undefined}\n        explain="CVEs on CISA's Known Exploited Vulnerabilities 
- **Current main file/path:** `frontend/src/components/StatsRow.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-337-3544990031

- **PR:** #337
- **Comment ID:** 3544990031
- **Gemini severity:** high
- **Original file:** `frontend/src/components/IOCLookup.jsx`
- **Original line:** 772
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/337#discussion_r3544990031
- **Gemini finding summary:** The current implementation of `handlePaste` has two issues: 1. It naively appends the pasted text to the end of the current value (`${value}${pasted}`). This results in incorrect type detection if the user pastes in the middle of the input or replaces a selected range of text. 2. It schedules `applyDetection` via `setTimeout(..., 0)`, but the subsequent `onChange` event from the paste will still trigger `handleValueChange` and schedule a redundant debounced detection 300ms later. Using a `isPasting` ref flag allows the browser's native paste behavior to correctly update the input value (handli
- **Gemini suggested fix:** const isPasting = useRef(false)

  const applyDetection = useCallback((val) => {
    const t = detectType(val)
    setDetectedType(t)
    return t
  }, [])

  // Auto-detect type after 300ms pause (paste triggers immediate detect)
  const handleValueChange = useCallback((e) => {
    const val = e.target.value
    setValue(val)
    if (detectDebounce.current) clearTimeout(detectDebounce.current)
    if (isPasting.current) {
      applyDetection(val)
      isPasting.current = false
    } else {
      detectDebounce.current = setTimeout(() => {
        applyDetection(val)
      }, 300)
    }
  }, [applyDetection])

  const handlePaste = useCallback(() => {
    isPasting.current = true
  }, [])
- **Current main file/path:** `frontend/src/components/IOCLookup.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-338-3545044188

- **PR:** #338
- **Comment ID:** 3545044188
- **Gemini severity:** high
- **Original file:** `frontend/src/App.jsx`
- **Original line:** 574
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/338#discussion_r3545044188
- **Gemini finding summary:** When an IOC is matched in the command palette, it is passed as a raw string to `setIocPrefill(q)`. However, `setIocPrefill` defaults any string payload to `type: 'ip'`. Since `looksLikeIoc` also matches domains and hashes, this causes domains and hashes to be incorrectly prefilled as IP addresses, leading to failed or incorrect lookups. We should detect the specific IOC type (domain, hash, or IP) and pass the structured object to `setIocPrefill` to ensure correct lookup behavior.
- **Gemini suggested fix:** const looksLikeIoc = q.length >= 3
      && !/^CVE-/i.test(q)
      && (
        /^(\d{1,3}\.){3}\d{1,3}$/.test(q)
        || /^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$/.test(q)
        || (q.includes('.') && !q.includes(' '))
      )
    if (looksLikeIoc) {
      const display = q.length > 40 ? `${q.slice(0, 40)}…` : q
      let type = 'domain'
      if (/^(\d{1,3}\.){3}\d{1,3}$/.test(q)) {
        type = 'ip'
      } else if (/^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$/.test(q)) {
        type = 'hash'
      }
      items.unshift({
        id: 'ioc-lookup',
        label: `Lookup IOC: ${display}`,
        hint: 'ioc',
        run: () => {
          setActiveTab('ioc')
          investigationNav.setIocPrefill({
            value: q,
            indicators: [{ type, 
- **Current main file/path:** `frontend/src/App.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-338-3545044198

- **PR:** #338
- **Comment ID:** 3545044198
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/CommandPalette.jsx`
- **Original line:** 17
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/338#discussion_r3545044198
- **Gemini finding summary:** Relying on the HTML `autoFocus` attribute can be unreliable when toggling the visibility/rendering of elements in React. To ensure the input is reliably focused every time the command palette is opened, we should manage focus programmatically using a `ref` and a `useEffect` hook.
- **Gemini suggested fix:** export default function CommandPalette({ open, onClose, getCommands }) {
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)
  const panelRef = useRef(null)
  const inputRef = useRef(null)

  useModalLayer(open, panelRef, { trackDepth: true, trapFocus: true })

  useEffect(() => {
    if (open) {
      const timer = setTimeout(() => {
        inputRef.current?.focus()
      }, 0)
      return () => clearTimeout(timer)
    } else {
      setQuery('')
      setHighlight(0)
    }
  }, [open])
- **Current main file/path:** `frontend/src/components/CommandPalette.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-338-3545044213

- **PR:** #338
- **Comment ID:** 3545044213
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/CommandPalette.jsx`
- **Original line:** 78
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/338#discussion_r3545044213
- **Gemini finding summary:** Currently, `handleKeyDown` is only attached to the `<input>` element. If focus moves to any other element inside the palette (such as the command buttons), pressing `Escape` or arrow keys will no longer work. Moving the `onKeyDown` handler to the `.cmdk-panel` container ensures robust keyboard navigation and accessibility regardless of where focus is currently trapped inside the dialog.
- **Gemini suggested fix:** <div
        className="cmdk-panel"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onKeyDown={handleKeyDown}
      >
        <input
          ref={inputRef}
          type="search"
          className="cmdk-input mono"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Tab, CVE-2024-1234, IOC value, refresh…"
          aria-label="Command search"
          autoComplete="off"
        />
- **Current main file/path:** `frontend/src/components/CommandPalette.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-339-3545519573

- **PR:** #339
- **Comment ID:** 3545519573
- **Gemini severity:** high
- **Original file:** `frontend/src/utils/observableExtraction.js`
- **Original line:** 151
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/339#discussion_r3545519573
- **Gemini finding summary:** Using `Number(o)` to validate IPv4 octets is overly permissive and can lead to false positives. For example, `Number("")` or `Number(" ")` evaluates to `0`, which would allow invalid IP formats like `127..0.1` or `127. .0.1` to pass validation. Additionally, scientific notation (e.g., `1e2` -> `100`) or hexadecimal strings (e.g., `0x10` -> `16`) are also successfully parsed as integers by `Number()`. To ensure strict dotted-decimal IPv4 validation, we should verify that each octet consists solely of digits before parsing it as an integer.
- **Gemini suggested fix:** if (type === OBSERVABLE_TYPES.IPV4) {
    const octets = value.split('.')
    if (octets.length !== 4) return null
    if (!octets.every(o => {
      if (!/^\d+$/.test(o)) return false
      const n = parseInt(o, 10)
      return n >= 0 && n <= 255
    })) return null
    return { type: OBSERVABLE_TYPES.IPV4, value }
  }
- **Current main file/path:** `frontend/src/utils/observableExtraction.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-340-3545932705

- **PR:** #340
- **Comment ID:** 3545932705
- **Gemini severity:** high
- **Original file:** `frontend/src/components/DetailDrawer/OverviewTab.jsx`
- **Original line:** 38
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/340#discussion_r3545932705
- **Gemini finding summary:** Parsing date-only strings (like `YYYY-MM-DD`) with `new Date(dateStr)` treats them as UTC midnight. When calling `toLocaleDateString()` without specifying a timezone, the browser formats the date in the user's local timezone. For users in timezones behind UTC (e.g., North America), this causes a timezone-shifting bug where the displayed due date is shifted to the previous day. Specifying `timeZone: 'UTC'` in the options resolves this issue.
- **Gemini suggested fix:** function formatKevDueDate(dateStr) {
  if (!dateStr) return null
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
  } catch {
    return String(dateStr).slice(0, 10)
  }
}
- **Current main file/path:** `frontend/src/components/DetailDrawer/OverviewTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-340-3545932726

- **PR:** #340
- **Comment ID:** 3545932726
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/ControlTooltip.jsx`
- **Original line:** 14
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/340#discussion_r3545932726
- **Gemini finding summary:** If `children` is not a valid React element (for example, if it is a plain string, number, or a fragment/array of elements), `cloneElement` will throw a runtime error. It is safer to import and use `isValidElement` from `'react'` to guard the cloning process.
- **Gemini suggested fix:** import { cloneElement, isValidElement, useId } from 'react'
import './ControlTooltip.css'

/**
 * Accessible tooltip on the control itself (hover + keyboard focus).
 * Reuses ExplainTip bubble styling without a separate "?" button.
 */
export default function ControlTooltip({ text, children, className = '' }) {
  const id = useId()
  if (!text) return children

  const child = isValidElement(children)
    ? cloneElement(children, {
        'aria-describedby': [children.props?.['aria-describedby'], id].filter(Boolean).join(' ') || id,
      })
    : children
- **Current main file/path:** `frontend/src/components/ControlTooltip.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-340-3545932732

- **PR:** #340
- **Comment ID:** 3545932732
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/StatsRow.jsx`
- **Original line:** 50
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/340#discussion_r3545932732
- **Gemini finding summary:** The condition `onClick && explain` unnecessarily restricts the tooltip to only be displayed when a click handler is present. If a stat cell has an explanation (`explain`) but no click handler, the tooltip will be silently omitted. It is safer and more correct to check only `explain` to decide whether to render the `ControlTooltip`.
- **Gemini suggested fix:** {explain ? (
          <ControlTooltip text={explain}>
            <span tabIndex={0} className="stat-label-text">{label}</span>
          </ControlTooltip>
        ) : (
          label
        )}
- **Current main file/path:** `frontend/src/components/StatsRow.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-340-3545932742

- **PR:** #340
- **Comment ID:** 3545932742
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 152
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/340#discussion_r3545932742
- **Gemini finding summary:** Using a fallback like `row.created_at || row.id || ''` for the React `key` can lead to duplicate key warnings if multiple suppressions have undefined or null values for both fields. It is safer to include the map index (`idx`) as a fallback to guarantee uniqueness.
- **Gemini suggested fix:** {suppressions.map((row, idx) => {
          const peer = row.scope_key || 'link'
          const label =
            row.scope === 'campaign_id'
              ? `Campaign ${peer}`
              : row.scope === 'pulse_id'
                ? `Pulse ${peer}`
                : `Relationship to ${peer}`
          return (
            <li key={row.scope + '-' + peer + '-' + (row.created_at || row.id || idx)} className="corr-suppressed-item">
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-341-3546104311

- **PR:** #341
- **Comment ID:** 3546104311
- **Gemini severity:** high
- **Original file:** `backend/api_queue.py`
- **Original line:** 273
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/341#discussion_r3546104311
- **Gemini finding summary:** If `request_id` is provided but is invalid or has already been released, the current logic falls back to popping from the active requests stack (`elif stack: rid = stack.pop()`). This can corrupt the active requests stack and prematurely release/delete metadata for other active requests. We should only fall back to popping from the stack if `request_id` is `None`.
- **Gemini suggested fix:** if request_id is not None:
        if request_id in _requests:
            _requests.pop(request_id, None)
            if request_id in stack:
                stack.remove(request_id)
            state.active = max(0, state.active - 1)
        return

    if stack:
        rid = stack.pop()
        _requests.pop(rid, None)
    state.active = max(0, state.active - 1)
- **Current main file/path:** `backend/api_queue.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-341-3546104320

- **PR:** #341
- **Comment ID:** 3546104320
- **Gemini severity:** medium
- **Original file:** `frontend/src/utils/apiQueuePresentation.js`
- **Original line:** 83
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/341#discussion_r3546104320
- **Gemini finding summary:** If `requests` or `sources` is `null` (which can happen if the backend returns `null` or if they are missing/malformed), the function will throw a `TypeError` because it tries to iterate over `requests` or call `Object.values(sources)`. Adding defensive checks to ensure `requests` is treated as an array and `sources` is treated as an object will prevent potential frontend crashes.
- **Gemini suggested fix:** export function highestQueueState(requests = [], sources = {}) {
  let best = null
  let bestPriority = 0

  const reqs = Array.isArray(requests) ? requests : []
  for (const req of reqs) {
    const state = String(req?.state || '').toLowerCase()
    const p = STATE_PRIORITY[state] || 0
    if (p > bestPriority) {
      bestPriority = p
      best = state
    }
  }

  if (!best) {
    const srcMap = sources && typeof sources === 'object' ? sources : {}
    for (const info of Object.values(srcMap)) {
      if (info?.paused_for_seconds > 0) return 'rate_limited'
      if (info?.queued > 0) return 'queued'
      if (info?.active > 0) return 'active'
    }
  }

  return best || null
}
- **Current main file/path:** `frontend/src/utils/apiQueuePresentation.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-342-3546273801

- **PR:** #342
- **Comment ID:** 3546273801
- **Gemini severity:** medium
- **Original file:** `docs/PRODUCT_STATUS.md`
- **Original line:** 15
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/342#discussion_r3546273801
- **Gemini finding summary:** The reference to `admin/health` is slightly misleading as there is no `admin/health` endpoint or page in the application. The backend endpoint exposing the queue status is `/api/health` (and `/api/admin/system`), while the corresponding admin page in the frontend is "Feed health" (`/admin?p=feedhealth`).\n\nConsider updating this to `/api/health` or "Feed health admin page" for clarity.
- **Gemini suggested fix:** | **API queue** | Outbound API serialization (#221) for NVD/OTX/etc.; /api/health exposes per-source task-level queue status (#341). |
- **Current main file/path:** `docs/PRODUCT_STATUS.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-342-3546273819

- **PR:** #342
- **Comment ID:** 3546273819
- **Gemini severity:** medium
- **Original file:** `docs/HANDOVER.md`
- **Original line:** 31
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/342#discussion_r3546273819
- **Gemini finding summary:** The reference to `admin/health` is slightly misleading as there is no `admin/health` endpoint or page in the application. The backend endpoint exposing the queue status is `/api/health` (and `/api/admin/system`), while the corresponding admin page in the frontend is "Feed health" (`/admin?p=feedhealth`).\n\nConsider updating this to `/api/health` or "Feed health admin page" for clarity.
- **Gemini suggested fix:** **What:** Per-source API queue task status in /api/health; indicator redesign;
- **Current main file/path:** `docs/HANDOVER.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-343-3546466579

- **PR:** #343
- **Comment ID:** 3546466579
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_backup_roundtrip_postgres.py`
- **Original line:** 103
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/343#discussion_r3546466579
- **Gemini finding summary:** To prevent test flakiness and ensure a clean state, it is highly recommended to truncate the tables before seeding them. If a previous test run failed or left the database in an unclean state, subsequent runs of this test will fail with unique constraint violations on `cve_id`.
- **Gemini suggested fix:** await _truncate_public_tables(conn)
            await _seed_core_rows(conn)
- **Current main file/path:** `backend/tests/test_backup_roundtrip_postgres.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-344-3546597042

- **PR:** #344
- **Comment ID:** 3546597042
- **Gemini severity:** medium
- **Original file:** `docs/SPRINT_2026-07.md`
- **Original line:** 414
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/344#discussion_r3546597042
- **Gemini finding summary:** For consistency with other file path references in this document (such as `tests/test_intel_snapshot_export.py` on the previous line and `tests/test_backup_roundtrip_postgres.py` on line 374), please use the full path `tests/test_backup_roundtrip_postgres.py` here.
- **Gemini suggested fix:** in the Postgres CI job (Wave 3 PR 9). **Post-B4:** `tests/test_backup_roundtrip_postgres.py` (#343).
- **Current main file/path:** `docs/SPRINT_2026-07.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-346-3547430374

- **PR:** #346
- **Comment ID:** 3547430374
- **Gemini severity:** high
- **Original file:** `deploy/briefr-update.sh`
- **Original line:** 85
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/346#discussion_r3547430374
- **Gemini finding summary:** Using `|| true` after a function call like `rollback_failed_update` disables `set -e` (errexit) inside that function for the entire duration of its execution in Bash. This means if any critical command inside `rollback_failed_update` fails (such as `git reset --hard`, `pip install`, or `build_frontend`), the script will not exit immediately and will instead continue executing subsequent commands, potentially leaving the deployment in a partially rolled-back or corrupted state. Since `rollback_failed_update` already ends with `return 1`, you can safely invoke it without `|| true`. If it fails o
- **Gemini suggested fix:** rollback_failed_update "Alembic upgrade failed"
- **Current main file/path:** `deploy/briefr-update.sh`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-346-3547430382

- **PR:** #346
- **Comment ID:** 3547430382
- **Gemini severity:** medium
- **Original file:** `deploy/lib.sh`
- **Original line:** 382
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/346#discussion_r3547430382
- **Gemini finding summary:** If Nginx is configured to redirect HTTP to HTTPS (which is standard in production), `curl -sf` will receive a `301` or `302` redirect response. Since `curl -f` only fails on status codes `>= 400`, a `3xx` redirect is treated as a success, and `curl` will exit with status `0`. This means the health check will falsely report `OK` even if the backend is completely down, because Nginx returns the redirect before proxying to the backend. To ensure the health gate actually verifies the backend through Nginx, configure `curl` to follow redirects (`-L`) and ignore SSL certificate validation errors (`-
- **Gemini suggested fix:** if curl -sfL -k "http://127.0.0.1/api/health" >/dev/null; then
- **Current main file/path:** `deploy/lib.sh`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-348-3547467524

- **PR:** #348
- **Comment ID:** 3547467524
- **Gemini severity:** medium
- **Original file:** `docs/HANDOVER.md`
- **Original line:** 47
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/348#discussion_r3547467524
- **Gemini finding summary:** The header for the J1 task section was accidentally changed to the J3 task header, resulting in duplicate J3 headers and mislabeling the J1 section. It should be reverted to `## 2026-07-09 — J1: update path — Alembic + health gate + rollback (deploy)`.
- **Gemini suggested fix:** ## 2026-07-09 — J1: update path — Alembic + health gate + rollback (deploy)
- **Current main file/path:** `docs/HANDOVER.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-350-3547733564

- **PR:** #350
- **Comment ID:** 3547733564
- **Gemini severity:** medium
- **Original file:** `frontend/src/scoring/riskScore.js`
- **Original line:** 308
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/350#discussion_r3547733564
- **Gemini finding summary:** The `daysSince` function has a timezone-dependent bug. When constructing `d` with `new Date(`${text}T00:00:00Z`)`, it is normalized to UTC midnight. However, `now` is constructed using `new Date()`, which represents the current system time.\n\nIf the user's local timezone is behind UTC, `now`'s absolute time might be behind `d` even if they represent the same calendar day locally, resulting in a negative difference (e.g., `-1` day).\n\nTo make this calculation deterministic and timezone-independent, both dates should be normalized to UTC midnight before calculating the difference.
- **Gemini suggested fix:** function daysSince(value) {
  if (!value) return null
  const text = String(value).trim().slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return null
  const d = new Date(`${text}T00:00:00Z`)
  const now = new Date()
  const nowUtc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  return Math.floor((nowUtc - d) / 86400000)
}
- **Current main file/path:** `frontend/src/scoring/riskScore.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-350-3547733571

- **PR:** #350
- **Comment ID:** 3547733571
- **Gemini severity:** medium
- **Original file:** `frontend/src/scoring/riskScore.js`
- **Original line:** 430
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/350#discussion_r3547733571
- **Gemini finding summary:** There is a discrepancy between the frontend's `classifyEnvironment` and the backend's `classify_environment` (in `backend/scoring/environment.py`).\n\nThe backend defines a six-tier system including `POSSIBLE` (rank 3), but the frontend's `classifyEnvironment` implementation completely omits the `POSSIBLE` tier, mapping scores directly from `LIKELY` to `WEAK`. This can lead to inconsistent classification if the frontend function is ever used for client-side calculations or previews.\n\nConsider aligning the frontend classification logic to support the `POSSIBLE` tier or documenting why they di
- **Gemini suggested fix:** (none)
- **Current main file/path:** `frontend/src/scoring/riskScore.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-351-3549315681

- **PR:** #351
- **Comment ID:** 3549315681
- **Gemini severity:** high
- **Original file:** `backend/correlation/lifecycle.py`
- **Original line:** 109
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/351#discussion_r3549315681
- **Gemini finding summary:** Prematurely returning `"active"` when a booster (KEV, PoC, or EPSS) is within the `active_cutoff` (14 days) prevents the loop from checking subsequent members or fields that might have more recent activity (within 7 days) and should classify the campaign as `"emerging"`. Since any booster date that is `>= active_cutoff` (14 days) is also `>= declining_cutoff` (30 days), updating `last_activity` with these dates is sufficient to ensure the campaign is classified as `"active"` at the end of the function if no `"emerging"` trigger is found. Removing the early returns fixes this correctness bug an
- **Gemini suggested fix:** if member.get("is_kev"):
            kev_dt = _parse_dt(member.get("kev_date_added"))
            if kev_dt and (last_activity is None or kev_dt > last_activity):
                last_activity = kev_dt

        if member.get("has_poc"):
            poc_dt = _parse_dt(member.get("modified")) or _parse_dt(member.get("published"))
            if poc_dt and (last_activity is None or poc_dt > last_activity):
                last_activity = poc_dt

        epss_dt = _parse_dt(member.get("epss_activity_at"))
        if epss_dt and (last_activity is None or epss_dt > last_activity):
            last_activity = epss_dt
- **Current main file/path:** `backend/correlation/lifecycle.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-351-3549315687

- **PR:** #351
- **Comment ID:** 3549315687
- **Gemini severity:** medium
- **Original file:** `backend/correlation/lifecycle.py`
- **Original line:** 17
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/351#discussion_r3549315687
- **Gemini finding summary:** If `value` is already a `datetime` object, converting it to a string and then parsing it back via `fromisoformat` is highly inefficient and unnecessary. Adding a fast-path check for `isinstance(value, datetime)` avoids this overhead and makes the function more robust.
- **Gemini suggested fix:** def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
- **Current main file/path:** `backend/correlation/lifecycle.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-352-3549341964

- **PR:** #352
- **Comment ID:** 3549341964
- **Gemini severity:** medium
- **Original file:** `backend/routers/cves.py`
- **Original line:** 145
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/352#discussion_r3549341964
- **Gemini finding summary:** The current normalization logic for `campaign_lifecycle` can result in the key being included in the dictionary with a value of `None` if `lifecycle` consists only of whitespace (e.g., `"   "`). This violates the API contract specified in `API_REFERENCE.md` which states that `campaign_lifecycle` should be omitted when not applicable or empty. We should ensure that `campaign_lifecycle` is only added to the dictionary if it contains a non-empty, non-whitespace string.
- **Gemini suggested fix:** d["member_of_campaign"] = bool(d.pop("member_of_campaign", 0))
    lifecycle = d.pop("campaign_lifecycle", None)
    if d["member_of_campaign"] and lifecycle:
        stripped = str(lifecycle).strip()
        if stripped:
            d["campaign_lifecycle"] = stripped
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-352-3549341977

- **PR:** #352
- **Comment ID:** 3549341977
- **Gemini severity:** medium
- **Original file:** `frontend/src/utils/correlationPresentation.js`
- **Original line:** 47
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/352#discussion_r3549341977
- **Gemini finding summary:** In `campaignBadgeTooltip`, using `String(lifecycle || 'active')` causes any missing, `null`, or `undefined` lifecycle to default to `'active'`. This prevents the function from ever reaching the generic fallback at the end of the function, and falsely labels campaigns with unknown lifecycles as "Active campaign" with the active-specific tooltip. We should only convert the lifecycle to a string if it is present, and otherwise default to an empty string or `null` so that the generic fallback is correctly used.
- **Gemini suggested fix:** export function campaignBadgeTooltip(lifecycle) {
  const key = lifecycle ? String(lifecycle).toLowerCase() : ''
  const label = CAMPAIGN_LIFECYCLE_LABELS[key] || 'Campaign cluster'
  if (key === 'active') {
    return `${label} — this CVE is grouped with related vulnerabilities in an OTX pulse cluster with recent KEV, PoC, or EPSS activity. Open the drawer for full correlation details.`
  }
  if (key === 'emerging') {
    return `${label} — newly linked to an OTX pulse cluster within the last week. Open the drawer for full correlation details.`
  }
  if (key === 'declining') {
    return `${label} — grouped in an OTX pulse cluster with no recent member activity (30+ days). Open the drawer for full correlation details.`
  }
  if (key === 'stale') {
    return `${label} — grouped in an olde
- **Current main file/path:** `frontend/src/utils/correlationPresentation.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-352-3549341981

- **PR:** #352
- **Comment ID:** 3549341981
- **Gemini severity:** medium
- **Original file:** `frontend/src/utils/correlationPresentation.js`
- **Original line:** 60
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/352#discussion_r3549341981
- **Gemini finding summary:** For consistency with `campaignBadgeTooltip` and to avoid unnecessary string coercion of default values, we should avoid using `String(lifecycle || 'active')` in `campaignLifecycleClass`. Instead, we can check if `lifecycle` is present before converting it to a string.
- **Gemini suggested fix:** export function campaignLifecycleClass(lifecycle) {
  const key = lifecycle ? String(lifecycle).toLowerCase() : ''
  if (key === 'emerging') return 'badge-campaign-emerging'
  if (key === 'declining') return 'badge-campaign-declining'
  if (key === 'stale') return 'badge-campaign-stale'
  return 'badge-campaign-active'
}
- **Current main file/path:** `frontend/src/utils/correlationPresentation.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-352-3549341986

- **PR:** #352
- **Comment ID:** 3549341986
- **Gemini severity:** medium
- **Original file:** `API_REFERENCE.md`
- **Original line:** 83
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/352#discussion_r3549341986
- **Gemini finding summary:** The phrase `(cheapest lifecycle when multiple campaigns apply)` in the documentation is likely a typo or misnomer (possibly carried over from the "cheap join" terminology). Based on the SQL query in `backend/routers/cves.py`, the query orders the lifecycles so that the most critical/active lifecycle is returned first (`active` -> `emerging` -> `declining` -> `stale`). Therefore, it actually returns the **highest priority** or **most active** lifecycle. We should update the documentation to reflect this clearly.
- **Gemini suggested fix:** - `campaign_lifecycle` — `"active"`, `"emerging"`, `"declining"`, or `"stale"` when `member_of_campaign` is `true`; omitted otherwise (highest priority lifecycle when multiple campaigns apply)
- **Current main file/path:** `API_REFERENCE.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-353-3549375008

- **PR:** #353
- **Comment ID:** 3549375008
- **Gemini severity:** high
- **Original file:** `backend/main.py`
- **Original line:** 158
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/353#discussion_r3549375008
- **Gemini finding summary:** ### Issue: Middleware Ordering and `BaseHTTPMiddleware` Conflict\n\nIn FastAPI/Starlette, middlewares are executed in the reverse order of their registration (the last added is the outermost). Currently, `GZipMiddleware` is registered at line 158, before the custom `add_security_headers` (line 163) and `request_context` (line 188) middlewares, which are registered using the `@app.middleware('http')` decorator.\n\nThis means `add_security_headers` and `request_context` (both of which are `BaseHTTPMiddleware` instances under the hood) will wrap `GZipMiddleware` and execute **after** it on the re
- **Gemini suggested fix:** # Move this registration to the end of the middleware stack (after request_context)\n# to ensure GZipMiddleware is the outermost middleware.\n# app.add_middleware(GZipMiddleware, minimum_size=256)
- **Current main file/path:** `backend/main.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Original review concern addressed in subsequent merges; no reproducible defect on main

### F-354-3549372582

- **PR:** #354
- **Comment ID:** 3549372582
- **Gemini severity:** medium
- **Original file:** `docs/SPRINT_2026-07.md`
- **Original line:** 85
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/354#discussion_r3549372582
- **Gemini finding summary:** The sprint items `C-Evolve-1` and `C-Evolve-2` were completely deleted from the sprint document instead of being marked as completed. To preserve the history of completed tasks in the sprint document (as stated in the document's own instructions: "Closed tracks stay in place for history"), they should be kept and marked as checked `[x]` with their respective PR numbers.
- **Gemini suggested fix:** - [x] **M1. Threat / Environment / Operational Priority surface** *(IMPLEMENTATION, STANDARD; dependency: ADR-002 = CLOSED; NOT parallel-safe with C-Evolve-3 or H2/H4 — shared `DetailDrawer`)*.
      **Shipped:** #350 — Threat/Environment/OP scoring, Investigation Score removed.
- [x] **C-Evolve-1. Correlation lifecycle computation** *(IMPLEMENTATION, STANDARD, parallel-safe with J*, M1, I2)*.
      **Shipped:** #351 — Correlation lifecycle computation.
- [x] **C-Evolve-2. Feed campaign badge** *(IMPLEMENTATION, STANDARD; dependency: C-Evolve-1; parallel-safe with J*, M1, I2)*.
      **Shipped:** #352 — Feed campaign badge.
- **Current main file/path:** `docs/SPRINT_2026-07.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-355-3549565675

- **PR:** #355
- **Comment ID:** 3549565675
- **Gemini severity:** high
- **Original file:** `backend/intel/provenance.py`
- **Original line:** 129
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/355#discussion_r3549565675
- **Gemini finding summary:** There is a logic bug here where the function returns `status="checked"` even when both `has_community_cache` and `ctx_at` are `False` (and `github_down` is `False`). In this case, the status should be `"pending"` to indicate that enrichment has not completed yet, consistent with the other provenance derivation functions.
- **Gemini suggested fix:** return _line(
        status="pending",
        source="SigmaHQ + Elastic + BRIEFR",
        as_of=None,
    )
- **Current main file/path:** `backend/intel/provenance.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-355-3549565688

- **PR:** #355
- **Comment ID:** 3549565688
- **Gemini severity:** medium
- **Original file:** `backend/intel/provenance.py`
- **Original line:** 51
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/355#discussion_r3549565688
- **Gemini finding summary:** Instead of passing `used_nvd_fallback` which requires querying the database twice (once in the router and once inside this function), we can pass `has_public_exploits` and derive `used_nvd_fallback` internally. This avoids redundant database roundtrips on a hot path.
- **Gemini suggested fix:** async def derive_exploit_provenance(
    db: DbConnection,
    cve_id: str,
    *,
    has_public_exploits: bool = False,
) -> dict[str, str | None]:
    """
    Public exploit section — Sploitus + nightly exploit index + NVD refs.
    """
    key = cve_id.upper()
    exploit_index_at = await get_cve_exploits_latest_fetched_at(db, key)
    sploitus_at = await get_feed_cache_timestamp(db, f"sploitus:{key}")
    sploitus_down = _circuit_open("sploitus")

    used_nvd_fallback = (
        has_public_exploits
        and not exploit_index_at
        and not sploitus_at
    )
- **Current main file/path:** `backend/intel/provenance.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-355-3549565693

- **PR:** #355
- **Comment ID:** 3549565693
- **Gemini severity:** medium
- **Original file:** `backend/routers/cves.py`
- **Original line:** 973
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/355#discussion_r3549565693
- **Gemini finding summary:** Simplify the call to `derive_exploit_provenance` by passing `has_public_exploits` instead of pre-calculating `used_nvd_fallback` with redundant database queries.
- **Gemini suggested fix:** cve["exploit_provenance"] = await derive_exploit_provenance(
                db,
                cve_key,
                has_public_exploits=bool(cve["public_exploits"]),
            )
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-355-3549565698

- **PR:** #355
- **Comment ID:** 3549565698
- **Gemini severity:** medium
- **Original file:** `backend/db/cache.py`
- **Original line:** 275
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/355#discussion_r3549565698
- **Gemini finding summary:** Converting the row to a dictionary with `dict(row[0])` is unnecessary and inconsistent with the rest of the file, which accesses keys directly on the row objects (e.g., `row[0]["cached_at"]`).
- **Gemini suggested fix:** ts = row[0]["cached_at"]
    return str(ts).strip() if ts else None
- **Current main file/path:** `backend/db/cache.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-355-3549565701

- **PR:** #355
- **Comment ID:** 3549565701
- **Gemini severity:** medium
- **Original file:** `backend/db/cache.py`
- **Original line:** 288
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/355#discussion_r3549565701
- **Gemini finding summary:** Converting the row to a dictionary with `dict(row[0])` is unnecessary and inconsistent with the rest of the file, which accesses keys directly on the row objects (e.g., `row[0]["fetched_at"]`).
- **Gemini suggested fix:** ts = row[0]["fetched_at"]
    return str(ts).strip() if ts else None
- **Current main file/path:** `backend/db/cache.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-356-3549564691

- **PR:** #356
- **Comment ID:** 3549564691
- **Gemini severity:** medium
- **Original file:** `docs/HANDOVER.md`
- **Original line:** 20
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/356#discussion_r3549564691
- **Gemini finding summary:** According to the guidelines at the top of `docs/HANDOVER.md` (lines 6-7), you should "Append a new dated entry per significant working session; never rewrite old entries." Overwriting the previous session's entry removes the historical record of what was merged (such as #352 and #353). Please keep the previous entry and add the new one above it.
- **Gemini suggested fix:** ## 2026-07-09 — FR1 provenance shipped; continuing Wave 3

**Merged:** #355 FR1 — per-section provenance (`exploit_provenance`, detection/correlation
`provenance`) with drawer `IntelProvenanceLine` + tooltips.

**Autonomous next (do not ask):** **H-verify** → C-Evolve-3 → I3/I5/I8/I9 → Phase B backlog.

---

## 2026-07-09 — C-Evolve-2 + I2 shipped; continuing Wave 2

**Merged:** #352 C-Evolve-2 feed campaign badge (`member_of_campaign` +
`campaign_lifecycle` on list/export; Campaign badge + tooltip on feed cards).
#353 I2 gzip (nginx snippet + `GZipMiddleware` fallback).

**Also on main from prior turns:** #350 M1 ADR-002 scoring, #351 C-Evolve-1 lifecycle,
#346–#349 Track J wave.

**Autonomous next (do not ask):** **FR1** — per-CVE intel provenance lines in drawer.
- **Current main file/path:** `docs/HANDOVER.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-357-3549613674

- **PR:** #357
- **Comment ID:** 3549613674
- **Gemini severity:** high
- **Original file:** `frontend/src/components/BriefCharts.jsx`
- **Original line:** 528
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613674
- **Gemini finding summary:** When a background refresh fails completely (e.g., both endpoints fail or network is down) while stale data is present, `useAsync` sets the main `error` state but keeps the stale `data`. Because `hasData` is true, `AsyncState` renders its children, but the children currently only render `partialError` (which is null or from the previous successful fetch). As a result, the background refresh error is silently swallowed.\n\nWe should render `error || partialError` to ensure the user is notified of complete refresh failures when stale data is displayed.
- **Gemini suggested fix:** {(error || partialError) && (\n                  <ErrorState\n                    error={error || partialError}\n                    onRetry={retry}\n                    compact\n                    className="brief-charts-error--partial"\n                  />\n                )}
- **Current main file/path:** `frontend/src/components/BriefCharts.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-357-3549613681

- **PR:** #357
- **Comment ID:** 3549613681
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/ui/Tooltip.jsx`
- **Original line:** 1
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613681
- **Gemini finding summary:** Import `useCallback` to memoize the `checkFlip` function so it can be safely used in both the `useEffect` and event handlers.
- **Gemini suggested fix:** import { useId, useState, useRef, useEffect, useCallback } from 'react'
- **Current main file/path:** `frontend/src/components/ui/Tooltip.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-357-3549613693

- **PR:** #357
- **Comment ID:** 3549613693
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/ui/Tooltip.jsx`
- **Original line:** 28
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613693
- **Gemini finding summary:** The `checkFlip` function is currently only executed on mount, window resize, or when `text` changes. However, if the tooltip is inside a scrollable container or if the page layout shifts, the tooltip's position relative to the viewport can change. If the user scrolls the tooltip to the top of the screen and hovers over it, the bubble will still open upwards and go off-screen because `checkFlip` was not re-run.\n\nWe should refactor `checkFlip` using `useCallback` so we can also trigger it on `onMouseEnter` and `onFocus` events.
- **Gemini suggested fix:** const checkFlip = useCallback(() => {\n    const el = wrapRef.current\n    if (!el || !text) return\n    const bubble = el.querySelector('.ui-tooltip-bubble')\n    if (!bubble) return\n    const rect = bubble.getBoundingClientRect()\n    setFlip(rect.top < 8)\n  }, [text])\n\n  useEffect(() => {\n    checkFlip()\n    window.addEventListener('resize', checkFlip)\n    return () => window.removeEventListener('resize', checkFlip)\n  }, [checkFlip])
- **Current main file/path:** `frontend/src/components/ui/Tooltip.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-357-3549613700

- **PR:** #357
- **Comment ID:** 3549613700
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/ui/Tooltip.jsx`
- **Original line:** 49
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613700
- **Gemini finding summary:** Add `onMouseEnter` and `onFocus` event handlers to trigger `checkFlip` when the tooltip is hovered or focused, ensuring it flips dynamically if positioned near the top of the viewport.
- **Gemini suggested fix:** return (\n    <span\n      ref={wrapRef}\n      className={`ui-tooltip-wrap${touchOpen ? ' ui-tooltip-wrap--open' : ''}`}\n      onKeyDown={onKeyDown}\n      onTouchStart={onTouchStart}\n      onMouseEnter={checkFlip}\n      onFocus={checkFlip}\n      onBlur={(e) => {\n        if (!e.currentTarget.contains(e.relatedTarget)) setTouchOpen(false)\n      }}\n    >
- **Current main file/path:** `frontend/src/components/ui/Tooltip.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-357-3549613707

- **PR:** #357
- **Comment ID:** 3549613707
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/BriefCharts.jsx`
- **Original line:** 8
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613707
- **Gemini finding summary:** Define a static `EMPTY_ARRAY` constant to provide referential stability for default fallback values.
- **Gemini suggested fix:** import { kevBucketDateRange } from '../utils/kevDeadline.js'\n\nconst EMPTY_ARRAY = []
- **Current main file/path:** `frontend/src/components/BriefCharts.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-357-3549613715

- **PR:** #357
- **Comment ID:** 3549613715
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/BriefCharts.jsx`
- **Original line:** 361
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613715
- **Gemini finding summary:** Using `?? []` creates a new array reference on every render when `data` is null or undefined. Since `epssChanges` is a dependency of the `epssMovers` `useMemo`, and `epssMovers` is a dependency of the history-fetching `useEffect`, this causes unnecessary re-evaluations and potential effect triggers.\n\nWe should use a static `EMPTY_ARRAY` constant defined outside the component to maintain referential stability.
- **Gemini suggested fix:** const kevEntries = data?.kevEntries ?? EMPTY_ARRAY\n  const epssChanges = data?.epssChanges ?? EMPTY_ARRAY
- **Current main file/path:** `frontend/src/components/BriefCharts.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-357-3549613717

- **PR:** #357
- **Comment ID:** 3549613717
- **Gemini severity:** medium
- **Original file:** `frontend/src/hooks/useAsync.js`
- **Original line:** 10
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/357#discussion_r3549613717
- **Gemini finding summary:** If `useAsync` is called without a `deps` argument, `[...deps, retryCount]` will throw a `TypeError: deps is not iterable`.\n\nWe should default `deps` to an empty array `[]` to prevent runtime crashes and ensure defensive programming.
- **Gemini suggested fix:** export default function useAsync(fn, deps = []) {
- **Current main file/path:** `frontend/src/hooks/useAsync.js`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-358-3549619055

- **PR:** #358
- **Comment ID:** 3549619055
- **Gemini severity:** high
- **Original file:** `frontend/src/components/ui/ConfirmModal.jsx`
- **Original line:** 97
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/358#discussion_r3549619055
- **Gemini finding summary:** The current implementation of `ConfirmModal` has a critical usability and accessibility bug: it registers a global `keydown` listener on `document` for the `Enter` key. If a user tabs to the **Cancel** button and presses `Enter` to cancel, the global listener intercepts the keypress and immediately triggers `onConfirm(input)` instead of canceling. Additionally, the global `Escape` listener is redundant because the underlying `Modal` component already handles the `Escape` key. To fix this, we can remove the global keydown listeners and use standard HTML form submission. Wrapping the modal conte
- **Gemini suggested fix:** const [input, setInput] = useState('')
  const close = onClose || onCancel
  const word = confirmWord || ''
  const canConfirm = !word || input === word

  useEffect(() => {
    if (!open) setInput('')
  }, [open])

  function handleSubmit(e) {
    e.preventDefault()
    if (canConfirm) {
      onConfirm(input)
    }
  }

  const footer = (
    <>
      <Button variant="ghost" onClick={close}>
        {cancelLabel}
      </Button>
      <Button
        variant="danger"
        type="submit"
        form="ui-confirm-form"
        disabled={!canConfirm}
      >
        {confirmLabel}
      </Button>
    </>
  )

  return (
    <Modal
      open={open}
      onClose={close}
      title={title}
      footer={footer}
      className={className}
      overlayClassName={overlayClassName}
    >
  
- **Current main file/path:** `frontend/src/components/ui/ConfirmModal.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-360-3549670425

- **PR:** #360
- **Comment ID:** 3549670425
- **Gemini severity:** high
- **Original file:** `frontend/src/context/InvestigationContext.jsx`
- **Original line:** 232
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/360#discussion_r3549670425
- **Gemini finding summary:** Using `itemsRef.current.some` inside the loop has two issues: 1. **Correctness/State Sync Bug**: Since `recordItem` updates the React state asynchronously, `itemsRef.current` is not updated immediately during the loop execution. If `campaign.members` contains duplicate IDs, or if there are concurrent updates, duplicate items will be added to the investigation thread. 2. **Performance**: It performs an $O(N)$ scan of the investigation items for every member, resulting in $O(N \times M)$ complexity. We can resolve both issues by initializing a local `Set` of existing and newly added CVE IDs, whi
- **Gemini suggested fix:** const anchorId = (typeof anchorCve === 'string' ? anchorCve : anchorCve?.cve_id)?.toUpperCase()
    const existingIds = new Set(
      itemsRef.current
        .filter(i => i.type === INV_TYPES.CVE)
        .map(i => i.id?.toUpperCase())
    )
    const memberIds = (campaign.members || [])
      .filter(id => typeof id === 'string')
      .map(id => id.toUpperCase())
      .filter(id => id !== anchorId)
    let added = 0
    for (const cveId of memberIds) {
      if (existingIds.has(cveId)) continue
      recordItem({
        type: INV_TYPES.CVE,
        id: cveId,
        title: cveId,
        description: campaign.summary || campaign.label || `Campaign cluster ${campaign.campaign_id || ''}`.trim(),
        source: INV_SOURCES.DRAWER,
        pivotFrom: anchor,
        meta: { campaign_id
- **Current main file/path:** `frontend/src/context/InvestigationContext.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-360-3549670432

- **PR:** #360
- **Comment ID:** 3549670432
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Original line:** 345
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/360#discussion_r3549670432
- **Gemini finding summary:** The `.corr-finding-foot` container is a horizontal flexbox with `justify-content: flex-end`. Since `.drawer-investigate-btn` has `margin-top: 8px` and `.corr-mark-unrelated-btn` does not, the two buttons will be vertically misaligned and cramped together on the right. Adding `margin: 0 auto 0 0` (via inline styles) solves both issues: 1. It resets `margin-top` to `0` to align them vertically. 2. It uses `margin-right: auto` to push the "Add to investigation" button to the left, creating a much cleaner and more balanced UI/UX.
- **Gemini suggested fix:** {onInvestigateCampaign && (item.members || []).some(id => id && id !== correlation?.cve_id) && (
                  <button
                    type="button"
                    className="drawer-investigate-btn"
                    style={{ margin: '0 auto 0 0' }}
                    onClick={() => onInvestigateCampaign(item, cve)}
                  >
                    Add to investigation
                  </button>
                )}
- **Current main file/path:** `frontend/src/components/DetailDrawer/IntelTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-362-3549749748

- **PR:** #362
- **Comment ID:** 3549749748
- **Gemini severity:** high
- **Original file:** `backend/routers/health.py`
- **Original line:** 120
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/362#discussion_r3549749748
- **Gemini finding summary:** Caching the entire `/api/health` response for 45 seconds introduces correctness issues because highly dynamic fields like `server_time_utc`, `server_time_local`, and `refresh_in_progress` will be frozen/stale. Additionally, caching the response per `tz` creates duplicate cache entries for identical database queries. ### Solution Cache only the slow database queries under a static key (`"health_db_stats"`), and construct the dynamic fields (server time, refresh status, etc.) on every request. This keeps the health check real-time while preserving 100% of the performance benefits.
- **Gemini suggested fix:** async def build_db_stats():
        db = await get_db()
        try:
            return {
                "cve_count": await get_cve_count(db),
                "last_updated": await get_last_updated(db),
                "nvd_sync_watermark": await get_nvd_sync_watermark(db),
                "timeline_summary": await get_timeline_activity_summary(db, days=90),
            }
        finally:
            await db.close()

    db_stats = await cached_read("health_db_stats", DEFAULT_TTL_SECONDS, build_db_stats)

    database_meta = _database_meta()
    database_meta["timeline_days_with_data_90d"] = db_stats["timeline_summary"].get("days_with_data", 0)
    database_meta["timeline_total_cves_90d"] = db_stats["timeline_summary"].get("total_cves", 0)

    now_utc = datetime.now(timezone.utc)
    de
- **Current main file/path:** `backend/routers/health.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-362-3549749757

- **PR:** #362
- **Comment ID:** 3549749757
- **Gemini severity:** medium
- **Original file:** `backend/routers/cves.py`
- **Original line:** 251
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/362#discussion_r3549749757
- **Gemini finding summary:** The cache key `f"stats:{frameworks or ''}"` is order-dependent. For example, `frameworks="pytorch,tensorflow"` and `frameworks="tensorflow,pytorch"` will create duplicate cache entries even though they produce identical results. ### Solution Normalize the framework list by sorting it before constructing the cache key. This also allows us to parse the framework list once and reuse it inside the `build()` function, avoiding redundant parsing.
- **Gemini suggested fix:** fw_list = _parse_framework_list(frameworks)
    normalized_fw = ",".join(sorted(fw_list))
    cache_key = f"stats:{normalized_fw}"

    async def build():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                """
                SELECT
                    SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
                    SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high,
                    SUM(CASE WHEN is_kev = 1 THEN 1 ELSE 0 END) AS kev_count,
                    SUM(CASE WHEN patch_available = 1 THEN 1 ELSE 0 END) AS patched,
                    SUM(CASE WHEN published >= datetime('now', '-1 day') THEN 1 ELSE 0 END) AS last_24h,
                    SUM(CASE WHEN severity = 'CRITICAL' AND published >= dateti
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-364-3549841611

- **PR:** #364
- **Comment ID:** 3549841611
- **Gemini severity:** high
- **Original file:** `backend/correlation/clusters.py`
- **Original line:** 62
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/364#discussion_r3549841611
- **Gemini finding summary:** Using SQLite-specific `datetime('now')` and `datetime(snooze_until)` functions will cause runtime database errors when the application is configured to use PostgreSQL. To ensure cross-database compatibility, pass the current UTC time from Python as a query parameter and perform a direct comparison.
- **Gemini suggested fix:** from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    watchlist_rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM watchlist
        WHERE state = 'pin'
           OR (state = 'snooze'
               AND snooze_until IS NOT NULL
               AND TRIM(snooze_until) != ''
               AND snooze_until > ?)
        """,
        (now_str,),
    )
- **Current main file/path:** `backend/correlation/clusters.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** PostgresConnection pg_adapt translates datetime(snooze_until) > datetime('now')

### F-364-3549841627

- **PR:** #364
- **Comment ID:** 3549841627
- **Gemini severity:** high
- **Original file:** `backend/correlation/clusters.py`
- **Original line:** 113
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/364#discussion_r3549841627
- **Gemini finding summary:** Executing individual queries for each campaign inside the loop introduces a classic N+1 query pattern. With a limit of up to 100, this can result in up to 1000 sequential database queries per request, severely degrading performance. Fetching all campaign members and stack members in bulk using `IN` clauses reduces the database roundtrips to just 2 or 3 queries.
- **Gemini suggested fix:** if not rows:
        return {
            "meta": {
                "stack_terms": stack_terms,
                "limit": limit,
                "include_stale": include_stale,
                "count": 0,
            },
            "clusters": [],
        }

    campaign_ids = [row["campaign_id"] for row in rows]
    placeholders = ",".join("?" for _ in campaign_ids)

    all_member_rows = await db.execute_fetchall(
        f"""
        SELECT m.campaign_id, m.cve_id
        FROM correlation_campaign_members m
        INNER JOIN cves c ON c.cve_id = m.cve_id
        WHERE m.campaign_id IN ({placeholders})
        ORDER BY m.cve_id ASC
        """,
        campaign_ids,
    )

    campaign_members: dict[str, list[str]] = {}
    for r in all_member_rows:
        campaign_members.setdefault(r[
- **Current main file/path:** `backend/correlation/clusters.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-365-3549840788

- **PR:** #365
- **Comment ID:** 3549840788
- **Gemini severity:** medium
- **Original file:** `docs/PRODUCT_STATUS.md`
- **Original line:** 68
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/365#discussion_r3549840788
- **Gemini finding summary:** The reference to `sprint Phase B` is outdated because Phase B has been reorganized and renamed to the explicit task sequence in `docs/SPRINT_2026-07.md`. Consider updating this reference to point to `docs/SPRINT_2026-07.md` or `WAVE 4` directly.
- **Gemini suggested fix:** | Correlation v2 core (campaigns, typed IOC edges, hub suppression, dismiss, priority, lifecycle, feed badge, drawer chip) + **Phase 4–5** cluster list + admin correlation status (#364) | Correlation phase-4 tail (Forge/PDF/webhook enrichments, watchlist sort in feed) — see SPRINT_2026-07.md |
- **Current main file/path:** `docs/PRODUCT_STATUS.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Documentation-only comment; no code defect on main

### F-366-3549889357

- **PR:** #366
- **Comment ID:** 3549889357
- **Gemini severity:** high
- **Original file:** `backend/webhooks/alerts.py`
- **Original line:** 182
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/366#discussion_r3549889357
- **Gemini finding summary:** ### Performance Issue: Inefficient Database Connection Management Opening and closing a database connection inside a loop for each matching CVE ID is highly inefficient and can easily lead to connection pool exhaustion under load. Refactor the function to open a single database connection at the start, reuse it to fetch the pinned CVEs and their descriptions, and ensure it is safely closed in a `finally` block.
- **Gemini suggested fix:** db = await get_db()
    try:
        pinned = {cve_id.upper() for cve_id in await list_pinned_cve_ids(db)}
        if not pinned:
            return 0

        sent = 0
        for raw_id in newly_kev_ids:
            cve_id = raw_id.upper()
            if cve_id not in pinned:
                continue
            description = await _fetch_cve_blurb(db, cve_id)
            result = await dispatch_event(
                EVENT_WATCHLIST_ALERT,
                _format_watchlist_alert(
                    cve_id=cve_id,
                    reason="added to CISA KEV",
                    detail="Pinned CVE is now on the Known Exploited Vulnerabilities catalog.",
                    description=description,
                ),
                dedupe_key=f"{cve_id}:kev",
            )
           
- **Current main file/path:** `backend/webhooks/alerts.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-366-3549889363

- **PR:** #366
- **Comment ID:** 3549889363
- **Gemini severity:** high
- **Original file:** `backend/webhooks/alerts.py`
- **Original line:** 247
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/366#discussion_r3549889363
- **Gemini finding summary:** ### Performance & Logic Issues: Connection Reuse & Lifetime Alert Limit 1. **Inefficient Database Connections**: Opening and closing a database connection inside the loop for each change is highly inefficient and risks connection pool exhaustion. 2. **Lifetime Alert Limit**: Using `f"{cve_id}:{field}"` as the deduplication key means a pinned CVE can only ever trigger a single EPSS score increase alert in its entire lifetime. If the EPSS score increases again in the future, the alert will be silently deduped and ignored. Refactor the function to reuse a single database connection and append the
- **Gemini suggested fix:** db = await get_db()
    try:
        pinned = {cve_id.upper() for cve_id in await list_pinned_cve_ids(db)}
        if not pinned:
            return 0
        changes = await get_recent_cve_changes(db, since_hours=since_hours, limit=500)

        sent = 0
        for change in changes:
            cve_id = (change.get("cve_id") or "").upper()
            if cve_id not in pinned:
                continue
            field = change.get("field_name") or ""
            old_val = change.get("old_value")
            new_val = change.get("new_value")

            reason = ""
            detail = ""
            if field == "epss_score":
                old_score = _parse_score(old_val)
                new_score = _parse_score(new_val)
                if old_score is None or new_score is None:
    
- **Current main file/path:** `backend/webhooks/alerts.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-368-3550194889

- **PR:** #368
- **Comment ID:** 3550194889
- **Gemini severity:** high
- **Original file:** `backend/operator_settings.py`
- **Original line:** 68
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/368#discussion_r3550194889
- **Gemini finding summary:** The global `settings` singleton is instantiated once at import time in `backend/settings.py`. When `hydrate_operator_settings_from_db` runs during the lifespan startup, it updates `os.environ`, but these changes are **not** automatically reflected in the already-instantiated `settings` object. As a result, any live checks (e.g., `settings.rate_limit_enabled`) will continue to use stale values from `.env` or the process environment, completely bypassing the hydrated database settings. We must explicitly propagate these hydrated values to the live `settings` object.
- **Gemini suggested fix:** applied = 0
    for row in rows:
        key = row["key"]
        if key in PROCESS_ENV_KEYS:
            continue
        value = row.get("value")
        if value is None:
            continue
        val_str = str(value)
        os.environ[key] = val_str
        attr = key.lower()
        if hasattr(settings, attr):
            try:
                current = getattr(settings, attr)
                if isinstance(current, bool):
                    setattr(settings, attr, val_str.lower() not in ("0", "false", "no", "off"))
                elif isinstance(current, int):
                    setattr(settings, attr, int(val_str))
                else:
                    setattr(settings, attr, val_str)
            except Exception:
                pass
        applied += 1
- **Current main file/path:** `backend/operator_settings.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-368-3550194898

- **PR:** #368
- **Comment ID:** 3550194898
- **Gemini severity:** medium
- **Original file:** `backend/operator_settings.py`
- **Original line:** 11
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/368#discussion_r3550194898
- **Gemini finding summary:** In accordance with the repository's refactoring plan (`docs/REFACTOR_PLAN.md`), new code should import directly from the `db.*` submodules instead of using the backward-compatibility shim `database.py`. Additionally, we should import `settings` to allow propagating hydrated settings to the live configuration object.
- **Gemini suggested fix:** from db.init import get_db
from db.app_settings import get_app_setting, list_app_settings, set_app_setting
from settings import PROCESS_ENV_KEYS, settings
- **Current main file/path:** `backend/operator_settings.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-368-3550194908

- **PR:** #368
- **Comment ID:** 3550194908
- **Gemini severity:** medium
- **Original file:** `backend/operator_settings.py`
- **Original line:** 31
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/368#discussion_r3550194908
- **Gemini finding summary:** Since `get_app_setting` is now imported at the top level directly from `db.app_settings`, this inline import is redundant and can be removed.
- **Gemini suggested fix:** for key in WRITABLE_CONFIG_KEYS:
- **Current main file/path:** `backend/operator_settings.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-368-3550194914

- **PR:** #368
- **Comment ID:** 3550194914
- **Gemini severity:** medium
- **Original file:** `backend/operator_settings.py`
- **Original line:** 85
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/368#discussion_r3550194914
- **Gemini finding summary:** To avoid opening and closing a database connection/transaction for every single key when saving multiple settings at once (e.g., in `apply_all_config`), we should introduce a bulk persistence helper `persist_operator_settings`.
- **Gemini suggested fix:** async def persist_operator_setting(key: str, value: str) -> None:
    await persist_operator_settings([(key, value)])


async def persist_operator_settings(settings_list: list[tuple[str, str]]) -> None:
    if not settings_list:
        return
    db = await get_db()
    try:
        for key, value in settings_list:
            await set_app_setting(db, key, value)
        await db.commit()
    finally:
        await db.close()
- **Current main file/path:** `backend/operator_settings.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-368-3550194919

- **PR:** #368
- **Comment ID:** 3550194919
- **Gemini severity:** medium
- **Original file:** `backend/routers/admin.py`
- **Original line:** 1150
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/368#discussion_r3550194919
- **Gemini finding summary:** Instead of calling `persist_operator_setting` inside the loop (which opens, commits, and closes a database connection for every single key), we should use the new bulk helper `persist_operator_settings` to persist all validated settings in a single connection/transaction.
- **Gemini suggested fix:** changed_keys: list[str] = []
    from operator_settings import persist_operator_settings

    for key, value in validated:
        dotenv_set_key(dotenv_path, key, value)
        os.environ[key] = value
        _propagate_to_settings(key, value)
        changed_keys.append(key)

    await persist_operator_settings(validated)
- **Current main file/path:** `backend/routers/admin.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-368-3550194926

- **PR:** #368
- **Comment ID:** 3550194926
- **Gemini severity:** medium
- **Original file:** `backend/tests/test_operator_settings.py`
- **Original line:** 14
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/368#discussion_r3550194926
- **Gemini finding summary:** In accordance with the repository's refactoring plan, new test files should also import directly from the `db.*` submodules instead of using the backward-compatibility shim `database.py`.
- **Gemini suggested fix:** import database
from db.init import get_db, init_db
from db.app_settings import get_app_setting, set_app_setting
- **Current main file/path:** `backend/tests/test_operator_settings.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-371-3550281320

- **PR:** #371
- **Comment ID:** 3550281320
- **Gemini severity:** medium
- **Original file:** `backend/onboarding/checklist.py`
- **Original line:** 74
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/371#discussion_r3550281320
- **Gemini finding summary:** The logic `feeds_ok = open_circuits == 0 or cve_count > 0` means that if there are any open circuits (unhealthy feeds) but the database already has at least one CVE, the "Feed sources healthy" checklist item will be marked as completed (`done: True`). This leads to a confusing UI state where a green checkmark (`✓`) is displayed alongside a detail message like `"1 open circuit(s)"`. To ensure the checklist accurately reflects the health of the feed sources, `feeds_ok` should only be `True` when there are no open circuits.
- **Gemini suggested fix:** feeds_ok = open_circuits == 0
- **Current main file/path:** `backend/onboarding/checklist.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-371-3550281334

- **PR:** #371
- **Comment ID:** 3550281334
- **Gemini severity:** medium
- **Original file:** `frontend/src/pages/admin/OverviewPage.jsx`
- **Original line:** 126
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/371#discussion_r3550281334
- **Gemini finding summary:** In `dismissOnboarding`, if the `adminApi.post` request fails (returns a non-2xx status code), the error is not handled or displayed because `adminApi` does not throw on non-2xx responses. The function will silently fail, and the user will receive no feedback. We should handle the `!res.ok` case and display an appropriate error toast.
- **Gemini suggested fix:** try {
      const res = await adminApi.post('/onboarding/dismiss', {})
      if (res.ok) {
        setOnboarding(prev => prev ? { ...prev, dismissed: true } : prev)
        toast('Checklist dismissed', true)
      } else {
        const data = await res.json().catch(() => ({}))
        toast(data.detail || 'Dismiss failed (' + res.status + ')', false)
      }
    } catch (e) { toast(String(e.message), false) }
- **Current main file/path:** `frontend/src/pages/admin/OverviewPage.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-372-3550316985

- **PR:** #372
- **Comment ID:** 3550316985
- **Gemini severity:** medium
- **Original file:** `scripts/import_intel_snapshot.py`
- **Original line:** 76
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/372#discussion_r3550316985
- **Gemini finding summary:** If `--replace-intel` is used on a greenfield or partially initialized database where some of the `INTEL_TABLES` do not exist yet, the `TRUNCATE` command will fail with an `UndefinedTableError`. Querying `information_schema.tables` first to filter only existing tables makes the truncation process robust.
- **Gemini suggested fix:** async def _truncate_intel_tables(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=60)
    try:
        rows = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ANY($1)
            """,
            list(INTEL_TABLES),
        )
        existing_tables = [row["table_name"] for row in rows]
        if existing_tables:
            quoted = ", ".join(f'"{t}"' for t in existing_tables)
            await conn.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
    finally:
        await conn.close()
- **Current main file/path:** `scripts/import_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-372-3550316995

- **PR:** #372
- **Comment ID:** 3550316995
- **Gemini severity:** medium
- **Original file:** `scripts/import_intel_snapshot.py`
- **Original line:** 114
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/372#discussion_r3550316995
- **Gemini finding summary:** If some tables in `INTEL_TABLES` are missing (e.g., if migrations are skipped or if the snapshot is older and doesn't contain all tables), `_row_counts` will crash with an `UndefinedTableError`. Catching this exception and defaulting the count to 0 allows the script to handle missing tables gracefully and raise a clean row count mismatch error instead of a database crash.
- **Gemini suggested fix:** async def _row_counts(database_url: str) -> dict[str, int]:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        counts: dict[str, int] = {}
        for table in INTEL_TABLES:
            try:
                counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))
            except asyncpg.UndefinedTableError:
                counts[table] = 0
        return counts
    finally:
        await conn.close()
- **Current main file/path:** `scripts/import_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-372-3550316998

- **PR:** #372
- **Comment ID:** 3550316998
- **Gemini severity:** medium
- **Original file:** `scripts/import_intel_snapshot.py`
- **Original line:** 157
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/372#discussion_r3550316998
- **Gemini finding summary:** If an exception occurs during the decompression phase (e.g., `gzip.open` or `shutil.copyfileobj` fails due to a corrupted file or disk full), the temporary file created by `tempfile.NamedTemporaryFile` will leak on disk because the `try...finally` block is only entered after decompression is complete. Wrapping the temporary file creation and decompression inside the `try...finally` block ensures that the temporary file is always cleaned up.
- **Gemini suggested fix:** staging_path: Path | None = None
    try:
        dump_path = input_path
        if input_path.name.endswith(".gz"):
            staging = tempfile.NamedTemporaryFile(suffix=".pgdump", delete=False)
            staging_path = Path(staging.name)
            staging.close()
            with gzip.open(input_path, "rb") as src, staging_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            dump_path = staging_path

        if replace_intel:
            asyncio.run(_truncate_intel_tables(database_url))
        run_pg_restore(database_url, dump_path)
        if not skip_migrations:
            _run_alembic_upgrade(database_url)
        restored = asyncio.run(_row_counts(database_url))
        for table in INTEL_TABLES:
            expected = manifest["row_counts"].get(t
- **Current main file/path:** `scripts/import_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-372-3550317004

- **PR:** #372
- **Comment ID:** 3550317004
- **Gemini severity:** medium
- **Original file:** `scripts/verify_intel_snapshot.py`
- **Original line:** 59
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/372#discussion_r3550317004
- **Gemini finding summary:** Using `dst.write(src.read())` loads the entire uncompressed database dump into memory at once, which can cause high memory usage or Out-Of-Memory (OOM) crashes on resource-constrained environments. Using `shutil.copyfileobj` streams the data in chunks and is much more memory-efficient.
- **Gemini suggested fix:** if bundle.name.endswith(".gz"):
            import shutil
            with tempfile.NamedTemporaryFile(suffix=".pgdump", delete=False) as tmp:
                staging = Path(tmp.name)
            try:
                with gzip.open(bundle, "rb") as src, staging.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                _verify_dump_tables(staging)
            finally:
                if staging.is_file():
                    staging.unlink()
- **Current main file/path:** `scripts/verify_intel_snapshot.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-373-3550388129

- **PR:** #373
- **Comment ID:** 3550388129
- **Gemini severity:** high
- **Original file:** `backend/threat_model/scenarios.py`
- **Original line:** 243
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/373#discussion_r3550388129
- **Gemini finding summary:** The current implementation executes a database query inside a loop for each of the 40 threat scenarios (the N+1 query problem). This can cause severe performance degradation on production databases. Additionally, if the `stack` parameter is empty or `None`, the query executes without any filter, scanning the entire database and returning unscoped scenarios instead of short-circuiting as intended by the API design. We can resolve both issues by short-circuiting early when `stack_terms` is empty, and using a single batched query with `ROW_NUMBER() OVER` to fetch the top 5 linked CVEs for all tec
- **Gemini suggested fix:** stack_clause, stack_params, stack_terms = _stack_match_clause(stack)

    if not stack_terms:
        return {
            "scenarios": [],
            "meta": {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stack_terms": [],
                "profile_required": True,
                "technique_total": 0,
                "gap_count": 0,
            },
        }

    cve_filter = f"WHERE m.cve_id IN (SELECT c.cve_id FROM cves c WHERE {stack_clause})"
    params = list(stack_params)

    exposure_rows = await db.execute_fetchall(
        f"""
        SELECT m.technique_id,
               COUNT(DISTINCT m.cve_id) AS cve_count,
               SUM(CASE WHEN c.is_kev = 1 THEN 1 ELSE 0 END) AS kev_count,
               MAX(c.epss_score)
- **Current main file/path:** `backend/threat_model/scenarios.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-373-3550388137

- **PR:** #373
- **Comment ID:** 3550388137
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 379
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/373#discussion_r3550388137
- **Gemini finding summary:** The `ThreatScenariosPanel` does not adhere to the project's robust error-handling standards (Track A5 / Track H3 / Track E1). Unlike other panels in `Forge.jsx`, it lacks a retry button and does not render the `errorRequestId` reference link to the admin log viewer. We should introduce a local `reloadKey` state to trigger re-fetching, and render the standard error block with the `Retry` button and `errorRequestId` link.
- **Gemini suggested fix:** const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!profileStack) {
      setData(null)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchThreatModelScenarios(profileStack)
      .then(payload => { if (!cancelled) setData(payload) })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to load threat scenarios')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-374-3550413748

- **PR:** #374
- **Comment ID:** 3550413748
- **Gemini severity:** high
- **Original file:** `backend/proof/bench.py`
- **Original line:** 29
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/374#discussion_r3550413748
- **Gemini finding summary:** `yaml.safe_load` can raise `yaml.YAMLError` (such as `ParserError` or `ScannerError`) if the provided `sigma_yaml` is malformed. Since this exception is not caught here or in the router, it will result in an unhandled `500 Internal Server Error` instead of a clean `400 Bad Request`.\n\nWe should wrap `yaml.safe_load` in a `try-except` block and raise a `ValueError` so that the router can handle it gracefully.
- **Gemini suggested fix:** try:\n        data = yaml.safe_load(sigma_yaml) or {}\n    except yaml.YAMLError as exc:\n        raise ValueError(f"Invalid Sigma YAML: {exc}") from exc
- **Current main file/path:** `backend/proof/bench.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-374-3550413754

- **PR:** #374
- **Comment ID:** 3550413754
- **Gemini severity:** high
- **Original file:** `backend/proof/bench.py`
- **Original line:** 59
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/374#discussion_r3550413754
- **Gemini finding summary:** Stripping all backslashes with `strip("\\")` can lead to incorrect matches and false positives. For example, a pattern like `\\cmd.exe` will have its backslash stripped to `cmd.exe`, which will incorrectly match `mycmd.exe` instead of requiring the backslash boundary. Additionally, if the pattern is just `\\` or `r\\`, it will strip to an empty string `""`, which will match every single log line.\n\nInstead, we should only strip the leading `r` if present, and keep the backslash for the suffix match. We should also ensure the suffix is not empty before performing the match.
- **Gemini suggested fix:** if pat.startswith("r\\") or pat.startswith("\\"):\n        suffix = pat[2:] if pat.startswith("r\\") else pat\n        return lower_line.endswith(suffix) if suffix else False
- **Current main file/path:** `backend/proof/bench.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-374-3550413760

- **PR:** #374
- **Comment ID:** 3550413760
- **Gemini severity:** medium
- **Original file:** `backend/proof/bench.py`
- **Original line:** 101
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/374#discussion_r3550413760
- **Gemini finding summary:** The current implementation of `run_proof` performs three separate passes over the `lines` list:\n1. A loop to find up to `max_samples` hits.\n2. A list comprehension `sum(1 for raw in lines if raw.strip())` to count non-empty lines.\n3. A second loop to count `hit_count` for all lines.\n\nThis is highly inefficient because `_line_matches` is called multiple times for the same lines, and the list is traversed repeatedly. We can consolidate all of this into a single, highly efficient pass.
- **Gemini suggested fix:** hits: list[dict[str, Any]] = []\n    hit_count = 0\n    non_empty = 0\n\n    for idx, raw in enumerate(lines, start=1):\n        line = raw.rstrip("\\n")\n        if not line.strip():\n            continue\n        non_empty += 1\n        matched = [p for p in use_patterns if _line_matches(line, p)]\n        if matched:\n            hit_count += 1\n            if len(hits) < max_samples:\n                hits.append({\n                    "line_number": idx,\n                    "line": line[:500],\n                    "matched_patterns": matched[:5]\n                })\n\n    miss_count = max(non_empty - hit_count, 0)
- **Current main file/path:** `backend/proof/bench.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-374-3550413766

- **PR:** #374
- **Comment ID:** 3550413766
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 147
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/374#discussion_r3550413766
- **Gemini finding summary:** Currently, `ProofBenchSection` resets its state (clearing pasted log lines and results) whenever the `packs` prop changes. This means if the user generates or saves a new pack for the *same* technique, their current work in the proof bench is completely wiped out, which is a frustrating user experience.\n\nWe can fix this by passing `techniqueId` to `ProofBenchSection` and only resetting the pasted lines and results when the active technique actually changes. When `packs` updates for the same technique, we can gracefully preserve the current selection or default to the first pack if the previo
- **Gemini suggested fix:** function ProofBenchSection({ packs, techniqueId }) {\n  const [selectedPackId, setSelectedPackId] = useState(packs[0]?.id ?? null)\n  const [lines, setLines] = useState('')\n  const [result, setResult] = useState(null)\n  const [running, setRunning] = useState(false)\n  const [error, setError] = useState(null)\n  const [errorRequestId, setErrorRequestId] = useState(null)\n\n  const selectedPack = useMemo(\n    () => packs.find(p => p.id === selectedPackId) || packs[0],\n    [packs, selectedPackId],\n  )\n\n  useEffect(() => {\n    setSelectedPackId(prev => {\n      if (prev && packs.some(p => p.id === prev)) return prev\n      return packs[0]?.id ?? null\n    })\n  }, [packs])\n\n  useEffect(() => {\n    setLines('')\n    setResult(null)\n    setError(null)\n    setErrorRequestId(null)\n  
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-374-3550413776

- **PR:** #374
- **Comment ID:** 3550413776
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 467
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/374#discussion_r3550413776
- **Gemini finding summary:** Pass `techniqueId` to `ProofBenchSection` to allow it to track when the active technique changes and avoid resetting pasted log lines when new packs are generated for the same technique.
- **Gemini suggested fix:** {packs.length > 0 && <ProofBenchSection packs={packs} techniqueId={techniqueId} />}
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-374-3550413791

- **PR:** #374
- **Comment ID:** 3550413791
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 155
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/374#discussion_r3550413791
- **Gemini finding summary:** The backend enforces a maximum limit of 5000 log lines. If the user pastes more than 5000 lines, the API will reject the request with a `422 Unprocessable Entity` error.\n\nWe should filter out empty lines first and perform a client-side validation check to show a friendly error message if the limit is exceeded, preventing unnecessary API failures.
- **Gemini suggested fix:** const splitLines = lines.split('\\n').filter(l => l.trim())\n    if (splitLines.length === 0) {\n      setError('Paste at least one log line')\n      setErrorRequestId(null)\n      return\n    }\n    if (splitLines.length > 5000) {\n      setError('Maximum of 5000 log lines allowed')\n      setErrorRequestId(null)\n      return\n    }
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-375-3550474982

- **PR:** #375
- **Comment ID:** 3550474982
- **Gemini severity:** high
- **Original file:** `backend/detection/backlog.py`
- **Original line:** 259
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/375#discussion_r3550474982
- **Gemini finding summary:** The backlog list currently returns all items with an `'open'` status, even if a hunt pack has since been generated or saved for that technique (which means it is no longer a gap). We should dynamically filter out items that are no longer gaps to prevent resolved items from showing up in the backlog.
- **Gemini suggested fix:** out: list[dict[str, Any]] = []
    for row in rows:
        if row["status"] == "open":
            pack_count = await _pack_count(db, row["technique_id"])
            if _coverage_status(pack_count, row["technique_id"]) != "gap":
                continue
        out.append(dict(row))
    return out
- **Current main file/path:** `backend/detection/backlog.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-375-3550474987

- **PR:** #375
- **Comment ID:** 3550474987
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 497
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/375#discussion_r3550474987
- **Gemini finding summary:** Add `reloadKey` to the props of `BacklogPanel` so that we can trigger a reload of the backlog list when a new hunt pack is generated.
- **Gemini suggested fix:** function BacklogPanel({ profileStack, onGeneratePack, generatingCve, onDismissed, reloadKey }) {
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-375-3550475003

- **PR:** #375
- **Comment ID:** 3550475003
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 516
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/375#discussion_r3550475003
- **Gemini finding summary:** Add `reloadKey` to the dependency array of `loadBacklog` so that the backlog list automatically refreshes when `reloadKey` changes (e.g., after a hunt pack is successfully generated).
- **Gemini suggested fix:** }, [profileStack, reloadKey])
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-375-3550475010

- **PR:** #375
- **Comment ID:** 3550475010
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/Forge.jsx`
- **Original line:** 891
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/375#discussion_r3550475010
- **Gemini finding summary:** Pass the `reloadKey` prop to `BacklogPanel` so that it can automatically refresh the backlog list when a hunt pack is generated.
- **Gemini suggested fix:** <BacklogPanel
            profileStack={profileStack}
            onGeneratePack={handleScenarioGenerate}
            generatingCve={generatingFromScenario}
            onDismissed={handlePackSaved}
            reloadKey={reloadKey}
          />
- **Current main file/path:** `frontend/src/components/Forge.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-375-3550475013

- **PR:** #375
- **Comment ID:** 3550475013
- **Gemini severity:** medium
- **Original file:** `backend/routers/detection_backlog.py`
- **Original line:** 59
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/375#discussion_r3550475013
- **Gemini finding summary:** Normalize the split stack terms by stripping leading/trailing whitespace and filtering out empty strings to ensure clean metadata in the API response.
- **Gemini suggested fix:** "stack_terms": [t.strip() for t in stack_filter.split(",") if t.strip()] if stack_filter else [],
- **Current main file/path:** `backend/routers/detection_backlog.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-375-3550475021

- **PR:** #375
- **Comment ID:** 3550475021
- **Gemini severity:** medium
- **Original file:** `backend/routers/detection_backlog.py`
- **Original line:** 72
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/375#discussion_r3550475021
- **Gemini finding summary:** Use keyword arguments for `HTTPException` to align with standard FastAPI practices and prevent positional argument mismatch.
- **Gemini suggested fix:** raise HTTPException(status_code=404, detail="Backlog item not found")
- **Current main file/path:** `backend/routers/detection_backlog.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-376-3550705815

- **PR:** #376
- **Comment ID:** 3550705815
- **Gemini severity:** critical
- **Original file:** `backend/db/ioc_watchlist.py`
- **Original line:** 32
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550705815
- **Gemini finding summary:** The `list_ioc_watchlist` function unconditionally uses the `?` placeholder. This will cause a syntax error on PostgreSQL environments. Use dialect-aware dispatching to support both PostgreSQL (`$1`) and SQLite (`?`).
- **Gemini suggested fix:** async def list_ioc_watchlist(db: DbConnection, user_id: int) -> list[dict]:
    if _is_postgres_connection(db):
        rows = await db.execute_fetchall(
            """
            SELECT id, user_id, ioc_type, ioc_value, label, created_at
            FROM ioc_watchlist
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
    else:
        rows = await db.execute_fetchall(
            """
            SELECT id, user_id, ioc_type, ioc_value, label, created_at
            FROM ioc_watchlist
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
    return [dict(row) for row in rows]
- **Current main file/path:** `backend/db/ioc_watchlist.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-376-3550705828

- **PR:** #376
- **Comment ID:** 3550705828
- **Gemini severity:** critical
- **Original file:** `backend/db/ioc_watchlist.py`
- **Original line:** 78
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550705828
- **Gemini finding summary:** The `SELECT` query in `upsert_ioc_watchlist_entry` unconditionally uses `?` placeholders, which will fail on PostgreSQL. Implement dialect-aware placeholder dispatching.
- **Gemini suggested fix:** if _is_postgres_connection(db):
        rows = await db.execute_fetchall(
            """
            SELECT id, user_id, ioc_type, ioc_value, label, created_at
            FROM ioc_watchlist
            WHERE user_id = $1 AND ioc_type = $2 AND ioc_value = $3
            """,
            (user_id, ioc_type, value),
        )
    else:
        rows = await db.execute_fetchall(
            """
            SELECT id, user_id, ioc_type, ioc_value, label, created_at
            FROM ioc_watchlist
            WHERE user_id = ? AND ioc_type = ? AND ioc_value = ?
            """,
            (user_id, ioc_type, value),
        )
    return dict(rows[0])
- **Current main file/path:** `backend/db/ioc_watchlist.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-376-3550705846

- **PR:** #376
- **Comment ID:** 3550705846
- **Gemini severity:** critical
- **Original file:** `backend/db/threatfox.py`
- **Original line:** 45
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550705846
- **Gemini finding summary:** The `upsert_threatfox_iocs` function unconditionally uses `?` placeholders and executes individual queries in a loop. This will fail on PostgreSQL and is highly inefficient. Batch the inserts using `executemany` with dialect-aware placeholders.
- **Gemini suggested fix:** async def upsert_threatfox_iocs(db: DbConnection, rows: list[dict]) -> int:
    """Insert or refresh ThreatFox rows. Returns rows written."""
    if not rows:
        return 0
    now = utcnow_str()
    
    pg = _is_postgres_connection(db)
    placeholders = ", ".join(f"${i}" for i in range(1, 10)) if pg else ", ".join("?" for _ in range(9))
    
    sql = f"""
        INSERT INTO threatfox_iocs (
            ioc_id, ioc_type, ioc_value, raw_ioc, malware,
            threat_type, confidence_level, first_seen, fetched_at
        ) VALUES ({placeholders})
        ON CONFLICT(ioc_id) DO UPDATE SET
            ioc_type = excluded.ioc_type,
            ioc_value = excluded.ioc_value,
            raw_ioc = excluded.raw_ioc,
            malware = excluded.malware,
            threat_type = exclu
- **Current main file/path:** `backend/db/threatfox.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-376-3550705855

- **PR:** #376
- **Comment ID:** 3550705855
- **Gemini severity:** high
- **Original file:** `backend/db/enrichment.py`
- **Original line:** 612
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550705855
- **Gemini finding summary:** Executing `UPDATE` queries in a loop for each CVE ID is highly inefficient and can cause significant performance degradation when processing large lists (up to 5000 entries). Instead, perform the updates in chunks using the `IN` clause, which is much faster and aligns with existing patterns in this file.
- **Gemini suggested fix:** async def sync_vulncheck_exploited_flags(db: DbConnection, cve_ids: list[str]) -> int:
    """Mark CVEs present in VulnCheck KEV catalog (resets prior flags)."""
    await db.execute("UPDATE cves SET is_vulncheck_exploited = 0 WHERE is_vulncheck_exploited = 1")
    
    normalized = sorted({(cve_id or "").strip().upper() for cve_id in cve_ids if (cve_id or "").strip()})
    if not normalized:
        return 0
        
    pg = _is_postgres_connection(db)
    updated = 0
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        cursor = await db.execute(
            f"UPDATE cves SET is_vulncheck_exploited = 1 WHERE cve_id IN ({placeholders})",
            tuple(c
- **Current main file/path:** `backend/db/enrichment.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-376-3550705970

- **PR:** #376
- **Comment ID:** 3550705970
- **Gemini severity:** high
- **Original file:** `backend/feeds/threatfox.py`
- **Original line:** 128
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550705970
- **Gemini finding summary:** Calling `response.json()` outside of a `try...except` block is risky. If the ThreatFox API returns a non-JSON response (e.g., an HTML error page from Cloudflare or a gateway timeout), it will raise an unhandled exception and crash the scheduler job. Wrap the JSON parsing in a `try...except` block.
- **Gemini suggested fix:** try:
        body = response.json()
    except Exception as exc:
        logger.error("Failed to parse ThreatFox JSON response: %s", exc)
        return []
    if body.get("query_status") != "ok":
        logger.warning("ThreatFox query_status: %s", body.get("query_status"))
        return []
- **Current main file/path:** `backend/feeds/threatfox.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-376-3550705986

- **PR:** #376
- **Comment ID:** 3550705986
- **Gemini severity:** high
- **Original file:** `backend/feeds/vulncheck_kev.py`
- **Original line:** 78
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550705986
- **Gemini finding summary:** Calling `response.json()` outside of a `try...except` block is risky. If the VulnCheck API returns a non-JSON response, it will raise an unhandled exception and crash the scheduler job. Wrap the JSON parsing in a `try...except` block.
- **Gemini suggested fix:** try:
            body = response.json()
        except Exception as exc:
            logger.error("Failed to parse VulnCheck JSON response on page %s: %s", page, exc)
            break
        data = body.get("data") or []
        if not data:
            break
- **Current main file/path:** `backend/feeds/vulncheck_kev.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-376-3550706005

- **PR:** #376
- **Comment ID:** 3550706005
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/IOCLookup.jsx`
- **Original line:** 720
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550706005
- **Gemini finding summary:** To prevent potential `TypeError` crashes if `items` is null or undefined, default it to an empty array `[]` in the destructuring assignment.
- **Gemini suggested fix:** function WatchlistPanel({ items = [], loading, error, errorRequestId, onRemove, removingId, onRerun, authed }) {
- **Current main file/path:** `frontend/src/components/IOCLookup.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-376-3550706023

- **PR:** #376
- **Comment ID:** 3550706023
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/IOCLookup.jsx`
- **Original line:** 893
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/376#discussion_r3550706023
- **Gemini finding summary:** The `loadWatchlist` function does not handle component unmounting or race conditions, which can lead to memory leak warnings or unexpected state updates if the component unmounts before the promise resolves. Align it with the `loadUsage` pattern by implementing a `cancelled` flag.
- **Gemini suggested fix:** const loadWatchlist = useCallback(() => {
    if (!authed) {
      setWatchlistItems([])
      return undefined
    }
    let cancelled = false
    setWatchlistLoading(true)
    setWatchlistError(null)
    setWatchlistErrorRequestId(null)
    return fetchIocWatchlist()
      .then(data => {
        if (!cancelled) setWatchlistItems(data.items || [])
      })
      .catch(err => {
        if (!cancelled) {
          setWatchlistError(err.message || 'Failed to load IOC watchlist')
          setWatchlistErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setWatchlistLoading(false)
      })
    return () => { cancelled = true }
  }, [authed])

  useEffect(() => {
    const cleanup = loadWatchlist()
    return ()
- **Current main file/path:** `frontend/src/components/IOCLookup.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-378-3550807676

- **PR:** #378
- **Comment ID:** 3550807676
- **Gemini severity:** critical
- **Original file:** `frontend/src/components/CVEFeed.jsx`
- **Original line:** 81
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/378#discussion_r3550807676
- **Gemini finding summary:** Since the `showingRange` and `setShowingRange` state variables have been removed from the component, there is a remaining reference to `setShowingRange(null)` on line 268 inside the `useEffect` that resets and reloads when filters change. This will cause a runtime `ReferenceError: setShowingRange is not defined` as soon as any filter is updated. Please remove line 268 to prevent this crash.
- **Gemini suggested fix:** (none)
- **Current main file/path:** `frontend/src/components/CVEFeed.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-378-3550807681

- **PR:** #378
- **Comment ID:** 3550807681
- **Gemini severity:** high
- **Original file:** `frontend/src/components/CVEFeed.jsx`
- **Original line:** 145
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/378#discussion_r3550807681
- **Gemini finding summary:** To make the `cardRef` and `onWatchlistPin` props stable for `CVECard`, we should define stable callbacks using `useCallback` here.
- **Gemini suggested fix:** const handleInvestigate = useCallback((c) => {
    investigation?.startInvestigation?.(c)
  }, [investigation])

  const handleLookupIoc = useCallback((c) => {
    investigation?.pivotToIocFromCve?.(c)
  }, [investigation])

  const handleWatchlistPin = useCallback((cveId) => {
    onWatchlistChange?.(cveId, 'pin')
  }, [onWatchlistChange])

  const setCardRef = useCallback((el, idx) => {
    cardRefs.current[idx] = el
  }, [])
- **Current main file/path:** `frontend/src/components/CVEFeed.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-378-3550807684

- **PR:** #378
- **Comment ID:** 3550807684
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/FeedVisibleRange.jsx`
- **Original line:** 39
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/378#discussion_r3550807684
- **Gemini finding summary:** If no cards are visible in the viewport (e.g., the user has scrolled past the feed), `first` remains `null`. Falling back to `first = 0` and `last = 0` will set the range to `Showing 1-1`, which is misleading when no cards are actually visible. We should set the range to `null` and return early instead.
- **Gemini suggested fix:** if (first === null) {
      setRange(null)
      return
    }
- **Current main file/path:** `frontend/src/components/FeedVisibleRange.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-378-3550807695

- **PR:** #378
- **Comment ID:** 3550807695
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/FeedVisibleRange.jsx`
- **Original line:** 64
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/378#discussion_r3550807695
- **Gemini finding summary:** Currently, the scroll and resize event listeners are removed and re-bound every time `cardCount` changes. We can optimize this by splitting the logic into two `useEffect` hooks: one that sets up the event listeners once on mount, and another that triggers `schedule()` when `cardCount` changes.
- **Gemini suggested fix:** useEffect(() => {
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule, { passive: true })
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [schedule])

  useEffect(() => {
    schedule()
  }, [schedule, cardCount])
- **Current main file/path:** `frontend/src/components/FeedVisibleRange.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-379-3550822249

- **PR:** #379
- **Comment ID:** 3550822249
- **Gemini severity:** high
- **Original file:** `backend/routers/cves.py`
- **Original line:** 1039
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/379#discussion_r3550822249
- **Gemini finding summary:** There are two issues here: 1. **Overwriting Bug**: `enrich_cve_circl` returns the full `cve` dict copy with CIRCL data merged in. When `cve.update(circl_patch)` is called in `get_cve`, it will overwrite any concurrent updates to `cve` (such as the `summary` updated by `_detail_enrich_osv`) back to their pre-enrichment state. We should only return a patch dict containing the fields that CIRCL enrichment actually modifies (`circl`, `capec_ids`, and `source_urls`). 2. **Reliability**: `get_db()` is called outside the `try` block. If a database connection cannot be acquired (e.g., due to pool exha
- **Gemini suggested fix:** async def _detail_enrich_circl(cve: dict) -> dict:
    try:
        db = await get_db()
        try:
            enriched = await enrich_cve_circl(db, dict(cve))
            await db.commit()
            patch = {}
            if "circl" in enriched:
                patch["circl"] = enriched["circl"]
            if "capec_ids" in enriched:
                patch["capec_ids"] = enriched["capec_ids"]
            if "source_urls" in enriched:
                patch["source_urls"] = enriched["source_urls"]
            return patch
        except Exception as exc:
            logger.error("CIRCL enrichment failed for %s: %s", cve.get("cve_id"), exc)
            return {}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error("Failed to acquire DB or 
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** test_gemini_reconciliation.py
- **Resolution evidence:** _detail_enrich_circl returns _circl_enrichment_patch only

### F-379-3550822254

- **PR:** #379
- **Comment ID:** 3550822254
- **Gemini severity:** high
- **Original file:** `backend/routers/cves.py`
- **Original line:** 994
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/379#discussion_r3550822254
- **Gemini finding summary:** There are two reliability issues here: 1. **Aborted Transaction State**: If `load_public_exploits_for_cve` fails, the transaction is aborted. On Postgres, executing any further queries (like `derive_exploit_provenance` in the `except` block) on the same connection will raise an `InFailedSQLTransaction` exception, which propagates out of the function and causes the entire request to 500. We should rollback the transaction and wrap the fallback `derive_exploit_provenance` call in a try-except block. 2. **Pool Exhaustion**: `get_db()` is called outside the `try` block. If connection pool exhausti
- **Gemini suggested fix:** async def _detail_enrich_exploits(cve_key: str, cve: dict) -> dict:
    from db.cache import get_cve_exploits_latest_fetched_at, get_feed_cache_timestamp

    try:
        db = await get_db()
        try:
            public_exploits = await load_public_exploits_for_cve(
                db,
                cve_key,
                has_poc=bool(cve.get("has_poc")),
                source_urls=cve.get("source_urls"),
            )
            provenance = await derive_exploit_provenance(
                db,
                cve_key,
                used_nvd_fallback=bool(public_exploits)
                and not await get_cve_exploits_latest_fetched_at(db, cve_key)
                and not await get_feed_cache_timestamp(db, f"sploitus:{cve_key}"),
            )
            await db.commit()
    
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** test_gemini_reconciliation.py
- **Resolution evidence:** _detail_enrich_exploits wraps get_db() in outer try for graceful degradation

### F-379-3550822259

- **PR:** #379
- **Comment ID:** 3550822259
- **Gemini severity:** high
- **Original file:** `backend/routers/cves.py`
- **Original line:** 1010
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/379#discussion_r3550822259
- **Gemini finding summary:** **Pool Exhaustion / DB Failure**: `get_db()` is called outside the `try` block. If connection pool exhaustion or database failure occurs, the unhandled exception will propagate and fail the entire request. Wrapping the entire function body in a `try-except` block ensures graceful degradation.
- **Gemini suggested fix:** async def _detail_enrich_otx(cve_key: str, otx_key: str) -> dict:
    if not otx_key:
        return {"otx_pulses": []}
    try:
        db = await get_db()
        try:
            pulses = await load_otx_pulses_for_cve(db, cve_key, otx_key)
            await db.commit()
            return {"otx_pulses": pulses}
        except Exception as exc:
            logger.error("OTX pulse load failed for %s: %s", cve_key, exc)
            return {"otx_pulses": []}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error("Failed to acquire DB or process OTX for %s: %s", cve_key, outer_exc)
        return {"otx_pulses": []}
- **Current main file/path:** `backend/routers/cves.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** test_gemini_reconciliation.py
- **Resolution evidence:** _detail_enrich_exploits wraps get_db() in outer try for graceful degradation

### F-380-3550831728

- **PR:** #380
- **Comment ID:** 3550831728
- **Gemini severity:** high
- **Original file:** `backend/db/cve.py`
- **Original line:** 489
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/380#discussion_r3550831728
- **Gemini finding summary:** While `cve_id` is normalized to uppercase locally for change history tracking, the original `cve` dictionary is passed to `_cve_upsert_params(cve)` without updating `cve["cve_id"]` to uppercase. If the incoming feed contains lowercase or mixed-case CVE IDs, they will be inserted into the database as-is. Since PostgreSQL is case-sensitive by default, this will break subsequent queries (such as `cve_exists` or embedding lookups) that query using uppercase IDs. Normalizing `cve["cve_id"]` to uppercase in the dictionary before calling `_cve_upsert_params` ensures case consistency in the database.
- **Gemini suggested fix:** params_batch: list[tuple] = []
    for cve in valid:
        cve_id = (cve.get("cve_id") or "").upper()
        cve["cve_id"] = cve_id
        has_ai, _atlas_tids = analyze_cve_ai_context(cve)
        cve["has_ai_context"] = has_ai
        _append_upsert_change_rows(cve_id, cve, snapshots.get(cve_id), history)
        params_batch.append(_cve_upsert_params(cve))
- **Current main file/path:** `backend/db/cve.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** test_gemini_reconciliation.py::test_upsert_cve_canonicalizes_mixed_case_id
- **Resolution evidence:** cve['cve_id'] uppercased before _cve_upsert_params

### F-381-3550843094

- **PR:** #381
- **Comment ID:** 3550843094
- **Gemini severity:** high
- **Original file:** `backend/routers/auth.py`
- **Original line:** 195
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/381#discussion_r3550843094
- **Gemini finding summary:** ### Issues Identified: 1. **AttributeError on PostgreSQL**: If the application is configured to use PostgreSQL (which is supported via `briefr_require_postgres` and `database_url`), the database driver (e.g., `asyncpg` or `psycopg2`) automatically deserializes `TIMESTAMP` columns into Python `datetime` objects. Calling `.strip()` on a `datetime` object will raise an `AttributeError`, causing a `500 Internal Server Error` on the `/refresh` endpoint. 2. **Fail-Open Security Risk**: If `expires_at` is missing, empty, or malformed (causing a `ValueError` during parsing), the current implementation
- **Gemini suggested fix:** expires_val = session.get("expires_at")
        if not expires_val:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if isinstance(expires_val, datetime):
            exp = expires_val
        else:
            try:
                exp = datetime.fromisoformat(str(expires_val).strip().replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(status_code=401, detail="Not authenticated")

        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Not authenticated")
- **Current main file/path:** `backend/routers/auth.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-382-3550868125

- **PR:** #382
- **Comment ID:** 3550868125
- **Gemini severity:** high
- **Original file:** `backend/alembic/versions/012_cve_trgm_search.py`
- **Original line:** 23
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/382#discussion_r3550868125
- **Gemini finding summary:** The GIN trigram indexes are created on `lower(description)` and `lower(summary)`. While this perfectly matches queries in `_text_match_or_clause`, `_stack_match_clause`, and `_framework_match_clause` (which all use `LOWER(column) LIKE ?`), the primary search filter in `_build_cve_filters` (line 539 of `backend/routers/cves.py`) currently uses:\n\n```python\nconditions.append(\"(c.cve_id LIKE ? OR c.description LIKE ? OR c.summary LIKE ?)\")\n```\n\nBecause this primary search path does not wrap `c.description` and `c.summary` in `LOWER()`, PostgreSQL will not be able to utilize these new GIN i
- **Gemini suggested fix:** (none)
- **Current main file/path:** `backend/alembic/versions/012_cve_trgm_search.py`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** test_gemini_reconciliation.py::test_build_cve_filters_search_uses_lower_for_trgm_alignment
- **Resolution evidence:** _build_cve_filters uses LOWER() for description/summary search

### F-383-3550931123

- **PR:** #383
- **Comment ID:** 3550931123
- **Gemini severity:** medium
- **Original file:** `SYSTEM_DESIGN.md`
- **Original line:** 150
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/383#discussion_r3550931123
- **Gemini finding summary:** The documentation states that PostgreSQL text search benefits from the `pg_trgm` GIN indexes created in Alembic migration `012_cve_trgm_search` (which are defined on `lower(description)` and `lower(summary)`). However, in `backend/routers/cves.py` under `_build_cve_filters` (line 539), the query for general search is built as:
- **Gemini suggested fix:** conditions.append("(c.cve_id LIKE ? OR c.description LIKE ? OR c.summary LIKE ?)")
- **Current main file/path:** `SYSTEM_DESIGN.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-383-3550931129

- **PR:** #383
- **Comment ID:** 3550931129
- **Gemini severity:** medium
- **Original file:** `API_REFERENCE.md`
- **Original line:** 90
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/383#discussion_r3550931129
- **Gemini finding summary:** The documentation notes that text search on PostgreSQL uses `pg_trgm` GIN indexes from Alembic migration `012_cve_trgm_search`. However, there is a discrepancy in the query implementation in `backend/routers/cves.py` (line 539) where the general search filter is constructed without the `LOWER()` function:
- **Gemini suggested fix:** conditions.append("(c.cve_id LIKE ? OR c.description LIKE ? OR c.summary LIKE ?)")
- **Current main file/path:** `API_REFERENCE.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** No matching unfixed pattern on current main; concern addressed or non-actionable

### F-384-3550974972

- **PR:** #384
- **Comment ID:** 3550974972
- **Gemini severity:** medium
- **Original file:** `TECHNICAL_INVENTORY.md`
- **Original line:** 34
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/384#discussion_r3550974972
- **Gemini finding summary:** There is a discrepancy between `TECHNICAL_INVENTORY.md` and `scripts/generate_technical_inventory_xlsx.py`. The build tool version is listed as `5.4.1` here, but the script lists it as `8.x` (matching the `Vite 8` mention in the row above). This should be updated to `8.x` for consistency.
- **Gemini suggested fix:** | Build tool | Vite | 8.x | Dev server and production bundle |
- **Current main file/path:** `TECHNICAL_INVENTORY.md`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** Suggested code appears present in current file

### F-385-3551612488

- **PR:** #385
- **Comment ID:** 3551612488
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/IOCLookup.jsx`
- **Original line:** 952
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/385#discussion_r3551612488
- **Gemini finding summary:** The error message here is inconsistent with the updated error message in `parseError` (line 81). Updating it to `'Not found in configured threat databases'` ensures terminology consistency across the lookup interface.
- **Gemini suggested fix:** setError('Not found in configured threat databases')
- **Current main file/path:** `frontend/src/components/IOCLookup.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** PR #385 merged: IOC not-found uses IOC_NOT_FOUND_IN_DATABASES

### F-385-3551612501

- **PR:** #385
- **Comment ID:** 3551612501
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/MorningBrief.jsx`
- **Original line:** 175
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/385#discussion_r3551612501
- **Gemini finding summary:** The ternary expression `{brief?.meta?.since_hours ? ' hours' : ' hours'}` is redundant because both branches return the exact same string. Additionally, it does not handle the singular `'hour'` case when `since_hours` is `1`. Simplifying this expression and adding singular/plural handling improves both code quality and grammatical correctness.
- **Gemini suggested fix:** Prioritized CVEs from the last
            {brief?.meta?.since_hours ? ' ' + brief.meta.since_hours : ' 24'}
            {brief?.meta?.since_hours === 1 ? ' hour' : ' hours'}, based on KEV deadlines, EPSS movement, and stack overlap.
- **Current main file/path:** `frontend/src/components/MorningBrief.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** PR #385 merged: hour label uses formatSinceHoursLabel()

### F-385-3551612508

- **PR:** #385
- **Comment ID:** 3551612508
- **Gemini severity:** medium
- **Original file:** `frontend/src/components/DetailDrawer/DetectTab.jsx`
- **Original line:** 199
- **Comment URL:** https://github.com/Soldier0x0/briefr/pull/385#discussion_r3551612508
- **Gemini finding summary:** The ternary operator here results in inconsistent casing for confidence levels (e.g., `'Medium confidence match'` vs `'HIGH confidence match'` or `'LOW confidence match'`). Converting the confidence string to sentence case dynamically ensures consistent and professional presentation across all confidence levels.
- **Gemini suggested fix:** {confidence.charAt(0) + confidence.slice(1).toLowerCase() + ' confidence match'}
- **Current main file/path:** `frontend/src/components/DetailDrawer/DetectTab.jsx`
- **Classification:** ALREADY_FIXED
- **Correction required:** NO
- **Planned action:** None
- **Regression test:** N/A
- **Resolution evidence:** PR #385 merged: confidence labels use confidenceMatchLabel()

## Root-Cause Matrix

### RC-CVE-ID-NORM
- Related Finding IDs: F-380-3550831728
- Related PRs: #380
- Affected current files: `backend/db/cve.py`
- Chosen correction: Canonicalize cve['cve_id'] to uppercase before upsert
- Tests required: See Regression Coverage section

### RC-ENRICH-CONCUR
- Related Finding IDs: F-379-3550822249, F-379-3550822254, F-379-3550822259
- Related PRs: #379
- Affected current files: `backend/routers/cves.py`
- Chosen correction: Field-scoped CIRCL patches; outer try around get_db(); rollback on exploit failure
- Tests required: See Regression Coverage section

### RC-IOC-VOICE
- Related Finding IDs: F-385-3551612488, F-385-3551612501, F-385-3551612508
- Related PRs: #385
- Affected current files: —
- Chosen correction: No change — fixed in PR #385
- Tests required: See Regression Coverage section

### RC-OTHER
- Related Finding IDs: F-306-3539062383, F-306-3539062387, F-306-3539062394, F-307-3539113977, F-308-3539146527, F-309-3539249276, F-309-3539249412, F-310-3539322943, F-310-3539322951, F-311-3541139984, F-311-3541139989, F-312-3541205002, F-312-3541205005, F-312-3541205013, F-313-3541251364, F-313-3541251380, F-313-3541251386, F-313-3541251391, F-314-3541338572, F-315-3541375455, F-315-3541375460, F-315-3541375464, F-316-3541398169, F-316-3541398172, F-316-3541398177, F-316-3541398180, F-317-3541433593, F-318-3541543439, F-319-3541685507, F-320-3541883878, F-320-3541883885, F-320-3541883896, F-320-3541883904, F-321-3542035901, F-321-3542035906, F-321-3542035913, F-322-3542172254, F-322-3542172272, F-322-3542172277, F-323-3542291283, F-323-3542291288, F-323-3542291292, F-324-3542424012, F-324-3542424018, F-325-3542574069, F-325-3542574083, F-325-3542574086, F-328-3543214762, F-329-3544074290, F-329-3544074308, F-330-3544110612, F-330-3544110622, F-331-3544151360, F-331-3544151377, F-331-3544151387, F-332-3544203459, F-332-3544203479, F-332-3544203484, F-332-3544203489, F-332-3544203494, F-332-3544203501, F-332-3544203506, F-332-3544203516, F-334-3544284295, F-334-3544284306, F-334-3544284330, F-334-3544284340, F-335-3544327471, F-335-3544327479, F-335-3544327488, F-336-3544975093, F-336-3544975105, F-337-3544990031, F-338-3545044188, F-338-3545044198, F-338-3545044213, F-339-3545519573, F-340-3545932705, F-340-3545932726, F-340-3545932732, F-340-3545932742, F-341-3546104311, F-341-3546104320, F-342-3546273801, F-342-3546273819, F-343-3546466579, F-344-3546597042, F-346-3547430374, F-346-3547430382, F-348-3547467524, F-350-3547733564, F-350-3547733571, F-351-3549315681, F-351-3549315687, F-352-3549341964, F-352-3549341977, F-352-3549341981, F-352-3549341986, F-353-3549375008, F-354-3549372582, F-355-3549565675, F-355-3549565688, F-355-3549565693, F-355-3549565698, F-355-3549565701, F-356-3549564691, F-357-3549613674, F-357-3549613681, F-357-3549613693, F-357-3549613700, F-357-3549613707, F-357-3549613715, F-357-3549613717, F-358-3549619055, F-360-3549670425, F-360-3549670432, F-362-3549749748, F-362-3549749757, F-364-3549841627, F-365-3549840788, F-366-3549889357, F-366-3549889363, F-368-3550194889, F-368-3550194898, F-368-3550194908, F-368-3550194914, F-368-3550194919, F-368-3550194926, F-371-3550281320, F-371-3550281334, F-372-3550316985, F-372-3550316995, F-372-3550316998, F-372-3550317004, F-373-3550388129, F-373-3550388137, F-374-3550413748, F-374-3550413754, F-374-3550413760, F-374-3550413766, F-374-3550413776, F-374-3550413791, F-375-3550474982, F-375-3550474987, F-375-3550475003, F-375-3550475010, F-375-3550475013, F-375-3550475021, F-376-3550705815, F-376-3550705828, F-376-3550705846, F-376-3550705855, F-376-3550705970, F-376-3550705986, F-376-3550706005, F-376-3550706023, F-378-3550807676, F-378-3550807681, F-378-3550807684, F-378-3550807695, F-381-3550843094, F-383-3550931123, F-383-3550931129, F-384-3550974972
- Related PRs: #306, #307, #308, #309, #310, #311, #312, #313, #314, #315, #316, #317, #318, #319, #320, #321, #322, #323, #324, #325, #328, #329, #330, #331, #332, #334, #335, #336, #337, #338, #339, #340, #341, #342, #343, #344, #346, #348, #350, #351, #352, #353, #354, #355, #356, #357, #358, #360, #362, #364, #365, #366, #368, #371, #372, #373, #374, #375, #376, #378, #381, #383, #384
- Affected current files: `backend/.env.example`, `backend/api_queue.py`, `backend/correlation/clusters.py`, `backend/correlation/lifecycle.py`, `backend/db/cache.py`, `backend/db/enrichment.py`, `backend/db/ioc_watchlist.py`, `backend/db/sync_state.py`, `backend/db/threatfox.py`, `backend/db/webhooks.py`, `backend/detection/backlog.py`, `backend/detection/nuclei_parser.py`, `backend/feeds/threatfox.py`, `backend/feeds/vulncheck_kev.py`, `backend/intel/provenance.py`, `backend/main.py`, `backend/onboarding/checklist.py`, `backend/operator_settings.py`, `backend/preferences/display_validate.py`, `backend/preferences/repo.py`, `backend/preferences/validate.py`, `backend/proof/bench.py`, `backend/routers/admin.py`, `backend/routers/auth.py`, `backend/routers/cves.py`, `backend/routers/detection_backlog.py`, `backend/routers/health.py`, `backend/routers/me.py`, `backend/tests/test_backup_roundtrip_postgres.py`, `backend/tests/test_db_cache_retention.py`, `backend/tests/test_db_init.py`, `backend/tests/test_db_watchlist.py`, `backend/tests/test_db_webhooks.py`, `backend/tests/test_intel_snapshot_export.py`, `backend/tests/test_operator_settings.py`, `backend/threat_model/scenarios.py`, `backend/webhooks/alerts.py`
- Chosen correction: None — classified ALREADY_FIXED/OBSOLETE/FALSE_POSITIVE
- Tests required: See Regression Coverage section

### RC-PG-SQLITE
- Related Finding IDs: F-336-3544975072, F-364-3549841611
- Related PRs: #336, #364
- Affected current files: `backend/correlation/clusters.py`, `backend/routers/cves.py`
- Chosen correction: No code change — pg_adapt translates router SQLite datetime SQL on Postgres
- Tests required: See Regression Coverage section

### RC-PG-TRGM-SEARCH
- Related Finding IDs: F-382-3550868125
- Related PRs: #382
- Affected current files: `backend/alembic/versions/012_cve_trgm_search.py`
- Chosen correction: LOWER() in _build_cve_filters for pg_trgm index alignment
- Tests required: See Regression Coverage section

## Correction Plan

Ordered by severity (implemented on `fix/gemini-review-reconciliation`):

1. **RC-AUTH-SESSION** — fail-closed `expires_at` on `/api/auth/refresh`
2. **RC-CVE-ID-NORM** — uppercase `cve['cve_id']` before upsert
3. **RC-ENRICH-CONCUR** — CIRCL field patches; outer try on `get_db()`; exploit rollback
4. **RC-PG-TRGM-SEARCH** — `LOWER()` in `_build_cve_filters` general search
5. **RC-DOCS-VERSION** — TECHNICAL_INVENTORY.md Vite 8.x

## Corrections Implemented

- `backend/routers/auth.py` — fail-closed session expiry parsing
- `backend/db/cve.py` — canonical CVE ID on dict before upsert
- `backend/routers/cves.py` — enrichment reliability + CIRCL patch + LOWER search
- `TECHNICAL_INVENTORY.md` — Vite version row

## Regression Coverage

- `backend/tests/test_gemini_reconciliation.py`
  - Auth refresh rejects expired/malformed/empty `expires_at`
  - CVE upsert canonicalizes mixed-case IDs
  - `_build_cve_filters` uses LOWER for search
  - CIRCL patch does not include `summary`

## Final Closed-Set Validation

- Raw substantive comments: 174
- Classified findings: 174
- Every comment ID accounted for: YES
- Unresolved VALID_UNFIXED after corrections: 0

## Root Cause of Review Process Failure

Some PRs were merged before asynchronous Gemini Code Assist inline review comments arrived. Merge gates did not require disposition of late review threads. This was a review timing and merge-process sequencing gap — not a tool defect.

## Future PR Review Contract

See `AGENTS.md` → **Automated inline review disposition (mandatory)**.
