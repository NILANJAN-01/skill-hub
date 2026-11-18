# Kotlin: the UI Automator 2.4 DSL

Artifact `androidx.test.uiautomator:uiautomator:2.4.1` (stable, 2026-11-04). Signatures below are from the 2.4.1 API reference and the library source; where the developer guide differs, the difference is noted.

## Imports you usually need

```kotlin
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.uiAutomator              // entry point (capital A)
import androidx.test.uiautomator.onElement                // UiObject2.onElement / UiDevice.onElement (chaining)
import androidx.test.uiautomator.onElements
import androidx.test.uiautomator.onElementOrNull
import androidx.test.uiautomator.scrollToElement
import androidx.test.uiautomator.textAsString             // AccessibilityNodeInfo.textAsString()
import androidx.test.uiautomator.simpleViewResourceName
import androidx.test.uiautomator.isClass
import androidx.test.uiautomator.waitForStable
import androidx.test.uiautomator.takeScreenshot
import androidx.test.uiautomator.saveToFile
import androidx.test.uiautomator.watcher.PermissionDialog // not androidx.test.uiautomator.PermissionDialog
```

Members of `UiAutomatorTestScope` (`onElement`, `startApp`, `watchFor`, ...) need no import inside `uiAutomator { }`; extension functions do.

## Test shape

```kotlin
@RunWith(AndroidJUnit4::class)
class LoginTest {
    @Test
    fun signInShowsHome() = uiAutomator {
        watchFor(PermissionDialog) { clickAllow() }
        startApp("com.example.app")
        onElement { simpleViewResourceName() == "email" }.setText("user@example.com")
        onElement { simpleViewResourceName() == "password" }.setText(password())
        onElement { textAsString() == "Sign in" }.click()
        onElement(timeoutMs = 20_000) { viewIdResourceName == "com.example.app:id/home_feed" }
    }

    private fun password() = InstrumentationRegistry.getArguments().getString("password") ?: "test-only"
}
```

`uiAutomator { }` creates the scope, runs the block, then unregisters every watcher registered with `watchFor`.

## UiAutomatorTestScope

| Member | Notes |
|---|---|
| `device: UiDevice`, `instrumentation: Instrumentation`, `uiAutomation: UiAutomation` | Escape hatches to the full API |
| `onElement(timeoutMs = 10000, pollIntervalMs = 100) { pred }: UiObject2` | DFS from the active window root; throws `ElementNotFoundException` |
| `onElementOrNull(timeoutMs, pollIntervalMs) { pred }: UiObject2?` | Optional elements; `onElementOrNull(0) { }` checks once |
| `onElements(timeoutMs, pollIntervalMs) { pred }: List<UiObject2>` | Waits for at least one match, returns all |
| `startApp(packageName, intentFlags = listOf())` | Launch (or leanback launch) intent; blocks until a node of the package is visible |
| `startActivity(MyActivity::class.java, intentFlags)` / `startActivity(packageName, activityName, intentFlags)` | Blocks until a new window shows (2.4.0-alpha07+) |
| `startActivityIntent(intent)` | Throws `IllegalArgumentException` if no activity resolves the intent. The guide calls it `startIntent`, which does not exist |
| `clearAppData()` | No argument: clears the **instrumentation target** app (`ActivityManager.clearApplicationUserData`). The guide's `clearAppData("pkg")` does not compile against 2.4.1 |
| `waitForAppToBeVisible(appPackageName, timeoutMs = 10000): Boolean` | True when any node of the package is in the tree |
| `waitForStableInActiveWindow(stableTimeoutMs = 3000, stableIntervalMs = 500, stablePollIntervalMs = 50, requireStableScreenshot = true): StableResult` | `StableResult.isTimeout` is true when it never settled |
| `activeWindowRoot()`, `windowRoots()`, `windows()` | `AccessibilityNodeInfo` / `AccessibilityWindowInfo` for all displays |
| `pressBack()`, `pressHome()`, `pressEnter()`, `pressDelete(count)` | |
| `type(text)` | Key events through `Instrumentation.sendKeySync` (fires key listeners like a keyboard). Into another app's window use `UiObject2.setText` |
| `watchFor(watcher) { scopeBlock }: WatcherRegistration`, `unregisterWatchers()` | `registration.unregister()` removes one early |

## Predicates (receiver is `AccessibilityNodeInfo`)

```kotlin
onElement { viewIdResourceName == "com.example.app:id/save" }   // View id: full name
onElement { simpleViewResourceName() == "save" }               // part after "/"
onElement { viewIdResourceName == "save_button" }               // Compose testTag (testTagsAsResourceId = true)
onElement { textAsString() == "Save" }
onElement { textAsString()?.startsWith("Total") == true }
onElement { contentDescription?.toString() == "Navigate up" }
onElement { isClass(android.widget.EditText::class.java) && isFocused }
onElement { packageName == "com.android.settings" && isScrollable }
```

Node extensions: `textAsString()`, `simpleViewResourceName()`, `isClass(cls)`, `boundsInScreen(): Rect`, `children { filter }`, `descendants { filter }`, `siblings { filter }`, `takeScreenshot(): Bitmap`, `waitForStable(...)`, and `onElement*` searching only under that node.

## Nesting, lists and scrolling

