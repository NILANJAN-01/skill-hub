# Migration map: legacy UI Automator to current APIs

Java targets `By` / `BySelector` / `Until` / `UiObject2`. Kotlin targets the 2.4 DSL (predicates on `AccessibilityNodeInfo`). `TIMEOUT` is your wait in milliseconds (e.g. `10_000`).

## Entry point, runner and build

| Old | Java | Kotlin |
|---|---|---|
| `class T extends UiAutomatorTestCase` | `@RunWith(AndroidJUnit4.class) public class T` + `@Before` that gets the device | `@RunWith(AndroidJUnit4::class) class T` with `@Test fun x() = uiAutomator { }` |
| `getUiDevice()` / `UiDevice.getInstance()` | `UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())` | `device` inside `uiAutomator { }` |
| `UiAutomatorInstrumentationTestRunner` | `testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"` | same |
| `androidx.test.runner.AndroidJUnit4` | `androidx.test.ext.junit.runners.AndroidJUnit4` (`androidx.test.ext:junit`) | same |
| `android.support.test.uiautomator.*`, `com.android.support.test.uiautomator:uiautomator-v18` | `androidx.test.uiautomator.*`, `androidx.test.uiautomator:uiautomator:2.4.1` | same |
| `com.android.uiautomator.*` (1.0, `uiautomator runtest`) | Rewrite as an instrumented test | Rewrite as an instrumented test |

## UiSelector → BySelector / predicate

| UiSelector | Java `By` / `BySelector` | Kotlin predicate |
|---|---|---|
| `.resourceId("pkg:id/x")` | `By.res("pkg:id/x")` or `By.res("pkg", "x")` | `viewIdResourceName == "pkg:id/x"` / `simpleViewResourceName() == "x"` |
| `.resourceIdMatches(regex)` | `By.res(Pattern.compile(regex))` | `viewIdResourceName?.matches(Regex(regex)) == true` |
| `.text("t")` | `By.text("t")` | `textAsString() == "t"` |
| `.textContains/StartsWith("t")` | `By.textContains/textStartsWith("t")` | `textAsString()?.contains("t") == true` |
| `.textMatches(regex)` | `By.text(Pattern.compile(regex))` | `textAsString()?.matches(Regex(regex)) == true` |
| `.description("d")` | `By.desc("d")` | `contentDescription?.toString() == "d"` |
| `.descriptionContains/StartsWith/Matches` | `By.descContains/descStartsWith/desc(Pattern)` | `contentDescription?.toString()?.contains("d") == true` |
| `.className("android.widget.Button")` / `.className(Button.class)` | `By.clazz("android.widget.Button")` / `By.clazz(Button.class)` | `isClass(Button::class.java)` |
| `.classNameMatches(regex)` | `By.clazz(Pattern.compile(regex))` | `className?.toString()?.matches(Regex(regex)) == true` |
| `.packageName("p")` / `.packageNameMatches` | `By.pkg("p")` / `By.pkg(Pattern)` | `packageName == "p"` |
| `.checked/checkable/clickable/longClickable/enabled/focused/focusable/scrollable/selected(b)` | same names on `By` / `BySelector` | `isChecked`, `isCheckable`, `isClickable`, `isLongClickable`, `isEnabled`, `isFocused`, `isFocusable`, `isScrollable`, `isSelected` |
| `.childSelector(child)` | `parentSel.hasDescendant(childSel)` to select the parent, or `parent.findObject(childSel)` to get the child | `onElement { parent }.onElement { child }` |
| `.fromParent(sibling)` | `parent = obj.getParent(); parent.findObject(siblingSel)` or `By.hasParent(...)` | `onElement { parent }.onElement { sibling }` |
| `.index(i)` | No equivalent; use structure (`hasParent`, `depth`) or `parent.getChildren().get(i)` | `children()[i]` on the parent node |
| `.instance(n)` | `device.findObjects(sel).get(n)` | `onElements { ... }[n]` |

