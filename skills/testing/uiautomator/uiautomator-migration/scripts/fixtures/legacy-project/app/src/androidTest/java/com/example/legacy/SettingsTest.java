package com.example.legacy;

import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.runner.AndroidJUnit4;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject;
import androidx.test.uiautomator.UiObjectNotFoundException;
import androidx.test.uiautomator.UiScrollable;
import androidx.test.uiautomator.UiSelector;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class SettingsTest {
    private UiDevice device;

    @Before
    public void setUp() {
        device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        device.registerWatcher("dialog", () -> false);
        device.pressHome();
    }

    @Test
    public void opensWifi() throws Exception {
        // Thread.sleep(500) in a comment is ignored
        UiScrollable list = new UiScrollable(new UiSelector().scrollable(true));
        UiObject wifi = list.getChildByText(new UiSelector().className("android.widget.TextView"), "Network");
        wifi.click();
        Thread.sleep(2000);
        device.click(540, 1200);
        device.findObject(By.text("Wi-Fi")).click();
        device.waitForIdle();
    }

    @Test
    public void legacyEntryPoint() throws UiObjectNotFoundException {
        UiDevice old = UiDevice.getInstance();
        old.setCompressedLayoutHeirarchy(true);
        old.dumpWindowHierarchy("/sdcard/dump.xml");
    }
}
