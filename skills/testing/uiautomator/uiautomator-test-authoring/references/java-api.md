# Java: UiDevice, By, Until and UiObject2

These classes are the supported, non-deprecated API for Java (and they also work from Kotlin). `UiSelector`, `UiObject`, `UiScrollable` and `UiCollection` are being deprecated; do not use them in new code.

## Test shape

```java
@RunWith(AndroidJUnit4.class)                       // androidx.test.ext.junit.runners.AndroidJUnit4
public class CalculatorTest {
    private static final String CALC = "com.myexample.calc";
    private static final long TIMEOUT_MS = 10_000;
    private UiDevice device;

    @Before
    public void startFromHome() {
        device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        device.pressHome();
        device.wait(Until.hasObject(By.pkg(device.getLauncherPackageName()).depth(0)), TIMEOUT_MS);
        Context context = ApplicationProvider.getApplicationContext();
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(CALC);
        assertNotNull(intent);                       // null: app missing, or <queries> needed on Android 11+
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK);
        context.startActivity(intent);
        assertTrue(device.wait(Until.hasObject(By.pkg(CALC).depth(0)), TIMEOUT_MS));
    }

    @Test
    public void twoPlusThreeIsFive() {
        click(By.res(CALC, "two"));
        click(By.res(CALC, "plus"));
        click(By.res(CALC, "three"));
        click(By.res(CALC, "equals"));
        UiObject2 result = waitFor(By.res(CALC, "result"));
        assertTrue(result.wait(Until.textEquals("5"), TIMEOUT_MS));
    }

    private UiObject2 waitFor(BySelector selector) {
        UiObject2 o = device.wait(Until.findObject(selector), TIMEOUT_MS);
        assertNotNull("not found: " + selector, o);
        return o;
    }

    private void click(BySelector selector) {
        waitFor(selector).click();
    }
}
```

`@SdkSuppress(minSdkVersion = 21)` (`androidx.test.filters`, in `androidx.test:runner`) skips a test on older devices.

## By / BySelector

`By.x(...)` starts a selector; chain more criteria on the `BySelector` (`By.text("OK").clazz("android.widget.Button")`).

| Criteria | Methods |
|---|---|
| Resource id | `res(String fullName)`, `res(String pkg, String id)` (builds `pkg:id/id`), `res(Pattern)` |
| Text | `text(String)`, `text(Pattern)`, `textContains`, `textStartsWith`, `textEndsWith` |
| Content description | `desc(String)`, `desc(Pattern)`, `descContains`, `descStartsWith`, `descEndsWith` |
| Hint (API 26+) | `hint(String)`, `hint(Pattern)`, `hintContains`, `hintStartsWith`, `hintEndsWith` |
| Class | `clazz(String)`, `clazz(Class)`, `clazz(String pkg, String cls)`, `clazz(Pattern)` |
| Package | `pkg(String)`, `pkg(Pattern)` |
| State | `checkable`, `checked`, `clickable`, `longClickable`, `enabled`, `focusable`, `focused`, `scrollable`, `selected` (each takes a boolean) |
| Structure | `depth(int)`, `hasChild(sel)`, `hasDescendant(sel[, maxDepth])`, `hasParent(sel)`, `hasAncestor(sel[, maxDistance])` |
| Display (API 30+) | `displayId(int)` |
| Copy | `By.copy(selector)` |

`By.Window` builds a `ByWindowSelector` for `device.findWindow(...)`, `findWindows(...)` and `hasWindow(...)` (2.4.0-alpha06+), which return `UiWindow` objects for multi-window tests.

```java
UiObject2 list = device.findObject(By.clazz("android.widget.ListView").hasChild(By.text("Apps")));
List<UiObject2> checked = device.findObjects(By.checked(true));
UiObject2 email = device.findObject(By.res("com.example.app:id/email").hasAncestor(By.res("com.example.app:id/login_form")));
```

`findObject` returns the first match in the hierarchy or **null** at once; wrap it in `device.wait(Until.findObject(sel), t)` when the element may still be loading.