## UiObject → UiObject2

| UiObject | Java | Kotlin |
|---|---|---|
| `device.findObject(new UiSelector()...)` | `device.wait(Until.findObject(sel), TIMEOUT)` + `assertNotNull` | `onElement { ... }` |
| `exists()` | `device.hasObject(sel)` | `onElementOrNull(0) { ... } != null` |
| `waitForExists(t)` | `device.wait(Until.hasObject(sel), t)` | `onElementOrNull(t) { ... } != null` |
| `waitUntilGone(t)` | `device.wait(Until.gone(sel), t)` | `device.wait(Until.gone(sel), t)` |
| `click()` | `obj.click()` | `.click()` |
| `clickAndWaitForNewWindow([t])` | `obj.clickAndWait(Until.newWindow(), t)` | same |
| `clickTopLeft()` / `clickBottomRight()` | `obj.click(new Point(b.left + 1, b.top + 1))` with `b = obj.getVisibleBounds()` | same |
| `longClick()` | `obj.longClick()` | same |
| `setText(s)` / `clearTextField()` | `obj.setText(s)` / `obj.clear()` | same |
| `getText()` / `getContentDescription()` / `getBounds()` | `getText()` / `getContentDescription()` / `getVisibleBounds()` | `.text`, `.contentDescription`, `.visibleBounds` |
| `getChild(sel)` / `getFromParent(sel)` | `obj.findObject(sel)` / `obj.getParent().findObject(sel)` | `.onElement { }` / `.parent.onElement { }` |
| `getChildCount()` | `obj.getChildCount()` | `.childCount` |
| `swipeUp/Down/Left/Right(steps)` | `obj.swipe(Direction.UP, 0.8f)` | same |
| `dragTo(x, y, steps)` / `dragTo(obj, steps)` | `obj.drag(new Point(x, y))` / `obj.drag(target.getVisibleCenter())` | same |
| `pinchIn/pinchOut(percent, steps)` | `obj.pinchClose(p / 100f)` / `obj.pinchOpen(p / 100f)` | same |
| `UiObjectNotFoundException` | `null` from `findObject`, or your own `AssertionError` after `wait` | `ElementNotFoundException` from `onElement` |

## UiScrollable and UiCollection

| Old | Java | Kotlin |
|---|---|---|
| `new UiScrollable(new UiSelector().scrollable(true))` | `UiObject2 s = device.wait(Until.findObject(By.scrollable(true)), TIMEOUT)` | `val s = onElement { isScrollable }` |
| `scrollIntoView(sel)` / `scrollTextIntoView("t")` | `s.scrollUntil(Direction.DOWN, Until.findObject(sel))` (null if never found) | `s.scrollToElement(Direction.DOWN) { textAsString() == "t" }` |
| `getChildByText(childSel, "t")` | `s.scrollUntil(Direction.DOWN, Until.findObject(By.copy(childSel).text("t")))` | `s.scrollToElement(Direction.DOWN) { textAsString() == "t" }` |
| `getChildByDescription(childSel, "d")` | same with `.desc("d")` | `{ contentDescription?.toString() == "d" }` |
| `scrollForward()` / `scrollBackward()` | `s.scroll(Direction.DOWN, 0.8f)` / `s.scroll(Direction.UP, 0.8f)` | same |
| `scrollToBeginning(n)` / `scrollToEnd(n)` | `s.scrollUntil(Direction.UP, Until.scrollFinished(Direction.UP))` / `DOWN` | same |
| `flingForward()` / `flingToEnd(n)` | `s.fling(Direction.DOWN)` / loop until `!s.fling(Direction.DOWN)` | same |
| `setAsHorizontalList()` | use `Direction.LEFT` / `Direction.RIGHT` | same |
| `setMaxSearchSwipes(n)` | `scrollUntil` stops at the end; or a counted loop of `scroll(...)` | `scrollToElement(timeoutMs = ...)` |
| `new UiCollection(sel).getChildCount(childSel)` | `device.findObject(sel).findObjects(childSel).size()` | `onElement { ... }.onElements { ... }.size` |