```kotlin
onElement { viewIdResourceName == "com.example.app:id/order_list" }
    .onElement { textAsString() == "Order #1042" }     // search inside the list only
    .click()

val rows = onElements { simpleViewResourceName() == "order_row" }   // List<UiObject2>
assertEquals(5, rows.size)

onElement { isScrollable }
    .scrollToElement(Direction.DOWN) { textAsString() == "Privacy" }  // throws ElementNotFoundException
    .click()
onElement { isScrollable }.scrollToElementOrNull(Direction.DOWN, timeoutMs = 5_000) { textAsString() == "Beta" }
```

`scrollToElementOrNull` returns null instead of throwing since 2.4.0-beta02. For gestures on the found `UiObject2` (`scroll`, `fling`, `swipe`, `pinchOpen`, `drag`, `setGestureMargin`) see [java-api.md](java-api.md); they are the same object.

## Waiting and stability

- `onElement*` already wait (default 10 s, poll 100 ms) and run registered watchers on every poll.
- `activeWindow().waitForStable()` / `onElement { ... }.waitForStable()`: wait until the subtree (and the screenshot, unless `requireStableScreenshot = false`) stops changing for `stableIntervalMs`. Use before screenshots or when counting items in a list that is still loading. A stable tree does not mean the app is idle (background work may continue).
- Need a condition the DSL lacks? `device.wait(Until.hasObject(By.res(...)), 5_000)` and `obj.wait(Until.textEquals("Done"), 5_000)` work inside the scope too.

## Watchers

```kotlin
watchFor(PermissionDialog) { clickAllow() }      // or clickDeny()
```

`PermissionDialog` matches the permission controller package and clicks `com.android.permissioncontroller:id/permission_allow_button` / `permission_deny_button`. A custom watcher implements `ScopedUiWatcher<T>` (`isVisible()` and `scope()`):

```kotlin
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.onElement
import androidx.test.uiautomator.onElementOrNull
import androidx.test.uiautomator.textAsString
import androidx.test.uiautomator.watcher.ScopedUiWatcher

private fun device(): UiDevice = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())

object RateAppDialog : ScopedUiWatcher<RateAppDialog.Scope> {
    override fun isVisible(): Boolean =
        device().onElementOrNull(timeoutMs = 0) { textAsString() == "Enjoying the app?" } != null

    override fun scope(): Scope = Scope

    object Scope {
        fun notNow() = device().onElement { textAsString() == "Not now" }.click()
    }
}

// in a test:
val registration = watchFor(RateAppDialog) { notNow() }
// ...
registration.unregister()
```

Use watchers only for UI that may or may not appear. For a dialog the flow always shows, find it with `onElement`.

## Windows and displays

```kotlin
val pip = windows().first { it.isInPictureInPictureMode }
pip.onElement { contentDescription?.toString() == "Play" }.click()

val ime = windows().firstOrNull { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
activeWindow().onElement { textAsString() == "OK" }.click()
```

Java-style window selectors also exist (2.4.0-alpha06+): `device.findWindow(By.Window...)` returns a `UiWindow`. To restrict every search to one display: `Configurator.getInstance().setDefaultDisplayId(id)`, and `resetDefaultDisplayId()` afterwards.

## Screenshots and ResultsReporter

```kotlin
uiAutomator {
    startApp("com.example.app")
    val reporter = ResultsReporter("LoginTest")                    // name of this result set
    val file = reporter.addNewFile(filename = "sign_in_button", title = "Sign in button")
    onElement { textAsString() == "Sign in" }.takeScreenshot().saveToFile(file)
    activeWindow().takeScreenshot().saveToFile(reporter.addNewFile("screen", "Whole screen"))
    reporter.reportToInstrumentation()     // Android Studio shows the files in the test results
}
```

`Bitmap.saveToFile(file)` (optional compress format and quality; also a `ParcelFileDescriptor` overload) is an extension; `UiObject2.takeScreenshot()`, `AccessibilityWindowInfo.takeScreenshot()` and `AccessibilityNodeInfo.takeScreenshot()` crop to the element or window. For files you save yourself, use a folder the test can write (for example `instrumentation.targetContext.getExternalFilesDir(null)`) and pull it with adb.

## Shell commands as the shell user (uiautomator-shell)

`androidx.test.uiautomator:uiautomator-shell:2.4.1` provides `androidx.test.shell.ShellServer`: a long-running on-device process that starts `/system/bin/sh` processes as the shell user.

`uiautomator` uses it internally but only as an implementation dependency, so to call it from tests add `androidTestImplementation("androidx.test.uiautomator:uiautomator-shell:2.4.1")`.

```kotlin
ShellServer.start().use { server ->            // ports chosen automatically (fixed in 2.4.1)
    val process = server.newProcess()          // ShellProcess with stdin/stdout/stderr streams
    // write a command to process stdin, read stdout ...
}
```

Prefer the scope helpers (`startApp`, `clearAppData`) or `device.executeShellCommand(cmd)` (public but discouraged) for simple setup; use `ShellServer` when you need several concurrent or long-running shell processes.

## Compose

UI Automator sees composables by text and content description. To use `Modifier.testTag`, the app sets once, high in the tree:

```kotlin
Scaffold(modifier = Modifier.semantics { testTagsAsResourceId = true }) {
    LazyColumn(modifier = Modifier.testTag("feed")) { /* ... */ }
}
```

Then in the test: `onElement { viewIdResourceName == "feed" }`, or in Java `device.findObject(By.res("feed"))`. Do not use `By.res("com.example.app", "feed")`: it builds `com.example.app:id/feed`, which a test tag never has.