## Until (conditions)

| Kind | Methods | Used with |
|---|---|---|
| Search (`SearchCondition`) | `hasObject(sel)`, `gone(sel)`, `findObject(sel)`, `findObjects(sel)` | `device.wait(...)`, `obj.wait(...)`, `scrollUntil` |
| Object state (`UiObject2Condition`) | `checked`, `checkable`, `clickable`, `longClickable`, `enabled`, `focusable`, `focused`, `scrollable`, `selected`, `textEquals`, `textNotEquals`, `textContains`, `textStartsWith`, `textEndsWith`, `textMatches`, `descEquals`, `descContains`, `descStartsWith`, `descEndsWith`, `descMatches` | `obj.wait(cond, t)` |
| Events (`EventCondition`) | `newWindow()`, `scrollFinished(Direction)` | `clickAndWait`, `performActionAndWait`, `scrollUntil` |

`Condition<T, U>` is a public interface (2.3.0+), so you can pass a lambda: `device.wait(d -> d.getCurrentPackageName().equals(PKG), t)` or `obj.wait(o -> o.getChildCount() > 3, t)`.

## Waiting for transitions

```java
device.performActionAndWait(() -> button.click(), Until.newWindow(), 2_000);
button.clickAndWait(Until.newWindow(), 2_000);
checkbox.wait(Until.checked(true), 2_000);
device.wait(Until.gone(By.res(PKG, "spinner")), 10_000);
UiObject2 dnd = scrollable.scrollUntil(Direction.DOWN, Until.findObject(By.textContains("Do Not Disturb")));
scrollable.scrollUntil(Direction.UP, Until.scrollFinished(Direction.UP));      // scroll to the top
```

## UiObject2

| Group | Methods |
|---|---|
| Click | `click()`, `click(long ms)`, `click(Point)`, `click(Point, long)`, `longClick()`, `clickAndWait(cond, t)`, `clickAndWait(Point, cond, t)` |
| Text | `setText(String)` (clears first), `clear()`, `getText()`, `getHint()` |
| Gestures | `swipe(Direction, float percent[, speed])`, `scroll(Direction, float percent[, speed])` (returns true if more to scroll), `fling(Direction[, speed])`, `drag(Point[, speed])`, `pinchOpen(float)`, `pinchClose(float)` |
| Scroll until | `scrollUntil(Direction, Condition)`, `scrollUntil(Direction, EventCondition)` |
| Gesture margins | `setGestureMargin(int px)`, `setGestureMargins(l, t, r, b)`, `setGestureMarginPercentage(float 0..0.5)`, `setGestureMarginsPercentage(...)` |
| Search inside | `findObject(sel)`, `findObjects(sel)`, `hasObject(sel)`, `getChildren()`, `getChildCount()`, `getParent()` |
| Wait | `wait(UiObject2Condition, t)`, `wait(SearchCondition, t)`, `wait(Condition, t)` |
| Properties | `getResourceName()`, `getContentDescription()`, `getClassName()`, `getApplicationPackage()`, `getVisibleBounds()`, `getVisibleCenter()`, `getDisplayId()`, `getDrawingOrder()`, `isChecked/Checkable/Clickable/Enabled/Focusable/Focused/LongClickable/Scrollable/Selected()`, `getAccessibilityNodeInfo()` |

A `UiObject2` is bound to one view: after the UI changes it throws `StaleObjectException`; find it again.

## UiDevice