## UiDevice and Configurator

| Old | Replacement |
|---|---|
| `waitForIdle()` before every step | Wait for the element you need (`Until`, `onElement`); `activeWindow().waitForStable()` before screenshots |
| `waitForWindowUpdate(pkg, t)` | `clickAndWait(Until.newWindow(), t)` / `performActionAndWait(..., Until.newWindow(), t)` |
| `registerWatcher` + `UiSelector` lookups that triggered it | Kotlin: `watchFor(PermissionDialog) { clickAllow() }` or a `ScopedUiWatcher`. Java: keep `registerWatcher`, call `device.runWatchers()` where the dialog can appear, `removeWatcher` in `@After` |
| `setCompressedLayoutHeirarchy(b)` | `setCompressedLayoutHierarchy(b)` |
| `dumpWindowHierarchy(String fileName)` | `dumpWindowHierarchy(File)` / `dumpWindowHierarchy(OutputStream)` |
| `getCurrentActivityName()` | `getCurrentPackageName()`, `waitForAppToBeVisible(pkg)`, or an element unique to the screen |
| `Configurator.setKeyInjectionDelay(ms)` | Remove (no effect since text is set directly) |
| `Configurator.setWaitForSelectorTimeout(ms)` | Only affects `UiObject`; give `Until`/`onElement` waits their own timeout |
| `Thread.sleep(ms)` | A condition wait (see the Java and Kotlin columns above) |
| `device.click(x, y)` / `swipe(x1, y1, x2, y2, steps)` | Act on the element (`obj.click()`, `obj.swipe(...)`); set gesture margins on edge-to-edge screens |

## Kotlin code written against 2.4 alphas

| Alpha code | 2.4.1 |
|---|---|
| `onView { }`, `onViews { }`, `onViewOrNull { }` (before alpha04) | `onElement { }`, `onElements { }`, `onElementOrNull { }` |
| `clearAppData("pkg")` | `clearAppData()` (target app). For another package, clear it from the host before the run (`adb shell pm clear <pkg>`, after asking) |
| `startIntent(intent)` | `startActivityIntent(intent)` |
| `import androidx.test.uiautomator.PermissionDialog` | `import androidx.test.uiautomator.watcher.PermissionDialog` |
| `scrollToElementOrNull` throwing (before beta02) | Returns `null` on timeout |
| APIs without an explicit package name (removed in alpha07) | Pass the package: `startApp(pkg)`, `waitForAppToBeVisible(pkg)` |

## Before and after

Java, legacy:

```java
UiScrollable settings = new UiScrollable(new UiSelector().scrollable(true));
UiObject network = settings.getChildByText(new UiSelector().className("android.widget.TextView"), "Network & internet");
network.clickAndWaitForNewWindow();
Thread.sleep(1000);
assertTrue(new UiObject(new UiSelector().text("Internet")).exists());
```

Java, migrated:

```java
UiObject2 settings = device.wait(Until.findObject(By.scrollable(true)), TIMEOUT);
assertNotNull(settings);
UiObject2 network = settings.scrollUntil(Direction.DOWN,
        Until.findObject(By.clazz("android.widget.TextView").text("Network & internet")));
assertNotNull("Network & internet not found", network);
network.clickAndWait(Until.newWindow(), TIMEOUT);
assertTrue(device.wait(Until.hasObject(By.text("Internet")), TIMEOUT));
```

Kotlin, migrated to the DSL:

```kotlin
@Test
fun opensNetworkSettings() = uiAutomator {
    startApp("com.android.settings")
    onElement { isScrollable }
        .scrollToElement(Direction.DOWN) { textAsString() == "Network & internet" }
        .click()
    onElement { textAsString() == "Internet" }
}
```

Settings labels differ between Android versions, OEMs and languages; prefer resource-ids where the target app has them.