| Group | Methods |
|---|---|
| Get it | `UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())` (the no-argument `getInstance()` is deprecated) |
| Find / wait | `findObject(BySelector)`, `findObjects`, `hasObject`, `wait(SearchCondition, t)`, `wait(Condition, t)`, `performActionAndWait(Runnable, EventCondition, t)`, `waitForIdle([t])`, `waitForWindowUpdate(pkg, t)` |
| Keys | `pressBack/Home/Menu/Enter/Delete/Search/RecentApps()`, `pressDPadUp/Down/Left/Right/Center()`, `pressKeyCode(code[, meta])`, `pressKeyCodes(int[] codes[, meta])` (e.g. POWER + VOLUME_DOWN together) |
| System UI | `openNotification()`, `openQuickSettings()`, `wakeUp()`, `sleep()`, `isScreenOn()` |
| Rotation | `setOrientationPortrait/Landscape/Natural/Left/Right([displayId])`, `freezeRotation([displayId])`, `unfreezeRotation`, `getDisplayRotation([displayId])`, `isNaturalOrientation()`; the setters throw `RemoteException` (declare `throws Exception` on the test) |
| Display | `getDisplayWidth/Height([displayId])`, `getDisplaySizeDp()`, `getProductName()`, `getLauncherPackageName()`, `getCurrentPackageName()` |
| Raw input | `click(x, y)`, `swipe(...)`, `drag(...)`: avoid fixed coordinates in tests |
| Debug | `takeScreenshot()` (Bitmap), `takeScreenshot(File[, scale, quality])`, `dumpWindowHierarchy(File | OutputStream)`, `setCompressedLayoutHierarchy(boolean)`, `getWindowRoots()` |
| Shell | `executeShellCommand(String)`: public but discouraged; runs as the shell user, no shell operators (`|`, `>`) |
| Watchers | `registerWatcher(name, UiWatcher)`, `removeWatcher(name)`, `runWatchers()`, `hasWatcherTriggered(name)`, `hasAnyWatcherTriggered()`, `resetWatcherTriggers()` |

## Watchers in Java

```java
private static final String RATE_DIALOG = "rate-dialog";

@Before public void addWatcher() {
    device.registerWatcher(RATE_DIALOG, () -> {
        UiObject2 notNow = device.findObject(By.text("Not now"));
        if (notNow == null) return false;
        notNow.click();
        return true;
    });
}

@After public void removeWatcher() { device.removeWatcher(RATE_DIALOG); }
```

Watchers run automatically only when a legacy `UiSelector` lookup fails (and on each Kotlin `onElement` poll). With `findObject(BySelector)` and `Until` they do not run, so call `device.runWatchers()` at the steps where the dialog can appear.

## System UI and other apps

```java
device.executeShellCommand("am start -a android.settings.SETTINGS");
device.openNotification();
device.openQuickSettings();
UiObject2 clock = device.wait(Until.findObject(By.res("com.android.systemui:id/clock")), 2_000);
```

System UI ids differ between Android versions and OEM builds; check them with a dump on each target.

## Configurator

`Configurator.getInstance()` is a process-wide singleton: save the old value and restore it in `@After`.

| Setting | Effect |
|---|---|
| `setWaitForIdleTimeout(ms)` | How long actions wait for idle (lower it on screens that animate forever) |
| `setWaitForSelectorTimeout(ms)` | Legacy `UiObject` only; no effect on `UiObject2` |
| `setActionAcknowledgmentTimeout(ms)`, `setScrollAcknowledgmentTimeout(ms)` | Legacy `UiObject` / `UiScrollable` only |
| `setToolType(MotionEvent.TOOL_TYPE_STYLUS ...)` | Tool type of injected touches |
| `setUiAutomationFlags(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES)` | Keep accessibility services (e.g. TalkBack) running |
| `setDefaultDisplayId(id)` / `resetDefaultDisplayId()` | Restrict searches to one display (2.4) |
| `addUiAccessibilityValidator(v)` / `removeUiAccessibilityValidator(v)` | Run accessibility checks before every action (2.4) |
| `setKeyInjectionDelay` | Deprecated, no effect |

## Accessibility of the app under test

UI Automator only sees what the accessibility tree exposes. Standard Views and Compose work out of the box; a custom `View` that draws its own content needs an `ExploreByTouchHelper` set with `ViewCompat.setAccessibilityDelegate(...)`. Give important controls an id, a visible label or a content description. `uiautomatorviewer` (old SDK tools, "Toggle NAF Nodes") or Android Studio's Layout Inspector show elements UI Automator cannot reach.
